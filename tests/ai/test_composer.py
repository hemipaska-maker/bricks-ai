"""Tests for bricks.ai.composer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bricks.ai.composer import (
    _RETRY_PROMPT,
    BlueprintComposer,
    ComposerError,
    ComposeResult,
    _build_example,
)
from bricks.core.registry import BrickRegistry

# ── helpers ──────────────────────────────────────────────────────────────────

_VALID_YAML = """\
name: add_two
steps:
  - name: add_step
    brick: add
    params:
      a: 3.0
      b: 4.0
    save_as: result
outputs_map:
  sum: "${result.result}"
"""

_INVALID_YAML = """\
name: bad
steps:
  - name: step1
    brick: nonexistent
    params:
      a: 1.0
    save_as: r1
outputs_map:
  result: "${r1.result}"
"""


def _make_mock_response(text: str, in_tok: int = 100, out_tok: int = 50) -> MagicMock:
    """Build a mock Anthropic response with the given text."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.usage.input_tokens = in_tok
    resp.usage.output_tokens = out_tok
    return resp


def _make_composer(registry: BrickRegistry) -> BlueprintComposer:
    """Create a BlueprintComposer with a mocked Anthropic client."""
    composer = BlueprintComposer.__new__(BlueprintComposer)
    composer._client = MagicMock()
    composer._model = "claude-haiku-4-5-20251001"
    from bricks.core.loader import BlueprintLoader
    from bricks.core.selector import AllBricksSelector

    composer._loader = BlueprintLoader()
    composer._selector = AllBricksSelector()
    composer._store = None
    return composer


# ── ComposeResult model ──────────────────────────────────────────────────────


class TestComposeResult:
    """Tests for ComposeResult Pydantic model."""

    def test_default_fields(self) -> None:
        """ComposeResult has sensible defaults."""
        result = ComposeResult(task="test")
        assert result.task == "test"
        assert result.blueprint_yaml == ""
        assert result.is_valid is False
        assert result.validation_errors == []
        assert result.api_calls == 0
        assert result.total_tokens == 0

    def test_all_fields(self) -> None:
        """ComposeResult accepts all fields."""
        result = ComposeResult(
            task="calc",
            blueprint_yaml="name: test",
            is_valid=True,
            validation_errors=[],
            api_calls=1,
            total_input_tokens=100,
            total_output_tokens=50,
            total_tokens=150,
            model="claude-haiku-4-5-20251001",
            duration_seconds=1.5,
        )
        assert result.is_valid is True
        assert result.api_calls == 1
        assert result.total_tokens == 150


# ── BlueprintComposer.compose ────────────────────────────────────────────────


class TestComposerCompose:
    """Tests for BlueprintComposer.compose()."""

    def test_compose_valid_yaml_returns_compose_result(self, math_registry: BrickRegistry) -> None:
        """A valid YAML response returns ComposeResult with is_valid=True."""
        composer = _make_composer(math_registry)
        composer._client.messages.create.return_value = _make_mock_response(_VALID_YAML)

        result = composer.compose("Add 3 + 4", math_registry)

        assert isinstance(result, ComposeResult)
        assert result.is_valid is True
        assert result.api_calls == 1
        assert result.total_input_tokens == 100
        assert result.total_output_tokens == 50
        assert result.total_tokens == 150
        assert result.validation_errors == []

    def test_compose_retry_on_validation_failure(self, math_registry: BrickRegistry) -> None:
        """Invalid YAML triggers one retry; second call returns valid YAML."""
        composer = _make_composer(math_registry)
        composer._client.messages.create.side_effect = [
            _make_mock_response(_INVALID_YAML, in_tok=100, out_tok=50),
            _make_mock_response(_VALID_YAML, in_tok=120, out_tok=60),
        ]

        result = composer.compose("Add numbers", math_registry)

        assert result.is_valid is True
        assert result.api_calls == 2
        assert result.total_input_tokens == 220
        assert result.total_output_tokens == 110
        assert result.total_tokens == 330

    def test_compose_max_two_calls_on_double_failure(self, math_registry: BrickRegistry) -> None:
        """If both calls fail validation, return is_valid=False with errors."""
        composer = _make_composer(math_registry)
        composer._client.messages.create.side_effect = [
            _make_mock_response(_INVALID_YAML),
            _make_mock_response(_INVALID_YAML),
        ]

        result = composer.compose("Do something", math_registry)

        assert result.is_valid is False
        assert result.api_calls == 2
        assert len(result.validation_errors) > 0

    def test_compose_api_error_raises_composer_error(self, math_registry: BrickRegistry) -> None:
        """API exceptions are wrapped as ComposerError."""
        composer = _make_composer(math_registry)
        composer._client.messages.create.side_effect = RuntimeError("network error")

        with pytest.raises(ComposerError, match="API call failed"):
            composer.compose("something", math_registry)

    def test_compose_no_text_block_raises_composer_error(self, math_registry: BrickRegistry) -> None:
        """A response with no text block raises ComposerError."""
        composer = _make_composer(math_registry)
        block = MagicMock(spec=[])  # no 'text' attribute
        resp = MagicMock()
        resp.content = [block]
        resp.usage.input_tokens = 10
        resp.usage.output_tokens = 5
        composer._client.messages.create.return_value = resp

        with pytest.raises(ComposerError, match="no text block"):
            composer.compose("something", math_registry)

    def test_compose_strips_code_fences(self, math_registry: BrickRegistry) -> None:
        """Code fences around YAML are stripped before parsing."""
        composer = _make_composer(math_registry)
        fenced = f"```yaml\n{_VALID_YAML}\n```"
        composer._client.messages.create.return_value = _make_mock_response(fenced)

        result = composer.compose("Add numbers", math_registry)
        assert result.is_valid is True


# ── ComposerError ────────────────────────────────────────────────────────────


class TestComposerError:
    """Tests for ComposerError exception."""

    def test_error_message(self) -> None:
        """ComposerError preserves message and cause."""
        err = ComposerError("Something went wrong", cause=ValueError("bad"))
        assert "Something went wrong" in str(err)
        assert isinstance(err.cause, ValueError)

    def test_error_without_cause(self) -> None:
        """ComposerError works without a cause."""
        err = ComposerError("No cause")
        assert err.cause is None

    def test_is_brick_error(self) -> None:
        """ComposerError inherits from BrickError."""
        from bricks.core.exceptions import BrickError

        err = ComposerError("test")
        assert isinstance(err, BrickError)


# ── Init ─────────────────────────────────────────────────────────────────────


class TestComposerInit:
    """Tests for BlueprintComposer initialization."""

    def test_raises_import_error_when_anthropic_missing(self) -> None:
        """ImportError raised when anthropic is not installed."""
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            pytest.raises(ImportError, match="anthropic"),
        ):
            BlueprintComposer(api_key="test_key")


# ── Retry Prompt ──────────────────────────────────────────────────────────


class TestRetryPrompt:
    """Tests for the retry prompt template."""

    def test_retry_prompt_includes_task_placeholder(self) -> None:
        """_RETRY_PROMPT contains {task} placeholder."""
        assert "{task}" in _RETRY_PROMPT

    def test_retry_prompt_renders_with_task(self) -> None:
        """_RETRY_PROMPT formats correctly with task, yaml, and errors."""
        rendered = _RETRY_PROMPT.format(
            task="Calculate 3 + 4",
            yaml="name: test",
            errors="- some error",
        )
        assert "Original task:" in rendered
        assert "Calculate 3 + 4" in rendered
        assert "name: test" in rendered
        assert "- some error" in rendered


# ── Build Example ─────────────────────────────────────────────────────────


class TestBuildExample:
    """Tests for _build_example() worked example generation."""

    def test_example_includes_inputs_section(self, math_registry: BrickRegistry) -> None:
        """_build_example() output includes an inputs: section."""
        example = _build_example(math_registry)
        assert "inputs:" in example

    def test_example_includes_inputs_references(self, math_registry: BrickRegistry) -> None:
        """_build_example() output uses ${inputs.X} references in params."""
        example = _build_example(math_registry)
        assert "${inputs." in example

    def test_example_empty_for_single_brick(self) -> None:
        """_build_example() returns empty string for registry with < 2 bricks."""
        from bricks.core.models import BrickMeta

        reg = BrickRegistry()
        reg.register("only", lambda: None, BrickMeta(name="only"))
        assert _build_example(reg) == ""


# ── Compose Populates Prompts ──────────────────────────────────────────────


class TestComposePopulatesPrompts:
    """Tests that compose() populates system_prompt and per-call prompts."""

    def test_compose_sets_system_prompt(self, math_registry: BrickRegistry) -> None:
        """compose() sets system_prompt on ComposeResult."""
        composer = _make_composer(math_registry)
        composer._client.messages.create.return_value = _make_mock_response(_VALID_YAML)
        result = composer.compose("Add 3 + 4", math_registry)
        assert result.system_prompt != ""
        assert "Blueprint composer" in result.system_prompt

    def test_compose_sets_call_detail_prompts(self, math_registry: BrickRegistry) -> None:
        """compose() sets system_prompt and user_prompt on each CallDetail."""
        composer = _make_composer(math_registry)
        composer._client.messages.create.return_value = _make_mock_response(_VALID_YAML)
        result = composer.compose("Add 3 + 4", math_registry)
        assert len(result.calls) == 1
        call = result.calls[0]
        assert call.system_prompt != ""
        assert call.user_prompt == "Add 3 + 4"

    def test_retry_call_has_task_in_user_prompt(self, math_registry: BrickRegistry) -> None:
        """On retry, the second call's user_prompt includes the original task."""
        composer = _make_composer(math_registry)
        composer._client.messages.create.side_effect = [
            _make_mock_response(_INVALID_YAML),
            _make_mock_response(_VALID_YAML),
        ]
        result = composer.compose("Add numbers", math_registry)
        assert result.api_calls == 2
        retry_call = result.calls[1]
        assert "Original task:" in retry_call.user_prompt
        assert "Add numbers" in retry_call.user_prompt
