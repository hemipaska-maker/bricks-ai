"""Benchmark showcase entry point — apples-to-apples only.

Usage:
    python -m benchmark.showcase.run --live                              # all scenarios
    python -m benchmark.showcase.run --live --scenario A                 # A presets (5, 25, 50)
    python -m benchmark.showcase.run --live --scenario A --steps 12      # single step count
    python -m benchmark.showcase.run --live --scenario C                 # reuse economics
    python -m benchmark.showcase.run --live --scenario D                 # determinism
    python -m benchmark.showcase.run --live --scenario A --scenario C    # multiple
    python -m benchmark.showcase.run --live --mode compose --scenario A --steps 5
    python -m benchmark.showcase.run --live --mode compose --scenario CRM-pipeline
    python -m benchmark.showcase.run --live --mode compose --scenario CRM-hallucination
    python -m benchmark.showcase.run --live --mode compose --scenario CRM-reuse

    # Zero-cost via ClaudeCodeProvider (no API key needed inside Claude Code session):
    python -m benchmark.showcase.run --live --claudecode --mode compose --scenario CRM-pipeline
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

from bricks_benchmark.constants import DEFAULT_MODEL, Scenario
from bricks_benchmark.showcase.formatters import (
    estimate_cost,
    log_compose_calls,
    print_a2_table,
    print_cost_summary,
)
from bricks_benchmark.showcase.metadata import make_run_dir, write_metadata

_run_logger = logging.getLogger("bricks_benchmark.showcase.run")

# ── default output dir ─────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).parent / "results"

# Default step presets for scenario A
A_PRESETS: list[int] = [5, 25, 50]

# Valid --scenario values
CRM_SCENARIOS = {"CRM-pipeline", "CRM-hallucination", "CRM-reuse"}
VALID_SCENARIOS = {"all", Scenario.A.value, Scenario.C.value, Scenario.D.value} | CRM_SCENARIOS

# Valid --mode values
VALID_MODES = {"tool_use", "compose"}


# ── per-turn callback for real-time logging ─────────────────────────────────


def _make_turn_callback(label: str) -> Any:
    """Return a callback that prints per-turn info for the given scenario label.

    Args:
        label: Scenario label like 'A-5'.

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
        """Log a single turn."""
        total = input_tokens + output_tokens
        if tool_calls:
            for tc in tool_calls:
                tc_name = tc["name"]
                summary = tc.get("summary", "")
                _run_logger.info(
                    "[%s] Turn %d/%s: tool_call %s %s (%.1fs)", label, turn, mode, tc_name, summary, elapsed
                )
        else:
            _run_logger.info(
                "[%s] Turn %d/%s: %d input + %d output = %d tokens (%.1fs)",
                label,
                turn,
                mode,
                input_tokens,
                output_tokens,
                total,
                elapsed,
            )

    return callback


# ── scenario expansion ──────────────────────────────────────────────────────


def expand_scenarios(
    raw: list[str],
    steps: int | None = None,
) -> list[str]:
    """Expand scenario names into individual sub-scenario labels.

    Args:
        raw: List of scenario names from CLI (e.g. ``['all']``, ``['A', 'C']``).
        steps: If specified, use this step count instead of presets for A.

    Returns:
        De-duplicated, ordered list of individual scenario labels.
    """
    a_labels = [f"A-{steps}"] if steps is not None else [f"A-{n}" for n in A_PRESETS]

    order: list[str] = [*a_labels, Scenario.C.value, Scenario.D.value, "CRM-pipeline", "CRM-hallucination", "CRM-reuse"]
    selected: set[str] = set()

    for s in raw:
        if s == "all":
            selected.update(order)
        elif s == Scenario.A.value:
            selected.update(a_labels)
        else:
            selected.add(s)

    # Preserve order for known scenarios; append unknown CRM-style labels at end
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


class _ProviderRunner:
    """Drop-in replacement for AgentRunner.run_without_tools using an LLMProvider.

    Used when --claudecode is set so the no-tools baseline also routes through
    claude -p instead of the Anthropic SDK.
    """

    _SYSTEM = (
        "You are a Python expert. The user gives you a data processing task. "
        "Reply with a single Python code block that solves the task. "
        "Use only the standard library. No explanations — just code."
    )

    def __init__(self, provider: Any) -> None:
        """Initialise with an LLMProvider.

        Args:
            provider: Any LLMProvider instance.
        """
        self._provider = provider

    def run_without_tools(self, task: str, **_kwargs: Any) -> Any:
        """Run the no-tools baseline via LLMProvider.complete().

        Token counts are set to 0 because ClaudeCodeProvider does not expose
        token usage from the subprocess.

        Args:
            task: Natural language task description.

        Returns:
            AgentResult with mode="no_tools" and zero token counts.
        """
        import time

        from bricks_benchmark.mcp.agent_result import AgentResult

        t0 = time.monotonic()
        answer = self._provider.complete(task, system=self._SYSTEM)
        return AgentResult(
            task=task,
            mode="no_tools",
            turns=1,
            total_input_tokens=0,
            total_output_tokens=0,
            total_tokens=0,
            final_answer=answer,
            duration_seconds=time.monotonic() - t0,
        )


# ── main runner ─────────────────────────────────────────────────────────────


def run_benchmark(
    scenarios: list[str],
    run_dir: Path,
    logger: logging.Logger,
) -> None:
    """Run the apples-to-apples benchmark (tool_use mode).

    Args:
        scenarios: List of scenario labels (e.g. ``['A-5', 'C']``).
        run_dir: Timestamped run directory.
        logger: Logger for recording progress.
    """
    from bricks_benchmark.mcp.agent_runner import AgentRunner
    from bricks_benchmark.mcp.report import write_apples_json, write_apples_markdown
    from bricks_benchmark.mcp.scenarios.a2_complexity import run_a
    from bricks_benchmark.mcp.scenarios.c2_reuse import run_c
    from bricks_benchmark.mcp.scenarios.d2_determinism import run_d
    from bricks_benchmark.showcase.registry_factory import build_registry
    from bricks_benchmark.showcase.result_writer import (
        BaselineRecord,
        ExecutionRecord,
        ScenarioResult,
        TotalRecord,
        check_correctness,
        check_no_tools_answer,
        write_scenario_result,
    )

    api_key = _require_api_key()
    runner = AgentRunner(api_key=api_key)
    apples_dir = run_dir / "apples_to_apples"
    apples_dir.mkdir(parents=True, exist_ok=True)

    total_input = 0
    total_output = 0
    t0 = time.monotonic()

    # ── A: Complexity Curve ──────────────────────────────────────────────
    from bricks_benchmark.mcp.scenarios.task_generator import TaskGenerator

    a_scenarios = [s for s in scenarios if s.startswith("A-")]
    a_results: list[dict[str, Any]] = []

    for label in a_scenarios:
        step_count = int(label.split("-")[1])
        gen = TaskGenerator()
        task = gen.generate(step_count)
        registry = build_registry(task.required_bricks)

        logger.info("=== %s ===", label)
        logger.info("[%s] Running...", label)
        result = run_a(runner, task.task_text, step_count, registry, on_turn=_make_turn_callback(label))

        nt = result["no_tools"]
        br = result["bricks"]

        if br.get("execution_result"):
            logger.info("[%s]   Execution: OK — outputs: %s", label, br["execution_result"])
            logger.debug("%s execution outputs: %s", label, br["execution_result"])
        if br.get("blueprint_yaml"):
            logger.debug("%s blueprint YAML:\n%s", label, br["blueprint_yaml"])

        nt_correct = check_no_tools_answer(nt.get("final_answer", ""), task.expected_outputs)
        nt_label = "CORRECT" if nt_correct else "WRONG"
        logger.info("[%s] No-tools: %d tokens  answer=%s", label, nt["total_tokens"], nt_label)
        logger.info("%s no-tools answer: %s", label, nt_label)
        ratio = f"{nt['total_tokens'] / br['total_tokens']:.1f}x" if br["total_tokens"] > 0 else "inf"
        logger.info("[%s] done  no_tools=%d  bricks=%d  (%s)", label, nt["total_tokens"], br["total_tokens"], ratio)

        total_input += nt.get("input_tokens", 0) + br.get("input_tokens", 0)
        total_output += nt.get("output_tokens", 0) + br.get("output_tokens", 0)
        a_results.append(result)

        # Write structured result JSON
        actual_outputs = br.get("execution_result") or {}
        filtered_expected = {k: v for k, v in task.expected_outputs.items() if k in actual_outputs}
        correct = check_correctness(actual_outputs, filtered_expected) if actual_outputs else False
        cost = estimate_cost(br.get("input_tokens", 0), br.get("output_tokens", 0))
        ratio_val = nt["total_tokens"] / br["total_tokens"] if br["total_tokens"] > 0 else 0.0
        scenario_result = ScenarioResult(
            scenario=label,
            mode="tool_use",
            steps=step_count,
            model=DEFAULT_MODEL,
            task_text=task.task_text,
            execution=ExecutionRecord(
                success=bool(actual_outputs),
                actual_outputs=actual_outputs,
                expected_outputs=filtered_expected,
                correct=correct,
            ),
            totals=TotalRecord(
                api_calls=br.get("turns", 0),
                input_tokens=br.get("input_tokens", 0),
                output_tokens=br.get("output_tokens", 0),
                total_tokens=br.get("total_tokens", 0),
                cost_usd=cost,
            ),
            baseline=BaselineRecord(
                no_tools_tokens=nt["total_tokens"],
                no_tools_input=nt.get("input_tokens", 0),
                no_tools_output=nt.get("output_tokens", 0),
                ratio=ratio_val,
                no_tools_correct=nt_correct,
            ),
        )
        write_scenario_result(run_dir, scenario_result)

    if a_results:
        print_a2_table(a_results)

    # ── C: Reuse Economics ───────────────────────────────────────────────
    c_result: dict[str, Any] | None = None
    if Scenario.C.value in scenarios:
        logger.info("=== C: Reuse Economics ===")
        logger.info("[C] Running (10 runs)...")

        gen = TaskGenerator()
        task = gen.generate(6)
        registry = build_registry(task.required_bricks)
        c_result = run_c(runner, task.task_text, registry, on_turn=_make_turn_callback("C"))

        nt_total = c_result["no_tools"]["total_tokens"]
        br_total = c_result["bricks"]["total_tokens"]
        ratio = f"{nt_total / br_total:.1f}x" if br_total > 0 else "inf"
        logger.info("[C] done  no_tools=%d  bricks=%d  (%s)", nt_total, br_total, ratio)

        total_input += c_result.get("no_tools", {}).get("input_tokens", 0)
        total_input += c_result.get("bricks", {}).get("input_tokens", 0)
        total_output += c_result.get("no_tools", {}).get("output_tokens", 0)
        total_output += c_result.get("bricks", {}).get("output_tokens", 0)

    # ── D: Determinism ───────────────────────────────────────────────────
    d_result: dict[str, Any] | None = None
    if Scenario.D.value in scenarios:
        logger.info("=== D: Determinism ===")
        logger.info("[D] Running (5 runs)...")

        gen = TaskGenerator()
        task = gen.generate(6)
        registry = build_registry(task.required_bricks)
        d_result = run_d(runner, task.task_text, registry, on_turn=_make_turn_callback("D"))

        nt_unique = d_result["no_tools"]["unique_outputs"]
        br_unique = d_result["bricks"]["unique_blueprints"]
        logger.info("[D] done  unique_codes=%d/5  unique_blueprints=%d/5", nt_unique, br_unique)

    # ── Write outputs ─────────────────────────────────────────────────────
    json_path = write_apples_json(
        apples_dir,
        "live",
        a_results,
        c_result or {},
        d_result or {},
    )
    md_path = write_apples_markdown(apples_dir, a_results, c_result or {})

    elapsed = time.monotonic() - t0
    print_cost_summary(total_input, total_output, elapsed)
    logger.info("results.json -> %s", json_path)
    logger.info("summary.md   -> %s", md_path)


# ── compose mode runner ────────────────────────────────────────────────────


def run_benchmark_compose(
    scenarios: list[str],
    run_dir: Path,
    logger: logging.Logger,
    claudecode: bool = False,
) -> None:
    """Run the compose-mode benchmark (single-call YAML, no tool_use).

    Args:
        scenarios: List of scenario labels (e.g. ``['A-12']``).
        run_dir: Timestamped run directory.
        logger: Logger for recording progress.
        claudecode: If True, use ClaudeCodeProvider instead of LiteLLMProvider.
    """
    from bricks.ai.composer import BlueprintComposer
    from bricks.core.engine import BlueprintEngine
    from bricks.core.loader import BlueprintLoader

    from bricks_benchmark.mcp.scenarios.task_generator import TaskGenerator
    from bricks_benchmark.showcase.registry_factory import build_registry
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

    provider = _build_provider(claudecode)
    composer = BlueprintComposer(provider=provider)
    if claudecode:
        runner: Any = _ProviderRunner(provider)
    else:
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        runner = AgentRunner(api_key=_require_api_key())
    loader = BlueprintLoader()
    gen = TaskGenerator()

    total_input = 0
    total_output = 0
    t0 = time.monotonic()

    a_scenarios = [s for s in scenarios if s.startswith("A-")]

    for label in a_scenarios:
        step_count = int(label.split("-")[1])
        task = gen.generate(step_count)
        registry = build_registry(task.required_bricks)
        logger.info("=== %s (compose) ===", label)
        logger.info("[%s] Composing...", label)

        result = composer.compose(task.task_text, registry)
        total_input += result.total_input_tokens
        total_output += result.total_output_tokens

        log_compose_calls(label, result, logger)

        # Build call records from compose result
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

        # Execute blueprint and check correctness
        execution = ExecutionRecord()
        if result.is_valid:
            try:
                bp_def = loader.load_string(result.blueprint_yaml)
                engine = BlueprintEngine(registry=registry)
                exec_result = engine.run(bp_def, inputs=bp_def.inputs)
                actual = exec_result.outputs
                filtered_expected = {k: v for k, v in task.expected_outputs.items() if k in actual}
                execution.success = True
                execution.actual_outputs = actual
                execution.expected_outputs = filtered_expected
                execution.correct = check_correctness(actual, filtered_expected)
                logger.info("[%s]   Execution: OK — outputs: %s", label, actual)
            except Exception as exc:
                execution.error = str(exc)
                logger.error("[%s]   Execution: FAILED — %s", label, exc)

        # No-tools baseline
        nt_result = runner.run_without_tools(task.task_text)
        total_input += nt_result.total_input_tokens
        total_output += nt_result.total_output_tokens
        nt_tokens = nt_result.total_tokens
        nt_correct = check_no_tools_answer(nt_result.final_answer, task.expected_outputs)
        nt_label = "CORRECT" if nt_correct else "WRONG"
        logger.info("[%s] No-tools: %d tokens  answer=%s", label, nt_tokens, nt_label)

        ratio_val = result.total_tokens / nt_tokens if nt_tokens > 0 else 0.0
        ratio = f"{ratio_val:.1f}x" if nt_tokens > 0 else "N/A"
        logger.info("[%s] done  compose=%d  no_tools=%d  (%s)", label, result.total_tokens, nt_tokens, ratio)

        # Build and write structured result
        cost = estimate_cost(result.total_input_tokens, result.total_output_tokens)
        scenario_result = ScenarioResult(
            scenario=label,
            mode="compose",
            steps=step_count,
            model=result.model,
            task_text=task.task_text,
            calls=call_records,
            execution=execution,
            totals=TotalRecord(
                api_calls=result.api_calls,
                input_tokens=result.total_input_tokens,
                output_tokens=result.total_output_tokens,
                total_tokens=result.total_tokens,
                cost_usd=cost,
                duration_seconds=result.duration_seconds,
            ),
            baseline=BaselineRecord(
                no_tools_tokens=nt_tokens,
                no_tools_input=nt_result.total_input_tokens,
                no_tools_output=nt_result.total_output_tokens,
                ratio=ratio_val,
                no_tools_correct=nt_correct,
            ),
        )
        json_path = write_scenario_result(run_dir, scenario_result)
        logger.info("[%s] Structured result -> %s", label, json_path)

    # ── CRM scenarios ────────────────────────────────────────────────────
    crm_scenarios = [s for s in scenarios if s in CRM_SCENARIOS]
    if crm_scenarios:
        from bricks_benchmark.showcase.crm_scenario import (
            run_crm_hallucination,
            run_crm_pipeline,
            run_crm_reuse,
        )

        for crm_label in crm_scenarios:
            logger.info("=== %s (compose) ===", crm_label)
            if crm_label == "CRM-pipeline":
                run_crm_pipeline(composer, runner, run_dir)
            elif crm_label == "CRM-hallucination":
                run_crm_hallucination(composer, runner, run_dir)
            elif crm_label == "CRM-reuse":
                run_crm_reuse(composer, run_dir)

    elapsed = time.monotonic() - t0
    print_cost_summary(total_input, total_output, elapsed)


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

    # Configure all Bricks namespace roots so child loggers are captured.
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
    """Parse args and run the apples-to-apples benchmark."""
    parser = argparse.ArgumentParser(
        description="Bricks apples-to-apples benchmark: same agent, tools on vs off.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m benchmark.showcase.run --live                          # all scenarios\n"
            "  python -m benchmark.showcase.run --live --scenario A --steps 12  # single step count\n"
            "  python -m benchmark.showcase.run --live --scenario A             # A presets (5, 25, 50)\n"
            "  python -m benchmark.showcase.run --live --scenario A --scenario C  # multiple\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        default=None,
        help=(
            "Which scenario(s) to run. Accepts: all (default), A, C, D, "
            "CRM-pipeline, CRM-hallucination, CRM-reuse. Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=None,
        help="Step count for scenario A (e.g. --steps 12). Without this, A runs presets: 5, 25, 50.",
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
        print("  python -m benchmark.showcase.run --live")
        print("  python -m benchmark.showcase.run --live --scenario A --steps 5")
        print()
        print("Set ANTHROPIC_API_KEY before running, or use --claudecode for zero-cost runs.")
        sys.exit(1)

    raw_scenarios = args.scenarios or ["all"]
    scenarios = expand_scenarios(raw_scenarios, steps=args.steps)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = make_run_dir(output_dir)

    logger = _setup_logger(run_dir)
    provider_label = "ClaudeCodeProvider (claude -p)" if args.claudecode else "Anthropic SDK"
    logger.info("Live mode: real LLM calls via %s", provider_label)
    logger.info("Scenarios: %s", ", ".join(scenarios))
    logger.info("Bricks v%s", __version__)
    logger.info("Run folder: %s", run_dir)
    logger.info("Mode: %s", args.mode)

    mode = args.mode
    try:
        if mode == "compose":
            run_benchmark_compose(scenarios, run_dir, logger, claudecode=args.claudecode)
        else:
            run_benchmark(scenarios, run_dir, logger)
    except Exception as exc:
        logger.error("FAILED: %s", exc, exc_info=True)
        sys.exit(1)

    write_metadata(run_dir, scenarios)
    print()


if __name__ == "__main__":
    main()
