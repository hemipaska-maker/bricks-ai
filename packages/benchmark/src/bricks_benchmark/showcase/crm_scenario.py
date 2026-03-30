"""CRM pipeline benchmark scenarios.

Three scenarios:
- CRM-pipeline     : 1 compose run, check correctness
- CRM-hallucination: 10x compose runs, pass/fail rate
- CRM-reuse        : compose once, reuse 19x with different seeds
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
    CallRecord,
    ExecutionRecord,
    ScenarioResult,
    TotalRecord,
    check_correctness,
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
    run_dir: Path,
    seed: int = 42,
) -> None:
    """Run CRM-pipeline scenario: 1 compose run, check correctness.

    Args:
        composer: Configured BlueprintComposer.
        run_dir: Output directory for structured result files.
        seed: CRM data seed.
    """
    task = generate_crm_task(seed)
    logger.info("[CRM-pipeline] Composing...")
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
        logger.info("[CRM-pipeline]   Execution: %s — outputs: %s", status, outputs)
        logger.debug("[CRM-pipeline]   Expected: %s", filtered_expected)
    else:
        filtered_expected = {}
        correct = False
        logger.error("[CRM-pipeline]   Execution: FAILED — %s", error)

    elapsed = time.monotonic() - t0
    logger.info(
        "[CRM-pipeline] done  compose=%d tokens  correct=%s  [%.1fs]",
        result.total_tokens,
        correct,
        elapsed,
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
    )
    json_path = write_scenario_result(run_dir, scenario_result)
    logger.info("[CRM-pipeline] Structured result -> %s", json_path)


def run_crm_hallucination(
    composer: BlueprintComposer,
    run_dir: Path,
    runs: int = 10,
) -> None:
    """Run CRM-hallucination: 10x compose runs, compare pass rates.

    Args:
        composer: Configured BlueprintComposer.
        run_dir: Output directory.
        runs: Number of repetitions (default 10).
    """
    logger.info("[CRM-hallucination] Running %dx compose...", runs)
    t0 = time.monotonic()

    compose_passes = 0
    compose_tokens_total = 0
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

        status = "PASS" if correct else "FAIL"
        logger.info("[CRM-hallucination] Run %d/%d: compose=%s", i + 1, runs, status)
        run_records.append(
            {
                "seed": seed,
                "compose_correct": correct,
                "compose_tokens": result.total_tokens,
            }
        )

    compose_rate = compose_passes / runs * 100
    elapsed = time.monotonic() - t0
    logger.info(
        "[CRM-hallucination] done  compose_pass_rate=%.0f%%  [%.1fs]",
        compose_rate,
        elapsed,
    )

    import json

    summary = {
        "scenario": "CRM-hallucination",
        "runs": runs,
        "compose_pass_rate": compose_rate,
        "compose_tokens_avg": compose_tokens_total // runs if runs else 0,
        "run_records": run_records,
    }
    summary_path = run_dir / "CRM-hallucination_compose.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("[CRM-hallucination] Summary -> %s", summary_path)


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
    logger.info("[CRM-reuse] Composing blueprint (seed=42), then reusing for %d more seeds...", seeds - 1)
    t0 = time.monotonic()

    first_task = generate_crm_task(42)
    registry = _build_crm_registry()
    loader = BlueprintLoader()
    engine = BlueprintEngine(registry=registry)

    first_result = composer.compose(first_task.task_text, registry, input_keys=["raw_api_response"])
    blueprint_yaml = first_result.blueprint_yaml
    compose_tokens = first_result.total_tokens
    logger.info("[CRM-reuse] Compose: %d tokens", compose_tokens)

    cumulative_tokens = [compose_tokens]
    reuse_correct = 0
    run_records: list[dict[str, Any]] = []

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
        cumulative = cumulative_tokens[-1]
        cumulative_tokens.append(cumulative)
        run_records.append(
            {
                "seed": seed,
                "correct": correct,
                "cumulative_tokens": cumulative,
                "error": error,
            }
        )
        logger.info("[CRM-reuse] Reuse %d/%d: %s  cumulative=%d tokens", i, seeds - 1, status, cumulative)

    elapsed = time.monotonic() - t0
    reuse_rate = reuse_correct / (seeds - 1) * 100 if seeds > 1 else 0.0
    logger.info("[CRM-reuse] done  reuse_pass_rate=%.0f%%  [%.1fs]", reuse_rate, elapsed)

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
    logger.info("[CRM-reuse] Summary -> %s", summary_path)
