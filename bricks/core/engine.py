"""BlueprintEngine: loads and executes YAML blueprints."""

from __future__ import annotations

from typing import Any

from bricks.core.context import ExecutionContext
from bricks.core.exceptions import BrickExecutionError
from bricks.core.models import BlueprintDefinition
from bricks.core.registry import BrickRegistry
from bricks.core.resolver import ReferenceResolver


class BlueprintEngine:
    """Executes a validated BlueprintDefinition step-by-step.

    Each step resolves its parameter references, looks up the brick
    in the registry, executes it, and optionally saves the result.
    """

    def __init__(self, registry: BrickRegistry) -> None:
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

        for step in blueprint.steps:
            resolved_params = self._resolver.resolve(step.params, context)
            callable_, _meta = self._registry.get(step.brick)

            try:
                result = callable_(**resolved_params)
            except Exception as exc:
                raise BrickExecutionError(
                    brick_name=step.brick,
                    step_name=step.name,
                    cause=exc,
                ) from exc

            if step.save_as is not None:
                context.save_result(step.save_as, result)
            context.advance_step()

        outputs: dict[str, Any] = self._resolver.resolve(blueprint.outputs_map, context)
        return outputs
