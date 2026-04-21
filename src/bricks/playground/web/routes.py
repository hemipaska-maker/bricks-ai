"""API route handlers for the Bricks Playground web server.

All routes live under the ``/playground`` prefix per design.md §6.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from bricks import __version__ as _bricks_version
from bricks.core.hooks import hookimpl as _hookimpl
from bricks.llm.base import LLMProvider
from bricks.playground.web.schemas import (
    EngineResult,
    RunMetadata,
    RunRequest,
    RunResponse,
    ScenarioDetail,
    ScenarioSummary,
    TokenBreakdown,
    UploadResponse,
)

router = APIRouter(prefix="/playground")

_PRESETS_DIR = Path(__file__).parent / "presets"
_UPLOAD_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _build_provider(provider: str, model: str, api_key: str | None) -> LLMProvider:
    """Return an LLMProvider for the given ``provider`` / ``model`` pair.

    All four providers from design.md §7 are implemented here. API keys
    live only in the request body (BYOK) and are never read from the
    environment.

    Args:
        provider: One of ``anthropic`` / ``openai`` / ``claude_code`` / ``ollama``.
        model: Provider-specific model identifier.
        api_key: BYOK key (required for anthropic / openai, ignored for
            ``claude_code`` and ``ollama``).

    Returns:
        An ``LLMProvider`` instance.

    Raises:
        HTTPException: 400 if BYOK is required but missing.
    """
    if provider == "claude_code":
        from bricks.providers.claudecode import ClaudeCodeProvider

        return ClaudeCodeProvider(model=model or None)

    if provider == "ollama":
        from bricks.providers.ollama import OllamaProvider

        return OllamaProvider(model=model)

    if provider in {"anthropic", "openai"} and not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} requires an api_key in the request body (BYOK)")

    if provider == "anthropic":
        from bricks.providers.anthropic import AnthropicProvider

        assert api_key is not None  # narrowed by the BYOK check above
        return AnthropicProvider(model=model, api_key=api_key)

    if provider == "openai":
        from bricks.providers.openai import OpenAIProvider

        assert api_key is not None
        return OpenAIProvider(model=model, api_key=api_key)

    raise HTTPException(
        status_code=400,
        detail=f"Unknown provider {provider!r}",
    )


def _preset_path(scenario_id: str) -> Path | None:
    """Resolve ``scenario_id`` to a YAML file inside ``presets/``.

    Accepts both ``crm-pipeline`` (dashes) and ``crm_pipeline`` (underscores).
    Returns ``None`` if no match exists.
    """
    for sep in (scenario_id, scenario_id.replace("-", "_"), scenario_id.replace("_", "-")):
        candidate = _PRESETS_DIR / f"{sep}.yaml"
        if candidate.is_file():
            return candidate
    return None


def _load_preset_dict(path: Path) -> dict[str, Any]:
    """Parse a preset YAML file into a dict; raise 500 on malformed YAML."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=500, detail=f"Malformed preset {path.name!r}: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail=f"Preset {path.name!r} did not parse to a mapping")
    return data


# ── GET /playground/scenarios ────────────────────────────────────────────────


@router.get("/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios() -> list[ScenarioSummary]:
    """Return the list of available preset scenarios."""
    out: list[ScenarioSummary] = []
    if not _PRESETS_DIR.is_dir():
        return out
    for path in sorted(_PRESETS_DIR.glob("*.yaml")):
        data = _load_preset_dict(path)
        out.append(
            ScenarioSummary(
                id=path.stem.replace("_", "-"),
                name=str(data.get("name", path.stem)),
                description=str(data.get("description", "")),
            )
        )
    return out


# ── GET /playground/scenarios/{id} ───────────────────────────────────────────


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail)
async def get_scenario(scenario_id: str) -> ScenarioDetail:
    """Return the full body of a preset scenario."""
    path = _preset_path(scenario_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No scenario with id {scenario_id!r}")
    data = _load_preset_dict(path)

    # Resolve the data source: inline `data`, else `dataset_id` lookup via
    # DatasetLoader (existing helper), else raise 500 if none.
    body: Any = data.get("data")
    dataset_id = data.get("dataset_id")
    if body is None and dataset_id:
        from bricks.playground.web.datasets import DatasetLoader

        loader = DatasetLoader()
        matching = next((ds for ds in loader.list_datasets() if ds.get("id") == dataset_id), None)
        if matching is None:
            raise HTTPException(status_code=500, detail=f"Dataset {dataset_id!r} referenced by preset not found")
        # DatasetLoader gives us a full_data JSON string; parse to a value.
        full = matching.get("full_data")
        if isinstance(full, str):
            try:
                body = json.loads(full)
            except json.JSONDecodeError:
                body = full
        else:
            body = full

    return ScenarioDetail(
        id=scenario_id,
        name=str(data.get("name", scenario_id)),
        description=str(data.get("description", "")),
        task=str(data.get("task_text", "")),
        data=body,
        expected_output=data.get("expected_outputs"),
        required_bricks=data.get("required_bricks"),
    )


# ── POST /playground/upload ──────────────────────────────────────────────────


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:  # noqa: B008
    """Accept a CSV or JSON upload; return parsed contents.

    Rejects payloads larger than ``_UPLOAD_MAX_BYTES`` (5 MB).
    """
    raw = await file.read()
    if len(raw) > _UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {_UPLOAD_MAX_BYTES // (1024 * 1024)} MB limit ({len(raw)} bytes)",
        )

    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()

    data: Any
    row_count: int | None = None

    if suffix == ".csv" or (file.content_type or "").endswith("csv"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"CSV must be UTF-8: {exc}") from exc
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        data = rows
        row_count = len(rows)
    else:
        # Default to JSON.
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Could not parse JSON: {exc}") from exc
        if isinstance(data, list):
            row_count = len(data)

    return UploadResponse(
        data=data,
        filename=filename,
        size_bytes=len(raw),
        row_count=row_count,
    )


# ── POST /playground/run ─────────────────────────────────────────────────────


def _checks_for(outputs: dict[str, Any], expected: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build per-key correctness checks; empty list if no expected output."""
    if expected is None:
        return []
    got = outputs or {}
    return [{"key": k, "expected": v, "got": got.get(k), "pass": got.get(k) == v} for k, v in expected.items()]


def _engine_result(result: Any, duration_ms: int, expected: dict[str, Any] | None, *, is_raw: bool) -> EngineResult:
    """Shape a showcase engine result into an :class:`EngineResult`."""
    outputs = result.outputs or {}
    return EngineResult(
        blueprint_yaml=None if is_raw else (result.raw_response or None),
        outputs=outputs,
        response=result.raw_response if is_raw else None,
        tokens=TokenBreakdown(
            **{
                "in": result.tokens_in,
                "out": result.tokens_out,
                "total": result.tokens_in + result.tokens_out,
            }
        ),
        duration_ms=duration_ms,
        cost_usd=None,
        checks=_checks_for(outputs, expected),
    )


@router.post("/run", response_model=RunResponse, response_model_exclude_none=True)
async def run_playground(req: RunRequest) -> RunResponse:
    """Run BricksEngine on the task and return structured results.

    When ``compare`` is ``True``, also runs ``RawLLMEngine`` and includes
    the ``raw_llm`` branch in the response. When ``False`` (default),
    ``RawLLMEngine`` is **not** instantiated or called — the response
    omits the ``raw_llm`` key entirely.
    """
    from bricks.playground.showcase.engine import BricksEngine, RawLLMEngine

    provider = _build_provider(req.provider, req.model, req.api_key)

    raw_data = req.data if isinstance(req.data, str) else json.dumps(req.data)
    fenced = raw_data if raw_data.strip().startswith("```") else f"```json\n{raw_data}\n```"

    t0 = time.monotonic()
    bricks_raw = BricksEngine(provider=provider).solve(req.task, fenced)
    bricks_ms = int((time.monotonic() - t0) * 1000)

    raw_llm_result: EngineResult | None = None
    if req.compare:
        t_raw = time.monotonic()
        raw_raw = RawLLMEngine(provider=provider).solve(req.task, fenced)
        raw_ms = int((time.monotonic() - t_raw) * 1000)
        raw_llm_result = _engine_result(raw_raw, raw_ms, req.expected_output, is_raw=True)

    metadata = RunMetadata(
        model=bricks_raw.model or req.model,
        provider=req.provider,
        version=_bricks_version,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )

    return RunResponse(
        bricks=_engine_result(bricks_raw, bricks_ms, req.expected_output, is_raw=False),
        raw_llm=raw_llm_result,
        run_metadata=metadata,
    )


# ── POST /playground/run-stream (SSE) ────────────────────────────────────────


class _HookStreamer:
    """Pluggy plugin that pushes each hook call onto an ``asyncio.Queue``.

    One plugin instance is registered per ``/playground/run-stream`` request.
    Hooks fire on the worker thread running ``BricksEngine.solve``; the
    plugin uses ``loop.call_soon_threadsafe`` to enqueue frames onto the
    event loop's queue so the SSE generator can pick them up without
    blocking the worker.
    """

    def __init__(self, queue: asyncio.Queue[Any], loop: asyncio.AbstractEventLoop) -> None:
        self._queue = queue
        self._loop = loop

    def _push(self, phase: str, **payload: Any) -> None:
        frame = {"phase": phase, **payload}
        self._loop.call_soon_threadsafe(self._queue.put_nowait, frame)

    # Each hookimpl mirrors a BricksHookSpec method.

    @_hookimpl
    def compose_start(self, task: str) -> None:
        # Trim the task to keep the frame light.
        self._push("compose_start", task=task[:200])

    @_hookimpl
    def compose_done(self, dsl: str, tokens_in: int, tokens_out: int) -> None:
        self._push("compose_done", tokens_in=tokens_in, tokens_out=tokens_out)

    @_hookimpl
    def execute_start(self, blueprint_yaml: str) -> None:
        self._push("execute_start")

    @_hookimpl
    def step_start(self, step_name: str, brick_name: str) -> None:
        self._push("step_start", step_name=step_name, brick_name=brick_name)

    @_hookimpl
    def step_done(self, step_name: str, brick_name: str, duration_ms: int) -> None:
        self._push("step_done", step_name=step_name, brick_name=brick_name, duration_ms=duration_ms)

    @_hookimpl
    def heal_attempt(self, tier: int, healer_name: str, succeeded: bool) -> None:
        self._push("heal_attempt", tier=tier, healer_name=healer_name, succeeded=succeeded)

    @_hookimpl
    def raw_llm_start(self) -> None:
        self._push("raw_llm_start")

    @_hookimpl
    def raw_llm_done(self, response: str, tokens_in: int, tokens_out: int) -> None:
        self._push("raw_llm_done", tokens_in=tokens_in, tokens_out=tokens_out)

    @_hookimpl
    def check_done(self, key: str, expected: Any, got: Any, passed: bool) -> None:
        self._push("check_done", key=key, expected=expected, got=got, passed=passed)

    @_hookimpl
    def run_failed(self, error: str) -> None:
        self._push("run_failed", error=error)


def _sse_frame(event: str | None, data: Any) -> str:
    """Format ``data`` as an SSE frame, optionally with an ``event:`` line."""
    payload = json.dumps(data, default=str)
    if event:
        return f"event: {event}\ndata: {payload}\n\n"
    return f"data: {payload}\n\n"


@router.post("/run-stream")
async def run_playground_stream(req: RunRequest) -> StreamingResponse:
    """SSE variant of ``/playground/run`` — streams lifecycle events.

    Frames:

    - ``data: {"phase": "<name>", ...}\\n\\n`` — one per hook call.
    - ``event: done\\ndata: {...RunResponse...}\\n\\n`` — final result.
    - ``event: error\\ndata: {"message": "..."}\\n\\n`` — on failure.

    The existing non-streaming ``/playground/run`` endpoint is untouched
    and still the right choice for programmatic callers.
    """
    from bricks.core.hooks import get_plugin_manager
    from bricks.playground.showcase.engine import BricksEngine, RawLLMEngine

    provider = _build_provider(req.provider, req.model, req.api_key)
    raw_data = req.data if isinstance(req.data, str) else json.dumps(req.data)
    fenced = raw_data if raw_data.strip().startswith("```") else f"```json\n{raw_data}\n```"

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Any] = asyncio.Queue()
    pm = get_plugin_manager()
    pm.register(_HookStreamer(queue, loop))

    sentinel_done = object()
    sentinel_err = object()
    err_holder: list[BaseException] = []
    result_holder: dict[str, Any] = {}

    def _run_in_thread() -> None:
        try:
            t0 = time.monotonic()
            bricks_raw = BricksEngine(provider=provider, plugin_manager=pm).solve(req.task, fenced)
            bricks_ms = int((time.monotonic() - t0) * 1000)

            raw_llm_result: EngineResult | None = None
            if req.compare:
                t_raw = time.monotonic()
                raw_raw = RawLLMEngine(provider=provider, plugin_manager=pm).solve(req.task, fenced)
                raw_ms = int((time.monotonic() - t_raw) * 1000)
                raw_llm_result = _engine_result(raw_raw, raw_ms, req.expected_output, is_raw=True)

            bricks_result = _engine_result(bricks_raw, bricks_ms, req.expected_output, is_raw=False)

            # Fire check_done for each key so the SSE stream carries per-check
            # events even though checks are computed after execute returns.
            for check in bricks_result.checks:
                pm.hook.check_done(
                    key=check.key,
                    expected=check.expected,
                    got=check.got,
                    passed=check.pass_,
                )

            metadata = RunMetadata(
                model=bricks_raw.model or req.model,
                provider=req.provider,
                version=_bricks_version,
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            )
            response = RunResponse(
                bricks=bricks_result,
                raw_llm=raw_llm_result,
                run_metadata=metadata,
            )
            result_holder["response"] = response.model_dump(exclude_none=True, by_alias=True)
            loop.call_soon_threadsafe(queue.put_nowait, sentinel_done)
        except Exception as exc:
            err_holder.append(exc)
            loop.call_soon_threadsafe(queue.put_nowait, sentinel_err)

    worker = asyncio.create_task(asyncio.to_thread(_run_in_thread))

    async def _generator() -> Any:
        try:
            while True:
                item = await queue.get()
                if item is sentinel_done:
                    yield _sse_frame("done", result_holder["response"])
                    return
                if item is sentinel_err:
                    msg = str(err_holder[0]) if err_holder else "unknown error"
                    yield _sse_frame("error", {"message": msg})
                    return
                yield _sse_frame(None, item)
        finally:
            if not worker.done():
                worker.cancel()
            with contextlib.suppress(BaseException):
                await worker

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(_generator(), media_type="text/event-stream", headers=headers)
