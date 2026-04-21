"""Support ticket benchmark scenario (BENCH_001).

Mirrors crm_scenario.py: both engines receive the same ticket task and are
evaluated with the same check_correctness() function.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from bricks.playground.showcase.engine import Engine
from bricks.playground.showcase.scenario_runner import _print_side_by_side, run_scenario
from bricks.playground.showcase.ticket_generator import generate_ticket_task

logger = logging.getLogger("bricks.showcase.ticket")


def run_ticket_pipeline(
    bricks_engine: Engine,
    llm_engine: Engine,
    run_dir: Path,
    seed: int = 42,
) -> None:
    """TICKET-pipeline: run both engines on one ticket task, show side-by-side.

    Args:
        bricks_engine: BricksEngine instance.
        llm_engine: RawLLMEngine instance.
        run_dir: Output directory for result files.
        seed: Ticket data seed (default 42).
    """
    task = generate_ticket_task(seed)
    logger.info("[TICKET-pipeline] Running BricksEngine and RawLLMEngine (seed=%d)...", seed)
    t0 = time.monotonic()

    bricks_result = run_scenario(bricks_engine, task)
    llm_result = run_scenario(llm_engine, task)

    _print_side_by_side("TICKET-pipeline", bricks_result, llm_result, seed)

    elapsed = time.monotonic() - t0
    logger.info(
        "[TICKET-pipeline] done  bricks=%s  llm=%s  [%.1fs]",
        "CORRECT" if bricks_result.correct else "WRONG",
        "CORRECT" if llm_result.correct else "WRONG",
        elapsed,
    )

    summary = {
        "scenario": "TICKET-pipeline",
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
    out_path = run_dir / "TICKET-pipeline_compose.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("[TICKET-pipeline] Result -> %s", out_path)
