"""Sample bricks for the benchmark showcase."""

from __future__ import annotations

from bricks.core import BrickRegistry
from bricks.core.brick import BrickFunction

__all__ = ["build_showcase_registry"]


def build_showcase_registry(*brick_fns: BrickFunction) -> BrickRegistry:
    """Build a BrickRegistry from decorated brick functions.

    Args:
        *brick_fns: Functions decorated with ``@brick``. Each must have a
            ``__brick_meta__`` attribute.

    Returns:
        A populated BrickRegistry ready for use with BlueprintEngine.
    """
    registry = BrickRegistry()
    for fn in brick_fns:
        registry.register(fn.__brick_meta__.name, fn, fn.__brick_meta__)
    return registry
