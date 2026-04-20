"""API route handlers for the Bricks Benchmark web server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from bricks.benchmark.web.datasets import DatasetLoader
from bricks.benchmark.web.schemas import BenchmarkRequest, BenchmarkResponse, EngineResultResponse

router = APIRouter()

_loader = DatasetLoader()
_PRESETS_DIR = Path(__file__).parent / "presets"

_CLAUDECODE_MODEL = "claudecode"


def _build_provider(model: str) -> Any:
    """Return an LLMProvider for the given model string.

    ``'claudecode'`` routes through ClaudeCodeProvider. Any other string is
    passed to LiteLLMProvider.

    Args:
        model: Model string — ``'claudecode'`` or a LiteLLM model string.

    Returns:
        An LLMProvider instance.
    """
    if model == _CLAUDECODE_MODEL:
        from bricks.providers.claudecode import ClaudeCodeProvider

        return ClaudeCodeProvider(timeout=300)

    from bricks.llm.litellm_provider import LiteLLMProvider

    return LiteLLMProvider(model=model)


# ── /api/run ────────────────────────────────────────────────────────────────


@router.post("/api/run", response_model=BenchmarkResponse)
async def run_benchmark(req: BenchmarkRequest) -> BenchmarkResponse:
    """Run both BricksEngine and RawLLMEngine on the same task, return comparison.

    Args:
        req: Benchmark request with task text, raw data, and optional settings.

    Returns:
        BenchmarkResponse with results from both engines and token savings stats.

    Raises:
        HTTPException: If engine construction fails (e.g. missing API key).
    """
    from bricks.benchmark.showcase.engine import BricksEngine, RawLLMEngine
    from bricks.benchmark.showcase.result_writer import check_correctness

    try:
        provider = _build_provider(req.model)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to build provider: {exc}") from exc

    bricks_engine = BricksEngine(provider=provider)
    llm_engine = RawLLMEngine(provider=provider)

    # Engines expect data wrapped in markdown JSON fences (extract_markdown_fences brick).
    # Guard against double-fencing if the data is already wrapped.
    raw = req.raw_data
    fenced_data = raw if raw.strip().startswith("```") else f"```json\n{raw}\n```"

    bricks_raw = bricks_engine.solve(req.task_text, fenced_data)
    llm_raw = llm_engine.solve(req.task_text, fenced_data)

    bricks_correct: bool | None = None
    llm_correct: bool | None = None
    if req.expected_outputs is not None:
        bricks_correct = check_correctness(bricks_raw.outputs, req.expected_outputs)
        llm_correct = check_correctness(llm_raw.outputs, req.expected_outputs)

    bricks_tokens = bricks_raw.tokens_in + bricks_raw.tokens_out
    llm_tokens = llm_raw.tokens_in + llm_raw.tokens_out

    savings_ratio = (llm_tokens / bricks_tokens) if bricks_tokens > 0 else 1.0
    savings_percent = ((1 - bricks_tokens / llm_tokens) * 100) if llm_tokens > 0 else 0.0

    return BenchmarkResponse(
        bricks_result=EngineResultResponse(
            engine_name="BricksEngine",
            outputs=bricks_raw.outputs,
            correct=bricks_correct,
            tokens_in=bricks_raw.tokens_in,
            tokens_out=bricks_raw.tokens_out,
            duration_seconds=bricks_raw.duration_seconds,
            model=bricks_raw.model,
            raw_response=bricks_raw.raw_response,
            error=bricks_raw.error,
        ),
        llm_result=EngineResultResponse(
            engine_name="RawLLMEngine",
            outputs=llm_raw.outputs,
            correct=llm_correct,
            tokens_in=llm_raw.tokens_in,
            tokens_out=llm_raw.tokens_out,
            duration_seconds=llm_raw.duration_seconds,
            model=llm_raw.model,
            raw_response=llm_raw.raw_response,
            error=llm_raw.error,
        ),
        savings_ratio=round(savings_ratio, 2),
        savings_percent=round(savings_percent, 1),
    )


# ── /api/datasets ────────────────────────────────────────────────────────────


@router.get("/api/datasets")
async def list_datasets() -> list[dict[str, Any]]:
    """Return all built-in datasets with metadata, preview, and full data.

    Returns:
        List of dataset dicts with id, name, description, row_count, fields,
        preview (first 3 rows), and full_data (JSON string).
    """
    return _loader.list_datasets()


# ── /api/bricks ──────────────────────────────────────────────────────────────


@router.get("/api/bricks")
async def list_bricks() -> list[dict[str, Any]]:
    """Return all registered stdlib bricks with name, description, and category.

    Returns:
        List of dicts with ``name``, ``description``, and ``category`` for each brick.
    """
    from bricks.core.registry import BrickRegistry

    registry = BrickRegistry.from_stdlib()
    return [
        {
            "name": name,
            "description": meta.description,
            "category": meta.category,
        }
        for name, meta in registry.list_all()
    ]


# ── /api/presets ─────────────────────────────────────────────────────────────


@router.get("/api/presets")
async def list_presets() -> list[dict[str, Any]]:
    """Return preset benchmark scenarios from the presets directory.

    Returns:
        List of preset dicts with name, dataset_id, task_text, and expected_outputs.
    """
    import yaml

    presets: list[dict[str, Any]] = []
    if not _PRESETS_DIR.exists():
        return presets

    for path in sorted(_PRESETS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "name" in data:
                presets.append(
                    {
                        "name": data.get("name", ""),
                        "dataset_id": data.get("dataset_id"),
                        "task_text": data.get("task_text", ""),
                        "expected_outputs": data.get("expected_outputs"),
                    }
                )
        except Exception:  # noqa: S112
            continue

    return presets
