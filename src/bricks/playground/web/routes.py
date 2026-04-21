"""API route handlers for the Bricks Playground web server.

All routes live under the ``/playground`` prefix per design.md §6.
"""

from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, File, HTTPException, UploadFile

from bricks import __version__ as _bricks_version
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

    Only ``claude_code`` is fully wired in this PR. Anthropic, OpenAI, and
    Ollama routes are implemented in #44 and raise 501 here.

    Args:
        provider: One of ``anthropic`` / ``openai`` / ``claude_code`` / ``ollama``.
        model: Provider-specific model identifier.
        api_key: BYOK key (required for anthropic / openai, ignored otherwise).

    Returns:
        An ``LLMProvider`` instance.

    Raises:
        HTTPException: 400 if BYOK is required but missing; 501 until #44 lands.
    """
    if provider == "claude_code":
        from bricks.providers.claudecode import ClaudeCodeProvider

        return ClaudeCodeProvider(model=model or None)

    if provider in {"anthropic", "openai"} and not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} requires an api_key in the request body (BYOK)")

    raise HTTPException(
        status_code=501,
        detail=f"Provider {provider!r} is not implemented in this build. See issue #44.",
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


@router.post("/run", response_model=RunResponse, response_model_exclude_none=True)
async def run_playground(req: RunRequest) -> RunResponse:
    """Run BricksEngine on the task and return structured results.

    ``compare`` is wired in #45; this PR always omits ``raw_llm`` from the
    response.
    """
    from bricks.playground.showcase.engine import BricksEngine
    from bricks.playground.showcase.result_writer import check_correctness

    provider = _build_provider(req.provider, req.model, req.api_key)
    engine = BricksEngine(provider=provider)

    raw_data = req.data if isinstance(req.data, str) else json.dumps(req.data)
    fenced = raw_data if raw_data.strip().startswith("```") else f"```json\n{raw_data}\n```"

    t0 = time.monotonic()
    result = engine.solve(req.task, fenced)
    duration_ms = int((time.monotonic() - t0) * 1000)

    checks = []
    if req.expected_output is not None:
        expected = req.expected_output
        got = result.outputs or {}
        for key, exp_val in expected.items():
            got_val = got.get(key)
            checks.append({"key": key, "expected": exp_val, "got": got_val, "pass": got_val == exp_val})
        # Whole-dict correctness is available via check_correctness as a sanity
        # gate but we already expose per-key results above.
        check_correctness(got, expected)

    bricks_result = EngineResult(
        blueprint_yaml=result.raw_response or None,
        outputs=result.outputs or {},
        response=None,
        tokens=TokenBreakdown(
            **{
                "in": result.tokens_in,
                "out": result.tokens_out,
                "total": result.tokens_in + result.tokens_out,
            }
        ),
        duration_ms=duration_ms,
        cost_usd=None,
        checks=[{"key": c["key"], "expected": c["expected"], "got": c["got"], "pass": c["pass"]} for c in checks],
    )

    metadata = RunMetadata(
        model=result.model or req.model,
        provider=req.provider,
        version=_bricks_version,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )

    return RunResponse(bricks=bricks_result, raw_llm=None, run_metadata=metadata)
