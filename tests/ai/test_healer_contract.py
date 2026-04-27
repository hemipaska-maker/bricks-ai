"""Tests for issue #39 — every Healer must satisfy the chain's contract.

``HealerChain`` makes implicit assumptions about every :class:`Healer`
that live today only in prose docstrings on the protocol:

1. ``can_heal(ctx)`` is **pure** — calling it twice returns the same
   value and does not mutate ``ctx``.
2. A healer that should not run returns ``HealResult()`` (or anything
   with ``produced_something is False``) — it must not raise.
3. LLM-backed healers include the failure cause in the prompt sent to
   the provider, so the model has the information it needs to recover.
4. ``HealResult.tokens_in`` / ``tokens_out`` equal what the underlying
   :class:`LLMProvider` reported — no double-counting, no zeroing-out.

The five shipped healers all behave today (their individual tests
cover behavior); a sixth tier added by a future PR could silently
violate any rule. This module loops the contract over every healer in
the default chain plus :class:`FullRecomposeHealer` (publicly available
even though composer omits it from the default), so adding a new tier
forces it through the same gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from bricks.ai.healing import (
    DictUnwrapHealer,
    FullRecomposeHealer,
    HealContext,
    Healer,
    HealResult,
    LLMRetryHealer,
    ParamNameHealer,
    ShapeAwareLLMHealer,
)
from bricks.core.exceptions import BrickExecutionError
from bricks.llm.base import CompletionResult, LLMProvider

# --- test doubles -----------------------------------------------------------


@dataclass
class _StubFlow:
    """Opaque flow handle — healers never introspect it for these tests."""

    label: str = "stub"


def _mock_provider(text: str = "", input_tokens: int = 0, output_tokens: int = 0) -> MagicMock:
    """``MagicMock(spec=LLMProvider)`` whose ``complete()`` returns the given counts.

    Mirrors the conventions in tests/ai/test_healing.py so anyone
    reading both files sees the same shape.
    """
    provider = MagicMock(spec=LLMProvider)
    provider.complete.return_value = CompletionResult(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model="test",
        duration_seconds=0.0,
        estimated=False,
    )
    return provider


def _make_ctx(
    cause: Exception,
    *,
    registry: Any = None,
    prior_attempts: list[Any] | None = None,
) -> HealContext:
    """Build a HealContext with the requested cause and (optional) priors."""
    return HealContext(
        task="pretend task",
        failed_flow=_StubFlow(),  # type: ignore[arg-type]
        failed_dsl="@flow\ndef pretend(): return 1\n",
        error=BrickExecutionError("brick_x", "step_1_brick_x", cause),
        attempt=0,
        prior_attempts=list(prior_attempts or []),
        registry=registry,
    )


# --- healer factories -------------------------------------------------------
#
# A factory is a zero-arg callable that builds a fresh healer per test —
# important for purity assertions that need a healer without lingering
# state between cases. The id= names are surfaced in the parametrize
# label so failures point at a single healer.


def _param_name_healer() -> Healer:
    return ParamNameHealer()


def _dict_unwrap_healer() -> Healer:
    return DictUnwrapHealer()


def _llm_retry_healer() -> Healer:
    return LLMRetryHealer(provider=_mock_provider(), system_prompt="SYS")


def _shape_aware_healer() -> Healer:
    return ShapeAwareLLMHealer(
        provider=_mock_provider(),
        system_prompt="SYS",
        trace_executor=lambda _flow: {},
    )


def _full_recompose_healer() -> Healer:
    return FullRecomposeHealer(fresh_compose=lambda _task, _excluded: HealResult())


ALL_HEALER_FACTORIES = [
    pytest.param(_param_name_healer, id="ParamNameHealer"),
    pytest.param(_dict_unwrap_healer, id="DictUnwrapHealer"),
    pytest.param(_llm_retry_healer, id="LLMRetryHealer"),
    pytest.param(_shape_aware_healer, id="ShapeAwareLLMHealer"),
    pytest.param(_full_recompose_healer, id="FullRecomposeHealer"),
]

# LLM-backed healers — provider is captured at construction so we can
# rebuild with a known-token mock per assertion below.
LLM_HEALER_BUILDERS = [
    pytest.param(
        lambda provider: LLMRetryHealer(provider=provider, system_prompt="SYS"),
        id="LLMRetryHealer",
    ),
    pytest.param(
        lambda provider: ShapeAwareLLMHealer(
            provider=provider,
            system_prompt="SYS",
            trace_executor=lambda _flow: {},
        ),
        id="ShapeAwareLLMHealer",
    ),
]


# --- contract assertions ----------------------------------------------------


@pytest.mark.parametrize("factory", ALL_HEALER_FACTORIES)
def test_can_heal_is_pure(factory: Any) -> None:
    """``can_heal(ctx)`` returns the same answer twice and does not mutate ctx.

    The chain calls ``can_heal`` inside ``_pick_healer`` once per
    iteration — if a healer mutates ctx (e.g. appends to
    ``prior_attempts`` to track its own offers) the next iteration
    sees a different ctx and the chain's accounting drifts.
    """
    healer = factory()
    cause = ValueError("synthetic — arbitrary cause for purity check")
    ctx = _make_ctx(cause)
    snapshot_priors = list(ctx.prior_attempts)
    snapshot_attempt = ctx.attempt
    snapshot_error = ctx.error

    first = healer.can_heal(ctx)
    second = healer.can_heal(ctx)

    assert first == second, f"{type(healer).__name__}.can_heal not idempotent: {first} → {second}"
    assert ctx.prior_attempts == snapshot_priors, "can_heal mutated ctx.prior_attempts"
    assert ctx.attempt == snapshot_attempt, "can_heal mutated ctx.attempt"
    assert ctx.error is snapshot_error, "can_heal swapped ctx.error"


@pytest.mark.parametrize("factory", ALL_HEALER_FACTORIES)
def test_decline_returns_healresult_without_raising(factory: Any) -> None:
    """A context every healer should reject must yield a ``HealResult``,
    not an exception. ``HealerChain`` catches ``BrickExecutionError`` from
    the executor but does NOT catch arbitrary exceptions from healers —
    a raise here would propagate out of the chain and crash compose.

    The decline context combines all the conditions that make every
    in-tree healer step aside:
      - cause is ``ValueError`` (not TypeError → ParamNameHealer skips;
        not AttributeError → DictUnwrapHealer skips)
      - ``registry=None`` (ParamNameHealer also requires a registry)
      - ``prior_attempts=[]`` (ShapeAwareLLMHealer needs a tier-20 fail
        on file; FullRecomposeHealer needs ≥3 priors)

    LLMRetryHealer's ``can_heal`` always returns True — so for it the
    contract is "``heal()`` returns a HealResult shape without raising"
    rather than "declines outright". The mock provider's empty
    completion makes ``produced_something`` False naturally.
    """
    healer = factory()
    ctx = _make_ctx(ValueError("unrelated cause — every tier should decline"))

    # Call heal() unconditionally — the contract says it must return a
    # HealResult (not raise) regardless of can_heal's verdict, so a
    # future tier that uses can_heal as advisory rather than gating
    # still gets exercised.
    result = healer.heal(ctx)

    assert isinstance(result, HealResult), (
        f"{type(healer).__name__}.heal returned {type(result).__name__}, expected HealResult"
    )
    # The chain's loop ignores results with produced_something=False —
    # so an empty result is the contractually-correct "no candidate".
    # We don't require produced_something=False here (a healer that
    # genuinely accepts this ctx and produces something is still
    # contract-compliant), but we do require the result *type* be
    # HealResult so the chain can read its fields.


@pytest.mark.parametrize("build", LLM_HEALER_BUILDERS)
def test_llm_healer_includes_cause_in_prompt(build: Any) -> None:
    """LLM healers must surface the cause's message in the prompt —
    without it the model has no signal to fix anything and just rolls
    the dice."""
    cause_marker = "CAUSE_MARKER_42_DO_NOT_REMOVE"
    provider = _mock_provider(text="@flow\ndef x(): pass\n", input_tokens=1, output_tokens=1)
    healer = build(provider)

    # Both healers need a triggering ctx. ShapeAwareLLMHealer requires
    # a prior tier-20 failure for can_heal — but heal() itself doesn't
    # gate on that, so we can call it directly to test prompt assembly.
    ctx = _make_ctx(RuntimeError(cause_marker))
    healer.heal(ctx)

    assert provider.complete.call_count == 1, "LLM healer must call provider exactly once per heal"
    call_kwargs = provider.complete.call_args.kwargs
    prompt = call_kwargs.get("prompt", "")
    assert cause_marker in prompt, (
        f"{type(healer).__name__} dropped the cause from its prompt — "
        f"the LLM has no signal to recover with. Prompt was: {prompt!r}"
    )


@pytest.mark.parametrize("build", LLM_HEALER_BUILDERS)
def test_llm_healer_tokens_match_provider(build: Any) -> None:
    """Token counters reported on ``HealResult`` must equal what the
    provider returned. Drift here corrupts ``ChainResult.total_tokens_in/out``,
    which is what the composer folds into billing accounting."""
    expected_in, expected_out = 11, 22
    provider = _mock_provider(
        text="@flow\ndef x(): pass\n",
        input_tokens=expected_in,
        output_tokens=expected_out,
    )
    healer = build(provider)
    ctx = _make_ctx(RuntimeError("trigger"))

    result = healer.heal(ctx)

    assert result.tokens_in == expected_in, (
        f"{type(healer).__name__}.tokens_in == {result.tokens_in}, provider reported {expected_in} — accounting drift"
    )
    assert result.tokens_out == expected_out, (
        f"{type(healer).__name__}.tokens_out == {result.tokens_out}, "
        f"provider reported {expected_out} — accounting drift"
    )
