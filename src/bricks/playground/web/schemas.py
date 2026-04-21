"""Pydantic v2 schemas for the Bricks Playground web API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Legacy schemas (used by scenario_loader + retained /api tests) ───────────
#
# Kept so the older internal `scenario_to_benchmark_request` helper and the
# existing unit tests continue to pass during the Playground v0.5.0 rollout.
# Slated for removal in the #46 polish sweep once scenario_loader moves to
# the new RunRequest payload shape.


class BenchmarkRequest(BaseModel):
    """Legacy request body (pre-v0.5.0 /api/run).

    Attributes:
        task_text: Natural-language task description.
        raw_data: JSON string of the input data.
        expected_outputs: Optional ground-truth outputs for correctness checking.
        required_bricks: Optional list of brick names to hint the composer.
        model: LLM model string (default: ``'claudecode'``).
    """

    task_text: str
    raw_data: str
    expected_outputs: dict[str, Any] | None = None
    required_bricks: list[str] | None = None
    model: str = "claudecode"


class EngineResultResponse(BaseModel):
    """Legacy per-engine result for /api/run."""

    engine_name: str
    outputs: dict[str, Any]
    correct: bool | None
    tokens_in: int
    tokens_out: int
    duration_seconds: float
    model: str
    raw_response: str
    error: str


class BenchmarkResponse(BaseModel):
    """Legacy two-engine benchmark comparison response."""

    bricks_result: EngineResultResponse
    llm_result: EngineResultResponse
    savings_ratio: float
    savings_percent: float


# ── v0.5.0 Playground schemas (design.md §6) ─────────────────────────────────


class ScenarioSummary(BaseModel):
    """Lightweight scenario descriptor returned by ``GET /playground/scenarios``."""

    id: str
    name: str
    description: str


class ScenarioDetail(BaseModel):
    """Full scenario body returned by ``GET /playground/scenarios/{id}``."""

    id: str
    name: str
    description: str
    task: str
    data: Any
    expected_output: dict[str, Any] | None = None
    required_bricks: list[str] | None = None


class UploadResponse(BaseModel):
    """Shape returned by ``POST /playground/upload``."""

    data: Any
    filename: str
    size_bytes: int
    row_count: int | None = None


class RunRequest(BaseModel):
    """Request body for ``POST /playground/run`` (design.md §6).

    API keys live only in the request body (BYOK). They are never read from
    environment variables. Non-``claude_code`` / non-``ollama`` providers
    require ``api_key``; validation is enforced at dispatch time.
    """

    provider: Literal["anthropic", "openai", "claude_code", "ollama"]
    model: str
    api_key: str | None = None
    task: str
    data: Any
    expected_output: dict[str, Any] | None = None
    compare: bool = False


class TokenBreakdown(BaseModel):
    """Per-engine token counter."""

    in_: int = Field(alias="in")
    out: int
    total: int

    model_config = {"populate_by_name": True}


class CheckResult(BaseModel):
    """One correctness check line item."""

    key: str
    expected: Any
    got: Any
    pass_: bool = Field(alias="pass")

    model_config = {"populate_by_name": True}


class BrickUsage(BaseModel):
    """One brick type and how many times it appeared in the blueprint."""

    name: str
    category: str
    count: int


class EngineResult(BaseModel):
    """Per-engine result payload for ``/playground/run`` (design.md §6)."""

    blueprint_yaml: str | None = None
    bricks_used: list[BrickUsage] | None = None
    response: str | None = None
    outputs: dict[str, Any]
    tokens: TokenBreakdown
    duration_ms: int
    cost_usd: float | None = None
    checks: list[CheckResult] = []


class RunMetadata(BaseModel):
    """Top-level metadata about the run."""

    model: str
    provider: str
    seed: int = 42
    version: str
    timestamp: str


class RunResponse(BaseModel):
    """Response body for ``POST /playground/run`` (design.md §6)."""

    bricks: EngineResult
    raw_llm: EngineResult | None = None
    run_metadata: RunMetadata
