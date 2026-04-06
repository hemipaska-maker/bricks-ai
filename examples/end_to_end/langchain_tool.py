"""LangChain Tool — expose the Bricks engine as a callable tool.

Shows how to wrap engine.execute() in a plain Python callable that any agent
framework (LangChain, CrewAI, AutoGen, etc.) can call as a tool.

LangChain is NOT a dependency of Bricks — the import below is commented out
so this file runs without installing langchain. Uncomment when integrating.

Demo mode (no API key — shows function definition only):
    python examples/end_to_end/langchain_tool.py

Live mode (composes a blueprint via LLM):
    ANTHROPIC_API_KEY=sk-ant-... python examples/end_to_end/langchain_tool.py
"""

from __future__ import annotations

import json
import os

_live = bool(os.getenv("BRICKS_MODEL") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))


def _build_engine() -> object:
    """Return a Bricks engine configured from environment."""
    from bricks import Bricks
    from bricks.llm.litellm_provider import LiteLLMProvider

    model = os.getenv("BRICKS_MODEL", "claude-haiku-4-5")
    return Bricks.default(provider=LiteLLMProvider(model=model))


def make_bricks_tool(engine: object) -> object:
    """Return a callable Bricks tool from a live engine.

    Args:
        engine: A :class:`~bricks.api.Bricks` instance.

    Returns:
        A plain callable that accepts a JSON string input.
    """
    from bricks import Bricks as _Bricks

    assert isinstance(engine, _Bricks)  # noqa: S101

    def run_bricks_task(task_json: str) -> str:
        """Execute a Bricks task.

        Args:
            task_json: JSON string with ``task`` (str) and optional ``inputs`` (dict).

        Returns:
            JSON string of the execution outputs.
        """
        payload = json.loads(task_json)
        result = engine.execute(task=payload["task"], inputs=payload.get("inputs"))
        return json.dumps(result["outputs"])

    return run_bricks_task


# ── Uncomment when langchain is installed ────────────────────────────────────
# from langchain.tools import Tool
#
# engine = _build_engine()
# bricks_tool = Tool(
#     name="bricks_execute",
#     description=(
#         "Execute a deterministic data processing task using Bricks. "
#         "Input must be a JSON string with 'task' (str) and optional 'inputs' (dict)."
#     ),
#     func=make_bricks_tool(engine),
# )
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    if not _live:
        print("DEMO mode — showing tool definition (set API key for live execution)")
        print()
        print("Tool input format:")
        example = {"task": "Filter values greater than 10 and return them.", "inputs": {"values": [5, 15, 3, 20, 8]}}
        print(f"  {json.dumps(example, indent=2)}")
        print()
        print("Integrate with LangChain:")
        print("  engine = Bricks.default(provider=LiteLLMProvider(model='claude-haiku-4-5'))")
        print("  tool = make_bricks_tool(engine)")
        print("  result = tool(json.dumps({'task': '...', 'inputs': {...}}))")
    else:
        model = os.getenv("BRICKS_MODEL", "claude-haiku-4-5")
        print(f"Running in LIVE mode (model: {model})")
        engine = _build_engine()
        tool = make_bricks_tool(engine)
        demo_input = json.dumps(
            {
                "task": "Filter the list for values greater than 10 and return them.",
                "inputs": {"values": [5, 15, 3, 20, 8]},
            }
        )
        print(f"Input:  {demo_input}")
        output = tool(demo_input)
        print(f"Output: {output}")

    print("OK")
