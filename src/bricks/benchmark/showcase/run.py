"""Benchmark showcase entry point — CRM + Ticket unified Engine pipeline.

BricksEngine and RawLLMEngine receive identical input.
Both are evaluated with the same check_correctness() function.
Only the system under test changes.

Usage:
    python -m bricks.benchmark.showcase.run --live                          # all scenarios, default model
    python -m bricks.benchmark.showcase.run --live --scenario CRM-pipeline
    python -m bricks.benchmark.showcase.run --live --scenario TICKET-pipeline
    python -m bricks.benchmark.showcase.run --live --model gpt-4o-mini      # OpenAI
    python -m bricks.benchmark.showcase.run --live --model gemini/gemini-2.0-flash
    python -m bricks.benchmark.showcase.run --live --model ollama/llama3    # local, no API key
    python -m bricks.benchmark.showcase.run --live --model claudecode       # ClaudeCode (claude -p), both engines
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from bricks import __version__
from bricks.benchmark.constants import DEFAULT_MODEL
from bricks.benchmark.showcase.formatters import print_cost_summary
from bricks.benchmark.showcase.metadata import make_run_dir, write_metadata

_run_logger = logging.getLogger("bricks.benchmark.showcase.run")

# ── default output dir ─────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).parent / "results"

# Valid --scenario values
CRM_SCENARIOS = {"CRM-pipeline", "CRM-hallucination", "CRM-reuse"}
TICKET_SCENARIOS = {"TICKET-pipeline"}
VALID_SCENARIOS = {"all"} | CRM_SCENARIOS | TICKET_SCENARIOS

# Special model value that routes through ClaudeCodeProvider
_CLAUDECODE_MODEL = "claudecode"


# ── scenario expansion ──────────────────────────────────────────────────────


def expand_scenarios(raw: list[str]) -> list[str]:
    """Expand scenario names into individual sub-scenario labels.

    Args:
        raw: List of scenario names from CLI (e.g. ``['all']``, ``['CRM-pipeline']``).

    Returns:
        De-duplicated, ordered list of individual scenario labels.
    """
    order: list[str] = ["CRM-pipeline", "CRM-hallucination", "CRM-reuse", "TICKET-pipeline"]
    selected: set[str] = set()

    for s in raw:
        if s == "all":
            selected.update(order)
        else:
            selected.add(s)

    known = [s for s in order if s in selected]
    extra = [s for s in selected if s not in order]
    return known + extra


# ── helpers ──────────────────────────────────────────────────────────────────


def validate_model_env(model: str) -> None:
    """Warn if the expected API key for a model is missing from the environment.

    This is a best-effort check — LiteLLM may resolve the key from other sources.
    Ollama, local models, and claudecode need no API key and are silently skipped.

    Args:
        model: Model string (e.g. 'gpt-4o-mini', 'gemini/gemini-2.0-flash', 'claudecode').
    """
    if model in (_CLAUDECODE_MODEL,) or model.startswith("ollama/"):
        return

    provider_keys: dict[str, str] = {
        "claude": "ANTHROPIC_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gpt": "OPENAI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    for prefix, env_var in provider_keys.items():
        if model.startswith(prefix) or f"/{prefix}" in model:
            if not os.environ.get(env_var):
                _run_logger.warning(
                    "Model %r typically requires %s — not found in environment",
                    model,
                    env_var,
                )
            return


def _build_provider(model: str) -> Any:
    """Return an LLMProvider for the given model string.

    ``'claudecode'`` routes through ClaudeCodeProvider (``claude -p`` subprocess).
    Any other string is passed to LiteLLMProvider.

    Args:
        model: Model string — ``'claudecode'`` or a LiteLLM model string.

    Returns:
        An LLMProvider instance.
    """
    if model == _CLAUDECODE_MODEL:
        from bricks.providers.claudecode import ClaudeCodeProvider

        return ClaudeCodeProvider(timeout=300)

    from bricks.llm.litellm_provider import LiteLLMProvider

    return LiteLLMProvider(model=model)


# ── main runner ─────────────────────────────────────────────────────────────


def run_benchmark(
    scenarios: list[str],
    run_dir: Path,
    logger: logging.Logger,
    model: str = DEFAULT_MODEL,
) -> None:
    """Run the CRM benchmark with both engines on each scenario.

    Both BricksEngine and RawLLMEngine share the same provider instance,
    ensuring a fair comparison on identical compute.

    Args:
        scenarios: List of CRM scenario labels.
        run_dir: Timestamped run directory.
        logger: Logger for recording progress.
        model: Model string — ``'claudecode'`` or a LiteLLM model string.
    """
    from bricks.benchmark.showcase.crm_scenario import (
        run_crm_hallucination,
        run_crm_pipeline,
        run_crm_reuse,
    )
    from bricks.benchmark.showcase.engine import BricksEngine, RawLLMEngine
    from bricks.benchmark.showcase.ticket_scenario import run_ticket_pipeline

    provider = _build_provider(model)
    bricks_engine = BricksEngine(provider=provider)
    llm_engine = RawLLMEngine(provider=provider)

    t0 = time.monotonic()

    for crm_label in scenarios:
        logger.info("=== %s ===", crm_label)
        if crm_label == "CRM-pipeline":
            run_crm_pipeline(bricks_engine, llm_engine, run_dir)
        elif crm_label == "CRM-hallucination":
            run_crm_hallucination(bricks_engine, llm_engine, run_dir)
        elif crm_label == "CRM-reuse":
            run_crm_reuse(bricks_engine, llm_engine, run_dir)
        elif crm_label == "TICKET-pipeline":
            run_ticket_pipeline(bricks_engine, llm_engine, run_dir)

    elapsed = time.monotonic() - t0
    print_cost_summary(0, 0, elapsed)


# ── logger setup ────────────────────────────────────────────────────────────


def _setup_logger(run_dir: Path) -> logging.Logger:
    """Create dual-output loggers: file (DEBUG) and console (INFO).

    Configures root loggers for all Bricks namespaces so every child logger
    (``bricks.ai.composer``, ``bricks.providers.claudecode.provider``, etc.)
    writes to the same ``benchmark_live.log`` and console stream.

    Args:
        run_dir: Directory where ``benchmark_live.log`` will be written.

    Returns:
        The ``bricks`` root logger.
    """
    log_path = run_dir / "benchmark_live.log"

    file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    console_fmt = logging.Formatter("[%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_fmt)

    for name in ("bricks", "bricks.providers.claudecode", "bricks.benchmark"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.DEBUG)
        lg.handlers.clear()
        lg.propagate = False
        lg.addHandler(fh)
        lg.addHandler(ch)

    return logging.getLogger("bricks")


# ── custom scenario runner ───────────────────────────────────────────────────


def _run_custom_scenario(yaml_path: str, model: str = DEFAULT_MODEL) -> None:
    """Load a YAML scenario file and run both engines on it, printing results.

    Args:
        yaml_path: Path to the scenario YAML file.
        model: LLM model string to use for both engines.
    """
    from bricks.benchmark.showcase.engine import BricksEngine, RawLLMEngine
    from bricks.benchmark.showcase.scenario_runner import _print_side_by_side, run_scenario
    from bricks.benchmark.web.scenario_loader import _resolve_raw_data, load_scenario

    path = Path(yaml_path)
    if not path.exists():
        print(f"Error: scenario file not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)

    try:
        scenario = load_scenario(path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        raw_data = _resolve_raw_data(scenario, base_dir=path.parent)
    except ValueError as exc:
        print(f"Error resolving data: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\nScenario: {scenario.name}")
    print(f"  {scenario.description}")
    print(f"  Model: {model}")
    print()

    provider = _build_provider(model)
    bricks_engine = BricksEngine(provider=provider)
    llm_engine = RawLLMEngine(provider=provider)

    # Adapt scenario to BenchmarkTask protocol (dataclass with required fields)
    from dataclasses import dataclass

    @dataclass
    class _ScenarioTask:
        task_text: str
        raw_api_response: str
        expected_outputs: dict[str, Any]
        required_bricks: list[str]

    task = _ScenarioTask(
        task_text=scenario.task_text,
        raw_api_response=raw_data,
        expected_outputs=scenario.expected_outputs or {},
        required_bricks=scenario.required_bricks or [],
    )

    bricks_result = run_scenario(bricks_engine, task)
    llm_result = run_scenario(llm_engine, task)
    _print_side_by_side(scenario.name, bricks_result, llm_result, 0)


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Parse args and run the CRM benchmark."""
    parser = argparse.ArgumentParser(
        description="Bricks CRM benchmark: BricksEngine vs RawLLMEngine, same input, same checker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m bricks.benchmark.showcase.run --live\n"
            "  python -m bricks.benchmark.showcase.run --live --model gpt-4o-mini\n"
            "  python -m bricks.benchmark.showcase.run --live --model gemini/gemini-2.0-flash\n"
            "  python -m bricks.benchmark.showcase.run --live --model ollama/llama3\n"
            "  python -m bricks.benchmark.showcase.run --live --model claudecode\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        default=None,
        help=(
            "Which scenario(s) to run. Accepts: all (default), "
            "CRM-pipeline, CRM-hallucination, CRM-reuse, TICKET-pipeline. "
            "Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=(
            f"Model to use for both engines (default: {DEFAULT_MODEL}). "
            "Use 'claudecode' to route through ClaudeCodeProvider (claude -p, free on Max plan). "
            "Other examples: gpt-4o-mini, gemini/gemini-2.0-flash, ollama/llama3. "
            "API key is read from the corresponding env var automatically."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT),
        help="Base directory for results (a timestamped subfolder is created inside).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Required. Make real LLM calls. Requires an API key (or --model claudecode).",
    )
    parser.add_argument(
        "--custom",
        type=str,
        default=None,
        metavar="YAML_FILE",
        help=(
            "Path to a custom scenario YAML file. "
            "Runs both engines on the scenario and prints a side-by-side comparison. "
            "Example: --custom examples/basic_custom.yaml"
        ),
    )
    args = parser.parse_args()

    if not args.live:
        print()
        print("Error: --live is required. This benchmark makes real API calls.")
        print()
        print("Usage:")
        print("  python -m bricks.benchmark.showcase.run --live")
        print("  python -m bricks.benchmark.showcase.run --live --model gpt-4o-mini")
        print("  python -m bricks.benchmark.showcase.run --live --model claudecode")
        print()
        print("API key is read from env (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.),")
        print("or use --model claudecode for zero-cost runs inside a Claude Code session.")
        sys.exit(1)

    if args.custom:
        _run_custom_scenario(args.custom, model=args.model)
        return

    raw_scenarios = args.scenarios or ["all"]
    scenarios = expand_scenarios(raw_scenarios)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = make_run_dir(output_dir)

    logger = _setup_logger(run_dir)

    if args.model == _CLAUDECODE_MODEL:
        provider_label = "ClaudeCodeProvider (claude -p)"
        logger.info("--model claudecode: both engines via ClaudeCode (fully free)")
    else:
        provider_label = f"LiteLLMProvider ({args.model})"
        logger.info("Benchmark model: %s", args.model)
        validate_model_env(args.model)

    logger.info("Provider:  %s", provider_label)
    logger.info("Scenarios: %s", ", ".join(scenarios))
    logger.info("Bricks v%s", __version__)
    logger.info("Run folder: %s", run_dir)

    try:
        run_benchmark(scenarios, run_dir, logger, model=args.model)
    except Exception as exc:
        logger.error("FAILED: %s", exc, exc_info=True)
        sys.exit(1)

    write_metadata(run_dir, scenarios, model=args.model)
    print()


if __name__ == "__main__":
    main()
