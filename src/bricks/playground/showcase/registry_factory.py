"""Registry builder for benchmark scenarios.

Builds a BrickRegistry containing exactly the bricks needed for a given
step count, using the TaskGenerator's required_bricks list.
"""

from __future__ import annotations

from bricks.core import BrickRegistry

# Map brick names to their decorated functions.
_BRICK_MAP: dict[str, object] | None = None


def _load_brick_map() -> dict[str, object]:
    """Lazily load the brick name → function mapping.

    Returns:
        Dict mapping brick names to decorated brick functions.
    """
    from bricks.playground.showcase.bricks.data_bricks import http_get, json_extract
    from bricks.playground.showcase.bricks.math_bricks import add, multiply, round_value, subtract
    from bricks.playground.showcase.bricks.string_bricks import format_result

    return {
        "multiply": multiply,
        "round_value": round_value,
        "add": add,
        "subtract": subtract,
        "format_result": format_result,
        "http_get": http_get,
        "json_extract": json_extract,
    }


def build_registry(required_bricks: list[str]) -> BrickRegistry:
    """Build a BrickRegistry containing only the specified bricks.

    Args:
        required_bricks: List of brick names to include.

    Returns:
        A populated BrickRegistry.

    Raises:
        KeyError: If a required brick name is not recognized.
    """
    global _BRICK_MAP
    if _BRICK_MAP is None:
        _BRICK_MAP = _load_brick_map()

    from bricks.playground.showcase.bricks import build_showcase_registry

    fns = [_BRICK_MAP[name] for name in required_bricks]
    return build_showcase_registry(*fns)
