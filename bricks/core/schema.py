"""JSON Schema generation for BrickMeta and BlueprintDefinition."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from bricks.core.models import BlueprintDefinition
from bricks.core.registry import BrickRegistry

if TYPE_CHECKING:
    from bricks.core.catalog import TieredCatalog


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
    params = _callable_params(callable_)
    input_keys = list(params.keys())
    output_keys = _output_keys(callable_)
    schema: dict[str, Any] = {
        "name": meta.name,
        "description": meta.description,
        "tags": meta.tags,
        "category": meta.category,
        "input_keys": input_keys,
        "output_keys": output_keys,
        "destructive": meta.destructive,
        "idempotent": meta.idempotent,
        "parameters": params,
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
                "blueprint": step.blueprint,
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


def catalog_schema(catalog: TieredCatalog) -> dict[str, Any]:
    """Generate a schema dict describing a TieredCatalog's current visible bricks.

    Returns the bricks currently visible via :meth:`~TieredCatalog.list_bricks`
    (Tier 1 common set + Tier 3 session cache), intended for AI agent consumption.

    Args:
        catalog: The TieredCatalog to describe.

    Returns:
        A dict with ``"bricks"`` (list of visible brick schemas) and
        ``"hint"`` (instructions for the AI on how to discover more bricks).
    """
    return {
        "bricks": catalog.list_bricks(),
        "hint": (
            "This is your current brick view (common set + recently accessed). "
            "Use lookup_brick(query) to search by name, tag, or description. "
            "Use get_brick(name) to fetch a specific brick."
        ),
    }


def _output_keys(callable_: Any) -> list[str]:
    """Extract output key names from a callable's return type annotation.

    Inspects the return type annotation for ``dict[str, ...]`` patterns
    and falls back to calling the function's class-based Output schema
    if available. Returns an empty list if output keys cannot be determined.

    Args:
        callable_: A Python callable (function or class instance).

    Returns:
        List of output key names.
    """
    # Class-based brick: check for Output inner class
    cls = callable_ if isinstance(callable_, type) else type(callable_)
    output_cls = getattr(cls, "Output", None)
    if output_cls is not None and hasattr(output_cls, "model_fields"):
        return list(output_cls.model_fields.keys())

    # Function-based brick: inspect return annotation for TypedDict or dict hints
    try:
        hints = inspect.get_annotations(callable_, eval_str=True)
        ret = hints.get("return")
        if ret is not None:
            origin = getattr(ret, "__origin__", None)
            if origin is dict:
                # Can't extract keys from generic dict[str, X]
                return []
    except Exception:  # noqa: S110
        pass

    return []


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
