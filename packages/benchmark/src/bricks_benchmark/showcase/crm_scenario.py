"""CRM pipeline benchmark scenarios.

Three scenarios:
- CRM-pipeline : 1 compose run + 1 no-tools baseline
- CRM-hallucination : 10x each (compose + no-tools), pass/fail rate comparison
- CRM-reuse : 20 seeds, compose once then reuse 19x with different inputs
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from bricks.ai.composer import BlueprintComposer
from bricks.core.engine import BlueprintEngine
from bricks.core.loader import BlueprintLoader
from bricks.core.registry import BrickRegistry as _BrickRegistry
from bricks_stdlib import register as _register_stdlib

from bricks_benchmark.showcase.crm_generator import generate_crm_task
from bricks_benchmark.showcase.formatters import estimate_cost
from bricks_benchmark.showcase.result_writer import (
    BaselineRecord,
    CallRecord,
    ExecutionRecord,
    ScenarioResult,
    TotalRecord,
    check_correctness,
    check_no_tools_answer,
    write_scenario_result,
)

logger = logging.getLogger("bricks.showcase.crm")


def _build_crm_registry() -> Any:
    """Return a stdlib registry for CRM tasks."""
    reg = _BrickRegistry()
    _register_stdlib(reg)
    return reg


def _run_compose_once(
    composer: BlueprintComposer,
    task_text: str,
    seed: int = 42,
) -> dict[str, Any]:
    """Compose and execute CRM pipeline for one seed.

    Args:
        composer: Configured BlueprintComposer.
        task_text: Natural language task description.
        seed: CRM data seed.

    Returns:
        dict with compose result and execution outputs.
    """
    from bricks_benchmark.showcase.crm_generator import generate_crm_task

    task = generate_crm_task(seed)
    registry = _build_crm_registry()
    loader = BlueprintLoader()
    engine = BlueprintEngine(registry=registry)

    result = composer.compose(task.task_text, registry, input_keys=["raw_api_response"])
    outputs: dict[str, Any] = {}
    error = ""
    success = False

    if result.is_valid:
        try:
            bp_def = loader.load_string(result.blueprint_yaml)
            exec_inputs = {"raw_api_response": task.raw_api_response}
            exec_result = engine.run(bp_def, inputs=exec_inputs)
            outputs = exec_result.outputs
            success = True
        except Exception as exc:
            error = str(exc)

    return {
        "compose_result": result,
        "task": task,
        "outputs": outputs,
        "error": error,
        "success": success,
    }


def run_crm_pipeline(
    composer: BlueprintComposer,
    runner: Any,
    run_dir: Path,
    seed: int = 42,
) -> None:
    """Run CRM-pipeline scenario: 1 compose + 1 no-tools baseline.

    Args:
        composer: Configured BlueprintComposer.
        runner: AgentRunner for no-tools baseline.
        run_dir: Output directory for structured result files.
        seed: CRM data seed.
    """
    task = generate_crm_task(seed)
    print("  [CRM-pipeline] Composing...", flush=True)
    t0 = time.monotonic()

    run = _run_compose_once(composer, task.task_text, seed)
    result = run["compose_result"]
    outputs = run["outputs"]
    success = run["success"]
    error = run.get("error", "")

    if success:
        filtered_expected = {k: v for k, v in task.expected_outputs.items() if k in outputs}
        correct = check_correctness(outputs, filtered_expected)
        status = "CORRECT" if correct else "WRONG"
        print(f"  [CRM-pipeline]   Execution: {status} — outputs: {outputs}")
    else:
        filtered_expected = {}
        correct = False
        print(f"  [CRM-pipeline]   Execution: FAILED — {error}")

    # No-tools baseline
    nt_result = runner.run_without_tools(task.task_text)
    nt_correct = check_no_tools_answer(nt_result.final_answer, task.expected_outputs)
    nt_label = "CORRECT" if nt_correct else "WRONG"
    print(f"  [CRM-pipeline] No-tools: {nt_result.total_tokens:,} tokens  answer={nt_label}")

    elapsed = time.monotonic() - t0
    ratio_val = result.total_tokens / nt_result.total_tokens if nt_result.total_tokens > 0 else 0.0
    print(
        f"  [CRM-pipeline] done  compose={result.total_tokens:,}  "
        f"no_tools={nt_result.total_tokens:,}  ({ratio_val:.1f}x)  [{elapsed:.1f}s]"
    )

    call_records = [
        CallRecord(
            call_number=c.call_number,
            system_prompt=c.system_prompt,
            user_prompt=c.user_prompt,
            response_text=c.yaml_text,
            yaml_generated=c.yaml_text,
            validation_errors=c.validation_errors,
            is_valid=c.is_valid,
            input_tokens=c.input_tokens,
            output_tokens=c.output_tokens,
            total_tokens=c.total_tokens,
            duration_seconds=c.duration_seconds,
        )
        for c in result.calls
    ]

    scenario_result = ScenarioResult(
        scenario="CRM-pipeline",
        mode="compose",
        model=result.model,
        task_text=task.task_text,
        calls=call_records,
        execution=ExecutionRecord(
            success=success,
            actual_outputs=outputs,
            expected_outputs=filtered_expected,
            correct=correct,
            error=error,
        ),
        totals=TotalRecord(
            api_calls=result.api_calls,
            input_tokens=result.total_input_tokens,
            output_tokens=result.total_output_tokens,
            total_tokens=result.total_tokens,
            cost_usd=estimate_cost(result.total_input_tokens, result.total_output_tokens),
            duration_seconds=result.duration_seconds,
        ),
        baseline=BaselineRecord(
            no_tools_tokens=nt_result.total_tokens,
            no_tools_input=nt_result.total_input_tokens,
            no_tools_output=nt_result.total_output_tokens,
            ratio=ratio_val,
            no_tools_correct=nt_correct,
        ),
    )
    json_path = write_scenario_result(run_dir, scenario_result)
    print(f"  [CRM-pipeline] Structured result -> {json_path}")


def run_crm_hallucination(
    composer: BlueprintComposer,
    runner: Any,
    run_dir: Path,
    runs: int = 10,
) -> None:
    """Run CRM-hallucination: 10x each (compose + no-tools), compare pass rates.

    Args:
        composer: Configured BlueprintComposer.
        runner: AgentRunner for no-tools baseline.
        run_dir: Output directory.
        runs: Number of repetitions (default 10).
    """
    print(f"  [CRM-hallucination] Running {runs}x compose + {runs}x no-tools...", flush=True)
    t0 = time.monotonic()

    compose_passes = 0
    no_tools_passes = 0
    compose_tokens_total = 0
    no_tools_tokens_total = 0
    run_records: list[dict[str, Any]] = []

    for i in range(runs):
        seed = 42 + i
        task = generate_crm_task(seed)
        run = _run_compose_once(composer, task.task_text, seed)
        result = run["compose_result"]
        outputs = run["outputs"]
        success = run["success"]

        correct = False
        if success and outputs:
            filtered_expected = {k: v for k, v in task.expected_outputs.items() if k in outputs}
            correct = check_correctness(outputs, filtered_expected)
        if correct:
            compose_passes += 1
        compose_tokens_total += result.total_tokens

        nt_result = runner.run_without_tools(task.task_text)
        nt_correct = check_no_tools_answer(nt_result.final_answer, task.expected_outputs)
        if nt_correct:
            no_tools_passes += 1
        no_tools_tokens_total += nt_result.total_tokens

        status = "PASS" if correct else "FAIL"
        nt_status = "PASS" if nt_correct else "FAIL"
        print(f"  [CRM-hallucination] Run {i + 1}/{runs}: compose={status} no_tools={nt_status}")
        run_records.append(
            {
                "seed": seed,
                "compose_correct": correct,
                "no_tools_correct": nt_correct,
                "compose_tokens": result.total_tokens,
                "no_tools_tokens": nt_result.total_tokens,
            }
        )

    compose_rate = compose_passes / runs * 100
    nt_rate = no_tools_passes / runs * 100
    elapsed = time.monotonic() - t0
    print(
        f"  [CRM-hallucination] done  "
        f"compose_pass_rate={compose_rate:.0f}%  no_tools_pass_rate={nt_rate:.0f}%  [{elapsed:.1f}s]"
    )

    # Write summary JSON
    import json

    summary = {
        "scenario": "CRM-hallucination",
        "runs": runs,
        "compose_pass_rate": compose_rate,
        "no_tools_pass_rate": nt_rate,
        "compose_tokens_avg": compose_tokens_total // runs if runs else 0,
        "no_tools_tokens_avg": no_tools_tokens_total // runs if runs else 0,
        "run_records": run_records,
    }
    summary_path = run_dir / "CRM-hallucination_compose.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  [CRM-hallucination] Summary -> {summary_path}")


def run_crm_reuse(
    composer: BlueprintComposer,
    run_dir: Path,
    seeds: int = 20,
) -> None:
    """Run CRM-reuse: compose once, reuse 19x with different seeds.

    Args:
        composer: Configured BlueprintComposer.
        run_dir: Output directory.
        seeds: Total number of seeds to run (first = compose, rest = reuse).
    """
    print(f"  [CRM-reuse] Composing blueprint (seed=42), then reusing for {seeds - 1} more seeds...", flush=True)
    t0 = time.monotonic()

    # First run: compose fresh
    first_task = generate_crm_task(42)
    registry = _build_crm_registry()
    loader = BlueprintLoader()
    engine = BlueprintEngine(registry=registry)

    first_result = composer.compose(first_task.task_text, registry, input_keys=["raw_api_response"])
    blueprint_yaml = first_result.blueprint_yaml
    compose_tokens = first_result.total_tokens
    print(f"  [CRM-reuse] Compose: {compose_tokens:,} tokens")

    cumulative_tokens = [compose_tokens]
    reuse_correct = 0
    run_records: list[dict[str, Any]] = []

    # Reuse for remaining seeds
    for i in range(1, seeds):
        seed = 42 + i
        task = generate_crm_task(seed)
        outputs: dict[str, Any] = {}
        correct = False
        error = ""

        if first_result.is_valid:
            try:
                bp_def = loader.load_string(blueprint_yaml)
                exec_inputs = {"raw_api_response": task.raw_api_response}
                exec_result = engine.run(bp_def, inputs=exec_inputs)
                outputs = exec_result.outputs
                filtered_expected = {k: v for k, v in task.expected_outputs.items() if k in outputs}
                correct = check_correctness(outputs, filtered_expected)
            except Exception as exc:
                error = str(exc)

        if correct:
            reuse_correct += 1
        status = "PASS" if correct else "FAIL"
        cumulative = cumulative_tokens[-1]  # only compose tokens; reuse costs 0 API calls
        cumulative_tokens.append(cumulative)
        run_records.append(
            {
                "seed": seed,
                "correct": correct,
                "cumulative_tokens": cumulative,
                "error": error,
            }
        )
        print(f"  [CRM-reuse] Reuse {i}/{seeds - 1}: {status}  cumulative={cumulative:,} tokens")

    elapsed = time.monotonic() - t0
    reuse_rate = reuse_correct / (seeds - 1) * 100 if seeds > 1 else 0.0
    print(f"  [CRM-reuse] done  reuse_pass_rate={reuse_rate:.0f}%  [{elapsed:.1f}s]")

    import json

    summary = {
        "scenario": "CRM-reuse",
        "total_seeds": seeds,
        "compose_tokens": compose_tokens,
        "reuse_pass_rate": reuse_rate,
        "cumulative_tokens": cumulative_tokens,
        "run_records": run_records,
    }
    summary_path = run_dir / "CRM-reuse_compose.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  [CRM-reuse] Summary -> {summary_path}")
