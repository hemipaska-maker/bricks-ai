"""Tests for bricks.ai.composer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bricks.ai.composer import ComposerError, SequenceComposer
from bricks.core.brick import brick
from bricks.core.registry import BrickRegistry


def _make_registry() -> BrickRegistry:
    reg = BrickRegistry()

    @brick(tags=["math"], description="Add two numbers")
    def add(a: float, b: float) -> float:
        return a + b

    reg.register("add", add, add.__brick_meta__)
    return reg


class TestComposerInit:
    def test_raises_import_error_when_anthropic_missing(self) -> None:
        """ComposerError wraps ImportError when anthropic is not installed."""
        reg = _make_registry()
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises(ImportError, match="anthropic"):
                SequenceComposer(registry=reg, api_key="test_key")


class TestComposerCompose:
    def _make_mock_response(self, yaml_content: str) -> MagicMock:
        """Build a mock Anthropic response containing the given YAML."""
        block = MagicMock()
        block.text = f"```yaml\n{yaml_content}\n```"
        response = MagicMock()
        response.content = [block]
        return response

    def _make_composer(self, registry: BrickRegistry) -> SequenceComposer:
        """Create a SequenceComposer with a mocked Anthropic client."""
        mock_client = MagicMock()
        composer = SequenceComposer.__new__(SequenceComposer)
        composer._registry = registry
        composer._model = "claude-3-5-haiku-latest"
        composer._max_tokens = 4096
        composer._client = mock_client
        from bricks.core.loader import SequenceLoader

        composer._loader = SequenceLoader()
        return composer

    def test_compose_valid_yaml(self) -> None:
        """A valid YAML response should produce a SequenceDefinition."""
        reg = _make_registry()
        composer = self._make_composer(reg)

        valid_yaml = """
name: add_sequence
description: "Adds two numbers"
inputs:
  a: "float"
  b: "float"
steps:
  - name: add_step
    brick: add
    params:
      a: "${inputs.a}"
      b: "${inputs.b}"
    save_as: result
outputs_map:
  sum: "${result}"
"""
        mock_response = self._make_mock_response(valid_yaml)
        composer._client.messages.create.return_value = mock_response

        sequence = composer.compose("Add two numbers a and b")

        assert sequence.name == "add_sequence"
        assert len(sequence.steps) == 1
        assert sequence.steps[0].brick == "add"

    def test_compose_invalid_yaml_raises_composer_error(self) -> None:
        """Invalid YAML in response raises ComposerError."""
        reg = _make_registry()
        composer = self._make_composer(reg)

        block = MagicMock()
        block.text = "```yaml\nnot: valid: yaml: [unclosed\n```"
        mock_response = MagicMock()
        mock_response.content = [block]
        composer._client.messages.create.return_value = mock_response

        with pytest.raises(ComposerError):
            composer.compose("something")

    def test_compose_api_error_raises_composer_error(self) -> None:
        """API exceptions are wrapped as ComposerError."""
        reg = _make_registry()
        composer = self._make_composer(reg)
        composer._client.messages.create.side_effect = RuntimeError("network error")

        with pytest.raises(ComposerError, match="API call failed"):
            composer.compose("something")

    def test_compose_no_text_block_raises_composer_error(self) -> None:
        """A response with no text block raises ComposerError."""
        reg = _make_registry()
        composer = self._make_composer(reg)

        block = MagicMock(spec=[])  # no 'text' attribute
        mock_response = MagicMock()
        mock_response.content = [block]
        composer._client.messages.create.return_value = mock_response

        with pytest.raises(ComposerError, match="no text block"):
            composer.compose("something")

    def test_compose_empty_content_list_raises_composer_error(self) -> None:
        """A response with an empty content list raises ComposerError."""
        reg = _make_registry()
        composer = self._make_composer(reg)

        mock_response = MagicMock()
        mock_response.content = []
        composer._client.messages.create.return_value = mock_response

        with pytest.raises(ComposerError, match="no text block"):
            composer.compose("something")


class TestExtractYaml:
    def _make_bare_composer(self) -> SequenceComposer:
        """Create a SequenceComposer with mocked internals for unit testing."""
        reg = BrickRegistry()
        composer = SequenceComposer.__new__(SequenceComposer)
        composer._registry = reg
        composer._model = "test"
        composer._max_tokens = 1024
        composer._client = MagicMock()
        from bricks.core.loader import SequenceLoader

        composer._loader = SequenceLoader()
        return composer

    def test_extracts_yaml_block(self) -> None:
        composer = self._make_bare_composer()
        text = "Some preamble.\n```yaml\nname: foo\n```\nSome postamble."
        result = composer._extract_yaml(text)
        assert result == "name: foo"

    def test_extracts_plain_code_block(self) -> None:
        composer = self._make_bare_composer()
        text = "```\nname: bar\n```"
        result = composer._extract_yaml(text)
        assert result == "name: bar"

    def test_falls_back_to_raw_text(self) -> None:
        composer = self._make_bare_composer()
        text = "name: baz\ndescription: test"
        result = composer._extract_yaml(text)
        assert result == text

    def test_strips_whitespace_in_block(self) -> None:
        composer = self._make_bare_composer()
        text = "```yaml\n\n  name: foo\n\n```"
        result = composer._extract_yaml(text)
        assert result == "name: foo"

    def test_strips_whitespace_in_fallback(self) -> None:
        composer = self._make_bare_composer()
        text = "  name: baz  "
        result = composer._extract_yaml(text)
        assert result == "name: baz"


class TestBuildBricksContext:
    def test_builds_context_with_registered_bricks(self) -> None:
        """_build_bricks_context returns a list with brick info."""
        reg = _make_registry()
        composer = SequenceComposer.__new__(SequenceComposer)
        composer._registry = reg
        composer._model = "test"
        composer._max_tokens = 1024
        composer._client = MagicMock()
        from bricks.core.loader import SequenceLoader

        composer._loader = SequenceLoader()

        context = composer._build_bricks_context()

        assert len(context) == 1
        assert context[0]["name"] == "add"
        assert "description" in context[0]
        assert "tags" in context[0]
        assert "parameters" in context[0]
        # Should not include extra keys like 'destructive' or 'idempotent'
        assert "destructive" not in context[0]
        assert "idempotent" not in context[0]

    def test_builds_empty_context_for_empty_registry(self) -> None:
        """_build_bricks_context returns an empty list for an empty registry."""
        reg = BrickRegistry()
        composer = SequenceComposer.__new__(SequenceComposer)
        composer._registry = reg
        composer._model = "test"
        composer._max_tokens = 1024
        composer._client = MagicMock()
        from bricks.core.loader import SequenceLoader

        composer._loader = SequenceLoader()

        context = composer._build_bricks_context()
        assert context == []


class TestComposerError:
    def test_error_message(self) -> None:
        err = ComposerError("Something went wrong", cause=ValueError("bad"))
        assert "Something went wrong" in str(err)
        assert isinstance(err.cause, ValueError)

    def test_error_without_cause(self) -> None:
        err = ComposerError("No cause")
        assert err.cause is None

    def test_is_brick_error(self) -> None:
        from bricks.core.exceptions import BrickError

        err = ComposerError("test")
        assert isinstance(err, BrickError)

    def test_cause_preserved(self) -> None:
        original = RuntimeError("original error")
        err = ComposerError("wrapper", cause=original)
        assert err.cause is original
