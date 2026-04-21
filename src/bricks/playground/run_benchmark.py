"""Main entry point: run the Bricks vs Python benchmark.

Usage:
    python -m bricks.playground.run_benchmark              # demo mode
    python -m bricks.playground.run_benchmark --live       # live mode (real API)
    python -m bricks.playground.run_benchmark --verbose    # show YAML/Python code
    python -m bricks.playground.run_benchmark --scenario 3 # one scenario only
"""

from __future__ import annotations

import argparse
import sys

from bricks.core import BrickRegistry
from bricks.playground.ai_generator import (
    generate_bricks_yaml,
    generate_python_code,
)
from bricks.playground.domain_bricks import build_registry
from bricks.playground.report import (
    print_full_report,
)
from bricks.playground.runner import BricksRunner, PythonRunner, RunResult
from bricks.playground.scenarios import ALL_SCENARIOS, Scenario


def _generate_live_code(scenarios: list[Scenario], registry: BrickRegistry) -> None:
    """Generate YAML and Python code via API for each scenario."""
    # Build list of available functions for Python generation
    available_functions = [
        ("load_csv_data", "Load CSV data from a named source"),
        ("filter_rows", "Filter rows by column condition (>, <, ==)"),
        ("calculate_stats", "Calculate min/max/mean/sum for a numeric column"),
        ("word_count", "Count words in a text column"),
        ("generate_summary", "Generate a formatted text summary"),
        ("format_number", "Format a number with prefix/suffix and decimals"),
        ("validate_schema", "Validate that rows contain required columns"),
        ("merge_reports", "Merge multiple text reports with separator"),
        ("multiply", "Multiply two numbers"),
        ("divide", "Divide two numbers"),
    ]

    for scenario in scenarios:
        print(f"Generating for scenario {scenario.name}...")

        try:
            # Pass input names + expected output keys so the AI generates
            # YAML that is compatible with the scenario's test data.
            yaml_code, bricks_tokens = generate_bricks_yaml(
                scenario.intent,
                registry,
                inputs=scenario.inputs,
                expected_outputs=list(scenario.expected_output.keys()),
            )
            scenario.bricks_yaml = yaml_code
            scenario.live_bricks_tokens = bricks_tokens
            scenario.live_mode = True
            print(f"  YAML: {len(yaml_code)} chars, {bricks_tokens} tokens")
        except Exception as e:
            print(f"  YAML generation failed: {e}")
            sys.exit(1)

        try:
            # Pass inputs so AI uses inputs['key'] instead of hardcoding.
            python_code, python_tokens = generate_python_code(
                scenario.intent, available_functions, inputs=scenario.inputs
            )
            scenario.python_code = python_code
            scenario.live_python_tokens = python_tokens
            print(f"  Python: {len(python_code)} chars, {python_tokens} tokens")
        except Exception as e:
            print(f"  Python generation failed: {e}")
            sys.exit(1)

        print()


def _run_one(
    scenario: Scenario,
    bricks_runner: BricksRunner,
    python_runner: PythonRunner,
    verbose: bool = False,
) -> tuple[RunResult, RunResult]:
    """Run a single scenario through both approaches."""
    if verbose:
        print(f"\n--- Scenario: {scenario.name} ({scenario.category}) ---")
        print(f"Intent: {scenario.intent}\n")
        print("  [Bricks YAML]")
        for line in scenario.bricks_yaml.strip().splitlines():
            print(f"    {line}")
        print()
        print("  [Python Code]")
        for line in scenario.python_code.strip().splitlines():
            print(f"    {line}")
        print()

    br = bricks_runner.run(scenario)
    pr = python_runner.run(scenario)

    if verbose:
        print(f"  Bricks: {br.status:<18} errors={br.errors}")
        print(f"  Python: {pr.status:<18} errors={pr.errors}")
        if br.tokens and pr.tokens:
            print(f"  Tokens: bricks={br.tokens.total:,}  python={pr.tokens.total:,}")
        print()

    return br, pr


def main() -> None:
    """Parse arguments and run the benchmark."""
    parser = argparse.ArgumentParser(
        description="Bricks vs Raw Python -- AI Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=("Use live API calls for YAML/Python generation (requires ANTHROPIC_API_KEY)."),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show YAML/Python code and detailed errors for each scenario.",
    )
    parser.add_argument(
        "--scenario",
        type=int,
        default=0,
        help="Run a specific scenario (1-10). Default: all.",
    )
    args = parser.parse_args()

    registry = build_registry()
    bricks_runner = BricksRunner(registry=registry)
    python_runner = PythonRunner()

    if args.scenario:
        if args.scenario < 1 or args.scenario > len(ALL_SCENARIOS):
            print(f"Error: --scenario must be 1-{len(ALL_SCENARIOS)}")
            sys.exit(1)
        scenarios = [ALL_SCENARIOS[args.scenario - 1]]
    else:
        scenarios = ALL_SCENARIOS

    # Live mode: generate YAML and Python code via AI
    if args.live:
        print("Running in LIVE mode -- generating YAML and Python code via API...")
        print()
        _generate_live_code(scenarios, registry)

    bricks_results: list[RunResult] = []
    python_results: list[RunResult] = []

    for scn in scenarios:
        br, pr = _run_one(scn, bricks_runner, python_runner, verbose=args.verbose)
        bricks_results.append(br)
        python_results.append(pr)

    # Print the full report
    if args.verbose:
        print("\n")
    print_full_report(scenarios, bricks_results, python_results)


if __name__ == "__main__":
    main()
