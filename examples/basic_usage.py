"""Basic Bricks usage: register bricks and run a simple blueprint."""

from typing import cast

from bricks.core import (
    BlueprintEngine,
    BrickRegistry,
    brick,
)
from bricks.core.brick import BrickFunction
from bricks.core.models import BlueprintDefinition, StepDefinition

# --- Create a registry ---
registry = BrickRegistry()


# --- Define function-based bricks ---
@brick(tags=["math"], description="Add two numbers")
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@brick(tags=["math"], description="Multiply two numbers")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


# --- Register bricks ---
registry.register("add", cast(BrickFunction, add), cast(BrickFunction, add).__brick_meta__)
registry.register("multiply", cast(BrickFunction, multiply), cast(BrickFunction, multiply).__brick_meta__)

# --- List registered bricks ---
print("Registered bricks:")
for name, meta in registry.list_all():
    print(f"  {name}: {meta.description} (tags={meta.tags})")

# --- Build a blueprint programmatically ---
blueprint = BlueprintDefinition(
    name="add_then_multiply",
    description="Add two numbers, then multiply the result",
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
    outputs_map={"final_result": "${product_result}"},
)

# --- Execute ---
engine = BlueprintEngine(registry=registry)
result = engine.run(blueprint, inputs={"x": 3.0, "y": 4.0, "factor": 2.0})
print(f"\nBlueprint result: {result}")
# Expected: {'final_result': 14.0}  (3+4=7, 7*2=14)
