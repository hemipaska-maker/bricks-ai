"""Benchmark showcase entry point — apples-to-apples only.

Usage:
    python -m benchmark.showcase.run --live                        # all scenarios
    python -m benchmark.showcase.run --live --scenario A2          # complexity curve
    python -m benchmark.showcase.run --live --scenario A2-3        # single sub-scenario
    python -m benchmark.showcase.run --live --scenario C2          # reuse economics
    python -m benchmark.showcase.run --live --scenario D2          # determinism
    python -m benchmark.showcase.run --live --scenario A2-3 --scenario C2  # multiple
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bricks import __version__
from bricks.core import BrickRegistry

# ── default output dir ─────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).parent / "results"

# Model used for cost estimation
_MODEL = "claude-haiku-4-5-20251001"

# Approximate pricing per 1M tokens (claude-haiku-4-5-20251001)
_PRICE_INPUT_PER_M = 0.80
_PRICE_OUTPUT_PER_M = 4.00

# Valid --scenario values
VALID_SCENARIOS = {"all", "A2", "A2-3", "A2-6", "A2-12", "C2", "D2"}

# Valid --mode values
VALID_MODES = {"tool_use", "compose"}


# ── git helpers ─────────────────────────────────────────────────────────────


def _git_info() -> tuple[str, str, bool]:
    """Return (commit_hash, branch, is_dirty)."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return commit, branch, dirty
    except Exception:
        return "unknown", "unknown", False


def _anthropic_sdk_version() -> str:
    """Return installed anthropic SDK version or 'not installed'."""
    try:
        import anthropic  # type: ignore[import-not-found]

        return str(anthropic.__version__)
    except Exception:
        return "not installed"


# ── run folder + metadata ────────────────────────────────────────────────────


def _make_run_dir(output_dir: Path) -> Path:
    """Create and return a unique timestamped run directory."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{ts}_v{__version__}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_metadata(run_dir: Path, scenarios_run: list[str]) -> Path:
    """Write run_metadata.json to run_dir and return the path."""
    commit, branch, dirty = _git_info()
    metadata: dict[str, object] = {
        "bricks_version": __version__,
        "python_version": sys.version.split()[0],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ai_model": _MODEL,
        "ai_provider": "anthropic",
        "anthropic_sdk_version": _anthropic_sdk_version(),
        "mode": "live",
        "command": " ".join(["python", "-m", "benchmark.showcase.run", *sys.argv[1:]]),
        "scenarios_run": scenarios_run,
        "os": f"{platform.system()} {platform.release()}",
        "git_commit": commit,
        "git_branch": branch,
        "git_dirty": dirty,
    }
    out = run_dir / "run_metadata.json"
    out.write_text(json.dumps(metadata, indent=2))
    return out


# ── registry builders ───────────────────────────────────────────────────────


def _build_math_registry_a3() -> BrickRegistry:
    """Build registry for A-3 (multiply, round_value, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, format_result)


def _build_math_registry_a6() -> BrickRegistry:
    """Build registry for A-6 (multiply, round_value, add, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, format_result)


def _build_math_registry_a12() -> BrickRegistry:
    """Build registry for A-12 (multiply, round_value, add, subtract, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value, subtract
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, subtract, format_result)


# ── per-turn callback for real-time logging ─────────────────────────────────


def _make_turn_callback(label: str) -> Any:
    """Return a callback that prints per-turn info for the given scenario label.

    Args:
        label: Scenario label like 'A2-3'.

    Returns:
        A callable matching the AgentRunner on_turn callback signature.
    """

    def callback(
        turn: int,
        mode: str,
        input_tokens: int,
        output_tokens: int,
        elapsed: float,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        total = input_tokens + output_tokens
        if tool_calls:
            for tc in tool_calls:
                name = tc["name"]
                summary = tc.get("summary", "")
                print(f"  [{label}] Turn {turn}/{mode}: tool_call {name} {summary} ({elapsed:.1f}s)")
        else:
            print(
                f"  [{label}] Turn {turn}/{mode}: "
                f"{input_tokens:,} input + {output_tokens:,} output = {total:,} tokens ({elapsed:.1f}s)"
            )

    return callback


# ── cost helpers ────────────────────────────────────────────────────────────


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for the given token counts."""
    return (input_tokens * _PRICE_INPUT_PER_M + output_tokens * _PRICE_OUTPUT_PER_M) / 1_000_000


# ── scenario expansion ──────────────────────────────────────────────────────


def expand_scenarios(raw: list[str]) -> list[str]:
    """Expand scenario names into individual sub-scenario labels.

    Args:
        raw: List of scenario names from CLI (e.g. ``['all']``, ``['A2', 'C2']``).

    Returns:
        De-duplicated, ordered list of individual scenario labels.
    """
    order = ["A2-3", "A2-6", "A2-12", "C2", "D2"]
    selected: set[str] = set()

    for s in raw:
        if s == "all":
            selected.update(order)
        elif s == "A2":
            selected.update(["A2-3", "A2-6", "A2-12"])
        else:
            selected.add(s)

    return [s for s in order if s in selected]


# ── summary table ───────────────────────────────────────────────────────────


def _print_a2_table(a2_results: list[dict[str, Any]]) -> None:
    """Print the A2 complexity curve summary table."""
    print()
    print("  +----------+------------+------------+--------+--------------+")
    print("  | Task     | No Tools   | Bricks     | Ratio  | Bricks turns |")
    print("  +----------+------------+------------+--------+--------------+")
    for r in a2_results:
        nt = r["no_tools"]["total_tokens"]
        br = r["bricks"]["total_tokens"]
        ratio = f"{nt / br:.1f}x" if br > 0 else "inf"
        turns = r["bricks"]["turns"]
        print(f"  | {r['label']:<8} | {nt:>10,} | {br:>10,} | {ratio:>6} | {turns:>12} |")
    print("  +----------+------------+------------+--------+--------------+")
    print()


# ── main runner ─────────────────────────────────────────────────────────────


def _require_api_key() -> str:
    """Return ANTHROPIC_API_KEY or raise with a helpful message."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY is not set.\nExport it before running:  export ANTHROPIC_API_KEY=sk-...")
    return key


def run_benchmark(
    scenarios: list[str],
    run_dir: Path,
    logger: logging.Logger,
) -> None:
    """Run the apples-to-apples benchmark for the given scenarios.

    Args:
        scenarios: List of scenario labels (e.g. ``['A2-3', 'C2']``).
        run_dir: Timestamped run directory.
        logger: Logger for recording progress.
    """
    from benchmark.mcp.agent_runner import AgentRunner
    from benchmark.mcp.report import write_apples_json, write_apples_markdown
    from benchmark.mcp.scenarios.a2_complexity import run_a2_3, run_a2_6, run_a2_12
    from benchmark.mcp.scenarios.c2_reuse import run_c2
    from benchmark.mcp.scenarios.d2_determinism import run_d2

    api_key = _require_api_key()
    runner = AgentRunner(api_key=api_key)
    apples_dir = run_dir / "apples_to_apples"
    apples_dir.mkdir(parents=True, exist_ok=True)

    total_input = 0
    total_output = 0
    t0 = time.monotonic()

    # ── A2: Complexity Curve ──────────────────────────────────────────────
    a2_scenarios = [s for s in scenarios if s.startswith("A2-")]
    a2_results: list[dict[str, Any]] = []

    a2_dispatch: dict[str, tuple[Any, Any]] = {
        "A2-3": (run_a2_3, _build_math_registry_a3),
        "A2-6": (run_a2_6, _build_math_registry_a6),
        "A2-12": (run_a2_12, _build_math_registry_a12),
    }

    for label in a2_scenarios:
        fn, reg_fn = a2_dispatch[label]
        logger.info("=== %s ===", label)
        print(f"  [{label}] Running...", flush=True)
        result = fn(runner, reg_fn(), on_turn=_make_turn_callback(label))

        nt = result["no_tools"]
        br = result["bricks"]

        # Log execution result and blueprint YAML
        if br.get("execution_result"):
            print(f"  [{label}]   Execution: OK — outputs: {br['execution_result']}")
            logger.debug("%s execution outputs: %s", label, br["execution_result"])
        if br.get("blueprint_yaml"):
            logger.debug("%s blueprint YAML:\n%s", label, br["blueprint_yaml"])

        # Log no-tools tokens
        print(f"  [{label}] No-tools: {nt['total_tokens']:,} tokens")
        ratio = f"{nt['total_tokens'] / br['total_tokens']:.1f}x" if br["total_tokens"] > 0 else "inf"
        print(f"  [{label}] done  no_tools={nt['total_tokens']:,}  bricks={br['total_tokens']:,}  ({ratio})")

        total_input += nt.get("input_tokens", 0) + br.get("input_tokens", 0)
        total_output += nt.get("output_tokens", 0) + br.get("output_tokens", 0)
        a2_results.append(result)

    if a2_results:
        _print_a2_table(a2_results)

    # ── C2: Reuse Economics ───────────────────────────────────────────────
    c2_result: dict[str, Any] | None = None
    if "C2" in scenarios:
        logger.info("=== C2: Reuse Economics ===")
        print("  [C2] Running (10 runs)...", flush=True)
        c2_result = run_c2(runner, _build_math_registry_a6(), on_turn=_make_turn_callback("C2"))

        nt_total = c2_result["no_tools"]["total_tokens"]
        br_total = c2_result["bricks"]["total_tokens"]
        ratio = f"{nt_total / br_total:.1f}x" if br_total > 0 else "inf"
        print(f"  [C2] done  no_tools={nt_total:,}  bricks={br_total:,}  ({ratio})")

        total_input += c2_result.get("no_tools", {}).get("input_tokens", 0)
        total_input += c2_result.get("bricks", {}).get("input_tokens", 0)
        total_output += c2_result.get("no_tools", {}).get("output_tokens", 0)
        total_output += c2_result.get("bricks", {}).get("output_tokens", 0)
        print()

    # ── D2: Determinism ───────────────────────────────────────────────────
    d2_result: dict[str, Any] | None = None
    if "D2" in scenarios:
        logger.info("=== D2: Determinism ===")
        print("  [D2] Running (5 runs)...", flush=True)
        d2_result = run_d2(runner, _build_math_registry_a6(), on_turn=_make_turn_callback("D2"))

        nt_unique = d2_result["no_tools"]["unique_outputs"]
        br_unique = d2_result["bricks"]["unique_blueprints"]
        print(f"  [D2] done  unique_codes={nt_unique}/5  unique_blueprints={br_unique}/5")
        print()

    # ── Write outputs ─────────────────────────────────────────────────────
    json_path = write_apples_json(
        apples_dir,
        "live",
        a2_results,
        c2_result or {},
        d2_result or {},
    )
    md_path = write_apples_markdown(apples_dir, a2_results, c2_result or {})

    elapsed = time.monotonic() - t0
    cost = _estimate_cost(total_input, total_output)

    # ── Total cost summary ────────────────────────────────────────────────
    print(f"  Total: {total_input + total_output:,} tokens used (input: {total_input:,} + output: {total_output:,})")
    print(f"  Estimated cost: ~${cost:.3f} ({_MODEL})")
    print(f"  Elapsed: {elapsed:.1f}s")
    print()
    print(f"  results.json -> {json_path}")
    print(f"  summary.md   -> {md_path}")


# ── compose mode helpers ───────────────────────────────────────────────────


def _count_yaml_steps(yaml_text: str) -> int:
    """Count steps in a YAML blueprint string."""
    return yaml_text.count("- name:")


def _log_compose_calls(
    label: str,
    result: Any,
    logger: logging.Logger,
) -> None:
    """Print and log per-call detail for a compose result.

    Args:
        label: Scenario label (e.g. 'A2-12').
        result: ComposeResult with calls list.
        logger: Logger for DEBUG-level detail.
    """
    for call in result.calls:
        suffix = " (retry)" if call.call_number > 1 else ""
        total = call.input_tokens + call.output_tokens
        print(
            f"  [{label}] Call {call.call_number}/compose{suffix}: "
            f"{call.input_tokens:,} input + {call.output_tokens:,} output "
            f"= {total:,} tokens ({call.duration_seconds:.1f}s)"
        )

        lines = len(call.yaml_text.strip().splitlines())
        steps = _count_yaml_steps(call.yaml_text)
        print(f"  [{label}]   YAML: {lines} lines, {steps} steps")

        if call.is_valid:
            print(f"  [{label}]   Validation: OK")
        else:
            errors_str = "; ".join(call.validation_errors[:3])
            print(f"  [{label}]   Validation: FAILED — {errors_str}")

        logger.debug("%s call %d YAML:\n%s", label, call.call_number, call.yaml_text)
        if call.validation_errors:
            logger.debug(
                "%s call %d errors: %s",
                label,
                call.call_number,
                call.validation_errors,
            )


# ── compose mode runner ────────────────────────────────────────────────────


def run_benchmark_compose(
    scenarios: list[str],
    run_dir: Path,
    logger: logging.Logger,
) -> None:
    """Run the compose-mode benchmark (single-call YAML, no tool_use).

    Args:
        scenarios: List of scenario labels (e.g. ``['A2-12']``).
        run_dir: Timestamped run directory.
        logger: Logger for recording progress.
    """
    from benchmark.mcp.agent_runner import AgentRunner
    from benchmark.mcp.scenarios import TASK_A2_3, TASK_A2_6, TASK_A2_12
    from bricks.ai.composer import BlueprintComposer
    from bricks.core.engine import BlueprintEngine
    from bricks.core.loader import BlueprintLoader

    api_key = _require_api_key()
    composer = BlueprintComposer(api_key=api_key)
    runner = AgentRunner(api_key=api_key)
    loader = BlueprintLoader()

    total_input = 0
    total_output = 0
    t0 = time.monotonic()

    a2_tasks: dict[str, tuple[str, Any]] = {
        "A2-3": (TASK_A2_3, _build_math_registry_a3),
        "A2-6": (TASK_A2_6, _build_math_registry_a6),
        "A2-12": (TASK_A2_12, _build_math_registry_a12),
    }

    a2_scenarios = [s for s in scenarios if s.startswith("A2-")]

    for label in a2_scenarios:
        task_str, reg_fn = a2_tasks[label]
        registry = reg_fn()
        logger.info("=== %s (compose) ===", label)
        print(f"  [{label}] Composing...", flush=True)

        result = composer.compose(task_str, registry)
        total_input += result.total_input_tokens
        total_output += result.total_output_tokens

        # Per-call detail
        _log_compose_calls(label, result, logger)

        # Execute the composed blueprint if valid
        if result.is_valid:
            try:
                bp_def = loader.load_string(result.blueprint_yaml)
                engine = BlueprintEngine(registry=registry)
                exec_result = engine.run(bp_def, inputs={})
                print(f"  [{label}]   Execution: OK — outputs: {exec_result.outputs}")
                logger.info("%s execution outputs: %s", label, exec_result.outputs)
            except Exception as exc:
                print(f"  [{label}]   Execution: FAILED — {exc}")
                logger.warning("%s execution failed: %s", label, exc)

        # Run no-tools for comparison
        nt_result = runner.run_without_tools(task_str)
        total_input += nt_result.total_input_tokens
        total_output += nt_result.total_output_tokens
        nt_tokens = nt_result.total_tokens
        print(f"  [{label}] No-tools: {nt_tokens:,} tokens")

        # Summary line
        ratio = f"{result.total_tokens / nt_tokens:.1f}x" if nt_tokens > 0 else "N/A"
        print(f"  [{label}] done  compose={result.total_tokens:,}  no_tools={nt_tokens:,}  ({ratio})")
        print()

    elapsed = time.monotonic() - t0
    cost = _estimate_cost(total_input, total_output)

    print(f"  Total: {total_input + total_output:,} tokens (input: {total_input:,} + output: {total_output:,})")
    print(f"  Estimated cost: ~${cost:.3f} ({_MODEL})")
    print(f"  Elapsed: {elapsed:.1f}s")
    print()


# ── logger setup ────────────────────────────────────────────────────────────


def _setup_logger(run_dir: Path) -> logging.Logger:
    """Create a logger that writes to console (WARNING+) and a log file (DEBUG).

    Args:
        run_dir: Directory where ``benchmark_live.log`` will be written.

    Returns:
        Configured logger.
    """
    log_path = run_dir / "benchmark_live.log"
    logger = logging.getLogger("bricks.showcase")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    return logger


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Parse args and run the apples-to-apples benchmark."""
    parser = argparse.ArgumentParser(
        description="Bricks apples-to-apples benchmark: same agent, tools on vs off.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m benchmark.showcase.run --live                        # all scenarios\n"
            "  python -m benchmark.showcase.run --live --scenario A2-3        # single sub-scenario\n"
            "  python -m benchmark.showcase.run --live --scenario A2          # all A2 sub-scenarios\n"
            "  python -m benchmark.showcase.run --live --scenario A2-3 --scenario C2  # multiple\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        default=None,
        help=(
            "Which scenario(s) to run. "
            "Accepts: all (default), A2, A2-3, A2-6, A2-12, C2, D2. "
            "Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT),
        help="Base directory for results (a timestamped subfolder is created inside).",
    )
    parser.add_argument(
        "--mode",
        default="tool_use",
        choices=sorted(VALID_MODES),
        help="Benchmark mode: tool_use (multi-turn) or compose (single-call YAML). Default: tool_use.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Required. Make real Anthropic API calls. Requires ANTHROPIC_API_KEY.",
    )
    args = parser.parse_args()

    if not args.live:
        print()
        print("Error: --live is required. This benchmark makes real API calls.")
        print()
        print("Usage:")
        print("  python -m benchmark.showcase.run --live")
        print("  python -m benchmark.showcase.run --live --scenario A2-3")
        print()
        print("Set ANTHROPIC_API_KEY before running.")
        sys.exit(1)

    raw_scenarios = args.scenarios or ["all"]
    invalid = [s for s in raw_scenarios if s not in VALID_SCENARIOS]
    if invalid:
        print(f"Error: invalid scenario(s): {', '.join(invalid)}")
        print(f"Valid values: {', '.join(sorted(VALID_SCENARIOS))}")
        sys.exit(1)

    scenarios = expand_scenarios(raw_scenarios)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = _make_run_dir(output_dir)

    logger = _setup_logger(run_dir)
    logger.info("Live mode: real API calls via Anthropic SDK")
    logger.info("Scenarios: %s", ", ".join(scenarios))

    mode = args.mode
    print()
    print(f"Bricks v{__version__}")
    print(f"Run folder: {run_dir}")
    print(f"Mode: {mode}")
    print(f"Scenarios: {', '.join(scenarios)}")
    print()

    try:
        if mode == "compose":
            run_benchmark_compose(scenarios, run_dir, logger)
        else:
            run_benchmark(scenarios, run_dir, logger)
    except Exception as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)

    _write_metadata(run_dir, scenarios)
    print()


if __name__ == "__main__":
    main()
