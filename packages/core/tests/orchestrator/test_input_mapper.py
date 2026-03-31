"""Tests for InputMapper."""

from __future__ import annotations

import pytest
from bricks.errors import BricksInputError
from bricks.orchestrator.input_mapper import InputMapper


class TestInputMapper:
    def test_single_input_auto_maps(self) -> None:
        """Single user key maps to single blueprint key regardless of name."""
        result = InputMapper().map({"data": [1, 2, 3]}, ["api_response"])
        assert result == {"api_response": [1, 2, 3]}

    def test_matching_keys_unchanged(self) -> None:
        """Keys already matching blueprint → returned unchanged."""
        inp = {"api_response": [1, 2], "threshold": 0.5}
        result = InputMapper().map(inp, ["api_response", "threshold"])
        assert result == inp

    def test_multi_key_position_mapping(self) -> None:
        """Two user keys map to two blueprint keys by position."""
        result = InputMapper().map({"x": 10, "y": 20}, ["a", "b"])
        assert result == {"a": 10, "b": 20}

    def test_empty_blueprint_inputs_returns_unchanged(self) -> None:
        """Blueprint with no declared inputs → user inputs returned as-is."""
        result = InputMapper().map({"foo": 1}, [])
        assert result == {"foo": 1}

    def test_mismatch_raises_bricks_input_error(self) -> None:
        """Count mismatch raises BricksInputError with helpful message."""
        with pytest.raises(BricksInputError, match="expects 2"):
            InputMapper().map({"a": 1, "b": 2, "c": 3}, ["x", "y"])
