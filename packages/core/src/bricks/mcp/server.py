"""MCP server entrypoint for Bricks.

Exposes the ``execute_task`` tool over stdio transport so any MCP-compatible
client (Claude Desktop, claude-code, etc.) can call Bricks pipelines.

All ``mcp`` imports are lazy (inside the async function) so this module is
importable even when the optional ``mcp`` package is not installed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


async def run_mcp_server(engine: Any) -> None:
    """Start the Bricks MCP server on stdio transport.

    Registers the ``execute_task`` tool and blocks until the client
    disconnects.  All ``mcp`` imports are deferred so the function is only
    imported when actually needed.

    Args:
        engine: A :class:`~bricks.api.Bricks` instance (or any object that
            exposes ``engine.execute(task, inputs)``).

    Raises:
        ImportError: If the ``mcp`` package is not installed.
    """
    import mcp.types as types  # noqa: PLC0415
    from mcp.server import Server  # noqa: PLC0415
    from mcp.server.stdio import stdio_server  # noqa: PLC0415

    server: Server = Server("bricks")

    @server.list_tools()  # type: ignore[misc, untyped-decorator, no-untyped-call]
    async def list_tools() -> list[types.Tool]:
        """Return the list of tools this server exposes."""
        return [
            types.Tool(
                name="execute_task",
                description=(
                    "Execute a deterministic data processing task using Bricks pipelines. "
                    "Returns structured JSON outputs. Blueprints are cached automatically "
                    "so repeated calls with the same task description consume zero LLM tokens."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Natural language description of the task to perform.",
                        },
                        "inputs": {
                            "type": "object",
                            "description": (
                                "Input values for the pipeline. "
                                "Keys are referenced as ${inputs.key_name} inside the blueprint."
                            ),
                            "additionalProperties": True,
                        },
                    },
                    "required": ["task"],
                },
            )
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        """Dispatch a tool call to the Bricks engine.

        Args:
            name: Tool name — must be ``execute_task``.
            arguments: Tool arguments dict from the MCP client.

        Returns:
            A single-element list with a :class:`~mcp.types.TextContent`
            containing either the JSON result or an error message.

        Raises:
            ValueError: If ``name`` is not ``execute_task``.
        """
        if name != "execute_task":
            raise ValueError(f"Unknown tool: {name!r}")
        try:
            result = engine.execute(
                task=arguments["task"],
                inputs=arguments.get("inputs"),
            )
            return [types.TextContent(type="text", text=json.dumps(result))]
        except Exception as exc:
            return [types.TextContent(type="text", text=f"Error: {exc}")]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
