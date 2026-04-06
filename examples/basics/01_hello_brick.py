"""01 — Hello Brick: define, register, and run your first brick.

Demonstrates:
- Decorating a function with @brick
- Creating a BrickRegistry
- Building a blueprint programmatically
- Executing with BlueprintEngine

Run::

    python examples/basics/01_hello_brick.py
"""

from __future__ import annotations

from bricks.core.brick import brick
from bricks.core.engine import BlueprintEngine
from bricks.core.models import BlueprintDefinition, StepDefinition
from bricks.core.registry import BrickRegistry

# 1. Define bricks with @brick ------------------------------------------------


@brick(tags=["math"], description="Add two numbers")
def add(a: float, b: float) -> float:
    """Return a + b."""
    return a + b


@brick(tags=["math"], description="Multiply two numbers")
def multiply(a: float, b: float) -> float:
    """Return a * b."""
    return a * b


# 2. Register bricks ----------------------------------------------------------

registry = BrickRegistry()
for fn in (add, multiply):
    registry.register(fn.__brick_meta__.name, fn, fn.__brick_meta__)

# 3. Build and run a blueprint ------------------------------------------------

blueprint = BlueprintDefinition(
    name="add_then_multiply",
    description="Add x + y, then multiply by factor",
    inputs={"x": "float", "y": "float", "factor": "float"},
    steps=[
        StepDefinition(
            name="sum_step",
            brick="add",
            params={"a": "${inputs.x}", "b": "${inputs.y}"},
            save_as="sum_result",
        ),
        StepDefinition(
            name="multiply_step",
            brick="multiply",
            params={"a": "${sum_result}", "b": "${inputs.factor}"},
            save_as="product_result",
        ),
    ],
    outputs_map={"result": "${product_result}"},
)

engine = BlueprintEngine(registry=registry)
outputs = engine.run(blueprint, inputs={"x": 3.0, "y": 4.0, "factor": 2.0}).outputs

print(f"3 + 4 = 7, x 2 = {outputs['result']}")  # -> 14.0
assert outputs["result"] == 14.0  # noqa: S101
print("OK")
