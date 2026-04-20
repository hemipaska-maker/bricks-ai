"""Tests for bricks.ai.composer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bricks.ai.composer import (
    _RETRY_PROMPT,
    BlueprintComposer,
    ComposerError,
    ComposeResult,
)
from bricks.core.registry import BrickRegistry
from bricks.llm.base import CompletionResult

# ── helpers ──────────────────────────────────────────────────────────────────

_VALID_DSL = """\
@flow
def add_numbers():
    result = step.add(a=3.0, b=4.0)
    return result
"""

_INVALID_DSL = """\
import os

@flow
def bad_flow():
    return step.add(a=1.0, b=2.0)
"""


def _make_composer(registry: BrickRegistry) -> BlueprintComposer:
    """Create a BlueprintComposer with a mocked LLMProvider."""
    from bricks.llm.base import LLMProvider

    composer = BlueprintComposer.__new__(BlueprintComposer)
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.complete.return_value = CompletionResult(text=_VALID_DSL)
    composer._provider = mock_provider
    from bricks.core.selector import AllBricksSelector

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
        assert result.dsl_code == ""
        assert result.is_valid is False
        assert result.validation_errors == []
        assert result.api_calls == 0
        assert result.total_tokens == 0

    def test_all_fields(self) -> None:
        """ComposeResult accepts all fields."""
        result = ComposeResult(
            task="calc",
            blueprint_yaml="name: test",
            dsl_code="@flow\ndef f(): return step.x()",
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
        assert result.dsl_code != ""


# ── BlueprintComposer.compose ────────────────────────────────────────────────


class TestComposerCompose:
    """Tests for BlueprintComposer.compose()."""

    def test_compose_valid_dsl_returns_compose_result(self, math_registry: BrickRegistry) -> None:
        """A valid DSL response returns ComposeResult with is_valid=True."""
        composer = _make_composer(math_registry)
        composer._provider.complete.return_value = CompletionResult(text=_VALID_DSL)

        result = composer.compose("Add 3 + 4", math_registry)

        assert isinstance(result, ComposeResult)
        assert result.is_valid is True
        assert result.api_calls == 1
        assert result.total_input_tokens == 0
        assert result.total_output_tokens == 0
        assert result.total_tokens == 0
        assert result.validation_errors == []

    def test_compose_retry_on_validation_failure(self, math_registry: BrickRegistry) -> None:
        """Invalid DSL triggers one retry; second call returns valid DSL."""
        composer = _make_composer(math_registry)
        composer._provider.complete.side_effect = [
            CompletionResult(text=_INVALID_DSL),
            CompletionResult(text=_VALID_DSL),
        ]

        result = composer.compose("Add numbers", math_registry)

        assert result.is_valid is True
        assert result.api_calls == 2
        assert result.total_input_tokens == 0
        assert result.total_output_tokens == 0
        assert result.total_tokens == 0

    def test_compose_max_two_calls_on_double_failure(self, math_registry: BrickRegistry) -> None:
        """If both calls fail validation, return is_valid=False with errors."""
        composer = _make_composer(math_registry)
        composer._provider.complete.side_effect = [
            CompletionResult(text=_INVALID_DSL),
            CompletionResult(text=_INVALID_DSL),
        ]

        result = composer.compose("Do something", math_registry)

        assert result.is_valid is False
        assert result.api_calls == 2
        assert len(result.validation_errors) > 0

    def test_compose_api_error_raises_composer_error(self, math_registry: BrickRegistry) -> None:
        """API exceptions are wrapped as ComposerError."""
        composer = _make_composer(math_registry)
        composer._provider.complete.side_effect = RuntimeError("network error")

        with pytest.raises(ComposerError, match="API call failed"):
            composer.compose("something", math_registry)

    def test_compose_empty_response_results_in_invalid(self, math_registry: BrickRegistry) -> None:
        """An empty string response from the provider results in is_valid=False."""
        composer = _make_composer(math_registry)
        composer._provider.complete.return_value = CompletionResult(text="")

        result = composer.compose("something", math_registry)
        assert result.is_valid is False

    def test_compose_strips_code_fences(self, math_registry: BrickRegistry) -> None:
        """Code fences around DSL are stripped before parsing."""
        composer = _make_composer(math_registry)
        fenced = f"```python\n{_VALID_DSL}\n```"
        composer._provider.complete.return_value = CompletionResult(text=fenced)

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

    def test_accepts_llm_provider(self) -> None:
        """BlueprintComposer accepts an LLMProvider instance."""
        from bricks.llm.base import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        composer = BlueprintComposer(provider=mock_provider)
        assert composer._provider is mock_provider


# ── Retry Prompt ──────────────────────────────────────────────────────────


class TestRetryPrompt:
    """Tests for the retry prompt template."""

    def test_retry_prompt_includes_task_placeholder(self) -> None:
        """_RETRY_PROMPT contains {task} placeholder."""
        assert "{task}" in _RETRY_PROMPT

    def test_retry_prompt_renders_with_task(self) -> None:
        """_RETRY_PROMPT formats correctly with task, code, and errors."""
        rendered = _RETRY_PROMPT.format(
            task="Calculate 3 + 4",
            code="@flow\ndef f(): pass",
            errors="- some error",
        )
        assert "Original task:" in rendered
        assert "Calculate 3 + 4" in rendered
        assert "- some error" in rendered


# ── Compose Populates Prompts ──────────────────────────────────────────────


class TestComposePopulatesPrompts:
    """Tests that compose() populates system_prompt and per-call prompts."""

    def test_compose_sets_system_prompt(self, math_registry: BrickRegistry) -> None:
        """compose() sets system_prompt on ComposeResult."""
        composer = _make_composer(math_registry)
        composer._provider.complete.return_value = CompletionResult(text=_VALID_DSL)
        result = composer.compose("Add 3 + 4", math_registry)
        assert result.system_prompt != ""
        assert "Blueprint composer" in result.system_prompt

    def test_compose_sets_call_detail_prompts(self, math_registry: BrickRegistry) -> None:
        """compose() sets system_prompt and user_prompt on each CallDetail."""
        composer = _make_composer(math_registry)
        composer._provider.complete.return_value = CompletionResult(text=_VALID_DSL)
        result = composer.compose("Add 3 + 4", math_registry)
        assert len(result.calls) == 1
        call = result.calls[0]
        assert call.system_prompt != ""
        assert call.user_prompt == "Add 3 + 4"

    def test_retry_call_has_task_in_user_prompt(self, math_registry: BrickRegistry) -> None:
        """On retry, the second call's user_prompt includes the original task."""
        composer = _make_composer(math_registry)
        composer._provider.complete.side_effect = [
            CompletionResult(text=_INVALID_DSL),
            CompletionResult(text=_VALID_DSL),
        ]
        result = composer.compose("Add numbers", math_registry)
        assert result.api_calls == 2
        retry_call = result.calls[1]
        assert "Original task:" in retry_call.user_prompt
        assert "Add numbers" in retry_call.user_prompt


# ── flow_def preservation ──────────────────────────────────────────────────


class TestComposeResultFlowDef:
    """Tests that ComposeResult.flow_def is correctly populated."""

    def test_compose_result_preserves_flow_def(self, math_registry: BrickRegistry) -> None:
        """compose() populates flow_def with a FlowDefinition when DSL is valid."""
        from bricks.core.dsl import FlowDefinition

        composer = _make_composer(math_registry)
        composer._provider.complete.return_value = CompletionResult(text=_VALID_DSL)
        result = composer.compose("Add 3 + 4", math_registry)
        assert result.flow_def is not None
        assert isinstance(result.flow_def, FlowDefinition)

    def test_compose_result_blueprint_yaml_still_populated(self, math_registry: BrickRegistry) -> None:
        """compose() still populates blueprint_yaml (no regression for web GUI)."""
        composer = _make_composer(math_registry)
        composer._provider.complete.return_value = CompletionResult(text=_VALID_DSL)
        result = composer.compose("Add 3 + 4", math_registry)
        assert result.blueprint_yaml != ""

    def test_compose_result_flow_def_none_on_invalid_dsl(self, math_registry: BrickRegistry) -> None:
        """compose() sets flow_def to None when DSL is invalid."""
        composer = _make_composer(math_registry)
        composer._provider.complete.side_effect = [
            CompletionResult(text=_INVALID_DSL),
            CompletionResult(text=_INVALID_DSL),
        ]
        result = composer.compose("task", math_registry)
        assert result.is_valid is False
        assert result.flow_def is None

    def test_compose_result_flow_def_excluded_from_model_dump(self, math_registry: BrickRegistry) -> None:
        """ComposeResult.model_dump() must NOT include flow_def (exclude=True required).

        Without exclude=True, model_dump() on a ComposeResult with a live
        FlowDefinition raises a serialization error.
        """
        from bricks.core.dsl import FlowDefinition

        composer = _make_composer(math_registry)
        composer._provider.complete.return_value = CompletionResult(text=_VALID_DSL)
        result = composer.compose("Add 3 + 4", math_registry)

        # flow_def must be set (sanity check)
        assert isinstance(result.flow_def, FlowDefinition)

        # model_dump() must succeed AND not include flow_def
        dumped = result.model_dump()
        assert "flow_def" not in dumped, "flow_def must be excluded from model_dump()"

    def test_compose_result_flow_def_is_populated_after_valid_compose(self, math_registry: BrickRegistry) -> None:
        """compose() with a valid DSL string populates flow_def with a FlowDefinition.

        This is an integration test using a test double that returns pre-written
        DSL — no LLM call is made.
        """
        from bricks.core.dsl import FlowDefinition

        composer = _make_composer(math_registry)
        composer._provider.complete.return_value = CompletionResult(text=_VALID_DSL)
        result = composer.compose("Add numbers", math_registry)

        assert result.is_valid is True
        assert result.flow_def is not None
        assert isinstance(result.flow_def, FlowDefinition)
        assert result.flow_def.name  # must have a name derived from function name


class TestDSLPromptTemplate:
    """Tests for DSL_PROMPT_TEMPLATE content (Mission 077)."""

    def test_prompt_contains_data_flow_contract(self) -> None:
        """DSL_PROMPT_TEMPLATE includes the data flow contract block."""
        from bricks.ai.composer import DSL_PROMPT_TEMPLATE

        prompt = DSL_PROMPT_TEMPLATE.format(
            brick_signatures="add(a: float, b: float) → dict",
            task="test task",
            input_context="",
        )
        assert "every brick returns a dict" in prompt.lower(), "Data flow contract missing from DSL_PROMPT_TEMPLATE"

    def test_prompt_contains_worked_example(self) -> None:
        """DSL_PROMPT_TEMPLATE includes the worked @flow example."""
        from bricks.ai.composer import DSL_PROMPT_TEMPLATE

        prompt = DSL_PROMPT_TEMPLATE.format(
            brick_signatures="add(a: float, b: float) → dict",
            task="test task",
            input_context="",
        )
        assert "crm_summary" in prompt, "Worked example missing from DSL_PROMPT_TEMPLATE"
        assert "do not copy it literally" in prompt, "Example instruction missing"
