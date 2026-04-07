"""DSL Benchmark: measure composition quality across a standard task set.

Runs 5 canonical tasks through the Python DSL pipeline using mock LLM
responses (no real API calls). Reports validity, step accuracy, brick
selection, token usage, and composition time.

Usage::

    python benchmarks/dsl_vs_yaml.py

Results are saved to ``benchmarks/results/dsl_benchmark_YYYYMMDD.md``.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Allow running as a standalone script from repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

import bricks
from bricks.ai.composer import BlueprintComposer
from bricks.core.models import BrickMeta
from bricks.core.registry import BrickRegistry
from bricks.llm.base import CompletionResult, LLMProvider

# ---------------------------------------------------------------------------
# Pre-canned DSL responses for each benchmark task
# ---------------------------------------------------------------------------

_DSL_SIMPLE_3_STEP = """\
@flow
def simple_pipeline():
    loaded = step.load_data(path="data.csv")
    cleaned = step.clean(text=loaded)
    return step.save(data=cleaned)
"""

_DSL_FILTER_AGGREGATE = """\
@flow
def filter_aggregate(data):
    filtered = step.filter_dict_list(data=data, field="amount", operator=">", value=100)
    return step.aggregate_field(data=filtered, field="amount", operation="sum")
"""

_DSL_FOR_EACH = """\
@flow
def batch_process(records):
    cleaned = for_each(records, do=lambda r: step.clean(text=r))
    return for_each(cleaned, do=lambda r: step.validate(data=r))
"""

_DSL_BRANCH = """\
@flow
def conditional_route(data):
    return branch(
        "is_valid",
        if_true=lambda: step.process(data=data),
        if_false=lambda: step.log_error(data=data),
    )
"""

_DSL_COMPLEX = """\
@flow
def crm_pipeline(data):
    loaded = step.load_data(path=data)
    cleaned = step.clean(text=loaded)
    filtered = step.filter_dict_list(data=cleaned, field="active", operator="==", value=True)
    validated = step.validate(data=filtered)
    enriched = step.enrich(data=validated)
    scored = step.score(data=enriched)
    sorted_data = step.sort_by(data=scored, field="score", descending=True)
    top10 = step.take(data=sorted_data, n=10)
    report = step.format_report(data=top10)
    return step.save(data=report)
"""

# ---------------------------------------------------------------------------
# Benchmark task definitions
# ---------------------------------------------------------------------------

BENCHMARK_TASKS = [
    {
        "name": "simple_3_step",
        "task": "Load data, clean text, save results",
        "dsl_response": _DSL_SIMPLE_3_STEP,
        "expected_bricks": ["load_data", "clean", "save"],
        "expected_step_count": 3,
        "uses_for_each": False,
        "uses_branch": False,
    },
    {
        "name": "filter_aggregate",
        "task": "Filter records where amount > 100, then compute the sum of amounts",
        "dsl_response": _DSL_FILTER_AGGREGATE,
        "expected_bricks": ["filter_dict_list", "aggregate_field"],
        "expected_step_count": 2,
        "uses_for_each": False,
        "uses_branch": False,
    },
    {
        "name": "for_each_pipeline",
        "task": "For each record in the list, clean the text field and validate it",
        "dsl_response": _DSL_FOR_EACH,
        "expected_bricks": ["clean", "validate"],
        "expected_step_count": None,
        "uses_for_each": True,
        "uses_branch": False,
    },
    {
        "name": "conditional_routing",
        "task": "Check if data is valid, if yes process it, if no log an error",
        "dsl_response": _DSL_BRANCH,
        "expected_bricks": ["is_valid", "process", "log_error"],
        "expected_step_count": None,
        "uses_for_each": False,
        "uses_branch": True,
    },
    {
        "name": "complex_10_step",
        "task": (
            "Load CRM data, clean all fields, filter active customers, validate emails, "
            "enrich with company data, score leads, sort by score, take top 10, "
            "format report, save output"
        ),
        "dsl_response": _DSL_COMPLEX,
        "expected_bricks": ["load_data", "clean", "filter_dict_list", "validate", "save"],
        "expected_step_count_min": 8,
        "expected_step_count": None,
        "uses_for_each": False,
        "uses_branch": False,
    },
]

# ---------------------------------------------------------------------------
# Registry with stub bricks for all expected names
# ---------------------------------------------------------------------------

_BRICK_NAMES = [
    "load_data",
    "clean",
    "save",
    "filter_dict_list",
    "aggregate_field",
    "validate",
    "enrich",
    "score",
    "sort_by",
    "take",
    "format_report",
    "process",
    "log_error",
    "is_valid",
]


def _make_registry() -> BrickRegistry:
    """Create a registry with stub bricks for all benchmark brick names."""
    reg = BrickRegistry()
    for name in _BRICK_NAMES:

        def stub(**kwargs: Any) -> dict[str, Any]:
            return {"result": None}

        reg.register(name, stub, BrickMeta(name=name, description=f"Stub: {name}"))
    return reg


def _make_composer(registry: BrickRegistry, response: str, tokens: int = 300) -> BlueprintComposer:
    """Create a mock composer that returns a predetermined DSL response."""
    composer = BlueprintComposer.__new__(BlueprintComposer)
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.complete.return_value = CompletionResult(
        text=response,
        input_tokens=tokens // 2,
        output_tokens=tokens // 2,
    )
    composer._provider = mock_provider
    from bricks.core.selector import AllBricksSelector  # noqa: PLC0415

    composer._selector = AllBricksSelector()
    composer._store = None
    return composer


# ---------------------------------------------------------------------------
# Run a single benchmark task
# ---------------------------------------------------------------------------


def _run_task(task: dict[str, Any], registry: BrickRegistry) -> dict[str, Any]:
    """Run a single benchmark task and return metrics.

    Args:
        task: A task definition dict.
        registry: Registry with stub bricks.

    Returns:
        Dict with metrics: valid, step_count, bricks_correct, tokens, time_s, uses_for_each, uses_branch.
    """
    composer = _make_composer(registry, task["dsl_response"])
    t0 = time.monotonic()
    result = composer.compose(task["task"], registry)
    elapsed = time.monotonic() - t0

    # Step count from blueprint
    step_count = 0
    if result.is_valid and result.blueprint_yaml:
        from bricks.core.loader import BlueprintLoader  # noqa: PLC0415

        try:
            bp = BlueprintLoader().load_string(result.blueprint_yaml)
            step_count = len(bp.steps)
        except Exception:
            step_count = -1

    # Brick accuracy: check expected bricks appear in dsl_code
    expected_bricks: list[str] = task.get("expected_bricks", [])
    dsl_code = result.dsl_code or task["dsl_response"]
    bricks_found = all(b in dsl_code for b in expected_bricks) if expected_bricks else True

    # for_each / branch detection
    has_for_each = "for_each" in dsl_code
    has_branch = "branch(" in dsl_code

    return {
        "valid": result.is_valid,
        "step_count": step_count,
        "expected_step_count": task.get("expected_step_count"),
        "expected_step_count_min": task.get("expected_step_count_min"),
        "bricks_correct": bricks_found,
        "tokens": result.total_tokens,
        "time_s": elapsed,
        "uses_for_each": has_for_each,
        "uses_branch": has_branch,
        "expected_for_each": task.get("uses_for_each", False),
        "expected_branch": task.get("uses_branch", False),
    }


def _format_check(val: bool) -> str:
    return "PASS" if val else "FAIL"


def _step_accuracy(metrics: dict[str, Any]) -> str:
    sc = metrics["step_count"]
    if sc < 0:
        return "err"
    expected = metrics["expected_step_count"]
    expected_min = metrics.get("expected_step_count_min")
    if expected is not None:
        return f"{sc}/{expected}" + (" PASS" if sc == expected else " FAIL")
    if expected_min is not None:
        return f"{sc}" + (" PASS" if sc >= expected_min else f" FAIL (min {expected_min})")
    return str(sc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all benchmark tasks and save the results report."""
    print(f"Bricks DSL Benchmark — v{bricks.__version__}")
    print("=" * 60)
    print()

    registry = _make_registry()
    results: list[tuple[str, dict[str, Any]]] = []

    for task in BENCHMARK_TASKS:
        print(f"  Running: {task['name']} ...")
        metrics = _run_task(task, registry)
        results.append((task["name"], metrics))
        status = "PASS" if metrics["valid"] else "FAIL"
        print(f"    {status}  steps={metrics['step_count']}  tokens={metrics['tokens']}  {metrics['time_s']:.2f}s")

    print()
    print("=" * 60)

    # Build markdown table
    lines: list[str] = [
        f"# Bricks DSL Benchmark — v{bricks.__version__}",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "| Task | DSL Valid | Steps | Bricks Correct | For-Each | Branch | Tokens | Time(s) |",
        "|------|:---------:|-------|:--------------:|:--------:|:------:|-------:|--------:|",
    ]

    pass_count = 0
    for name, m in results:
        valid = _format_check(m["valid"])
        steps = _step_accuracy(m)
        bricks_ok = _format_check(m["bricks_correct"])
        fe = _format_check(m["uses_for_each"]) if m["expected_for_each"] else "n/a"
        br = _format_check(m["uses_branch"]) if m["expected_branch"] else "n/a"
        lines.append(f"| {name} | {valid} | {steps} | {bricks_ok} | {fe} | {br} | {m['tokens']} | {m['time_s']:.2f} |")
        if m["valid"]:
            pass_count += 1

    lines += [
        "",
        f"**Result: {pass_count}/{len(results)} tasks valid**",
        "",
        "## Notes",
        "- Benchmark uses mock LLM responses (no real API calls).",
        "- Token counts reflect mock response sizes.",
        "- Step counts measured from `FlowDefinition.to_blueprint()` output.",
    ]

    report = "\n".join(lines)
    print(report)

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = results_dir / f"dsl_benchmark_{date_str}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
