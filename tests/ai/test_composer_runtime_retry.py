"""Integration tests for the composer ↔ HealerChain wiring.

The scaffolding tests in ``test_healing.py`` cover the chain and each
healer in isolation. This module verifies the composer calls the chain
correctly when ``executor=`` is supplied, and that ``executor=None``
preserves today's behavior for existing callers.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from bricks.ai.composer import BlueprintComposer
from bricks.ai.healing import HealAttempt, HealResult
from bricks.core.brick import BrickMeta
from bricks.core.exceptions import BrickExecutionError
from bricks.core.registry import BrickRegistry
from bricks.llm.base import CompletionResult, LLMProvider

# A DSL snippet the validate_dsl pass accepts and that executes to a simple
# dict when run through the composer's _parse_dsl_response + a fake executor.
_WORKING_DSL = "@flow\ndef ok_task(raw_api_response):\n    return step.identity(value=raw_api_response)\n"
_REPLACEMENT_DSL = "@flow\ndef fixed_task(raw_api_response):\n    return step.identity(value=raw_api_response)\n"


def _registry_with_identity() -> BrickRegistry:
    """Tiny registry — one brick ``identity`` that returns its input."""
    registry = BrickRegistry()

    def identity(value: Any) -> dict[str, Any]:
        return {"result": value}

    registry.register("identity", identity, BrickMeta(name="identity", tags=[], category="test"))
    return registry


def _provider_returning(*texts: str) -> MagicMock:
    """Build a MagicMock LLMProvider that hands out texts in order."""
    provider = MagicMock(spec=LLMProvider)
    completions = [
        CompletionResult(text=t, input_tokens=10, output_tokens=5, model="test", duration_seconds=0.1, estimated=False)
        for t in texts
    ]
    provider.complete.side_effect = completions
    return provider


class TestExecutorNone:
    """``executor=None`` must preserve today's pre-healing behavior exactly."""

    def test_compose_without_executor_skips_healing(self) -> None:
        provider = _provider_returning(_WORKING_DSL)
        composer = BlueprintComposer(provider=provider)
        registry = _registry_with_identity()

        result = composer.compose(task="just run it", registry=registry, input_keys=["raw_api_response"])

        # Back-compat fields populated.
        assert result.is_valid is True
        assert result.flow_def is not None
        assert result.blueprint_yaml  # non-empty
        # New fields stay at their defaults when executor is not passed.
        assert result.exec_outputs is None
        assert result.exec_error == ""
        assert result.heal_attempts == []
        # Only one LLM call — no healing.
        assert provider.complete.call_count == 1


class TestExecutorSuccessFirstTry:
    """When the first execution succeeds, no healers run."""

    def test_exec_outputs_populated_and_no_heal_attempts(self) -> None:
        provider = _provider_returning(_WORKING_DSL)
        composer = BlueprintComposer(provider=provider)
        registry = _registry_with_identity()

        executor_calls: list[Any] = []

        def _run(flow: Any) -> dict[str, Any]:
            executor_calls.append(flow)
            return {"result": "ok"}

        result = composer.compose(
            task="just run it",
            registry=registry,
            input_keys=["raw_api_response"],
            executor=_run,
        )

        assert result.exec_outputs == {"result": "ok"}
        assert result.exec_error == ""
        assert result.heal_attempts == []
        assert len(executor_calls) == 1
        # Still only one LLM call — healers never invoked.
        assert provider.complete.call_count == 1


class TestExecutorFailsThenHealsSucceeds:
    """Execution fails once, tier-20 LLM retry produces working DSL, retry succeeds."""

    def test_tier_20_llm_retry_unblocks_execution(self) -> None:
        # LLM returns the original (bad) DSL, then a replacement after healing.
        provider = _provider_returning(_WORKING_DSL, _REPLACEMENT_DSL)
        composer = BlueprintComposer(provider=provider)
        registry = _registry_with_identity()

        call_count = {"n": 0}

        def _run(flow: Any) -> dict[str, Any]:
            del flow  # executor signature fixed by contract
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise BrickExecutionError("identity", "step_1_identity", RuntimeError("first try bad"))
            return {"result": "healed"}

        result = composer.compose(
            task="heal me",
            registry=registry,
            input_keys=["raw_api_response"],
            executor=_run,
        )

        assert result.exec_outputs == {"result": "healed"}
        assert result.exec_error == ""
        # One successful heal attempt, tier 20 (LLMRetryHealer).
        assert len(result.heal_attempts) == 1
        attempt = result.heal_attempts[0]
        assert attempt.tier == 20
        assert attempt.exec_succeeded is True
        # Two LLM calls: original compose + one retry prompt.
        assert provider.complete.call_count == 2


class TestHealingExhaustsCleanly:
    """Every tier fails → exec_error surfaced, no exception escapes compose."""

    def test_exhausted_chain_sets_exec_error(self) -> None:
        # LLM keeps producing DSL, but executor always raises BrickExecutionError.
        # Enough replacement texts to cover every tier in the default chain
        # x max_attempts=4, so StopIteration can't mask the test's intent.
        provider = _provider_returning(_WORKING_DSL, *([_REPLACEMENT_DSL] * 8))
        composer = BlueprintComposer(provider=provider)
        registry = _registry_with_identity()

        def _run(_: Any) -> dict[str, Any]:
            raise BrickExecutionError("identity", "step_1_identity", RuntimeError("persistent"))

        result = composer.compose(
            task="cannot heal",
            registry=registry,
            input_keys=["raw_api_response"],
            executor=_run,
        )

        assert result.exec_outputs is None
        assert "persistent" in result.exec_error
        assert len(result.heal_attempts) >= 1
        assert all(a.exec_succeeded is False for a in result.heal_attempts)


class TestFrameworkErrorsPassthrough:
    """Non-BrickExecutionError errors must NOT be swallowed by the healer chain."""

    def test_non_brick_exec_error_propagates(self) -> None:
        provider = _provider_returning(_WORKING_DSL)
        composer = BlueprintComposer(provider=provider)
        registry = _registry_with_identity()

        def _run(_: Any) -> dict[str, Any]:
            raise RuntimeError("framework bug — must not be masked")

        try:
            composer.compose(
                task="framework crash",
                registry=registry,
                input_keys=["raw_api_response"],
                executor=_run,
            )
        except RuntimeError as exc:
            assert "framework bug" in str(exc)
        else:
            raise AssertionError("RuntimeError must propagate unchanged")


class TestExplicitEmptyHealerList:
    """``healers=[]`` opts out of healing entirely but still accepts an executor."""

    def test_empty_healers_surfaces_error_without_retrying(self) -> None:
        provider = _provider_returning(_WORKING_DSL)
        composer = BlueprintComposer(provider=provider, healers=[])
        registry = _registry_with_identity()

        def _run(_: Any) -> dict[str, Any]:
            raise BrickExecutionError("identity", "step_1_identity", RuntimeError("no healer to catch"))

        result = composer.compose(
            task="no healing",
            registry=registry,
            input_keys=["raw_api_response"],
            executor=_run,
        )

        assert result.exec_outputs is None
        assert "no healer to catch" in result.exec_error
        assert result.heal_attempts == []
        # Only the original compose call — no retry happened.
        assert provider.complete.call_count == 1


class TestTokensRollUp:
    """Tokens spent by healers must appear in ComposeResult totals."""

    def test_heal_tokens_roll_into_total(self) -> None:
        provider = _provider_returning(_WORKING_DSL, _REPLACEMENT_DSL)
        composer = BlueprintComposer(provider=provider)
        registry = _registry_with_identity()

        call_count = {"n": 0}

        def _run(_: Any) -> dict[str, Any]:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise BrickExecutionError("identity", "step_1_identity", RuntimeError("boom"))
            return {"result": 1}

        result = composer.compose(
            task="heal tokens",
            registry=registry,
            input_keys=["raw_api_response"],
            executor=_run,
        )

        # The LLMProvider mock returns 10 in / 5 out per call x 2 calls.
        assert result.total_input_tokens == 20
        assert result.total_output_tokens == 10
        assert result.total_tokens == 30


def test_compose_result_back_compat_for_positional_callers() -> None:
    """Existing callers that ignore the new fields must keep working."""
    provider = _provider_returning(_WORKING_DSL)
    composer = BlueprintComposer(provider=provider)
    registry = _registry_with_identity()

    result = composer.compose(task="compat", registry=registry, input_keys=["raw_api_response"])
    # Only touch pre-existing fields.
    assert result.is_valid
    assert result.flow_def is not None
    assert result.total_tokens >= 0
    assert result.api_calls >= 1


def test_healer_attempt_dataclass_surface_remains_stable() -> None:
    """Pin the HealAttempt fields the composer exposes via heal_attempts."""
    # This is a smoke check that guards downstream consumers like the
    # showcase engine's logger from silent field renames.
    attempt = HealAttempt(
        healer_name="LLMRetryHealer",
        tier=20,
        produced_flow=True,
        exec_succeeded=True,
    )
    assert attempt.error_after == ""
    assert attempt.tokens_in == 0


def test_heal_result_produced_something_false_on_empty() -> None:
    """Smoke test — guards the check composer relies on."""
    assert HealResult().produced_something is False
    assert HealResult(new_dsl="nope").produced_something is True
