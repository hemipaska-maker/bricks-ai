"""Scenario C2: apples-to-apples reuse economics (10 runs of A2-6 task)."""

from __future__ import annotations

from typing import Any

from benchmark.mcp.agent_result import AgentResult
from benchmark.mcp.agent_runner import AgentRunner, OnTurnCallback
from benchmark.mcp.scenarios import TASK_A2_6
from bricks.core import BrickRegistry

REUSE_RUNS = 10


def run_c2(
    runner: AgentRunner,
    registry: BrickRegistry,
    on_turn: OnTurnCallback = None,
) -> dict[str, Any]:
    """Run A2-6 task 10 times in both modes and return comparison dict.

    No_tools: 10 separate conversations — code is regenerated every time.
    Bricks: run 1 calls the API to compose a Blueprint; runs 2-10 simulate
    the session cache (Blueprint is reused, 0 tokens each).

    Args:
        runner: Configured AgentRunner instance.
        registry: BrickRegistry for the bricks mode.
        on_turn: Optional per-turn callback for logging.

    Returns:
        Comparison dict with per-mode token totals.
    """
    no_tools_results: list[AgentResult] = []
    bricks_results: list[AgentResult] = []
    first_blueprint: str | None = None

    for i in range(REUSE_RUNS):
        no_tools = runner.run_without_tools(TASK_A2_6, on_turn=on_turn)
        no_tools_results.append(no_tools)

        if i == 0:
            bricks = runner.run_with_bricks(TASK_A2_6, registry, on_turn=on_turn)
            first_blueprint = bricks.blueprint_yaml
            bricks_results.append(bricks)
        else:
            # Simulate session cache: Blueprint is stored after run 1.
            # Subsequent runs re-execute locally — no API call, 0 tokens.
            bricks_results.append(
                AgentResult(
                    task=TASK_A2_6,
                    mode="bricks",
                    turns=0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_tokens=0,
                    blueprint_yaml=first_blueprint,
                    final_answer="[Blueprint reused from run 1 — 0 tokens]",
                )
            )

    nt_input = sum(r.total_input_tokens for r in no_tools_results)
    nt_output = sum(r.total_output_tokens for r in no_tools_results)
    br_input = sum(r.total_input_tokens for r in bricks_results)
    br_output = sum(r.total_output_tokens for r in bricks_results)

    return {
        "runs": REUSE_RUNS,
        "step_count": 6,
        "no_tools": {
            "total_tokens": nt_input + nt_output,
            "input_tokens": nt_input,
            "output_tokens": nt_output,
            "per_run_avg": (nt_input + nt_output) // REUSE_RUNS,
        },
        "bricks": {
            "total_tokens": br_input + br_output,
            "input_tokens": br_input,
            "output_tokens": br_output,
            "first_run_tokens": bricks_results[0].total_tokens,
            "reuse_tokens": (br_input + br_output) - bricks_results[0].total_tokens,
        },
        "blueprint_yaml": first_blueprint,
    }
