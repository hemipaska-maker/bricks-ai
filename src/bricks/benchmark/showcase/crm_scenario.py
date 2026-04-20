"""CRM benchmark scenarios — unified Engine pipeline.

All three scenarios use the same run_scenario() function.
Both engines receive identical input; both use check_correctness().
Only the system under test changes.

Scenarios:
- CRM-pipeline     : 1 run each, side-by-side comparison
- CRM-hallucination: 10x each, compare pass rates
- CRM-reuse        : Bricks composes once + reuses 19x; RawLLM calls LLM 20x
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from bricks.benchmark.showcase.crm_generator import generate_crm_task
from bricks.benchmark.showcase.engine import Engine, EngineResult
from bricks.benchmark.showcase.result_writer import check_correctness
from bricks.benchmark.showcase.scenario_runner import _print_side_by_side, run_scenario

logger = logging.getLogger("bricks.showcase.crm")


def run_crm_pipeline(
    bricks_engine: Engine,
    llm_engine: Engine,
    run_dir: Path,
    seed: int = 42,
) -> None:
    """CRM-pipeline: run both engines on one task, show side-by-side.

    Args:
        bricks_engine: BricksEngine instance.
        llm_engine: RawLLMEngine instance.
        run_dir: Output directory for result files.
        seed: CRM data seed (default 42).
    """
    task = generate_crm_task(seed)
    logger.info("[CRM-pipeline] Running BricksEngine and RawLLMEngine (seed=%d)...", seed)
    t0 = time.monotonic()

    bricks_result = run_scenario(bricks_engine, task)
    llm_result = run_scenario(llm_engine, task)

    _print_side_by_side("CRM-pipeline", bricks_result, llm_result, seed)

    elapsed = time.monotonic() - t0
    logger.info(
        "[CRM-pipeline] done  bricks=%s  llm=%s  [%.1fs]",
        "CORRECT" if bricks_result.correct else "WRONG",
        "CORRECT" if llm_result.correct else "WRONG",
        elapsed,
    )

    summary = {
        "scenario": "CRM-pipeline",
        "seed": seed,
        "bricks": {
            "correct": bricks_result.correct,
            "outputs": bricks_result.outputs,
            "expected": bricks_result.expected,
            "tokens_in": bricks_result.tokens_in,
            "tokens_out": bricks_result.tokens_out,
            "duration_seconds": bricks_result.duration_seconds,
            "model": bricks_result.model,
            "error": bricks_result.error,
        },
        "llm": {
            "correct": llm_result.correct,
            "outputs": llm_result.outputs,
            "expected": llm_result.expected,
            "tokens_in": llm_result.tokens_in,
            "tokens_out": llm_result.tokens_out,
            "duration_seconds": llm_result.duration_seconds,
            "model": llm_result.model,
            "error": llm_result.error,
        },
    }
    out_path = run_dir / "CRM-pipeline_compose.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("[CRM-pipeline] Result -> %s", out_path)


def run_crm_hallucination(
    bricks_engine: Engine,
    llm_engine: Engine,
    run_dir: Path,
    runs: int = 10,
) -> None:
    """CRM-hallucination: 10x each engine, compare pass rates.

    Args:
        bricks_engine: BricksEngine instance.
        llm_engine: RawLLMEngine instance.
        run_dir: Output directory.
        runs: Number of repetitions (default 10).
    """
    logger.info("[CRM-hallucination] Running %dx BricksEngine + %dx RawLLMEngine...", runs, runs)
    t0 = time.monotonic()

    bricks_passes = 0
    llm_passes = 0
    bricks_tokens_total = 0
    llm_tokens_total = 0
    run_records: list[dict[str, Any]] = []

    for i in range(runs):
        seed = 42 + i
        task = generate_crm_task(seed)

        bricks_result = run_scenario(bricks_engine, task)
        llm_result = run_scenario(llm_engine, task)

        if bricks_result.correct:
            bricks_passes += 1
        if llm_result.correct:
            llm_passes += 1

        bricks_tokens_total += bricks_result.tokens_in + bricks_result.tokens_out
        llm_tokens_total += llm_result.tokens_in + llm_result.tokens_out

        b_status = "PASS" if bricks_result.correct else "FAIL"
        l_status = "PASS" if llm_result.correct else "FAIL"
        logger.info(
            "[CRM-hallucination] Run %d/%d: bricks=%s llm=%s",
            i + 1,
            runs,
            b_status,
            l_status,
        )
        run_records.append(
            {
                "seed": seed,
                "bricks_correct": bricks_result.correct,
                "llm_correct": llm_result.correct,
                "bricks_tokens": bricks_result.tokens_in + bricks_result.tokens_out,
                "llm_tokens": llm_result.tokens_in + llm_result.tokens_out,
            }
        )

    bricks_rate = bricks_passes / runs * 100
    llm_rate = llm_passes / runs * 100
    elapsed = time.monotonic() - t0
    logger.info(
        "[CRM-hallucination] done  bricks_pass_rate=%.0f%%  llm_pass_rate=%.0f%%  [%.1fs]",
        bricks_rate,
        llm_rate,
        elapsed,
    )
    print()
    print(f"  CRM-hallucination ({runs} seeds)")
    print(f"  BricksEngine: {bricks_passes}/{runs} correct ({bricks_rate:.0f}%)")
    print(f"  RawLLMEngine: {llm_passes}/{runs} correct ({llm_rate:.0f}%)")
    print()

    summary = {
        "scenario": "CRM-hallucination",
        "runs": runs,
        "bricks_pass_rate": bricks_rate,
        "llm_pass_rate": llm_rate,
        "bricks_tokens_avg": bricks_tokens_total // runs if runs else 0,
        "llm_tokens_avg": llm_tokens_total // runs if runs else 0,
        "run_records": run_records,
    }
    out_path = run_dir / "CRM-hallucination_compose.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("[CRM-hallucination] Summary -> %s", out_path)


def run_crm_reuse(
    bricks_engine: Engine,
    llm_engine: Engine,
    run_dir: Path,
    seeds: int = 20,
) -> None:
    """CRM-reuse: Bricks composes once + reuses 19x; RawLLM calls LLM 20x.

    Demonstrates token amortization: Bricks pays compose cost once,
    then executes at zero LLM cost. RawLLM pays per call.

    Args:
        bricks_engine: BricksEngine instance (must be BricksEngine for reuse).
        llm_engine: RawLLMEngine instance.
        run_dir: Output directory.
        seeds: Total seeds (first = compose, rest = reuse).
    """
    from bricks.benchmark.showcase.engine import BricksEngine

    logger.info(
        "[CRM-reuse] Bricks: compose once + reuse %dx. RawLLM: %d calls.",
        seeds - 1,
        seeds,
    )
    t0 = time.monotonic()

    # -- Bricks: compose once ----------------------------------------------
    first_task = generate_crm_task(42)
    first_bricks = run_scenario(bricks_engine, first_task)
    blueprint_yaml = first_bricks.raw_response
    compose_tokens = first_bricks.tokens_in + first_bricks.tokens_out
    logger.info("[CRM-reuse] Bricks compose: %d tokens", compose_tokens)

    bricks_records: list[dict[str, Any]] = [
        {
            "seed": 42,
            "correct": first_bricks.correct,
            "tokens": compose_tokens,
            "reused": False,
        }
    ]

    # -- Bricks: reuse 19x ------------------------------------------------
    bricks_reuse_correct = 0
    if first_bricks.correct or blueprint_yaml or first_bricks.flow_def:
        for i in range(1, seeds):
            seed = 42 + i
            task = generate_crm_task(seed)
            if isinstance(bricks_engine, BricksEngine) and (blueprint_yaml or first_bricks.flow_def):
                reuse_result = bricks_engine.solve_reuse(
                    blueprint_yaml,
                    task.raw_api_response,
                    flow_def=first_bricks.flow_def,
                )
                correct = check_correctness(reuse_result.outputs, task.expected_outputs)
            else:
                correct = False
                reuse_result = EngineResult(outputs={}, tokens_in=0, tokens_out=0, duration_seconds=0.0, model="")
            if correct:
                bricks_reuse_correct += 1
            status = "PASS" if correct else "FAIL"
            logger.info("[CRM-reuse] Bricks reuse %d/%d: %s", i, seeds - 1, status)
            bricks_records.append({"seed": seed, "correct": correct, "tokens": 0, "reused": True})

    # -- RawLLM: 20 calls -------------------------------------------------
    llm_passes = 0
    llm_tokens_total = 0
    llm_records: list[dict[str, Any]] = []
    for i in range(seeds):
        seed = 42 + i
        task = generate_crm_task(seed)
        llm_result = run_scenario(llm_engine, task)
        if llm_result.correct:
            llm_passes += 1
        tok = llm_result.tokens_in + llm_result.tokens_out
        llm_tokens_total += tok
        llm_records.append({"seed": seed, "correct": llm_result.correct, "tokens": tok})

    elapsed = time.monotonic() - t0
    bricks_total_tokens = compose_tokens
    llm_avg_tokens = llm_tokens_total // seeds if seeds else 0

    reuse_rate = bricks_reuse_correct / (seeds - 1) * 100 if seeds > 1 else 0.0
    llm_rate = llm_passes / seeds * 100 if seeds else 0.0

    logger.info(
        "[CRM-reuse] done  bricks_compose=%d tokens  reuse_pass=%.0f%%  llm_pass=%.0f%%  [%.1fs]",
        bricks_total_tokens,
        reuse_rate,
        llm_rate,
        elapsed,
    )
    print()
    print(f"  CRM-reuse ({seeds} seeds)")
    print(f"  BricksEngine: compose {compose_tokens} tokens once, then 0 tokens x {seeds - 1} reuse runs")
    print(f"    Reuse pass rate: {bricks_reuse_correct}/{seeds - 1} ({reuse_rate:.0f}%)")
    print(f"  RawLLMEngine:  {llm_avg_tokens} tokens x {seeds} calls = {llm_tokens_total} tokens total")
    print(f"    Pass rate: {llm_passes}/{seeds} ({llm_rate:.0f}%)")
    print()

    summary = {
        "scenario": "CRM-reuse",
        "total_seeds": seeds,
        "bricks_compose_tokens": compose_tokens,
        "bricks_reuse_pass_rate": reuse_rate,
        "llm_pass_rate": llm_rate,
        "llm_tokens_avg": llm_avg_tokens,
        "llm_tokens_total": llm_tokens_total,
        "bricks_records": bricks_records,
        "llm_records": llm_records,
    }
    out_path = run_dir / "CRM-reuse_compose.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("[CRM-reuse] Summary -> %s", out_path)
