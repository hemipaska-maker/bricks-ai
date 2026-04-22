"""Tests for issue #60 — composer must persist the raw LLM output on failure paths.

When the LLM emits DSL that fails AST validation or can't be parsed into a
``FlowDefinition``, callers need the offending text to triage without
paying for another compose (~$1.25 per live failure in the tracked
repro). This suite asserts the structured ``dsl_code`` / ``blueprint_yaml``
attributes flow through both paths.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from bricks.ai.composer import (
    BlueprintComposer,
    CallDetail,
    ComposeResult,
    CompositionError,
)
from bricks.core.selector import AllBricksSelector
from bricks.llm.base import CompletionResult, LLMProvider


def _make_composer(response_text: str) -> BlueprintComposer:
    """Build a composer whose provider always returns ``response_text``."""
    composer = BlueprintComposer.__new__(BlueprintComposer)
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.complete.return_value = CompletionResult(text=response_text, input_tokens=5, output_tokens=10)
    composer._provider = mock_provider
    composer._selector = AllBricksSelector()
    composer._store = None
    composer._explicit_healers = None
    composer._pm = None
    return composer


def test_composition_error_carries_dsl_code_attr() -> None:
    """``CompositionError.dsl_code`` exposes the offending LLM output
    as a structured attr so callers don't have to string-parse the
    message."""
    composer = _make_composer("unused")
    raw_bad_dsl = "@flow\ndef bad():\n    import os  # forbidden by validator\n"
    try:
        composer._parse_dsl_response(raw_bad_dsl)
    except CompositionError as exc:
        # dsl_code carries the post-fence-strip body. We don't care about
        # trailing whitespace — what matters is the identifying text is
        # present as a structured attr, not buried in the message.
        assert "import os" in exc.dsl_code, f"dsl_code not populated: {exc.dsl_code!r}"
        assert exc.dsl_code.strip() == raw_bad_dsl.strip()
        assert "LLM generated invalid DSL code" in str(exc)
        return
    raise AssertionError("expected CompositionError")


def test_composition_error_constructor_stores_both_structured_attrs() -> None:
    """The ``ComposerError`` / ``CompositionError`` public constructor
    exposes both attrs so a caller that catches one can always read them
    without hasattr guards."""
    err = CompositionError("no flow", dsl_code="x = 1", blueprint_yaml="name: x\n")
    assert err.dsl_code == "x = 1"
    assert err.blueprint_yaml == "name: x\n"
    # Default is empty string when not provided — not None — so downstream
    # branches like ``raw_response = exc.blueprint_yaml`` don't need a
    # None-guard.
    err2 = CompositionError("no flow")
    assert err2.dsl_code == ""
    assert err2.blueprint_yaml == ""


def test_compose_returns_is_valid_false_when_parse_raises(monkeypatch: Any) -> None:
    """Even when ``_parse_dsl_response`` throws, ``compose()`` must NOT
    propagate the exception — it should return a structured
    ``ComposeResult(is_valid=False)`` with ``dsl_code`` set. This is the
    key unblocker from issue #60: callers never lose the raw LLM text."""
    composer = _make_composer("unused")

    raw_dsl = "@flow\ndef some_flow():\n    return None\n"

    # Simulate the wire shape: the provider returns valid-looking DSL,
    # validate_dsl reports OK (so CallDetail.is_valid=True), but
    # _parse_dsl_response raises post-validation (e.g. exec failure).
    fake_call = CallDetail(
        call_number=1,
        input_tokens=10,
        output_tokens=20,
        yaml_text=raw_dsl,
        is_valid=True,
    )
    monkeypatch.setattr(composer, "_compose_call", lambda *a, **kw: fake_call)
    monkeypatch.setattr(
        composer,
        "_parse_dsl_response",
        MagicMock(side_effect=CompositionError("parse failed post-validation", dsl_code=raw_dsl)),
    )

    from bricks.core.registry import BrickRegistry

    result = composer.compose(task="whatever", registry=BrickRegistry())

    assert isinstance(result, ComposeResult)
    assert result.is_valid is False, "compose must not raise — return is_valid=False instead"
    assert result.dsl_code == raw_dsl, f"dsl_code must round-trip the raw text, got {result.dsl_code!r}"
    assert result.validation_errors, "post-validation failures must be recorded as validation_errors"
    assert any("parse failed post-validation" in e for e in result.validation_errors)


def test_compose_persists_dsl_code_on_ast_validation_failure(monkeypatch: Any) -> None:
    """When the LLM emits syntactically invalid DSL, ``CallDetail.is_valid``
    is False and ``_parse_dsl_response`` never runs. The raw text should
    still land in ``ComposeResult.dsl_code`` so it's visible downstream."""
    composer = _make_composer("unused")

    raw_dsl = "not-valid-python-code-at-all ((("
    fake_call = CallDetail(
        call_number=1,
        input_tokens=10,
        output_tokens=20,
        yaml_text=raw_dsl,
        is_valid=False,
        validation_errors=["SyntaxError: unexpected token"],
    )
    monkeypatch.setattr(composer, "_compose_call", lambda *a, **kw: fake_call)

    from bricks.core.registry import BrickRegistry

    result = composer.compose(task="whatever", registry=BrickRegistry())

    assert result.is_valid is False
    # dsl_code is stripped of fences; the raw body survives.
    assert result.dsl_code == raw_dsl
    assert result.validation_errors == ["SyntaxError: unexpected token"]
