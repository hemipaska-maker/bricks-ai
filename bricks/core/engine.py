"""BlueprintEngine: loads and executes YAML blueprints."""

from __future__ import annotations

from typing import Any

from bricks.core.brick import BaseBrick, BrickModel
from bricks.core.context import ExecutionContext
from bricks.core.exceptions import BrickExecutionError
from bricks.core.models import BlueprintDefinition, BrickMeta
from bricks.core.registry import BrickRegistry
from bricks.core.resolver import ReferenceResolver


def _call_teardown(
    callable_: Any,
    resolved_params: dict[str, Any],
    meta: BrickMeta,
    error: Exception,
) -> None:
    """Call teardown on a brick (class-based or function-based), suppressing exceptions.

    Args:
        callable_: The brick callable.
        resolved_params: The resolved parameter dict passed to the brick.
        meta: Brick metadata.
        error: The original execution error.
    """
    try:
        if isinstance(callable_, BaseBrick):
            callable_.teardown(BrickModel(), meta, error)
        elif hasattr(callable_, "__brick_teardown__") and callable_.__brick_teardown__ is not None:
            callable_.__brick_teardown__(resolved_params, error)
    except Exception:  # noqa: S110
        pass  # Never mask the original error


class BlueprintEngine:
    """Executes a validated BlueprintDefinition step-by-step.

    Each step resolves its parameter references, looks up the brick
    in the registry, executes it, and optionally saves the result.

    On failure, teardown is called on the failing step, then in reverse
    order on all previously completed steps, before re-raising.
    """

    def __init__(self, registry: BrickRegistry) -> None:
        """Initialise the engine.

        Args:
            registry: The brick registry to use for step execution.
        """
        self._registry = registry
        self._resolver = ReferenceResolver()

    def run(self, blueprint: BlueprintDefinition, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a blueprint and return its output map.

        Args:
            blueprint: A validated BlueprintDefinition.
            inputs: Runtime input values matching the blueprint's input schema.

        Returns:
            A dictionary of output values as defined by ``outputs_map``.

        Raises:
            BrickExecutionError: If any step fails during execution.
        """
        context = ExecutionContext(inputs=inputs)
        completed: list[tuple[Any, dict[str, Any], BrickMeta]] = []

        for step in blueprint.steps:
            resolved_params = self._resolver.resolve(step.params, context)
            callable_, meta = self._registry.get(step.brick)

            try:
                result = callable_(**resolved_params)
            except Exception as exc:
                # Teardown the failing step, then reverse-teardown completed steps
                _call_teardown(callable_, resolved_params, meta, exc)
                for prev_callable, prev_params, prev_meta in reversed(completed):
                    _call_teardown(prev_callable, prev_params, prev_meta, exc)
                raise BrickExecutionError(
                    brick_name=step.brick,
                    step_name=step.name,
                    cause=exc,
                ) from exc

            completed.append((callable_, resolved_params, meta))
            if step.save_as is not None:
                context.save_result(step.save_as, result)
            context.advance_step()

        outputs: dict[str, Any] = self._resolver.resolve(blueprint.outputs_map, context)
        return outputs
