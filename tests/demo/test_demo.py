"""Tests for the bricks.demo module (demo mode — no LLM required)."""

from __future__ import annotations

import pytest

from bricks.demo.data import (
    EXPECTED_ACTIVE_REVENUE,
    SAMPLE_CRM,
    SIMULATED_LLM_RESPONSES,
    DemoMetrics,
    generate_variants,
)
from bricks.demo.runner import DemoRunner

# ---------------------------------------------------------------------------
# data.py tests
# ---------------------------------------------------------------------------


def test_sample_crm_expected_revenue() -> None:
    """EXPECTED_ACTIVE_REVENUE matches sum of active customer revenues."""
    total = sum(c["monthly_revenue"] for c in SAMPLE_CRM if c["status"] == "active")
    assert total == pytest.approx(EXPECTED_ACTIVE_REVENUE)


def test_sample_crm_has_five_records() -> None:
    """SAMPLE_CRM always contains exactly 5 records."""
    assert len(SAMPLE_CRM) == 5


def test_generate_variants_length() -> None:
    """generate_variants() returns exactly 5 pairs."""
    assert len(generate_variants()) == 5


def test_generate_variants_expected_values() -> None:
    """Each variant's expected revenue matches the sum of its active customers."""
    for customers, expected in generate_variants():
        actual = sum(c["monthly_revenue"] for c in customers if c["status"] == "active")
        assert actual == pytest.approx(expected), f"Variant expected {expected}, got {actual}"


def test_simulated_llm_responses_has_five_entries() -> None:
    """SIMULATED_LLM_RESPONSES has an entry for each variant."""
    assert len(SIMULATED_LLM_RESPONSES) == len(generate_variants())


def test_simulated_llm_responses_three_correct_two_wrong() -> None:
    """Simulated LLM has exactly 3 correct and 2 wrong responses."""
    correct = sum(
        1
        for (_, expected), simulated in zip(generate_variants(), SIMULATED_LLM_RESPONSES, strict=True)
        if abs(simulated - expected) < 0.01
    )
    assert correct == 3


def test_demo_metrics_defaults() -> None:
    """DemoMetrics initialises with all-zero fields."""
    m = DemoMetrics()
    assert m.compose_tokens == 0
    assert m.bricks_run_tokens == 0
    assert m.llm_run_tokens == 0
    assert m.bricks_correct == 0
    assert m.llm_correct == 0
    assert m.num_variants == 5
    assert m.live is False


# ---------------------------------------------------------------------------
# DemoRunner demo-mode tests (no LLM provider)
# ---------------------------------------------------------------------------


def test_demo_runner_act1_demo_mode() -> None:
    """DemoRunner.run_act1() completes without error in demo mode."""
    runner = DemoRunner(provider=None)
    runner.run_act1()  # must not raise


def test_demo_runner_act1_sets_blueprint() -> None:
    """After run_act1() in demo mode, _blueprint is loaded."""
    runner = DemoRunner(provider=None)
    runner.run_act1()
    assert runner._blueprint is not None


def test_demo_runner_act2_demo_mode() -> None:
    """DemoRunner.run_act2() completes without error in demo mode."""
    runner = DemoRunner(provider=None)
    runner.run_act2()  # must not raise


def test_demo_runner_act2_bricks_five_correct() -> None:
    """In demo mode, Bricks gets all 5 variants correct."""
    runner = DemoRunner(provider=None)
    runner.run_act2()
    assert runner._metrics.bricks_correct == 5


def test_demo_runner_act2_llm_three_correct() -> None:
    """In demo mode, simulated LLM gets exactly 3/5 correct."""
    runner = DemoRunner(provider=None)
    runner.run_act2()
    assert runner._metrics.llm_correct == 3


def test_demo_runner_act3_demo_mode() -> None:
    """DemoRunner.run_act3() completes without error in demo mode."""
    runner = DemoRunner(provider=None)
    runner.run_act3()  # must not raise


def test_demo_runner_all_acts_demo_mode() -> None:
    """DemoRunner.run_all() runs all three acts end-to-end without error."""
    runner = DemoRunner(provider=None)
    runner.run_all()  # must not raise


def test_demo_runner_act2_standalone_loads_blueprint() -> None:
    """Act 2 can run standalone (without Act 1) and still loads the blueprint."""
    runner = DemoRunner(provider=None)
    runner.run_act2()
    assert runner._blueprint is not None
