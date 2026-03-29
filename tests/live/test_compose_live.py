"""Live integration tests for BlueprintComposer using ClaudeCodeProvider.

Run with: pytest --live -m live
Skipped by default (no --live flag).
"""

from __future__ import annotations

import pytest
from bricks.ai.composer import BlueprintComposer
from bricks.core.registry import BrickRegistry
from bricks.llm.base import LLMProvider
from bricks_stdlib import register as _register_stdlib


@pytest.mark.live
def test_compose_returns_valid_yaml(llm_provider: LLMProvider) -> None:
    """compose() returns a valid blueprint YAML for a simple task."""
    registry = BrickRegistry()
    _register_stdlib(registry)
    composer = BlueprintComposer(provider=llm_provider)
    result = composer.compose("add two numbers a and b", registry)
    assert result.blueprint_yaml
    assert result.is_valid, f"Blueprint invalid: {result.validation_errors}"


@pytest.mark.live
def test_compose_uses_input_keys_hint(llm_provider: LLMProvider) -> None:
    """input_keys hint causes LLM to use the specified variable name."""
    registry = BrickRegistry()
    _register_stdlib(registry)
    composer = BlueprintComposer(provider=llm_provider)
    result = composer.compose(
        "convert a number to string",
        registry,
        input_keys=["my_number"],
    )
    assert result.is_valid
    assert "my_number" in result.blueprint_yaml
