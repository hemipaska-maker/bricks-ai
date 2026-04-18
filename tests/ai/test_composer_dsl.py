"""Tests for BlueprintComposer DSL generation pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bricks.ai.composer import (
    BlueprintComposer,
    ComposeResult,
    CompositionError,
)
from bricks.core.registry import BrickRegistry
from bricks.llm.base import CompletionResult, LLMProvider

# ---------------------------------------------------------------------------
# DSL fixtures
# ---------------------------------------------------------------------------

_SIMPLE_DSL = """\
@flow
def add_numbers():
    result = step.add(a=3.0, b=4.0)
    return result
"""

_FOR_EACH_DSL = """\
@flow
def process_items(items):
    cleaned = for_each(items, do=lambda x: step.add(a=x, b=0.0))
    return cleaned
"""

_BRANCH_DSL = """\
@flow
def conditional_flow():
    result = branch("add", if_true=lambda: step.add(a=1.0, b=2.0), if_false=lambda: step.multiply(a=1.0, b=2.0))
    return result
"""

_MULTI_STEP_DSL = """\
@flow
def five_step_flow():
    a = step.add(a=1.0, b=2.0)
    b = step.multiply(a=3.0, b=4.0)
    c = step.add(a=5.0, b=6.0)
    d = step.multiply(a=7.0, b=8.0)
    e = step.add(a=9.0, b=10.0)
    return e
"""

_INVALID_DSL_IMPORT = """\
import os

@flow
def bad_flow():
    return step.add(a=1.0, b=2.0)
"""

_NO_FLOW_DSL = """\
def plain_function():
    return step.add(a=1.0, b=2.0)
"""

_FENCED_DSL = f"```python\n{_SIMPLE_DSL}\n```"


# ---------------------------------------------------------------------------
# Mock provider helpers
# ---------------------------------------------------------------------------


def _make_composer(registry: BrickRegistry, response: str = _SIMPLE_DSL) -> BlueprintComposer:
    """Create a BlueprintComposer backed by a mock LLM provider."""
    composer = BlueprintComposer.__new__(BlueprintComposer)
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.complete.return_value = CompletionResult(text=response, input_tokens=10, output_tokens=20)
    composer._provider = mock_provider
    from bricks.core.selector import AllBricksSelector

    composer._selector = AllBricksSelector()
    composer._store = None
    return composer


# ---------------------------------------------------------------------------
# Test: compose() → ComposeResult
# ---------------------------------------------------------------------------


def test_compose_valid_dsl_returns_blueprint(math_registry: BrickRegistry) -> None:
    """Mock LLM returns valid DSL — compose() returns ComposeResult with BlueprintDefinition."""
    composer = _make_composer(math_registry)
    result = composer.compose("Add 3 + 4", math_registry)

    assert isinstance(result, ComposeResult)
    assert result.is_valid is True


def test_compose_result_has_dsl_code(math_registry: BrickRegistry) -> None:
    """ComposeResult.dsl_code contains the generated (stripped) DSL code."""
    composer = _make_composer(math_registry)
    result = composer.compose("Add numbers", math_registry)

    assert result.dsl_code != ""
    assert "@flow" in result.dsl_code


def test_compose_result_has_blueprint_yaml(math_registry: BrickRegistry) -> None:
    """ComposeResult.blueprint_yaml is populated (backwards compat)."""
    composer = _make_composer(math_registry)
    result = composer.compose("Add numbers", math_registry)

    assert result.blueprint_yaml != ""
    import yaml as _yaml

    loaded = _yaml.safe_load(result.blueprint_yaml)
    assert isinstance(loaded, dict)


def test_compose_strips_markdown_fences(math_registry: BrickRegistry) -> None:
    """LLM wraps code in ```python...```, parser handles it transparently."""
    composer = _make_composer(math_registry, response=_FENCED_DSL)
    result = composer.compose("Add numbers", math_registry)

    assert result.is_valid is True
    assert "```" not in result.dsl_code


def test_compose_rejects_invalid_dsl(math_registry: BrickRegistry) -> None:
    """Mock LLM returns code with 'import os' — compose() marks is_valid=False."""
    composer = _make_composer(math_registry, response=_INVALID_DSL_IMPORT)
    # Force both calls to return invalid DSL so we never retry to valid
    composer._provider.complete.return_value = CompletionResult(text=_INVALID_DSL_IMPORT)

    result = composer.compose("bad task", math_registry)

    assert result.is_valid is False
    assert len(result.validation_errors) > 0


def test_compose_rejects_no_flow_function(math_registry: BrickRegistry) -> None:
    """Mock LLM returns code without @flow — compose() marks is_valid=False."""
    composer = _make_composer(math_registry, response=_NO_FLOW_DSL)
    composer._provider.complete.return_value = CompletionResult(text=_NO_FLOW_DSL)

    result = composer.compose("no flow", math_registry)

    assert result.is_valid is False
    assert any("@flow" in e or "flow" in e.lower() for e in result.validation_errors)


def test_compose_prompt_includes_brick_signatures(math_registry: BrickRegistry) -> None:
    """The prompt sent to LLM contains available brick names."""
    composer = _make_composer(math_registry)
    result = composer.compose("Add numbers", math_registry)

    assert result.system_prompt != ""
    # math_registry has 'add' and 'multiply' bricks
    assert "add" in result.system_prompt


def test_compose_prompt_includes_task(math_registry: BrickRegistry) -> None:
    """The prompt contains the user's task description."""
    composer = _make_composer(math_registry)
    result = composer.compose("Multiply large numbers together", math_registry)

    assert result.system_prompt != ""
    assert "Multiply large numbers together" in result.system_prompt


def test_compose_with_for_each(math_registry: BrickRegistry) -> None:
    """Mock LLM returns DSL with for_each — produces a valid ComposeResult."""
    composer = _make_composer(math_registry, response=_FOR_EACH_DSL)
    result = composer.compose("Process a list of items", math_registry)

    assert result.is_valid is True
    assert result.blueprint_yaml != ""


def test_compose_with_branch(math_registry: BrickRegistry) -> None:
    """Mock LLM returns DSL with branch — produces a valid ComposeResult."""
    composer = _make_composer(math_registry, response=_BRANCH_DSL)
    result = composer.compose("Route conditionally", math_registry)

    assert result.is_valid is True
    assert result.blueprint_yaml != ""


def test_compose_multi_step(math_registry: BrickRegistry) -> None:
    """5-step DSL composes correctly into a valid ComposeResult."""
    composer = _make_composer(math_registry, response=_MULTI_STEP_DSL)
    result = composer.compose("Run a 5-step pipeline", math_registry)

    assert result.is_valid is True
    assert result.blueprint_yaml != ""


def test_compose_tracks_tokens(math_registry: BrickRegistry) -> None:
    """ComposeResult has token counts from the LLM call."""
    composer = _make_composer(math_registry)
    # Provider returns 10 input + 20 output tokens
    result = composer.compose("Add numbers", math_registry)

    assert result.total_input_tokens == 10
    assert result.total_output_tokens == 20
    assert result.total_tokens == 30


def test_compose_error_includes_code_in_message(math_registry: BrickRegistry) -> None:
    """_parse_dsl_response raises CompositionError containing the bad code."""
    composer = _make_composer(math_registry)

    with pytest.raises(CompositionError) as exc_info:
        composer._parse_dsl_response(_INVALID_DSL_IMPORT)

    assert "import" in str(exc_info.value).lower() or "Import" in str(exc_info.value)
    assert _INVALID_DSL_IMPORT.strip()[:10] in str(exc_info.value) or "Code:" in str(exc_info.value)
