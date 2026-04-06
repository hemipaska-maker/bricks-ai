"""MCP server entrypoint for Bricks.

Exposes the ``execute_task`` tool over stdio transport so any MCP-compatible
client (Claude Desktop, claude-code, etc.) can call Bricks pipelines.

All ``mcp`` imports are lazy (inside the async function) so this module is
importable even when the optional ``mcp`` package is not installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger("bricks.mcp")


async def run_mcp_server(engine: Any) -> None:
    """Start the Bricks MCP server on stdio transport.

    Registers the ``execute_task`` tool, resource handlers, and prompt
    templates, then blocks until the client disconnects. All ``mcp``
    imports are deferred so the function is only imported when needed.

    Args:
        engine: A :class:`~bricks.api.Bricks` instance (or any object that
            exposes ``engine.execute(task, inputs, verbose)``,
            ``engine.registry``, and ``engine.blueprint_store``).

    Raises:
        ImportError: If the ``mcp`` package is not installed.
    """
    import mcp.types as types  # noqa: PLC0415
    from mcp.server import Server  # noqa: PLC0415
    from mcp.server.lowlevel.helper_types import ReadResourceContents  # noqa: PLC0415
    from mcp.server.stdio import stdio_server  # noqa: PLC0415
    from pydantic.networks import AnyUrl  # noqa: PLC0415

    from bricks.core.exceptions import (  # noqa: PLC0415
        BlueprintValidationError,
        BrickExecutionError,
        OrchestratorError,
    )

    server: Server = Server("bricks")

    @server.list_tools()  # type: ignore[misc, untyped-decorator, no-untyped-call]
    async def list_tools() -> list[types.Tool]:
        """Return the list of tools this server exposes."""
        logger.info("list_tools called")
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
                        "verbose": {
                            "type": "boolean",
                            "description": (
                                "When true, include the composed YAML blueprint, "
                                "step-by-step execution trace, and timing metadata."
                            ),
                            "default": False,
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
            containing either the JSON result or a structured error object.

        Raises:
            ValueError: If ``name`` is not ``execute_task``.
        """
        if name != "execute_task":
            raise ValueError(f"Unknown tool: {name!r}")
        task = arguments["task"]
        verbose = bool(arguments.get("verbose", False))
        logger.info("execute_task called: task=%r, verbose=%s", task, verbose)
        try:
            result = await asyncio.to_thread(
                engine.execute,
                task,
                arguments.get("inputs"),
                verbose,
            )
            logger.info(
                "execute_task result: cache_hit=%s, tokens=%d",
                result.get("cache_hit"),
                result.get("tokens_used", 0),
            )
            logger.debug("execute_task outputs: %r", result.get("outputs"))
            return [types.TextContent(type="text", text=json.dumps(result))]
        except BlueprintValidationError as exc:
            logger.error("execute_task BlueprintValidationError: %s", exc)
            error: dict[str, Any] = {
                "error": True,
                "error_type": "validation_error",
                "message": str(exc),
                "details": {"validation_errors": getattr(exc, "errors", [])},
                "retryable": True,
            }
            return [types.TextContent(type="text", text=json.dumps(error))]
        except BrickExecutionError as exc:
            logger.error("execute_task BrickExecutionError: %s", exc)
            error = {
                "error": True,
                "error_type": "execution_failed",
                "message": str(exc),
                "details": {
                    "step": getattr(exc, "step_name", ""),
                    "brick": getattr(exc, "brick_name", ""),
                },
                "retryable": False,
            }
            return [types.TextContent(type="text", text=json.dumps(error))]
        except OrchestratorError as exc:
            logger.error("execute_task OrchestratorError: %s", exc)
            error = {
                "error": True,
                "error_type": "composition_failed",
                "message": str(exc),
                "details": {},
                "retryable": True,
            }
            return [types.TextContent(type="text", text=json.dumps(error))]
        except Exception as exc:
            logger.error("execute_task unexpected error: %s", exc)
            error = {
                "error": True,
                "error_type": "internal_error",
                "message": str(exc),
                "details": {},
                "retryable": False,
            }
            return [types.TextContent(type="text", text=json.dumps(error))]

    @server.list_resources()  # type: ignore[misc, untyped-decorator, no-untyped-call]
    async def list_resources() -> list[types.Resource]:
        """Return the list of resources this server exposes."""
        return [
            types.Resource(
                uri=AnyUrl("bricks://catalog"),
                name="Brick Catalog",
                description="All registered bricks with schemas and tags",
            ),
            types.Resource(
                uri=AnyUrl("bricks://blueprints"),
                name="Cached Blueprints",
                description="All cached task blueprints in the store",
            ),
        ]

    @server.read_resource()  # type: ignore[misc, untyped-decorator, no-untyped-call]
    async def read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        """Serve a Bricks resource by URI.

        Args:
            uri: Resource URI — ``bricks://catalog`` or ``bricks://blueprints``.

        Returns:
            A list with a single :class:`ReadResourceContents` item.

        Raises:
            ValueError: If the URI is not recognised.
        """
        uri_str = str(uri)
        logger.info("Resource read: %s", uri_str)
        if uri_str == "bricks://catalog":
            catalog = [
                {
                    "name": n,
                    "description": m.description,
                    "tags": m.tags,
                    "category": m.category,
                }
                for n, m in engine.registry.list_all()
            ]
            return [ReadResourceContents(content=json.dumps(catalog, indent=2), mime_type="application/json")]
        if uri_str == "bricks://blueprints":
            store = engine.blueprint_store
            blueprints = store.list_all() if store is not None else []
            data = [
                {
                    "name": b.name,
                    "blueprint_yaml": b.yaml,
                    "cached_at": b.created_at.isoformat(),
                    "use_count": b.use_count,
                }
                for b in blueprints
            ]
            return [ReadResourceContents(content=json.dumps(data, indent=2), mime_type="application/json")]
        raise ValueError(f"Unknown resource: {uri_str!r}")

    @server.list_prompts()  # type: ignore[misc, untyped-decorator, no-untyped-call]
    async def list_prompts() -> list[types.Prompt]:
        """Return the list of prompt templates this server offers."""
        return [
            types.Prompt(
                name="process_csv",
                description="Process CSV/tabular data through a Bricks pipeline",
                arguments=[
                    types.PromptArgument(name="description", description="What to do with the data", required=True),
                    types.PromptArgument(name="columns", description="Column names in the data", required=False),
                ],
            ),
            types.Prompt(
                name="validate_data",
                description="Validate data against rules using Bricks validation bricks",
                arguments=[
                    types.PromptArgument(name="description", description="What to validate", required=True),
                    types.PromptArgument(name="rules", description="Validation rules to apply", required=False),
                ],
            ),
            types.Prompt(
                name="filter_and_aggregate",
                description="Filter records by condition and compute aggregates",
                arguments=[
                    types.PromptArgument(name="filter_condition", description="What to filter by", required=True),
                    types.PromptArgument(
                        name="aggregation",
                        description="What to compute (sum, count, average)",
                        required=True,
                    ),
                ],
            ),
        ]

    @server.get_prompt()  # type: ignore[misc, untyped-decorator, no-untyped-call]
    async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
        """Render a prompt template by name.

        Args:
            name: Prompt template name.
            arguments: Template variable substitutions.

        Returns:
            A :class:`~mcp.types.GetPromptResult` with the rendered message.

        Raises:
            ValueError: If the prompt name is not recognised.
        """
        logger.info("Prompt requested: %s", name)
        args = arguments or {}
        if name == "process_csv":
            task = f"Process the data: {args.get('description', '')}."
            if args.get("columns"):
                task += f" The data has columns: {args['columns']}."
            return types.GetPromptResult(
                description="Process CSV data",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=task),
                    )
                ],
            )
        if name == "validate_data":
            task = f"Validate the data: {args.get('description', '')}."
            if args.get("rules"):
                task += f" Rules: {args['rules']}."
            return types.GetPromptResult(
                description="Validate data",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=task),
                    )
                ],
            )
        if name == "filter_and_aggregate":
            task = (
                f"Filter records where {args.get('filter_condition', '')}, then compute {args.get('aggregation', '')}."
            )
            return types.GetPromptResult(
                description="Filter and aggregate",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=task),
                    )
                ],
            )
        raise ValueError(f"Unknown prompt: {name!r}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
