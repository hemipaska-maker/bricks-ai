"""JSON Schema generation for BrickMeta and BlueprintDefinition."""

from __future__ import annotations

import inspect
from typing import Any

from bricks.core.models import BlueprintDefinition
from bricks.core.registry import BrickRegistry


def brick_schema(name: str, registry: BrickRegistry) -> dict[str, Any]:
    """Generate a JSON Schema dict describing a registered brick.

    Args:
        name: The registered brick name.
        registry: The registry to look up the brick.

    Returns:
        A JSON Schema compatible dict with brick metadata and parameter info.

    Raises:
        BrickNotFoundError: If the brick name is not registered.
    """
    callable_, meta = registry.get(name)
    schema: dict[str, Any] = {
        "name": meta.name,
        "description": meta.description,
        "tags": meta.tags,
        "destructive": meta.destructive,
        "idempotent": meta.idempotent,
        "parameters": _callable_params(callable_),
    }
    return schema


def blueprint_schema(blueprint: BlueprintDefinition) -> dict[str, Any]:
    """Generate a JSON Schema dict describing a BlueprintDefinition.

    Args:
        blueprint: The blueprint definition to describe.

    Returns:
        A JSON Schema compatible dict describing the blueprint inputs and outputs.
    """
    return {
        "name": blueprint.name,
        "description": blueprint.description,
        "inputs": blueprint.inputs,
        "steps": [
            {
                "name": step.name,
                "brick": step.brick,
                "params": step.params,
                "save_as": step.save_as,
            }
            for step in blueprint.steps
        ],
        "outputs_map": blueprint.outputs_map,
    }


def registry_schema(registry: BrickRegistry) -> list[dict[str, Any]]:
    """Generate a JSON Schema list describing all registered bricks.

    Args:
        registry: The registry to enumerate.

    Returns:
        A list of brick schema dicts, sorted by brick name.
    """
    return [brick_schema(name, registry) for name, _meta in registry.list_all()]


def _callable_params(callable_: Any) -> dict[str, Any]:
    """Extract parameter information from a callable using inspect.

    Args:
        callable_: A Python callable (function or bound method).

    Returns:
        A dict mapping parameter names to their annotation strings.
    """
    params: dict[str, Any] = {}
    try:
        sig = inspect.signature(callable_)
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "inputs", "metadata"):
                continue
            annotation = str(param.annotation) if param.annotation is not inspect.Parameter.empty else "Any"
            params[param_name] = {
                "type": annotation,
                "required": param.default is inspect.Parameter.empty,
            }
    except (ValueError, TypeError):
        pass
    return params
