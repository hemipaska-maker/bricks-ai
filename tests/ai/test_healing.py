"""Tests for the ``HealerChain`` orchestrator and related dataclasses.

Concrete healer tiers (10/15/20/30/40) have their own test modules; this
file only exercises the chain mechanics: tier ordering, max_attempts cap,
the BrickExecutionError-only retry contract, and the trace produced in
:class:`ChainResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from bricks.ai.healing import (
    ChainResult,
    DictUnwrapHealer,
    FullRecomposeHealer,
    HealAttempt,
    HealContext,
    HealerChain,
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
    """Stand-in for a FlowDefinition — the chain only treats it as an opaque
    handle the executor receives. Carries an identifier so tests can assert
    which flow reached the executor."""

    label: str


@dataclass
class _FakeHealer:
    """Configurable healer for chain-mechanics tests.

    Records every ``can_heal`` / ``heal`` invocation so assertions can
    inspect the sequence.
    """

    tier: int
    name: str
    produces_dsl: str = ""
    produces_flow: _StubFlow | None = None
    accept: bool = True
    tokens_in: int = 0
    tokens_out: int = 0
    heal_calls: list[HealContext] = field(default_factory=list)
    can_heal_calls: list[HealContext] = field(default_factory=list)

    def can_heal(self, ctx: HealContext) -> bool:
        self.can_heal_calls.append(ctx)
        return self.accept

    def heal(self, ctx: HealContext) -> HealResult:
        self.heal_calls.append(ctx)
        return HealResult(
            new_dsl=self.produces_dsl,
            new_flow=self.produces_flow,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
        )


def _make_ctx(error_message: str = "simulated failure") -> HealContext:
    """Build a minimal HealContext. The failed_flow is a stub — the chain
    never introspects it in scaffolding-level tests."""
    return HealContext(
        task="pretend task",
        failed_flow=_StubFlow(label="original"),  # type: ignore[arg-type]
        failed_dsl="@flow\ndef pretend(): return 1\n",
        error=BrickExecutionError("brick_x", "step_1_brick_x", RuntimeError(error_message)),
        attempt=0,
        prior_attempts=[],
    )


def _ok_executor(outputs: dict[str, Any]):
    """Return an executor that always returns *outputs*."""

    def _run(_: Any) -> dict[str, Any]:
        return outputs

    return _run


def _failing_executor(message: str = "still broken"):
    """Return an executor that always raises BrickExecutionError."""

    def _run(_: Any) -> dict[str, Any]:
        raise BrickExecutionError("brick_x", "step_1_brick_x", RuntimeError(message))

    return _run


def _noop_parser(_: str) -> _StubFlow:
    """Return a stub flow. The chain only needs the executor to accept it."""
    return _StubFlow(label="parsed")


# --- tests ------------------------------------------------------------------


class TestHealerChainOrdering:
    """Chain must sort healers by tier ascending and pick the first match."""

    def test_healers_sorted_ascending_on_construction(self) -> None:
        high = _FakeHealer(tier=40, name="t40")
        mid = _FakeHealer(tier=20, name="t20")
        low = _FakeHealer(tier=10, name="t10")
        chain = HealerChain(healers=[high, low, mid])
        assert [h.tier for h in chain.healers] == [10, 20, 40]

    def test_lowest_tier_with_can_heal_true_wins(self) -> None:
        declines = _FakeHealer(tier=10, name="t10", accept=False)
        winner = _FakeHealer(tier=20, name="t20", produces_dsl="@flow\ndef x():\n    return 1\n")
        loser_later = _FakeHealer(tier=30, name="t30", produces_dsl="should_not_run")
        chain = HealerChain(healers=[loser_later, declines, winner], max_attempts=1)

        result = chain.heal(
            _make_ctx(),
            executor=_ok_executor({"result": 42}),
            parser=_noop_parser,
        )

        assert result.success is True
        assert declines.heal_calls == [], "declining healer must not be invoked"
        assert len(winner.heal_calls) == 1, "tier 20 should run"
        assert loser_later.heal_calls == [], "tier 30 must not run after tier 20 succeeds"


class TestMaxAttempts:
    """Chain must stop after max_attempts iterations even if healers keep
    proposing flows."""

    def test_caps_iterations(self) -> None:
        always_fails = _FakeHealer(tier=20, name="t20", produces_dsl="@flow\ndef x():\n    return 1\n")
        chain = HealerChain(healers=[always_fails], max_attempts=2)

        result = chain.heal(
            _make_ctx(),
            executor=_failing_executor("still broken"),
            parser=_noop_parser,
        )

        assert result.success is False
        assert len(result.attempts) == 2
        assert all(a.exec_succeeded is False for a in result.attempts)
        assert result.final_error, "final_error must describe the last failure"

    def test_single_attempt_default(self) -> None:
        # max_attempts=2 is the class default — exercise that without
        # overriding it.
        healer = _FakeHealer(tier=20, name="t20", produces_dsl="@flow\ndef x():\n    return 1\n")
        chain = HealerChain(healers=[healer])
        assert chain._max_attempts == 2


class TestHealerDeclining:
    """When no healer's can_heal returns True, chain stops immediately
    with an empty-attempts ChainResult."""

    def test_all_decline_short_circuits(self) -> None:
        mute = _FakeHealer(tier=10, name="t10", accept=False)
        chain = HealerChain(healers=[mute], max_attempts=3)

        result = chain.heal(
            _make_ctx("original error"),
            executor=_ok_executor({"should": "not run"}),
            parser=_noop_parser,
        )

        assert result.success is False
        assert result.attempts == []
        assert "original error" in result.final_error


class TestProducedNothing:
    """A healer that returns HealResult with no DSL and no flow must be
    recorded as an attempt but not trigger an executor call."""

    def test_empty_result_still_records_attempt(self) -> None:
        shrugs = _FakeHealer(tier=10, name="t10")  # produces_dsl="" by default
        chain = HealerChain(healers=[shrugs], max_attempts=1)

        executor_calls: list[Any] = []

        def _exec(flow: Any) -> dict[str, Any]:
            executor_calls.append(flow)
            return {}

        result = chain.heal(_make_ctx(), executor=_exec, parser=_noop_parser)

        assert executor_calls == [], "executor must not run when healer produced nothing"
        assert len(result.attempts) == 1
        assert result.attempts[0].produced_flow is False
        assert result.attempts[0].exec_succeeded is None


class TestErrorPassthrough:
    """Non-BrickExecutionError exceptions from the executor must propagate
    unchanged — we do not want to mask framework bugs."""

    def test_non_brick_exception_propagates(self) -> None:
        healer = _FakeHealer(tier=20, name="t20", produces_dsl="@flow\ndef x():\n    return 1\n")
        chain = HealerChain(healers=[healer], max_attempts=3)

        def _explode(_: Any) -> dict[str, Any]:
            raise RuntimeError("framework bug — do not retry")

        with pytest.raises(RuntimeError, match="framework bug"):
            chain.heal(_make_ctx(), executor=_explode, parser=_noop_parser)


class TestSuccessfulHealTrace:
    """ChainResult.attempts must record an exec_succeeded=True entry for
    the winning attempt and carry tokens through."""

    def test_success_carries_tokens_and_outputs(self) -> None:
        healer = _FakeHealer(
            tier=20,
            name="t20",
            produces_dsl="@flow\ndef ok():\n    return 1\n",
            tokens_in=100,
            tokens_out=40,
        )
        chain = HealerChain(healers=[healer], max_attempts=2)

        result = chain.heal(
            _make_ctx(),
            executor=_ok_executor({"answer": 42}),
            parser=_noop_parser,
        )

        assert result.success is True
        assert result.outputs == {"answer": 42}
        assert result.total_tokens_in == 100
        assert result.total_tokens_out == 40
        assert len(result.attempts) == 1
        assert result.attempts[0].exec_succeeded is True
        assert result.attempts[0].healer_name == "t20"

    def test_healer_returning_prebuilt_flow_skips_parser(self) -> None:
        prebuilt = _StubFlow(label="prebuilt")
        healer = _FakeHealer(tier=20, name="t20", produces_flow=prebuilt)
        chain = HealerChain(healers=[healer], max_attempts=1)

        executed: list[Any] = []

        def _exec(flow: Any) -> dict[str, Any]:
            executed.append(flow)
            return {}

        parser_calls: list[str] = []

        def _parser(dsl: str) -> _StubFlow:
            parser_calls.append(dsl)
            return _StubFlow(label="fallback-parsed")

        chain.heal(_make_ctx(), executor=_exec, parser=_parser)

        assert executed == [prebuilt], "prebuilt flow must reach executor verbatim"
        assert parser_calls == [], "parser must not be called when new_flow is already set"


def test_heal_attempt_defaults() -> None:
    """Smoke test the HealAttempt dataclass defaults so later refactors do
    not silently break assumptions used by other tests."""
    att = HealAttempt(healer_name="x", tier=10, produced_flow=False, exec_succeeded=None)
    assert att.error_after == ""
    assert att.tokens_in == 0
    assert att.tokens_out == 0


def test_chain_result_defaults() -> None:
    """Smoke test the ChainResult dataclass defaults."""
    result = ChainResult(success=False)
    assert result.outputs is None
    assert result.final_flow is None
    assert result.final_dsl == ""
    assert result.attempts == []
    assert result.total_tokens_in == 0
    assert result.total_tokens_out == 0


# --- LLMRetryHealer (tier 20) -----------------------------------------------


class TestLLMRetryHealer:
    """Tier-20 LLM retry — fires on any BrickExecutionError."""

    def _provider_returning(self, text: str, tokens_in: int = 42, tokens_out: int = 17) -> MagicMock:
        provider = MagicMock(spec=LLMProvider)
        provider.complete.return_value = CompletionResult(
            text=text,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            model="test",
            duration_seconds=0.1,
            estimated=False,
        )
        return provider

    def test_can_heal_accepts_any_brick_execution_error(self) -> None:
        healer = LLMRetryHealer(provider=MagicMock(spec=LLMProvider), system_prompt="SYS")
        assert healer.can_heal(_make_ctx()) is True

    def test_heal_prompts_with_brick_step_cause_and_strips_fences(self) -> None:
        provider = self._provider_returning("```python\n@flow\ndef fixed():\n    return 1\n```")
        healer = LLMRetryHealer(provider=provider, system_prompt="SYSTEM-PROMPT")

        ctx = _make_ctx("missing columns")
        result = healer.heal(ctx)

        assert result.new_dsl.startswith("@flow"), "fences must be stripped"
        assert "```" not in result.new_dsl
        assert result.tokens_in == 42
        assert result.tokens_out == 17

        # The call must carry the system prompt and reference the failing step.
        provider.complete.assert_called_once()
        call = provider.complete.call_args
        assert call.kwargs["system"] == "SYSTEM-PROMPT"
        prompt = call.kwargs["prompt"]
        assert "brick_x" in prompt, "retry prompt must include the failing brick name"
        assert "step_1_brick_x" in prompt, "retry prompt must include the failing step name"
        assert "missing columns" in prompt, "retry prompt must include the cause message"

    def test_heal_passes_through_empty_dsl_if_llm_returns_empty(self) -> None:
        provider = self._provider_returning("")
        healer = LLMRetryHealer(provider=provider, system_prompt="SYS")
        result = healer.heal(_make_ctx())
        assert result.new_dsl == ""
        assert result.produced_something is False


# --- ShapeAwareLLMHealer (tier 30) ------------------------------------------


class TestShapeAwareLLMHealer:
    """Tier-30 shape-aware retry — only fires after tier 20 failed."""

    def _provider(self, text: str = "@flow\ndef v2():\n    return 1\n") -> MagicMock:
        provider = MagicMock(spec=LLMProvider)
        provider.complete.return_value = CompletionResult(
            text=text, input_tokens=100, output_tokens=50, model="test", duration_seconds=0.1, estimated=False
        )
        return provider

    def test_can_heal_false_without_trace_executor(self) -> None:
        healer = ShapeAwareLLMHealer(provider=self._provider(), system_prompt="SYS", trace_executor=None)
        ctx = _make_ctx()
        # Even with a prior tier-20 failure, no trace_executor → cannot heal.
        ctx.prior_attempts = [
            HealAttempt(
                healer_name=LLMRetryHealer.name,
                tier=20,
                produced_flow=True,
                exec_succeeded=False,
                error_after="x",
            )
        ]
        assert healer.can_heal(ctx) is False

    def test_can_heal_false_on_first_attempt(self) -> None:
        """Without a prior tier-20 failure, tier-30 must stand down."""
        healer = ShapeAwareLLMHealer(provider=self._provider(), system_prompt="SYS", trace_executor=lambda _: {})
        ctx = _make_ctx()
        ctx.prior_attempts = []
        assert healer.can_heal(ctx) is False

    def test_can_heal_true_after_tier_20_failed(self) -> None:
        healer = ShapeAwareLLMHealer(provider=self._provider(), system_prompt="SYS", trace_executor=lambda _: {})
        ctx = _make_ctx()
        ctx.prior_attempts = [
            HealAttempt(
                healer_name=LLMRetryHealer.name,
                tier=20,
                produced_flow=True,
                exec_succeeded=False,
                error_after="x",
            )
        ]
        assert healer.can_heal(ctx) is True

    def test_heal_includes_observed_shapes_in_prompt(self) -> None:
        trace_result = {"step_1_parse": "dict<keys=['customers']>", "step_2_filter": "str"}

        def _trace_exec(_: Any) -> dict[str, Any]:
            return trace_result

        provider = self._provider()
        healer = ShapeAwareLLMHealer(provider=provider, system_prompt="SYS", trace_executor=_trace_exec)
        result = healer.heal(_make_ctx())

        prompt = provider.complete.call_args.kwargs["prompt"]
        for step_name, shape in trace_result.items():
            assert step_name in prompt
            assert shape in prompt

        assert result.tokens_in == 100
        assert result.tokens_out == 50

    def test_heal_tolerates_trace_executor_raising(self) -> None:
        """A crashing trace_executor must not crash the healer."""

        def _bad_trace(_: Any) -> dict[str, Any]:
            raise RuntimeError("tracer broke")

        provider = self._provider()
        healer = ShapeAwareLLMHealer(provider=provider, system_prompt="SYS", trace_executor=_bad_trace)
        result = healer.heal(_make_ctx())

        prompt = provider.complete.call_args.kwargs["prompt"]
        assert "(no shape info available)" in prompt
        assert result.produced_something is True


# --- FullRecomposeHealer (tier 40) ------------------------------------------


class TestFullRecomposeHealer:
    """Tier-40 full recompose — only fires after 3 prior attempts failed."""

    def test_can_heal_requires_three_prior_attempts(self) -> None:
        healer = FullRecomposeHealer(fresh_compose=lambda task, excluded: HealResult())
        ctx = _make_ctx()
        ctx.prior_attempts = []
        assert healer.can_heal(ctx) is False
        ctx.prior_attempts = [HealAttempt(healer_name="a", tier=10, produced_flow=False, exec_succeeded=None)] * 2
        assert healer.can_heal(ctx) is False
        ctx.prior_attempts = [HealAttempt(healer_name="a", tier=10, produced_flow=False, exec_succeeded=None)] * 3
        assert healer.can_heal(ctx) is True

    def test_heal_extracts_failed_brick_names_and_delegates(self) -> None:
        called: dict[str, Any] = {}

        def _fresh(task: str, excluded: list[str]) -> HealResult:
            called["task"] = task
            called["excluded"] = excluded
            return HealResult(new_dsl="@flow\ndef fresh():\n    return 1\n", tokens_in=7, tokens_out=3)

        healer = FullRecomposeHealer(fresh_compose=_fresh)
        ctx = _make_ctx()
        ctx.prior_attempts = [
            HealAttempt(
                healer_name="t20",
                tier=20,
                produced_flow=True,
                exec_succeeded=False,
                error_after="Brick 'filter_dict_list' failed at step 'step_2': oops",
            ),
            HealAttempt(
                healer_name="t30",
                tier=30,
                produced_flow=True,
                exec_succeeded=False,
                error_after="Brick 'filter_dict_list' failed at step 'step_3': oops",
            ),
            HealAttempt(
                healer_name="t20",
                tier=20,
                produced_flow=True,
                exec_succeeded=False,
                error_after="Brick 'map_values' failed at step 'step_1': boom",
            ),
        ]

        result = healer.heal(ctx)

        assert called["task"] == ctx.task
        # Exclusions dedupe, preserve first-seen order, and include current error's brick.
        assert called["excluded"] == ["filter_dict_list", "map_values", "brick_x"]
        assert result.tokens_in == 7
        assert result.tokens_out == 3
        assert result.new_dsl.startswith("@flow")


# --- ParamNameHealer (tier 10) ----------------------------------------------


class _FakeRegistry:
    """Minimal registry stand-in — only implements the .get method tier 10 needs."""

    def __init__(self, bricks: dict[str, Any]) -> None:
        self._bricks = bricks

    def get(self, name: str):
        if name not in self._bricks:
            raise KeyError(name)
        return (self._bricks[name], None)


class TestParamNameHealer:
    """Tier-10 deterministic fix for TypeError: unexpected keyword argument."""

    def _dsl(self) -> str:
        return "@flow\ndef do_it(data):\n    result = step.count_dict_list(item=data)\n    return result\n"

    def _registry_with_count(self) -> _FakeRegistry:
        def count_dict_list(items: list, *, metadata: Any = None) -> dict:
            return {"result": len(items)}

        return _FakeRegistry({"count_dict_list": count_dict_list})

    def _ctx(
        self,
        cause: Exception,
        *,
        dsl: str | None = None,
        registry: _FakeRegistry | None = None,
        brick: str = "count_dict_list",
    ) -> HealContext:
        return HealContext(
            task="count the items",
            failed_flow=_StubFlow(label="orig"),  # type: ignore[arg-type]
            failed_dsl=dsl or self._dsl(),
            error=BrickExecutionError(brick, "step_1", cause),
            attempt=0,
            prior_attempts=[],
            registry=registry or self._registry_with_count(),
        )

    def test_can_heal_only_on_typeerror_with_matching_message(self) -> None:
        healer = ParamNameHealer()
        typeerror = self._ctx(TypeError("got an unexpected keyword argument 'item'"))
        assert healer.can_heal(typeerror) is True

        attr = self._ctx(AttributeError("boom"))
        assert healer.can_heal(attr) is False

        unrelated_type = self._ctx(TypeError("some other message"))
        assert healer.can_heal(unrelated_type) is False

    def test_can_heal_false_without_registry(self) -> None:
        healer = ParamNameHealer()
        ctx = HealContext(
            task="x",
            failed_flow=_StubFlow(label="x"),  # type: ignore[arg-type]
            failed_dsl="",
            error=BrickExecutionError("b", "s", TypeError("unexpected keyword argument 'y'")),
            attempt=0,
            prior_attempts=[],
            registry=None,
        )
        assert healer.can_heal(ctx) is False

    def test_heal_rewrites_bad_kwarg_to_closest_match(self) -> None:
        healer = ParamNameHealer()
        ctx = self._ctx(TypeError("got an unexpected keyword argument 'item'"))
        result = healer.heal(ctx)

        assert result.produced_something is True
        assert "items=data" in result.new_dsl
        assert "item=data" not in result.new_dsl
        # Deterministic tiers must not spend tokens.
        assert result.tokens_in == 0
        assert result.tokens_out == 0

    def test_heal_returns_empty_when_no_close_match(self) -> None:
        healer = ParamNameHealer()
        ctx = self._ctx(TypeError("got an unexpected keyword argument 'xyzabc'"))
        result = healer.heal(ctx)
        assert result.produced_something is False

    def test_heal_wont_loop_if_prior_attempt_failed_with_same_rewrite(self) -> None:
        healer = ParamNameHealer()
        ctx = self._ctx(TypeError("got an unexpected keyword argument 'item'"))
        ctx.prior_attempts = [
            HealAttempt(
                healer_name=ParamNameHealer.name,
                tier=10,
                produced_flow=True,
                exec_succeeded=False,
                error_after="the kwarg 'item' still wrong",
            )
        ]
        result = healer.heal(ctx)
        assert result.produced_something is False

    def test_heal_rewrites_for_each_inner_kwarg_post_issue_34_fix(self) -> None:
        """Regression guard for issue #34.

        Before the fix, ``BrickExecutionError.brick_name`` was ``"__for_each__"``,
        so the healer looked up the wrapper's params (``items`` / ``do_brick``
        / ``on_error``) instead of the real inner brick's and could not
        propose a sane fix. After the fix the attribution points at the real
        inner brick (``count_dict_list``), whose close-match swap
        ``item`` → ``items`` is the correct repair.
        """
        dsl = (
            "@flow\n"
            "def count_batches(batches):\n"
            "    return for_each(items=batches, do=lambda b: step.count_dict_list(item=b))\n"
        )
        ctx = HealContext(
            task="count each batch",
            failed_flow=_StubFlow(label="orig"),  # type: ignore[arg-type]
            failed_dsl=dsl,
            # brick_name is the real inner brick, as produced by the fixed
            # __for_each__ builtin (not "__for_each__").
            error=BrickExecutionError(
                "count_dict_list",
                "count_dict_list[item_0]",
                TypeError("count_dict_list() got an unexpected keyword argument 'item'"),
            ),
            attempt=0,
            prior_attempts=[],
            registry=self._registry_with_count(),
        )

        result = ParamNameHealer().heal(ctx)

        assert result.produced_something is True, "healer should propose a fix now that attribution is correct"
        assert "items=b" in result.new_dsl
        assert "item=b" not in result.new_dsl


# --- DictUnwrapHealer (tier 15) ---------------------------------------------


class TestDictUnwrapHealer:
    """Tier-15 deterministic fix for the wrapper-dict mistake."""

    _TICKET_DSL = (
        "@flow\n"
        "def ticket_counts(raw_api_response):\n"
        "    parsed = step.extract_json_from_str(text=raw_api_response)\n"
        "    high = step.filter_dict_list(items=parsed.output, key='priority', value='high')\n"
        "    return step.count_dict_list(items=high.output)\n"
    )

    _TASK_WITH_KEY = "Parse the JSON. The dict has key 'tickets' with the list of items."
    _TASK_WITHOUT_KEY = "Just parse some JSON and count things."

    def _ctx(
        self,
        cause: Exception,
        *,
        task: str = _TASK_WITH_KEY,
        brick: str = "filter_dict_list",
    ) -> HealContext:
        return HealContext(
            task=task,
            failed_flow=_StubFlow(label="orig"),  # type: ignore[arg-type]
            failed_dsl=self._TICKET_DSL,
            error=BrickExecutionError(brick, "step_2", cause),
            attempt=0,
            prior_attempts=[],
        )

    def test_can_heal_requires_attribute_error_shape(self) -> None:
        healer = DictUnwrapHealer()
        assert healer.can_heal(self._ctx(AttributeError("'str' object has no attribute 'get'"))) is True
        assert healer.can_heal(self._ctx(TypeError("nope"))) is False
        assert healer.can_heal(self._ctx(AttributeError("some other attribute error"))) is False

    def test_can_heal_declines_after_prior_same_healer_failed(self) -> None:
        healer = DictUnwrapHealer()
        ctx = self._ctx(AttributeError("'str' object has no attribute 'get'"))
        ctx.prior_attempts = [
            HealAttempt(
                healer_name=DictUnwrapHealer.name,
                tier=15,
                produced_flow=True,
                exec_succeeded=False,
                error_after="still broken",
            )
        ]
        assert healer.can_heal(ctx) is False

    def test_heal_inserts_extract_dict_field_before_failing_step(self) -> None:
        healer = DictUnwrapHealer()
        ctx = self._ctx(AttributeError("'str' object has no attribute 'get'"))
        result = healer.heal(ctx)

        assert result.produced_something is True
        assert "step.extract_dict_field" in result.new_dsl
        assert "field='tickets'" in result.new_dsl or 'field="tickets"' in result.new_dsl
        # The consumer must now reference the unwrapped step.
        assert "items=parsed_items.output" in result.new_dsl
        # Deterministic — no tokens.
        assert result.tokens_in == 0

    def test_heal_declines_when_task_has_no_key_hint(self) -> None:
        healer = DictUnwrapHealer()
        ctx = self._ctx(
            AttributeError("'str' object has no attribute 'get'"),
            task=self._TASK_WITHOUT_KEY,
        )
        result = healer.heal(ctx)
        assert result.produced_something is False
