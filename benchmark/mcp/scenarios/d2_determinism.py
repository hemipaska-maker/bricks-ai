"""Scenario D2: apples-to-apples determinism (5 runs with identical inputs)."""

from __future__ import annotations

from typing import Any

from benchmark.mcp.agent_result import AgentResult
from benchmark.mcp.agent_runner import AgentRunner, OnTurnCallback
from benchmark.mcp.scenarios import TASK_A2_6
from bricks.core import BrickRegistry

DETERMINISM_RUNS = 5


def run_d2(
    runner: AgentRunner,
    registry: BrickRegistry,
    on_turn: OnTurnCallback = None,
) -> dict[str, Any]:
    """Run A2-6 task 5 times with identical inputs in both modes.

    No_tools: compare generated code across 5 runs — shows variability.
    Bricks: compare Blueprint YAML across 5 runs — should be identical.

    Args:
        runner: Configured AgentRunner instance.
        registry: BrickRegistry for the bricks mode.
        on_turn: Optional per-turn callback for logging.

    Returns:
        Dict with per-mode uniqueness metrics and per-run token counts.
    """
    no_tools_results: list[AgentResult] = []
    bricks_results: list[AgentResult] = []

    for _ in range(DETERMINISM_RUNS):
        no_tools_results.append(runner.run_without_tools(TASK_A2_6, on_turn=on_turn))
        bricks_results.append(runner.run_with_bricks(TASK_A2_6, registry, on_turn=on_turn))

    codes = [r.code_generated or "" for r in no_tools_results]
    unique_codes = len(set(codes))

    yamls = [r.blueprint_yaml or "" for r in bricks_results]
    unique_yamls = len(set(yamls))

    return {
        "runs": DETERMINISM_RUNS,
        "step_count": 6,
        "no_tools": {
            "unique_outputs": unique_codes,
            "all_identical": unique_codes == 1,
        },
        "bricks": {
            "unique_blueprints": unique_yamls,
            "all_identical": unique_yamls == 1,
        },
        "no_tools_results": [{"run": i + 1, "total_tokens": r.total_tokens} for i, r in enumerate(no_tools_results)],
        "bricks_results": [
            {"run": i + 1, "total_tokens": r.total_tokens, "turns": r.turns} for i, r in enumerate(bricks_results)
        ],
    }
