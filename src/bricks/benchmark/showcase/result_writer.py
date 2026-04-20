"""Structured result file writer for benchmark runs.

Serializes benchmark run data to structured JSON — one file per scenario.
All models are Pydantic v2 BaseModel for easy serialization and validation.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from bricks.benchmark.constants import FLOAT_TOLERANCE


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
