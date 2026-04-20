"""Runners that execute scenarios through Bricks or raw Python."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bricks.benchmark.domain_bricks import (
    calculate_stats,
    divide,
    filter_rows,
    format_number,
    generate_summary,
    load_csv_data,
    merge_reports,
    multiply,
    validate_schema,
    word_count,
)
from bricks.benchmark.scenarios import Scenario
from bricks.benchmark.token_counter import TokenEstimate, TokenEstimator
from bricks.core import (
    BlueprintEngine,
    BlueprintLoader,
    BlueprintValidator,
    BrickRegistry,
)
from bricks.core.exceptions import (
    BlueprintValidationError,
    BrickExecutionError,
    YamlLoadError,
)


@dataclass
class RunResult:
    """Outcome of running a single scenario under one approach."""

    status: str  # correct | wrong_answer | caught_pre_exec | runtime_error
    outputs: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    error_quality: str = "none"  # "clear", "poor", "none"
    tokens: TokenEstimate | None = None
    security_safe: bool = True


class BricksRunner:
    """Run a scenario through the Bricks pipeline: load → validate → execute."""

    def __init__(self, registry: BrickRegistry) -> None:
        self._registry = registry
        self._loader = BlueprintLoader()
        self._validator = BlueprintValidator(registry=registry)
        self._engine = BlueprintEngine(registry=registry)
        self._estimator = TokenEstimator()

    def run(self, scenario: Scenario) -> RunResult:
        """Execute a scenario and return a RunResult."""
        # 1. Parse YAML
        try:
            sequence = self._loader.load_string(scenario.bricks_yaml)
        except YamlLoadError as exc:
            return RunResult(
                status="runtime_error",
                errors=[str(exc)],
                error_quality="clear",
                tokens=self._estimator.estimate_bricks(scenario, had_error=True),
            )

        # 2. Validate
        try:
            self._validator.validate(sequence)
        except BlueprintValidationError as exc:
            return RunResult(
                status="caught_pre_exec",
                errors=list(exc.errors),
                error_quality="clear",
                tokens=self._estimator.estimate_bricks(scenario, had_error=True),
                security_safe=True,
            )

        # 3. Execute
        try:
            outputs = self._engine.run(sequence, inputs=scenario.inputs).outputs
        except BrickExecutionError as exc:
            return RunResult(
                status="runtime_error",
                errors=[f"BrickExecutionError in step '{exc.step_name}', brick '{exc.brick_name}': {exc.cause}"],
                error_quality="clear",
                tokens=self._estimator.estimate_bricks(scenario, had_error=True),
                security_safe=True,
            )

        # 4. Compare outputs
        tokens = self._estimator.estimate_bricks(scenario, had_error=False)
        if _outputs_match(outputs, scenario.expected_output):
            return RunResult(
                status="correct",
                outputs=outputs,
                tokens=tokens,
                security_safe=True,
            )
        return RunResult(
            status="wrong_answer",
            outputs=outputs,
            errors=[f"Expected {scenario.expected_output!r}, got {outputs!r}"],
            error_quality="none",
            tokens=tokens,
            security_safe=True,
        )


class PythonRunner:
    """Run a scenario by exec'ing AI-generated Python code."""

    def __init__(self) -> None:
        self._estimator = TokenEstimator()

    def run(self, scenario: Scenario) -> RunResult:
        """Execute a scenario's Python code and return a RunResult."""
        # Build a restricted namespace with domain functions + inputs
        namespace: dict[str, Any] = {
            "inputs": dict(scenario.inputs),
            "load_csv_data": load_csv_data,
            "filter_rows": filter_rows,
            "calculate_stats": calculate_stats,
            "word_count": word_count,
            "generate_summary": generate_summary,
            "format_number": format_number,
            "validate_schema": validate_schema,
            "merge_reports": merge_reports,
            "multiply": multiply,
            "divide": divide,
        }

        try:
            # SECURITY: exec() is intentional here — this runner exists to demonstrate
            # the security risks of code generation. The namespace is restricted to
            # domain functions only. This code is never used in production.
            exec(scenario.python_code, namespace)  # noqa: S102
        except Exception as exc:
            return RunResult(
                status="runtime_error",
                errors=[f"{type(exc).__name__}: {exc}"],
                error_quality="poor",
                tokens=self._estimator.estimate_python(scenario, had_error=True),
                security_safe=True,
            )

        result = namespace.get("result")
        if not isinstance(result, dict):
            return RunResult(
                status="runtime_error",
                errors=["Python code did not set 'result' dict"],
                error_quality="poor",
                tokens=self._estimator.estimate_python(scenario, had_error=True),
            )

        # Check for security violations (leaked data)
        leaked_keys = [k for k in result if k.startswith("_leaked")]
        security_safe = len(leaked_keys) == 0

        tokens = self._estimator.estimate_python(scenario, had_error=False)

        if scenario.category == "security" and not security_safe:
            return RunResult(
                status="runtime_error",
                outputs=result,
                errors=[f"Security breach: leaked keys {leaked_keys}"],
                error_quality="poor",
                tokens=tokens,
                security_safe=False,
            )

        if _outputs_match(result, scenario.expected_output):
            return RunResult(
                status="correct",
                outputs=result,
                tokens=tokens,
                security_safe=security_safe,
            )
        return RunResult(
            status="wrong_answer",
            outputs=result,
            errors=[f"Expected {scenario.expected_output!r}, got {result!r}"],
            error_quality="none",
            tokens=tokens,
            security_safe=security_safe,
        )


def _outputs_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Check that all expected keys match in the actual output."""
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        if isinstance(exp_val, float) and isinstance(act_val, float):
            if abs(exp_val - act_val) > 0.01:
                return False
        elif act_val != exp_val:
            return False
    return True
