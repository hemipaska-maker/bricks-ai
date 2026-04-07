"""Tests for bricks_benchmark.showcase.engine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bricks_benchmark.showcase.engine import (
    BenchmarkResult,
    Engine,
    EngineResult,
    RawLLMEngine,
)


class TestEngineResult:
    """Tests for EngineResult dataclass."""

    def test_construction_with_required_fields(self) -> None:
        """EngineResult stores all required fields."""
        result = EngineResult(
            outputs={"count": 5},
            tokens_in=100,
            tokens_out=50,
            duration_seconds=1.5,
            model="test-model",
        )
        assert result.outputs == {"count": 5}
        assert result.tokens_in == 100
        assert result.tokens_out == 50
        assert result.duration_seconds == 1.5
        assert result.model == "test-model"
        assert result.raw_response == ""
        assert result.error == ""

    def test_optional_fields_default_empty(self) -> None:
        """EngineResult raw_response and error default to empty string."""
        result = EngineResult(
            outputs={},
            tokens_in=0,
            tokens_out=0,
            duration_seconds=0.0,
            model="",
        )
        assert result.raw_response == ""
        assert result.error == ""


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_construction(self) -> None:
        """BenchmarkResult stores all fields."""
        result = BenchmarkResult(
            engine_name="TestEngine",
            outputs={"x": 42},
            expected={"x": 42},
            correct=True,
            tokens_in=100,
            tokens_out=50,
            duration_seconds=1.0,
            model="test-model",
        )
        assert result.engine_name == "TestEngine"
        assert result.correct is True
        assert result.outputs == {"x": 42}

    def test_defaults(self) -> None:
        """BenchmarkResult optional fields default correctly."""
        result = BenchmarkResult(
            engine_name="E",
            outputs={},
            expected={},
            correct=False,
            tokens_in=0,
            tokens_out=0,
            duration_seconds=0.0,
            model="",
        )
        assert result.raw_response == ""
        assert result.error == ""


class TestEngineABC:
    """Tests for Engine abstract base class."""

    def test_cannot_instantiate_abstract(self) -> None:
        """Engine cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Engine()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_solve(self) -> None:
        """Concrete subclass without solve() raises TypeError."""

        class Incomplete(Engine):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]


class TestRawLLMEngine:
    """Tests for RawLLMEngine."""

    def _make_provider(self, text: str, tokens_in: int = 50, tokens_out: int = 20) -> MagicMock:
        """Build a mock provider returning CompletionResult."""
        from bricks.llm.base import CompletionResult

        provider = MagicMock()
        provider.complete.return_value = CompletionResult(
            text=text,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            model="mock-model",
        )
        return provider

    def test_parses_valid_json(self) -> None:
        """RawLLMEngine parses a clean JSON response correctly."""
        provider = self._make_provider('{"active_count": 18, "total": 3447.5}')
        engine = RawLLMEngine(provider=provider)
        result = engine.solve("Count active customers.", '{"data": []}')
        assert result.outputs == {"active_count": 18, "total": 3447.5}
        assert result.error == ""
        assert result.tokens_in == 50
        assert result.tokens_out == 20
        assert result.model == "mock-model"

    def test_parses_json_with_markdown_fences(self) -> None:
        """RawLLMEngine strips markdown code fences before JSON parse."""
        provider = self._make_provider('```json\n{"count": 5}\n```')
        engine = RawLLMEngine(provider=provider)
        result = engine.solve("task", "data")
        assert result.outputs == {"count": 5}
        assert result.error == ""

    def test_json_parse_failure_returns_empty_dict(self) -> None:
        """RawLLMEngine returns empty dict and error on JSON parse failure."""
        provider = self._make_provider("Sorry, I cannot compute this.")
        engine = RawLLMEngine(provider=provider)
        result = engine.solve("task", "data")
        assert result.outputs == {}
        assert "JSON parse failed" in result.error

    def test_engine_name_in_class(self) -> None:
        """RawLLMEngine class name is accessible for BenchmarkResult."""
        provider = self._make_provider("{}")
        engine = RawLLMEngine(provider=provider)
        assert engine.__class__.__name__ == "RawLLMEngine"


class TestBricksEngineSolveDirectExecution:
    """Tests that BricksEngine.solve() uses flow_def.execute() when available."""

    def test_uses_direct_execution_when_flow_def_available(self) -> None:
        """solve() calls flow_def.execute() and skips BlueprintLoader when flow_def is set."""
        from bricks_benchmark.showcase.engine import BricksEngine

        mock_flow_def = MagicMock()
        mock_flow_def.execute.return_value = {"active_count": 3}

        mock_compose_result = MagicMock()
        mock_compose_result.is_valid = True
        mock_compose_result.flow_def = mock_flow_def
        mock_compose_result.blueprint_yaml = "yaml: placeholder"
        mock_compose_result.total_input_tokens = 10
        mock_compose_result.total_output_tokens = 5
        mock_compose_result.model = "test-model"

        engine = BricksEngine.__new__(BricksEngine)
        engine._composer = MagicMock()
        engine._composer.compose.return_value = mock_compose_result
        engine._engine = MagicMock()
        engine._loader = MagicMock()
        engine._registry = MagicMock()

        result = engine.solve("task", "raw data")

        mock_flow_def.execute.assert_called_once()
        engine._loader.load_string.assert_not_called()
        assert result.outputs == {"active_count": 3}

    def test_falls_back_to_yaml_when_flow_def_is_none(self) -> None:
        """solve() falls back to BlueprintLoader when flow_def is None."""
        from bricks.core.models import ExecutionResult

        from bricks_benchmark.showcase.engine import BricksEngine

        mock_compose_result = MagicMock()
        mock_compose_result.is_valid = True
        mock_compose_result.flow_def = None
        mock_compose_result.blueprint_yaml = "yaml: placeholder"
        mock_compose_result.total_input_tokens = 10
        mock_compose_result.total_output_tokens = 5
        mock_compose_result.model = "test-model"

        engine = BricksEngine.__new__(BricksEngine)
        engine._composer = MagicMock()
        engine._composer.compose.return_value = mock_compose_result
        engine._engine = MagicMock()
        engine._engine.run.return_value = ExecutionResult(outputs={"x": 1}, steps=[])
        engine._loader = MagicMock()
        engine._registry = MagicMock()

        result = engine.solve("task", "raw data")

        engine._loader.load_string.assert_called_once_with("yaml: placeholder")
        assert result.outputs == {"x": 1}
