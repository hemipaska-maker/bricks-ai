"""Structured result file writer for benchmark runs.

Serializes benchmark run data to structured JSON — one file per scenario.
All models are Pydantic v2 BaseModel for easy serialization and validation.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from benchmark.constants import FLOAT_TOLERANCE


class CallRecord(BaseModel):
    """Record of a single API call within a benchmark run."""

    call_number: int
    system_prompt: str = ""
    user_prompt: str = ""
    response_text: str = ""
    yaml_generated: str = ""
    validation_errors: list[str] = Field(default_factory=list)
    is_valid: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0


class ExecutionRecord(BaseModel):
    """Record of blueprint execution results."""

    success: bool = False
    actual_outputs: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: dict[str, Any] = Field(default_factory=dict)
    correct: bool = False
    error: str = ""


class TotalRecord(BaseModel):
    """Aggregated token/cost totals."""

    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0


class BaselineRecord(BaseModel):
    """No-tools baseline for ratio calculation."""

    no_tools_tokens: int = 0
    no_tools_input: int = 0
    no_tools_output: int = 0
    ratio: float = 0.0
    no_tools_correct: bool = False


class ScenarioResult(BaseModel):
    """Complete structured result for one scenario run."""

    scenario: str
    mode: str
    steps: int = 0
    model: str = ""
    task_text: str = ""
    calls: list[CallRecord] = Field(default_factory=list)
    execution: ExecutionRecord = Field(default_factory=ExecutionRecord)
    totals: TotalRecord = Field(default_factory=TotalRecord)
    baseline: BaselineRecord = Field(default_factory=BaselineRecord)


def check_correctness(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: float = FLOAT_TOLERANCE,
) -> bool:
    """Compare actual vs expected outputs with float tolerance.

    Args:
        actual: Outputs from blueprint execution.
        expected: Expected outputs from TaskGenerator.
        tolerance: Float comparison tolerance.

    Returns:
        True if all expected keys are present and values match within tolerance.
    """
    if not expected:
        return False

    for key, exp_val in expected.items():
        if key not in actual:
            return False
        act_val = actual[key]

        if isinstance(exp_val, float) and isinstance(act_val, (int, float)):
            if not math.isclose(float(act_val), exp_val, rel_tol=tolerance):
                return False
        elif isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
            if not math.isclose(float(act_val), float(exp_val), rel_tol=tolerance):
                return False
        elif isinstance(exp_val, str) and isinstance(act_val, str):
            if act_val != exp_val:
                return False
        else:
            if act_val != exp_val:
                return False

    return True


def check_no_tools_answer(
    answer: str,
    expected: dict[str, Any],
    tolerance: float = FLOAT_TOLERANCE,
) -> bool:
    """Check if expected numeric values appear in the no-tools LLM answer text.

    Searches the raw text response for each expected numeric value (formatted
    to 2 decimal places). String values are checked as substrings. This does
    not execute any code — it is a text scan only.

    Args:
        answer: The LLM's raw text response (final_answer from AgentResult).
        expected: Expected outputs from TaskGenerator.
        tolerance: Relative tolerance for floating-point comparisons.

    Returns:
        True if all expected values are found in the answer text.
    """
    if not expected or not answer:
        return False

    for val in expected.values():
        if isinstance(val, (int, float)):
            fval = float(val)
            # Try several common formatting styles
            candidates = [
                str(round(fval, 2)),
                f"{fval:.2f}",
                f"{fval:,.2f}",
                f"{fval:.0f}",
                str(int(fval)) if fval == int(fval) else None,
            ]
            if not any(c and c in answer for c in candidates):
                return False
        elif isinstance(val, str):
            if val not in answer:
                return False

    return True


def write_scenario_result(run_dir: Path, result: ScenarioResult) -> Path:
    """Write a structured scenario result JSON file.

    Args:
        run_dir: The run directory.
        result: Complete scenario result.

    Returns:
        Path to the written JSON file.
    """
    filename = f"{result.scenario}_{result.mode}.json"
    out_path = run_dir / filename
    out_path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return out_path
