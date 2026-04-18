"""Tests for benchmark.showcase.result_writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bricks.benchmark.showcase.result_writer import (
    BaselineRecord,
    CallRecord,
    ExecutionRecord,
    ScenarioResult,
    TotalRecord,
    check_correctness,
    write_scenario_result,
)


class TestCallRecord:
    """Tests for CallRecord model."""

    def test_defaults(self) -> None:
        """CallRecord has sensible defaults for all optional fields."""
        record = CallRecord(call_number=1)
        assert record.call_number == 1
        assert record.system_prompt == ""
        assert record.user_prompt == ""
        assert record.response_text == ""
        assert record.yaml_generated == ""
        assert record.validation_errors == []
        assert record.is_valid is False
        assert record.input_tokens == 0
        assert record.output_tokens == 0
        assert record.total_tokens == 0
        assert record.duration_seconds == 0.0

    def test_full_construction(self) -> None:
        """CallRecord stores all fields correctly."""
        record = CallRecord(
            call_number=2,
            system_prompt="sys",
            user_prompt="user",
            response_text="resp",
            yaml_generated="yaml",
            validation_errors=["err1"],
            is_valid=True,
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
            duration_seconds=1.5,
        )
        assert record.call_number == 2
        assert record.system_prompt == "sys"
        assert record.is_valid is True
        assert record.total_tokens == 300


class TestExecutionRecord:
    """Tests for ExecutionRecord model."""

    def test_defaults(self) -> None:
        """ExecutionRecord defaults to failure state."""
        record = ExecutionRecord()
        assert record.success is False
        assert record.actual_outputs == {}
        assert record.expected_outputs == {}
        assert record.correct is False
        assert record.error == ""


class TestScenarioResult:
    """Tests for ScenarioResult model."""

    def test_minimal_construction(self) -> None:
        """ScenarioResult can be created with just scenario and mode."""
        result = ScenarioResult(scenario="A-5", mode="compose")
        assert result.scenario == "A-5"
        assert result.mode == "compose"
        assert result.steps == 0
        assert result.calls == []

    def test_serialization_roundtrip(self) -> None:
        """ScenarioResult survives JSON serialization and deserialization."""
        original = ScenarioResult(
            scenario="A-25",
            mode="compose",
            steps=25,
            model="claude-haiku-4-5-20251001",
            task_text="Calculate property valuation",
            calls=[
                CallRecord(
                    call_number=1,
                    system_prompt="You are a composer",
                    user_prompt="Calculate...",
                    response_text="name: bp\nsteps: []",
                    yaml_generated="name: bp\nsteps: []",
                    is_valid=True,
                    input_tokens=100,
                    output_tokens=200,
                    total_tokens=300,
                    duration_seconds=1.5,
                ),
            ],
            execution=ExecutionRecord(
                success=True,
                actual_outputs={"total_cost": 2626312.5},
                expected_outputs={"total_cost": 2626312.5},
                correct=True,
            ),
            totals=TotalRecord(
                api_calls=1,
                input_tokens=100,
                output_tokens=200,
                total_tokens=300,
                cost_usd=0.0009,
                duration_seconds=1.5,
            ),
            baseline=BaselineRecord(
                no_tools_tokens=500,
                no_tools_input=200,
                no_tools_output=300,
                ratio=1.67,
            ),
        )
        json_str = original.model_dump_json()
        restored = ScenarioResult.model_validate_json(json_str)
        assert restored.scenario == original.scenario
        assert restored.steps == original.steps
        assert len(restored.calls) == 1
        assert restored.calls[0].system_prompt == "You are a composer"
        assert restored.execution.correct is True
        assert restored.totals.cost_usd == pytest.approx(0.0009)
        assert restored.baseline.ratio == pytest.approx(1.67)


class TestCheckCorrectness:
    """Tests for check_correctness function."""

    def test_exact_match(self) -> None:
        """Exact integer match returns True."""
        assert check_correctness({"x": 42}, {"x": 42}) is True

    def test_float_within_tolerance(self) -> None:
        """Float values within tolerance match."""
        assert check_correctness({"x": 100.005}, {"x": 100.0}) is True

    def test_float_outside_tolerance(self) -> None:
        """Float values outside tolerance do not match."""
        assert check_correctness({"x": 200.0}, {"x": 100.0}) is False

    def test_missing_key(self) -> None:
        """Missing key in actual returns False."""
        assert check_correctness({"a": 1}, {"a": 1, "b": 2}) is False

    def test_extra_keys_ok(self) -> None:
        """Extra keys in actual are ignored."""
        assert check_correctness({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 2}) is True

    def test_string_match(self) -> None:
        """String values must match exactly."""
        assert check_correctness({"s": "hello"}, {"s": "hello"}) is True
        assert check_correctness({"s": "hello"}, {"s": "world"}) is False

    def test_empty_expected(self) -> None:
        """Empty expected outputs returns False."""
        assert check_correctness({"x": 1}, {}) is False

    def test_int_vs_float_comparison(self) -> None:
        """Int and float values compare correctly."""
        assert check_correctness({"x": 42}, {"x": 42.0}) is True

    def test_custom_tolerance(self) -> None:
        """Custom tolerance is respected."""
        assert check_correctness({"x": 110.0}, {"x": 100.0}, tolerance=0.15) is True
        assert check_correctness({"x": 110.0}, {"x": 100.0}, tolerance=0.05) is False


class TestWriteScenarioResult:
    """Tests for write_scenario_result function."""

    def test_write_creates_file(self, tmp_path: Path) -> None:
        """write_scenario_result creates a JSON file in the run directory."""
        result = ScenarioResult(scenario="A-5", mode="compose", steps=5)
        path = write_scenario_result(tmp_path, result)
        assert path.exists()
        assert path.name == "A-5_compose.json"

    def test_write_valid_json(self, tmp_path: Path) -> None:
        """Written file contains valid JSON matching the model."""
        result = ScenarioResult(
            scenario="A-25",
            mode="tool_use",
            steps=25,
            execution=ExecutionRecord(success=True, correct=True),
        )
        path = write_scenario_result(tmp_path, result)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["scenario"] == "A-25"
        assert data["mode"] == "tool_use"
        assert data["execution"]["correct"] is True

    def test_write_roundtrip(self, tmp_path: Path) -> None:
        """Written JSON can be deserialized back to ScenarioResult."""
        original = ScenarioResult(
            scenario="C",
            mode="tool_use",
            task_text="test task",
            totals=TotalRecord(api_calls=3, total_tokens=1500),
        )
        path = write_scenario_result(tmp_path, original)
        restored = ScenarioResult.model_validate_json(path.read_text(encoding="utf-8"))
        assert restored.scenario == "C"
        assert restored.totals.api_calls == 3
        assert restored.totals.total_tokens == 1500
