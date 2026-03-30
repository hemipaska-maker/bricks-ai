"""Benchmark showcase entry point — CRM compose-mode benchmark.

Usage:
    python -m bricks_benchmark.showcase.run --live                         # all CRM scenarios
    python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline
    python -m bricks_benchmark.showcase.run --live --scenario CRM-hallucination
    python -m bricks_benchmark.showcase.run --live --scenario CRM-reuse
    python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline --scenario CRM-reuse

    # Zero-cost via ClaudeCodeProvider (no API key needed inside Claude Code session):
    python -m bricks_benchmark.showcase.run --live --claudecode --scenario CRM-pipeline
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

from bricks_benchmark.constants import DEFAULT_MODEL
from bricks_benchmark.showcase.formatters import print_cost_summary
from bricks_benchmark.showcase.metadata import make_run_dir, write_metadata

_run_logger = logging.getLogger("bricks_benchmark.showcase.run")

# ── default output dir ─────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).parent / "results"

# Valid --scenario values
CRM_SCENARIOS = {"CRM-pipeline", "CRM-hallucination", "CRM-reuse"}
VALID_SCENARIOS = {"all"} | CRM_SCENARIOS


# ── scenario expansion ──────────────────────────────────────────────────────


def expand_scenarios(raw: list[str]) -> list[str]:
    """Expand scenario names into individual sub-scenario labels.

    Args:
        raw: List of scenario names from CLI (e.g. ``['all']``, ``['CRM-pipeline']``).

    Returns:
        De-duplicated, ordered list of individual scenario labels.
    """
    order: list[str] = ["CRM-pipeline", "CRM-hallucination", "CRM-reuse"]
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


def _require_api_key() -> str:
    """Return ANTHROPIC_API_KEY or raise with a helpful message."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY is not set.\nExport it before running:  export ANTHROPIC_API_KEY=sk-...")
    return key


def _build_provider(claudecode: bool) -> Any:
    """Return LiteLLMProvider or ClaudeCodeProvider depending on flag.

    Args:
        claudecode: If True, return ClaudeCodeProvider (zero cost inside Claude Code).

    Returns:
        An LLMProvider instance.
    """
    if claudecode:
        from bricks_provider_claudecode import ClaudeCodeProvider

        return ClaudeCodeProvider(timeout=300)
    from bricks.llm.litellm_provider import LiteLLMProvider

    api_key = _require_api_key()
    return LiteLLMProvider(model=DEFAULT_MODEL, api_key=api_key)


# ── main runner ─────────────────────────────────────────────────────────────


def run_benchmark(
    scenarios: list[str],
    run_dir: Path,
    logger: logging.Logger,
    claudecode: bool = False,
) -> None:
    """Run the CRM compose-mode benchmark.

    Args:
        scenarios: List of CRM scenario labels.
        run_dir: Timestamped run directory.
        logger: Logger for recording progress.
        claudecode: If True, use ClaudeCodeProvider instead of LiteLLMProvider.
    """
    from bricks.ai.composer import BlueprintComposer

    from bricks_benchmark.showcase.crm_scenario import (
        run_crm_hallucination,
        run_crm_pipeline,
        run_crm_reuse,
    )

    provider = _build_provider(claudecode)
    composer = BlueprintComposer(provider=provider)

    t0 = time.monotonic()

    for crm_label in scenarios:
        logger.info("=== %s ===", crm_label)
        if crm_label == "CRM-pipeline":
            run_crm_pipeline(composer, run_dir)
        elif crm_label == "CRM-hallucination":
            run_crm_hallucination(composer, run_dir)
        elif crm_label == "CRM-reuse":
            run_crm_reuse(composer, run_dir)

    elapsed = time.monotonic() - t0
    print_cost_summary(0, 0, elapsed)


# ── logger setup ────────────────────────────────────────────────────────────


def _setup_logger(run_dir: Path) -> logging.Logger:
    """Create dual-output loggers: file (DEBUG) and console (INFO).

    Configures root loggers for all Bricks namespaces so every child logger
    (``bricks.ai.composer``, ``bricks_provider_claudecode.provider``, etc.)
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

    for name in ("bricks", "bricks_provider_claudecode", "bricks_benchmark"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.DEBUG)
        lg.handlers.clear()
        lg.propagate = False
        lg.addHandler(fh)
        lg.addHandler(ch)

    return logging.getLogger("bricks")


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Parse args and run the CRM benchmark."""
    parser = argparse.ArgumentParser(
        description="Bricks CRM benchmark: Bricks compose vs raw LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m bricks_benchmark.showcase.run --live\n"
            "  python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline\n"
            "  python -m bricks_benchmark.showcase.run --live --claudecode --scenario CRM-pipeline\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        default=None,
        help=(
            "Which scenario(s) to run. Accepts: all (default), "
            "CRM-pipeline, CRM-hallucination, CRM-reuse. Can be specified multiple times."
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
        help="Required. Make real LLM calls. Requires ANTHROPIC_API_KEY (or --claudecode).",
    )
    parser.add_argument(
        "--claudecode",
        action="store_true",
        default=False,
        help="Use ClaudeCodeProvider (claude -p) instead of Anthropic API. Zero cost on Max plan.",
    )
    args = parser.parse_args()

    if not args.live:
        print()
        print("Error: --live is required. This benchmark makes real API calls.")
        print()
        print("Usage:")
        print("  python -m bricks_benchmark.showcase.run --live")
        print("  python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline")
        print()
        print("Set ANTHROPIC_API_KEY before running, or use --claudecode for zero-cost runs.")
        sys.exit(1)

    raw_scenarios = args.scenarios or ["all"]
    scenarios = expand_scenarios(raw_scenarios)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = make_run_dir(output_dir)

    logger = _setup_logger(run_dir)
    provider_label = "ClaudeCodeProvider (claude -p)" if args.claudecode else "Anthropic SDK"
    logger.info("Live mode: real LLM calls via %s", provider_label)
    logger.info("Scenarios: %s", ", ".join(scenarios))
    logger.info("Bricks v%s", __version__)
    logger.info("Run folder: %s", run_dir)

    try:
        run_benchmark(scenarios, run_dir, logger, claudecode=args.claudecode)
    except Exception as exc:
        logger.error("FAILED: %s", exc, exc_info=True)
        sys.exit(1)

    write_metadata(run_dir, scenarios)
    print()


if __name__ == "__main__":
    main()
