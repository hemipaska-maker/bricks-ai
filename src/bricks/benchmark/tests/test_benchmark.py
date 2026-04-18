"""Tests for the Bricks vs Python benchmark."""

from __future__ import annotations

import pytest

from bricks.benchmark.domain_bricks import (
    build_registry,
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
from bricks.benchmark.runner import BricksRunner, PythonRunner
from bricks.benchmark.scenarios import (
    ALL_SCENARIOS,
    SCENARIO_1,
    SCENARIO_2,
    SCENARIO_3,
    SCENARIO_4,
    SCENARIO_5,
    SCENARIO_6,
    SCENARIO_7,
    SCENARIO_8,
    SCENARIO_9,
    SCENARIO_10,
)
from bricks.benchmark.token_counter import TokenEstimator

# ──────────────────────────────────────────────────────────────────────
# Domain bricks
# ──────────────────────────────────────────────────────────────────────


class TestDomainBricks:
    """Unit tests for each domain brick."""

    def test_load_csv_data_sales(self) -> None:
        result = load_csv_data("sales")
        assert result["row_count"] == 5
        assert "revenue" in result["columns"]

    def test_load_csv_data_employees(self) -> None:
        result = load_csv_data("employees")
        assert result["row_count"] == 3
        assert "salary" in result["columns"]

    def test_load_csv_data_unknown(self) -> None:
        result = load_csv_data("unknown")
        assert result["row_count"] == 0

    def test_filter_rows(self) -> None:
        data = [{"x": 10}, {"x": 20}, {"x": 30}]
        result = filter_rows(data, "x", ">", 15)
        assert result["row_count"] == 2

    def test_calculate_stats(self) -> None:
        data = [{"v": 10.0}, {"v": 20.0}, {"v": 30.0}]
        result = calculate_stats(data, "v")
        assert result["mean"] == 20.0
        assert result["sum"] == 60.0
        assert result["count"] == 3

    def test_word_count(self) -> None:
        data = [{"text": "hello world"}, {"text": "one two three"}]
        result = word_count(data, "text")
        assert result["total_words"] == 5
        assert result["avg_per_row"] == 2.5

    def test_generate_summary(self) -> None:
        result = generate_summary("Report", {"a": 1, "b": 2})
        assert "Report" in result
        assert "a: 1" in result

    def test_format_number(self) -> None:
        result = format_number(1234.5, decimals=2, prefix="$", suffix="")
        assert result == "$1,234.50"

    def test_validate_schema_valid(self) -> None:
        data = [{"a": 1, "b": 2}]
        result = validate_schema(data, ["a", "b"])
        assert result["valid"] is True

    def test_validate_schema_missing(self) -> None:
        data = [{"a": 1}]
        result = validate_schema(data, ["a", "b"])
        assert result["valid"] is False
        assert "b" in result["missing"]

    def test_merge_reports(self) -> None:
        result = merge_reports(["AAA", "BBB"], separator=" | ")
        assert result == "AAA | BBB"

    def test_multiply(self) -> None:
        assert multiply(3.0, 4.0) == 12.0

    def test_divide(self) -> None:
        assert divide(10.0, 2.0) == 5.0

    def test_divide_by_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            divide(10.0, 0.0)


class TestBuildRegistry:
    """Registry builder tests."""

    def test_registry_has_all_bricks(self) -> None:
        registry = build_registry()
        expected = {
            "load_csv_data",
            "filter_rows",
            "calculate_stats",
            "word_count",
            "generate_summary",
            "format_number",
            "validate_schema",
            "merge_reports",
            "multiply",
            "divide",
        }
        actual = {name for name, _ in registry.list_all()}
        assert actual == expected


# ──────────────────────────────────────────────────────────────────────
# BricksRunner
# ──────────────────────────────────────────────────────────────────────


class TestBricksRunner:
    """Tests for the Bricks pipeline runner."""

    @pytest.fixture()
    def runner(self) -> BricksRunner:
        return BricksRunner(registry=build_registry())

    def test_scenario_1_correct(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_1)
        assert result.status == "correct"
        assert result.outputs is not None
        assert abs(result.outputs["total"] - 60.0) < 0.01

    def test_scenario_2_correct(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_2)
        assert result.status == "correct"
        assert result.outputs is not None
        assert abs(result.outputs["mean_revenue"] - 2533.33) < 0.01

    def test_scenario_3_caught_pre_exec(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_3)
        assert result.status == "caught_pre_exec"
        assert any("sentiment_analysis" in e for e in result.errors)

    def test_scenario_4_caught_pre_exec(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_4)
        assert result.status == "caught_pre_exec"

    def test_scenario_5_caught_pre_exec(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_5)
        assert result.status == "caught_pre_exec"

    def test_scenario_6_caught_pre_exec(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_6)
        assert result.status == "caught_pre_exec"
        errors_lower = [e.lower() for e in result.errors]
        assert any("save_as" in e or "duplicate" in e for e in errors_lower)

    def test_scenario_7_clear_runtime_error(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_7)
        assert result.status == "runtime_error"
        assert result.error_quality == "clear"

    def test_scenario_8_clear_runtime_error(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_8)
        assert result.status == "runtime_error"
        assert result.error_quality == "clear"
        assert any("compute_ratio" in e for e in result.errors)

    def test_scenario_9_correct(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_9)
        assert result.status == "correct"

    def test_scenario_10_security_safe(self, runner: BricksRunner) -> None:
        result = runner.run(SCENARIO_10)
        assert result.security_safe is True


# ──────────────────────────────────────────────────────────────────────
# PythonRunner
# ──────────────────────────────────────────────────────────────────────


class TestPythonRunner:
    """Tests for the raw Python exec runner."""

    @pytest.fixture()
    def runner(self) -> PythonRunner:
        return PythonRunner()

    def test_scenario_1_correct(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_1)
        assert result.status == "correct"

    def test_scenario_2_correct(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_2)
        assert result.status == "correct"

    def test_scenario_3_runtime_error(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_3)
        assert result.status == "runtime_error"
        assert result.error_quality == "poor"

    def test_scenario_4_runtime_error(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_4)
        assert result.status == "runtime_error"
        assert result.error_quality == "poor"

    def test_scenario_5_runtime_error(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_5)
        assert result.status == "runtime_error"
        assert result.error_quality == "poor"

    def test_scenario_6_wrong_answer(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_6)
        assert result.status == "wrong_answer"

    def test_scenario_7_runtime_error(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_7)
        assert result.status == "runtime_error"
        assert result.error_quality == "poor"

    def test_scenario_8_runtime_error(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_8)
        assert result.status == "runtime_error"
        assert result.error_quality == "poor"

    def test_scenario_9_correct(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_9)
        assert result.status == "correct"

    def test_scenario_10_security_breach(self, runner: PythonRunner) -> None:
        result = runner.run(SCENARIO_10)
        assert result.security_safe is False


# ──────────────────────────────────────────────────────────────────────
# Token counter
# ──────────────────────────────────────────────────────────────────────


class TestTokenCounter:
    """Tests for the token estimator."""

    def test_bricks_less_than_python_all_scenarios(self) -> None:
        estimator = TokenEstimator()
        for scn in ALL_SCENARIOS:
            bt = estimator.estimate_bricks(scn)
            pt = estimator.estimate_python(scn)
            msg = f"{scn.name}: bricks={bt.total} > python={pt.total}"
            assert bt.total <= pt.total, msg

    def test_bricks_reuse_cost_zero_scenario_9(self) -> None:
        estimator = TokenEstimator()
        bt = estimator.estimate_bricks(SCENARIO_9)
        assert bt.reuse_cost == 0

    def test_python_reuse_cost_positive_scenario_9(self) -> None:
        estimator = TokenEstimator()
        pt = estimator.estimate_python(SCENARIO_9)
        assert pt.reuse_cost > 0

    def test_bricks_error_correction_always_zero(self) -> None:
        estimator = TokenEstimator()
        for scn in ALL_SCENARIOS:
            bt = estimator.estimate_bricks(scn, had_error=True)
            assert bt.error_correction == 0

    def test_python_error_correction_positive_when_error(self) -> None:
        estimator = TokenEstimator()
        pt = estimator.estimate_python(SCENARIO_3, had_error=True)
        assert pt.error_correction > 0


# ──────────────────────────────────────────────────────────────────────
# Report (smoke test)
# ──────────────────────────────────────────────────────────────────────


class TestReport:
    """Smoke test that the report generates without error."""

    def test_full_report_runs(self, capsys: pytest.CaptureFixture[str]) -> None:
        registry = build_registry()
        bricks_runner = BricksRunner(registry=registry)
        python_runner = PythonRunner()

        bricks_results = [bricks_runner.run(scn) for scn in ALL_SCENARIOS]
        python_results = [python_runner.run(scn) for scn in ALL_SCENARIOS]

        from bricks.benchmark.report import print_full_report

        print_full_report(ALL_SCENARIOS, bricks_results, python_results)

        captured = capsys.readouterr()
        assert "FINAL SCORECARD" in captured.out
        assert "TOKEN SAVINGS" in captured.out
        assert "SECURITY" in captured.out
