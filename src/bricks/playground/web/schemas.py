"""Pydantic v2 schemas for the Bricks Benchmark web API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class BenchmarkRequest(BaseModel):
    """Request body for POST /api/run.

    Attributes:
        task_text: Natural language description of the computation task.
        raw_data: JSON string containing the input data.
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
    """Result from one engine for one benchmark run.

    Attributes:
        engine_name: Class name of the engine (e.g. ``'BricksEngine'``).
        outputs: Parsed structured outputs from the engine.
        correct: True/False if expected_outputs were provided, None otherwise.
        tokens_in: Input token count.
        tokens_out: Output token count.
        duration_seconds: Wall-clock time for this run.
        model: Model identifier string used.
        raw_response: Full LLM response text (YAML blueprint or JSON).
        error: Non-empty string if the engine failed.
    """

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
    """Complete benchmark comparison response.

    Attributes:
        bricks_result: Result from BricksEngine.
        llm_result: Result from RawLLMEngine.
        savings_ratio: llm_total_tokens / bricks_total_tokens (1.0 if bricks used 0 tokens).
        savings_percent: ``(1 - bricks_tokens / llm_tokens) * 100``.
    """

    bricks_result: EngineResultResponse
    llm_result: EngineResultResponse
    savings_ratio: float
    savings_percent: float
