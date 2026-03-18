"""AgentRunner: multi-turn agent loop with and without Bricks MCP tools."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

from benchmark.mcp.agent_result import AgentResult, ToolCallRecord
from benchmark.mcp.scenarios import APPLES_SYSTEM
from bricks.core import BrickRegistry
from bricks.core.catalog import TieredCatalog
from bricks.core.engine import BlueprintEngine
from bricks.core.loader import BlueprintLoader
from bricks.core.validation import BlueprintValidator

# Type alias for the per-turn callback.
# (turn, mode, input_tokens, output_tokens, elapsed, tool_calls)
OnTurnCallback = Callable[..., None] | None

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 20

# Tool definitions matching the MCP server schema.
# Used in run_with_bricks(); absent in run_without_tools().
BRICKS_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_bricks",
        "description": "List all available bricks in the registry.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "lookup_brick",
        "description": "Search bricks by name, tag, or description substring.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search term"}},
            "required": ["query"],
        },
    },
    {
        "name": "execute_blueprint",
        "description": "Validate and execute a YAML blueprint string with the Bricks engine.",
        "input_schema": {
            "type": "object",
            "properties": {
                "blueprint_yaml": {"type": "string", "description": "YAML blueprint content"},
                "inputs": {"type": "object", "description": "Input values for the blueprint"},
            },
            "required": ["blueprint_yaml"],
        },
    },
]


class AgentRunner:
    """Runs a task through Claude with or without Bricks MCP tools.

    Tool responses are simulated locally using the real Bricks engine
    (TieredCatalog, BlueprintEngine) — no actual MCP transport needed.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialise the runner.

        Args:
            api_key: Anthropic API key. Falls back to ``ANTHROPIC_API_KEY`` env var.
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def run_without_tools(
        self,
        task: str,
        model: str = DEFAULT_MODEL,
        on_turn: OnTurnCallback = None,
    ) -> AgentResult:
        """Run task with no tools — agent generates Python code.

        Single-turn: one API call with APPLES_SYSTEM, no tools attached.

        Args:
            task: Natural language task description.
            model: Anthropic model ID.
            on_turn: Optional callback fired after each API turn.

        Returns:
            AgentResult with ``mode="no_tools"`` and ``turns=1``.
        """
        import anthropic  # type: ignore[import-not-found]

        from bricks.core.utils import strip_code_fence

        client = anthropic.Anthropic(api_key=self._api_key)
        t0 = time.monotonic()

        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=APPLES_SYSTEM,
            messages=[{"role": "user", "content": task}],
        )

        elapsed = time.monotonic() - t0
        in_tok: int = response.usage.input_tokens
        out_tok: int = response.usage.output_tokens

        if on_turn:
            on_turn(1, "no_tools", in_tok, out_tok, elapsed)

        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        code = strip_code_fence(text)

        return AgentResult(
            task=task,
            mode="no_tools",
            turns=1,
            total_input_tokens=in_tok,
            total_output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            final_answer=text,
            code_generated=code,
            duration_seconds=elapsed,
        )

    def run_with_bricks(
        self,
        task: str,
        registry: BrickRegistry,
        model: str = DEFAULT_MODEL,
        on_turn: OnTurnCallback = None,
    ) -> AgentResult:
        """Run task with Bricks MCP tools — agent discovers and executes Blueprints.

        Multi-turn loop (up to MAX_TURNS): agent calls list_bricks, lookup_brick,
        and execute_blueprint. Tool responses are served from the real Bricks engine.

        Args:
            task: Natural language task description (identical to no_tools mode).
            registry: BrickRegistry with available bricks.
            model: Anthropic model ID.
            on_turn: Optional callback fired after each API turn.

        Returns:
            AgentResult with ``mode="bricks"`` and all tool call records.
        """
        import anthropic  # type: ignore[import-not-found]

        client = anthropic.Anthropic(api_key=self._api_key)
        all_brick_names = [name for name, _ in registry.list_all()]
        catalog = TieredCatalog(registry, common_set=all_brick_names)
        loader = BlueprintLoader()
        engine = BlueprintEngine(registry=registry)
        validator = BlueprintValidator(registry=registry)

        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        total_input = 0
        total_output = 0
        turns = 0
        tool_calls: list[ToolCallRecord] = []
        final_answer = ""
        last_blueprint_yaml: str | None = None
        last_execution_result: dict[str, Any] | None = None

        t0 = time.monotonic()

        for _ in range(MAX_TURNS):
            turn_t0 = time.monotonic()
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=APPLES_SYSTEM,
                tools=BRICKS_TOOLS,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )
            turn_elapsed = time.monotonic() - turn_t0
            turns += 1
            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            if response.stop_reason == "end_turn":
                if on_turn:
                    on_turn(turns, "bricks", response.usage.input_tokens, response.usage.output_tokens, turn_elapsed)
                for block in response.content:
                    if block.type == "text":
                        final_answer = block.text
                        break
                break

            # stop_reason == "tool_use": append assistant turn and process tools
            messages.append({"role": "assistant", "content": response.content})

            turn_tool_calls: list[dict[str, Any]] = []
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_input: dict[str, Any] = block.input  # type: ignore[assignment]
                tool_output = _execute_tool(
                    block.name,
                    tool_input,
                    catalog,
                    engine,
                    loader,
                    validator,
                )

                if block.name == "execute_blueprint" and isinstance(tool_output, dict) and tool_output.get("success"):
                    last_blueprint_yaml = tool_input.get("blueprint_yaml")
                    exec_out = tool_output.get("outputs")
                    last_execution_result = exec_out if isinstance(exec_out, dict) else None

                summary = ""
                if block.name == "list_bricks" and isinstance(tool_output, list):
                    summary = f"-> {len(tool_output)} bricks found"
                elif block.name == "execute_blueprint" and isinstance(tool_output, dict):
                    if tool_output.get("success"):
                        summary = "-> success"
                    else:
                        err = str(tool_output.get("error", ""))[:60]
                        summary = f"-> error: {err}"

                turn_tool_calls.append({"name": block.name, "summary": summary})
                tool_calls.append(ToolCallRecord(name=block.name, inputs=tool_input, output=tool_output))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_output),
                    }
                )

            if on_turn:
                on_turn(
                    turns,
                    "bricks",
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                    turn_elapsed,
                    turn_tool_calls,
                )

            messages.append({"role": "user", "content": tool_results})

        elapsed = time.monotonic() - t0

        return AgentResult(
            task=task,
            mode="bricks",
            turns=turns,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            tool_calls=tool_calls,
            final_answer=final_answer,
            blueprint_yaml=last_blueprint_yaml,
            execution_result=last_execution_result,
            duration_seconds=elapsed,
        )


def _execute_tool(
    name: str,
    inputs: dict[str, Any],
    catalog: TieredCatalog,
    engine: BlueprintEngine,
    loader: BlueprintLoader,
    validator: BlueprintValidator,
) -> Any:
    """Execute a simulated MCP tool call using the real Bricks engine.

    Args:
        name: Tool name (``list_bricks``, ``lookup_brick``, ``execute_blueprint``).
        inputs: Tool input parameters dict.
        catalog: TieredCatalog for brick discovery.
        engine: BlueprintEngine for execution.
        loader: BlueprintLoader for parsing YAML strings.
        validator: BlueprintValidator for pre-execution validation.

    Returns:
        JSON-serialisable tool result.
    """
    if name == "list_bricks":
        return catalog.list_bricks()
    if name == "lookup_brick":
        return catalog.lookup_brick(inputs["query"])
    if name == "execute_blueprint":
        bp_yaml: str = inputs["blueprint_yaml"]
        bp_inputs: dict[str, Any] = inputs.get("inputs") or {}
        try:
            bp = loader.load_string(bp_yaml)
            validator.validate(bp)
            result = engine.run(bp, inputs=bp_inputs).outputs
            return {"success": True, "outputs": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
    return {"error": f"Unknown tool: {name}"}
