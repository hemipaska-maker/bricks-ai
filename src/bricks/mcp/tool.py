"""MCP tool definition for execute_task.

Framework-agnostic: the ``execute_task`` function is a plain Python callable
and ``EXECUTE_TASK_SCHEMA`` is a JSON-schema dict that can be registered with
any MCP-compatible framework (FastMCP, mcp-python, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bricks.orchestrator.runtime import RuntimeOrchestrator


def execute_task(
    orchestrator: RuntimeOrchestrator,
    task: str,
    inputs: dict[str, Any] | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute a task using the configured RuntimeOrchestrator.

    This is the single tool an agent needs. It hides all internals: brick
    selection, blueprint composition, caching, and deterministic execution.
    On a blueprint store hit the call consumes zero LLM tokens.

    Args:
        orchestrator: A configured ``RuntimeOrchestrator`` instance.
        task: Natural language description of the task to perform.
        inputs: Input values for ``${inputs.X}`` references in the composed
                blueprint. Pass the agent's input data here.
        verbose: When True, include blueprint YAML, step trace, model, and
                 timing metadata in the response.

    Returns:
        A dict with keys:

        - ``outputs``: task outputs from the executed blueprint
        - ``cache_hit``: True when blueprint was served from cache (0 tokens)
        - ``api_calls``: number of LLM calls made
        - ``tokens_used``: total LLM tokens consumed
        - ``input_tokens``: LLM input tokens consumed
        - ``output_tokens``: LLM output tokens consumed
    """
    return orchestrator.execute(task, inputs or {}, verbose=verbose)


#: JSON schema for registering execute_task as an MCP tool.
EXECUTE_TASK_SCHEMA: dict[str, Any] = {
    "name": "execute_task",
    "description": (
        "Execute a task using deterministic Bricks pipelines. "
        "Returns structured outputs. Caches blueprints automatically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Natural language description of the task to perform.",
            },
            "inputs": {
                "type": "object",
                "description": (
                    "Input values for the pipeline. Keys are referenced as ${inputs.key_name} inside the blueprint."
                ),
                "additionalProperties": True,
            },
            "verbose": {
                "type": "boolean",
                "description": (
                    "When true, include the composed YAML blueprint, step-by-step execution trace, "
                    "and timing metadata in the response."
                ),
                "default": False,
            },
        },
        "required": ["task"],
    },
}
