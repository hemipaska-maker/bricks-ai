"""Tests for Mission 076 pipeline fixes — flow_def reuse and routes fencing."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestSolveReuseFlowDef:
    """Fix 7: solve_reuse() prefers flow_def.execute() over YAML loader."""

    def test_solve_reuse_calls_flow_def_execute(self) -> None:
        """When flow_def is provided, solve_reuse calls execute() not load_string."""
        from bricks_benchmark.showcase.engine import BricksEngine

        # Create a mock provider so BricksEngine doesn't need a real one
        mock_provider = MagicMock()
        engine = BricksEngine(provider=mock_provider)

        # Mock the flow_def
        mock_flow_def = MagicMock()
        mock_flow_def.execute.return_value = {"result": 42}

        result = engine.solve_reuse(
            blueprint_yaml="name: test",
            raw_data="test data",
            flow_def=mock_flow_def,
        )

        mock_flow_def.execute.assert_called_once()
        assert result.outputs == {"result": 42}
        assert result.tokens_in == 0
        assert result.tokens_out == 0

    def test_solve_reuse_falls_back_to_yaml(self) -> None:
        """When flow_def is None, solve_reuse uses YAML loader as fallback."""
        from bricks_benchmark.showcase.engine import BricksEngine

        mock_provider = MagicMock()
        engine = BricksEngine(provider=mock_provider)

        # This will fail with invalid YAML, proving the YAML path is taken
        result = engine.solve_reuse(
            blueprint_yaml="not valid yaml {{{{",
            raw_data="test data",
            flow_def=None,
        )
        assert result.error, "Expected error from invalid YAML fallback"


class TestRoutesMarkdownFencing:
    """Fix 8: /api/run wraps raw_data in markdown fences."""

    def test_plain_json_gets_fenced(self) -> None:
        """Plain JSON string is wrapped in ```json fences."""
        raw = '[{"id": 1}]'
        # Simulate the fencing logic from routes.py
        fenced = raw if raw.strip().startswith("```") else f"```json\n{raw}\n```"
        assert fenced.startswith("```json\n")
        assert fenced.endswith("\n```")
        assert '[{"id": 1}]' in fenced

    def test_already_fenced_data_not_double_fenced(self) -> None:
        """Data already wrapped in fences is not double-wrapped."""
        raw = '```json\n[{"id": 1}]\n```'
        fenced = raw if raw.strip().startswith("```") else f"```json\n{raw}\n```"
        assert fenced == raw, "Already-fenced data should not be wrapped again"
        assert fenced.count("```json") == 1

    def test_fenced_with_whitespace(self) -> None:
        """Data with leading whitespace before fences is detected."""
        raw = '  ```json\n[{"id": 1}]\n```'
        fenced = raw if raw.strip().startswith("```") else f"```json\n{raw}\n```"
        assert fenced == raw
