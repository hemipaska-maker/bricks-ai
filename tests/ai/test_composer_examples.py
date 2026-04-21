"""Regression tests for the worked examples baked into DSL_PROMPT_TEMPLATE.

The examples are part of the system prompt — if they contain invalid DSL the
LLM will be trained on a broken pattern and cascade the bug into generated
blueprints. These tests guarantee every `@flow` block in the template parses
through :func:`bricks.core.validator_dsl.validate_dsl` and exercises its
stated pattern.
"""

from __future__ import annotations

import ast

import pytest

from bricks.ai.composer import DSL_PROMPT_TEMPLATE
from bricks.core.validator_dsl import validate_dsl


def _extract_examples(template: str) -> list[str]:
    """Return every ``@flow`` function literal found in *template*.

    Splits the template on the ``@flow`` marker, then for each chunk takes
    lines until the block dedents back to column 0 — giving the full
    function text including multi-line returns.

    The template uses doubled braces for ``.format`` escaping; the examples
    themselves contain literal ``{{`` / ``}}`` pairs that must be unescaped
    before the DSL validator will accept them.
    """
    rendered = template.replace("{{", "{").replace("}}", "}")
    parts = rendered.split("@flow\n")[1:]  # drop preamble
    examples: list[str] = []
    for part in parts:
        lines = part.splitlines()
        # A real example starts with ``def <name>(...)`` on the very next line.
        # Rule-body mentions of ``@flow`` (e.g. "decorated with @flow") are
        # skipped here.
        if not lines or not lines[0].lstrip().startswith("def "):
            continue
        collected = ["@flow"]
        for line in lines:
            if not line.strip():
                break
            if collected[-1] != "@flow" and not line.startswith((" ", "\t")):
                break
            collected.append(line)
        examples.append("\n".join(collected).rstrip())
    return examples


def _brick_calls(code: str) -> set[str]:
    """Return the set of ``step.<name>`` and primitive calls in *code*."""
    tree = ast.parse(code)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "step":
            names.add(f"step.{node.attr}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def test_template_has_three_examples() -> None:
    """The prompt must ship exactly three worked examples (A, B, C)."""
    examples = _extract_examples(DSL_PROMPT_TEMPLATE)
    assert len(examples) == 3, f"expected 3 examples, found {len(examples)}"


@pytest.mark.parametrize("idx", [0, 1, 2])
def test_each_example_passes_ast_validator(idx: int) -> None:
    """Each embedded example must satisfy validate_dsl — otherwise we are
    teaching the LLM to emit code the composer will reject."""
    examples = _extract_examples(DSL_PROMPT_TEMPLATE)
    code = examples[idx]
    result = validate_dsl(code)
    assert result.valid, f"example #{idx + 1} failed validation: {result.errors}\ncode:\n{code}"


def test_example_a_uses_extract_dict_field() -> None:
    """Example A teaches the unwrap-before-filter pattern (issue #28)."""
    code = _extract_examples(DSL_PROMPT_TEMPLATE)[0]
    calls = _brick_calls(code)
    assert "step.extract_dict_field" in calls, (
        "example A must demonstrate extract_dict_field unwrap so the LLM "
        "learns not to pass a wrapper dict directly to filter_dict_list"
    )
    assert "step.filter_dict_list" in calls


def test_example_b_uses_for_each_and_reduce_sum_list() -> None:
    """Example B teaches for_each + list-of-Node reduce_sum (issue #28)."""
    code = _extract_examples(DSL_PROMPT_TEMPLATE)[1]
    calls = _brick_calls(code)
    assert "for_each" in calls
    assert "step.reduce_sum" in calls
    # reduce_sum must be called with a list kwarg so the pattern is exercised.
    tree = ast.parse(code)
    reduce_calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "reduce_sum"
    ]
    assert reduce_calls, "reduce_sum call not found"
    values_kw = next((kw for kw in reduce_calls[0].keywords if kw.arg == "values"), None)
    assert values_kw is not None, "reduce_sum must be called with values= kwarg"
    assert isinstance(values_kw.value, ast.List), "values= must be a list literal so the list-of-Node pattern is taught"


def test_example_c_uses_branch() -> None:
    """Example C teaches branch routing (issue #28)."""
    code = _extract_examples(DSL_PROMPT_TEMPLATE)[2]
    calls = _brick_calls(code)
    assert "branch" in calls
