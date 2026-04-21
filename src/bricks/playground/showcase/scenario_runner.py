"""Shared scenario runner — works with any BenchmarkTask-compatible task object.

Extracted from crm_scenario.py so that every benchmark domain (CRM, tickets,
logs, …) can reuse the same solve → check → result pipeline without copying
code.
"""

from __future__ import annotations

from bricks.playground.showcase.engine import BenchmarkResult, BenchmarkTask, Engine, EngineResult
from bricks.playground.showcase.result_writer import check_correctness


def run_scenario(engine: Engine, task: BenchmarkTask) -> BenchmarkResult:
    """Run one engine on one task and evaluate correctness.

    Single unified pipeline: solve → check → result.  Works identically with
    any Engine implementation and any BenchmarkTask-compatible task object.

    Args:
        engine: Any Engine instance (BricksEngine or RawLLMEngine).
        task: Any object satisfying the BenchmarkTask protocol — must have
            ``task_text``, ``raw_api_response``, ``expected_outputs``, and
            ``required_bricks``.

    Returns:
        BenchmarkResult with outputs, correctness flag, and metadata.
    """
    result: EngineResult = engine.solve(task.task_text, task.raw_api_response)
    correct = check_correctness(result.outputs, task.expected_outputs)
    return BenchmarkResult(
        engine_name=engine.__class__.__name__,
        outputs=result.outputs,
        expected=task.expected_outputs,
        correct=correct,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        duration_seconds=result.duration_seconds,
        model=result.model,
        raw_response=result.raw_response,
        error=result.error,
        flow_def=result.flow_def,
    )


def _print_side_by_side(
    scenario_label: str,
    bricks: BenchmarkResult,
    llm: BenchmarkResult,
    seed: int,
) -> None:
    """Print a side-by-side comparison table for two engine results.

    Args:
        scenario_label: Label shown in the table header (e.g. 'CRM-pipeline').
        bricks: BricksEngine result.
        llm: RawLLMEngine result.
        seed: Seed used to generate the task (shown in header).
    """
    print()
    print(f"  {scenario_label} Results (seed={seed})")
    print(f"  {'-' * 70}")
    header = f"  {'Key':<25} {'BricksEngine':>20} {'RawLLMEngine':>20}"
    print(header)
    print(f"  {'-' * 70}")

    all_keys = sorted(set(bricks.expected.keys()) | set(bricks.outputs.keys()) | set(llm.outputs.keys()))
    for key in all_keys:
        exp = bricks.expected.get(key, "?")
        b_val = bricks.outputs.get(key, "—")
        l_val = llm.outputs.get(key, "—")
        b_mark = "OK" if key in bricks.outputs and check_correctness({key: bricks.outputs[key]}, {key: exp}) else "X"
        l_mark = "OK" if key in llm.outputs and check_correctness({key: llm.outputs[key]}, {key: exp}) else "X"
        b_str = f"{b_val} {b_mark}"
        l_str = f"{l_val} {l_mark}"
        print(f"  {key:<25} {b_str:>20} {l_str:>20}")

    print(f"  {'-' * 70}")
    b_ok = "YES OK" if bricks.correct else "NO  X"
    l_ok = "YES OK" if llm.correct else "NO  X"
    print(f"  {'Correct':<25} {b_ok:>20} {l_ok:>20}")
    b_tok = f"{bricks.tokens_in}/{bricks.tokens_out}"
    l_tok = f"{llm.tokens_in}/{llm.tokens_out}"
    print(f"  {'Tokens (in/out)':<25} {b_tok:>20} {l_tok:>20}")
    b_dur = f"{bricks.duration_seconds:.1f}s"
    l_dur = f"{llm.duration_seconds:.1f}s"
    print(f"  {'Duration':<25} {b_dur:>20} {l_dur:>20}")
    print(f"  {'Model':<25} {bricks.model[:18]:>20} {llm.model[:18]:>20}")
    print()
