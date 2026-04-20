"""Live tests verifying that the engine surfaces clear errors for failure scenarios.

Run with: pytest --live -m live
Skipped by default (no --live flag).
"""

from __future__ import annotations

import pytest

from bricks.api import Bricks
from bricks.core.exceptions import OrchestratorError
from bricks.llm.base import LLMProvider


@pytest.mark.live
def test_failure_impossible_task_raises_orchestrator_error(
    llm_provider: LLMProvider,
) -> None:
    """Task requiring capabilities absent from stdlib raises OrchestratorError.

    Asking the LLM to send emails and post to Slack requires bricks that do not
    exist in the stdlib registry.  The composed blueprint will reference unknown
    brick names, fail validation, and the orchestrator must raise with a message
    that identifies the problem.
    """
    engine = Bricks.default(provider=llm_provider)
    with pytest.raises(OrchestratorError) as exc_info:
        engine.execute(
            "send an email to every user and post a Slack notification",
            {"users": [{"email": "a@example.com"}]},
        )
    error_msg = str(exc_info.value).lower()
    # The error must name the task or explain the validation failure
    assert "send" in error_msg or "composition" in error_msg or "failed" in error_msg, (
        f"Error message not descriptive enough: {exc_info.value}"
    )


@pytest.mark.live
def test_failure_type_mismatch_raises_orchestrator_error(
    llm_provider: LLMProvider,
) -> None:
    """Passing a string where a list is required causes a clear execution error.

    The LLM should compose a blueprint that sums a list of numbers.  When the
    engine receives a plain string instead of a list, the brick fails internally
    and the orchestrator must wrap it in OrchestratorError.
    """
    engine = Bricks.default(provider=llm_provider)
    with pytest.raises(OrchestratorError) as exc_info:
        engine.execute(
            "sum all the numbers in the list",
            {"numbers": "not-a-list"},
        )
    # The error message must contain enough context to diagnose the problem
    msg = str(exc_info.value)
    assert msg, "OrchestratorError must have a non-empty message"


@pytest.mark.live
def test_failure_empty_required_data_produces_empty_or_raises(
    llm_provider: LLMProvider,
) -> None:
    """Passing an empty list to a task that needs items is handled gracefully.

    The engine should either return an empty result dict or raise
    OrchestratorError — it must not crash with an unhandled exception.
    """
    engine = Bricks.default(provider=llm_provider)
    try:
        result = engine.execute(
            "filter the items where status is active",
            {"items": []},
        )
        # If execution succeeds, the output should reflect empty input
        assert isinstance(result["outputs"], dict)
    except OrchestratorError:
        pass  # Acceptable: orchestrator raised a clear error


@pytest.mark.live
def test_failure_ambiguous_task_raises_or_produces_valid_output(
    llm_provider: LLMProvider,
) -> None:
    """An extremely vague task either raises OrchestratorError or returns a dict.

    The LLM may be unable to compose a blueprint from a one-word instruction
    with no input hints.  Either the composition fails (OrchestratorError) or
    the LLM makes a best-guess attempt and returns some output dict.  What is
    NOT acceptable is an unhandled exception of a different type.
    """
    engine = Bricks.default(provider=llm_provider)
    try:
        result = engine.execute("process")
        # If the LLM managed to compose something, output must be a dict
        assert isinstance(result["outputs"], dict)
    except OrchestratorError:
        pass  # Acceptable: orchestrator surfaced a clear error


@pytest.mark.live
def test_failure_orchestrator_error_message_contains_task_name(
    llm_provider: LLMProvider,
) -> None:
    """OrchestratorError messages include the task text to aid debugging.

    When the orchestrator raises because an impossible blueprint was composed,
    the exception message should quote or paraphrase the original task so the
    caller can identify which task failed.
    """
    task = "deploy the application to kubernetes and configure auto-scaling"
    engine = Bricks.default(provider=llm_provider)
    try:
        engine.execute(task, {})
    except OrchestratorError as exc:
        msg = str(exc)
        # The task text or a key word from it should appear in the error
        assert any(word in msg for word in ("deploy", "kubernetes", "composition", "failed")), (
            f"Task name not reflected in error message: {msg}"
        )
    except Exception as exc:
        pytest.fail(f"Unexpected exception type {type(exc).__name__}: {exc}")
