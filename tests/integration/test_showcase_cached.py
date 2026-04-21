"""Cached-fixture integration test for the full compose → HealerChain → engine path.

Exercises the seam where every bug in this session has lived (#25, #26,
#34) — without depending on live API keys. A ``FixtureReplayProvider``
returns pre-captured ``CompletionResult`` objects in order, so CI can run
the happy path and the heal path deterministically.

Fixture refresh
---------------
To capture fresh fixtures when prompts or bricks change intentionally::

    ANTHROPIC_API_KEY=sk-ant-... python -m bricks.playground.showcase.run \\
        --live --scenario CRM-pipeline --seed 42

Copy the winning DSL into ``fixtures/crm_pipeline_happy.json``; for the
heal fixture, break one kwarg (e.g. ``items=`` → ``item=``) so the
deterministic ``ParamNameHealer`` tier triggers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bricks.llm.base import CompletionResult, LLMProvider
from bricks.playground.showcase.engine import BricksEngine

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ── fixture-replay provider ─────────────────────────────────────────────────


class FixtureReplayProvider(LLMProvider):
    """LLMProvider that pops scripted ``CompletionResult`` objects per call.

    Raises ``IndexError`` if the code under test makes more calls than the
    fixture has responses — that is a meaningful failure signal for any
    future change that adds retries.
    """

    def __init__(self, responses: list[CompletionResult]) -> None:
        self._queue = list(responses)
        self.call_count = 0

    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        if not self._queue:
            raise IndexError(
                f"FixtureReplayProvider exhausted after {self.call_count} call(s); "
                "compose made more LLM calls than the fixture expected."
            )
        self.call_count += 1
        return self._queue.pop(0)


def _load_fixture(name: str) -> dict[str, Any]:
    payload = json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return payload


def _provider_from(fixture: dict[str, Any]) -> FixtureReplayProvider:
    responses = [
        CompletionResult(
            text=r["dsl"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            cached_input_tokens=r.get("cached_input_tokens", 0),
            model=r.get("model", ""),
            duration_seconds=0.0,
            estimated=False,
        )
        for r in fixture["responses"]
    ]
    return FixtureReplayProvider(responses)


_CRM_RAW = json.dumps(
    {
        "customers": [
            {"id": 1, "status": "active", "monthly_revenue": 100.0},
            {"id": 2, "status": "inactive", "monthly_revenue": 0.0},
            {"id": 3, "status": "active", "monthly_revenue": 50.0},
        ]
    }
)


# ── happy path ─────────────────────────────────────────────────────────────


def test_crm_pipeline_happy_path_no_heal() -> None:
    """Compose → execute succeeds on the first LLM response; no healer fires."""
    fixture = _load_fixture("crm_pipeline_happy.json")
    provider = _provider_from(fixture)
    engine = BricksEngine(provider=provider)

    result = engine.solve(
        task_text="Count the customers whose status is 'active'.",
        raw_data=_CRM_RAW,
    )

    assert result.error == "", f"expected clean run, got: {result.error}"
    assert result.outputs == fixture["expected_outputs"], (
        f"expected {fixture['expected_outputs']!r}, got {result.outputs!r}"
    )
    assert provider.call_count == 1, f"happy path should be 1 LLM call, was {provider.call_count}"
    # Positive token counters from the fixture.
    assert result.tokens_in > 0
    assert result.tokens_out > 0


# ── heal path ──────────────────────────────────────────────────────────────


def test_crm_pipeline_heal_path_recovers_via_param_name_healer() -> None:
    """Compose emits DSL that crashes at runtime (wrong kwarg); the
    deterministic tier-10 ``ParamNameHealer`` repairs it without calling
    the LLM a second time, and execution succeeds."""
    fixture = _load_fixture("crm_pipeline_heal.json")
    provider = _provider_from(fixture)
    engine = BricksEngine(provider=provider)

    result = engine.solve(
        task_text="Count the customers whose status is 'active'.",
        raw_data=_CRM_RAW,
    )

    assert result.error == "", f"heal chain failed to recover: {result.error!r}"
    assert result.outputs == fixture["expected_outputs"]
    # Exactly one LLM call — the deterministic healer does not re-compose.
    assert provider.call_count == 1, f"heal path should be 1 LLM call, was {provider.call_count}"

    flow_def = result.flow_def
    assert flow_def is not None, "flow_def should be set after a successful run"
    # The rewritten DSL must contain the corrected kwarg.
    rewritten = flow_def.to_yaml()
    assert "items:" in rewritten


# ── contract guard ─────────────────────────────────────────────────────────


def test_provider_raises_if_extra_calls_attempted() -> None:
    """If a future change multiplies compose calls, the fixture runs dry
    and the test fails loudly — exactly the regression signal we want
    for prompt-caching or retry-loop changes (#27)."""
    provider = FixtureReplayProvider([])
    with pytest.raises(IndexError, match="exhausted"):
        provider.complete("anything")
