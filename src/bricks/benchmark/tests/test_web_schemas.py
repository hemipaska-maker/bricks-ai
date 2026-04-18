"""Tests for bricks.benchmark.web.schemas."""

from __future__ import annotations

import pytest

from bricks.benchmark.web.schemas import BenchmarkRequest, BenchmarkResponse, EngineResultResponse


class TestBenchmarkRequest:
    """Tests for BenchmarkRequest schema."""

    def test_required_fields(self) -> None:
        """BenchmarkRequest accepts task_text and raw_data as required fields."""
        req = BenchmarkRequest(task_text="Count active users", raw_data='{"users": []}')
        assert req.task_text == "Count active users"
        assert req.raw_data == '{"users": []}'

    def test_defaults(self) -> None:
        """BenchmarkRequest optional fields default correctly."""
        req = BenchmarkRequest(task_text="t", raw_data="d")
        assert req.expected_outputs is None
        assert req.required_bricks is None
        assert req.model == "claudecode"

    def test_custom_model(self) -> None:
        """BenchmarkRequest accepts a custom model string."""
        req = BenchmarkRequest(task_text="t", raw_data="d", model="gpt-4o-mini")
        assert req.model == "gpt-4o-mini"

    def test_with_expected_outputs(self) -> None:
        """BenchmarkRequest stores expected_outputs dict."""
        req = BenchmarkRequest(
            task_text="t",
            raw_data="d",
            expected_outputs={"count": 5, "total": 3.14},
        )
        assert req.expected_outputs == {"count": 5, "total": 3.14}

    def test_with_required_bricks(self) -> None:
        """BenchmarkRequest stores required_bricks list."""
        req = BenchmarkRequest(
            task_text="t",
            raw_data="d",
            required_bricks=["filter_dict_list", "count_dict_list"],
        )
        assert req.required_bricks == ["filter_dict_list", "count_dict_list"]


class TestEngineResultResponse:
    """Tests for EngineResultResponse schema."""

    def _make(self, correct: bool | None = None) -> EngineResultResponse:
        """Build a minimal EngineResultResponse for testing."""
        return EngineResultResponse(
            engine_name="TestEngine",
            outputs={"count": 5},
            correct=correct,
            tokens_in=100,
            tokens_out=50,
            duration_seconds=1.5,
            model="test-model",
            raw_response="yaml: content",
            error="",
        )

    def test_correct_is_none_when_no_expected(self) -> None:
        """correct is None when expected_outputs were not provided."""
        result = self._make(correct=None)
        assert result.correct is None

    def test_correct_true(self) -> None:
        """correct stores True when engine output matches expected."""
        result = self._make(correct=True)
        assert result.correct is True

    def test_correct_false(self) -> None:
        """correct stores False when engine output does not match expected."""
        result = self._make(correct=False)
        assert result.correct is False

    def test_all_fields_stored(self) -> None:
        """EngineResultResponse stores all provided fields."""
        result = self._make()
        assert result.engine_name == "TestEngine"
        assert result.outputs == {"count": 5}
        assert result.tokens_in == 100
        assert result.tokens_out == 50
        assert result.duration_seconds == 1.5
        assert result.model == "test-model"
        assert result.raw_response == "yaml: content"
        assert result.error == ""


class TestBenchmarkResponse:
    """Tests for BenchmarkResponse schema and savings math."""

    def _make_engine_result(self, tokens_in: int, tokens_out: int) -> EngineResultResponse:
        """Build a minimal EngineResultResponse with given token counts."""
        return EngineResultResponse(
            engine_name="Engine",
            outputs={},
            correct=None,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_seconds=1.0,
            model="m",
            raw_response="",
            error="",
        )

    def test_savings_ratio_computed(self) -> None:
        """BenchmarkResponse stores savings_ratio and savings_percent."""
        resp = BenchmarkResponse(
            bricks_result=self._make_engine_result(100, 50),
            llm_result=self._make_engine_result(400, 200),
            savings_ratio=4.0,
            savings_percent=75.0,
        )
        assert resp.savings_ratio == pytest.approx(4.0)
        assert resp.savings_percent == pytest.approx(75.0)

    def test_savings_zero_percent_when_equal(self) -> None:
        """0% savings when both engines use the same tokens."""
        resp = BenchmarkResponse(
            bricks_result=self._make_engine_result(100, 50),
            llm_result=self._make_engine_result(100, 50),
            savings_ratio=1.0,
            savings_percent=0.0,
        )
        assert resp.savings_ratio == pytest.approx(1.0)
        assert resp.savings_percent == pytest.approx(0.0)
