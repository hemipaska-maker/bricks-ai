"""Tests for bricks.ai.composer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bricks.ai.composer import BlueprintComposer, ComposerError
from bricks.core.registry import BrickRegistry


class TestComposerInit:
    def test_raises_import_error_when_anthropic_missing(self, math_registry: BrickRegistry) -> None:
        """ComposerError wraps ImportError when anthropic is not installed."""
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            pytest.raises(ImportError, match="anthropic"),
        ):
            BlueprintComposer(registry=math_registry, api_key="test_key")


class TestComposerCompose:
    def _make_mock_response(self, yaml_content: str) -> MagicMock:
        """Build a mock Anthropic response containing the given YAML."""
        block = MagicMock()
        block.text = f"```yaml\n{yaml_content}\n```"
        response = MagicMock()
        response.content = [block]
        return response

    def _make_composer(self, registry: BrickRegistry) -> BlueprintComposer:
        """Create a BlueprintComposer with a mocked Anthropic client."""
        mock_client = MagicMock()
        composer = BlueprintComposer.__new__(BlueprintComposer)
        composer._registry = registry
        composer._model = "claude-haiku-4-5-20251001"
        composer._max_tokens = 4096
        composer._client = mock_client
        from bricks.core.loader import BlueprintLoader

        composer._loader = BlueprintLoader()
        return composer

    def test_compose_valid_yaml(self, math_registry: BrickRegistry) -> None:
        """A valid YAML response should produce a BlueprintDefinition."""
        composer = self._make_composer(math_registry)

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

        blueprint = composer.compose("Add two numbers a and b")

        assert blueprint.name == "add_sequence", f"Expected 'add_sequence', got {blueprint.name!r}"
        assert len(blueprint.steps) == 1, f"Expected length 1, got {len(blueprint.steps)}"
        assert blueprint.steps[0].brick == "add", f"Expected 'add', got {blueprint.steps[0].brick!r}"

    def test_compose_invalid_yaml_raises_composer_error(self, math_registry: BrickRegistry) -> None:
        """Invalid YAML in response raises ComposerError."""
        composer = self._make_composer(math_registry)

        block = MagicMock()
        block.text = "```yaml\nnot: valid: yaml: [unclosed\n```"
        mock_response = MagicMock()
        mock_response.content = [block]
        composer._client.messages.create.return_value = mock_response

        with pytest.raises(ComposerError):
            composer.compose("something")

    def test_compose_api_error_raises_composer_error(self, math_registry: BrickRegistry) -> None:
        """API exceptions are wrapped as ComposerError."""
        composer = self._make_composer(math_registry)
        composer._client.messages.create.side_effect = RuntimeError("network error")

        with pytest.raises(ComposerError, match="API call failed"):
            composer.compose("something")

    def test_compose_no_text_block_raises_composer_error(self, math_registry: BrickRegistry) -> None:
        """A response with no text block raises ComposerError."""
        composer = self._make_composer(math_registry)

        block = MagicMock(spec=[])  # no 'text' attribute
        mock_response = MagicMock()
        mock_response.content = [block]
        composer._client.messages.create.return_value = mock_response

        with pytest.raises(ComposerError, match="no text block"):
            composer.compose("something")

    def test_compose_empty_content_list_raises_composer_error(self, math_registry: BrickRegistry) -> None:
        """A response with an empty content list raises ComposerError."""
        composer = self._make_composer(math_registry)

        mock_response = MagicMock()
        mock_response.content = []
        composer._client.messages.create.return_value = mock_response

        with pytest.raises(ComposerError, match="no text block"):
            composer.compose("something")


class TestExtractYaml:
    def _make_bare_composer(self) -> BlueprintComposer:
        """Create a BlueprintComposer with mocked internals for unit testing."""
        reg = BrickRegistry()
        composer = BlueprintComposer.__new__(BlueprintComposer)
        composer._registry = reg
        composer._model = "test"
        composer._max_tokens = 1024
        composer._client = MagicMock()
        from bricks.core.loader import BlueprintLoader

        composer._loader = BlueprintLoader()
        return composer

    def test_extracts_yaml_block(self) -> None:
        composer = self._make_bare_composer()
        text = "Some preamble.\n```yaml\nname: foo\n```\nSome postamble."
        result = composer._extract_yaml(text)
        assert result == "name: foo", f"Expected 'name: foo', got {result!r}"

    def test_extracts_plain_code_block(self) -> None:
        composer = self._make_bare_composer()
        text = "```\nname: bar\n```"
        result = composer._extract_yaml(text)
        assert result == "name: bar", f"Expected 'name: bar', got {result!r}"

    def test_falls_back_to_raw_text(self) -> None:
        composer = self._make_bare_composer()
        text = "name: baz\ndescription: test"
        result = composer._extract_yaml(text)
        assert result == text, f"Expected {text!r}, got {result!r}"

    def test_strips_whitespace_in_block(self) -> None:
        composer = self._make_bare_composer()
        text = "```yaml\n\n  name: foo\n\n```"
        result = composer._extract_yaml(text)
        assert result == "name: foo", f"Expected 'name: foo', got {result!r}"

    def test_strips_whitespace_in_fallback(self) -> None:
        composer = self._make_bare_composer()
        text = "  name: baz  "
        result = composer._extract_yaml(text)
        assert result == "name: baz", f"Expected 'name: baz', got {result!r}"


class TestBuildBricksContext:
    def test_builds_context_with_registered_bricks(self, math_registry: BrickRegistry) -> None:
        """_build_bricks_context returns a list with brick info."""
        composer = BlueprintComposer.__new__(BlueprintComposer)
        composer._registry = math_registry
        composer._model = "test"
        composer._max_tokens = 1024
        composer._client = MagicMock()
        from bricks.core.loader import BlueprintLoader

        composer._loader = BlueprintLoader()

        context = composer._build_bricks_context()

        assert len(context) == 2, f"Expected length 2, got {len(context)}"
        names = [c["name"] for c in context]
        assert "add" in names, "Expected 'add' to be in collection"
        assert "description" in context[0], "Expected 'description' key in context"
        assert "tags" in context[0], "Expected 'tags' key in context"
        assert "parameters" in context[0], "Expected 'parameters' key in context"
        # Should not include extra keys like 'destructive' or 'idempotent'
        assert "destructive" not in context[0], "Expected 'destructive' not to be in context"
        assert "idempotent" not in context[0], "Expected 'idempotent' not to be in context"

    def test_builds_empty_context_for_empty_registry(self) -> None:
        """_build_bricks_context returns an empty list for an empty registry."""
        reg = BrickRegistry()
        composer = BlueprintComposer.__new__(BlueprintComposer)
        composer._registry = reg
        composer._model = "test"
        composer._max_tokens = 1024
        composer._client = MagicMock()
        from bricks.core.loader import BlueprintLoader

        composer._loader = BlueprintLoader()

        context = composer._build_bricks_context()
        assert context == [], f"Expected [], got {context!r}"


class TestComposerError:
    def test_error_message(self) -> None:
        err = ComposerError("Something went wrong", cause=ValueError("bad"))
        assert "Something went wrong" in str(err), f"Expected 'Something went wrong' in {str(err)!r}"
        assert isinstance(err.cause, ValueError), f"Expected ValueError, got {type(err.cause).__name__}"

    def test_error_without_cause(self) -> None:
        err = ComposerError("No cause")
        assert err.cause is None, f"Expected None, got {err.cause!r}"

    def test_is_brick_error(self) -> None:
        from bricks.core.exceptions import BrickError

        err = ComposerError("test")
        assert isinstance(err, BrickError), f"Expected BrickError, got {type(err).__name__}"

    def test_cause_preserved(self) -> None:
        original = RuntimeError("original error")
        err = ComposerError("wrapper", cause=original)
        assert err.cause is original, "Expected cause to be the original exception"
