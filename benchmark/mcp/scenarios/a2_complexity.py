"""Scenario A: apples-to-apples complexity curve (parametric N steps)."""

from __future__ import annotations

from typing import Any

from benchmark.mcp.agent_result import AgentResult
from benchmark.mcp.agent_runner import AgentRunner, OnTurnCallback
from bricks.core import BrickRegistry


def run_a(
    runner: AgentRunner,
    task_text: str,
    step_count: int,
    registry: BrickRegistry,
    on_turn: OnTurnCallback = None,
) -> dict[str, Any]:
    """Run an A-N scenario in both modes and return comparison dict.

    Args:
        runner: Configured AgentRunner instance.
        task_text: Task description from TaskGenerator.
        step_count: Number of Blueprint steps.
        registry: BrickRegistry for the bricks mode.
        on_turn: Optional per-turn callback for logging.

    Returns:
        Comparison dict with ``label``, ``steps``, ``no_tools``, ``bricks``.
    """
    no_tools = runner.run_without_tools(task_text, on_turn=on_turn)
    bricks = runner.run_with_bricks(task_text, registry, on_turn=on_turn)
    return _compare(f"A-{step_count}", step_count, no_tools, bricks)


def _compare(
    label: str,
    steps: int,
    no_tools: AgentResult,
    bricks: AgentResult,
) -> dict[str, Any]:
    """Build a comparison dict from two AgentResult instances.

    Args:
        label: Human-readable sub-scenario label (e.g. ``"A-5"``).
        steps: Number of Blueprint steps in this sub-scenario.
        no_tools: Result from the no-tools run.
        bricks: Result from the Bricks-tools run.

    Returns:
        Dict with label, steps, and nested no_tools / bricks summaries.
    """
    return {
        "label": label,
        "steps": steps,
        "no_tools": {
            "turns": no_tools.turns,
            "total_tokens": no_tools.total_tokens,
            "input_tokens": no_tools.total_input_tokens,
            "output_tokens": no_tools.total_output_tokens,
            "code_lines": len((no_tools.code_generated or "").splitlines()),
            "final_answer": no_tools.final_answer,
        },
        "bricks": {
            "turns": bricks.turns,
            "total_tokens": bricks.total_tokens,
            "input_tokens": bricks.total_input_tokens,
            "output_tokens": bricks.total_output_tokens,
            "tool_calls": len(bricks.tool_calls),
            "execution_result": bricks.execution_result,
            "blueprint_yaml": bricks.blueprint_yaml,
        },
    }
