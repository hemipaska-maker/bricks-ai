"""Example: loading and running a YAML blueprint file.

This example demonstrates:
- Registering @brick-decorated functions
- Loading a blueprint from a YAML string
- Executing it with the BlueprintEngine
- Reading the output map
"""

from __future__ import annotations

from typing import cast

from bricks.core.brick import BrickFunction, brick
from bricks.core.engine import BlueprintEngine
from bricks.core.loader import BlueprintLoader
from bricks.core.registry import BrickRegistry
from bricks.core.validation import BlueprintValidator

# -- 1. Define bricks ----------------------------------------------------------


@brick(tags=["math"], description="Multiply two numbers together", destructive=False)
def multiply(a: float, b: float) -> float:
    """Multiply a by b."""
    return a * b


@brick(tags=["math"], description="Round a float to N decimal places")
def round_value(value: float, decimals: int = 2) -> float:
    """Round value to the given number of decimal places."""
    return round(value, decimals)


@brick(tags=["io"], description="Format a float as a readable string")
def format_result(value: float, label: str = "Result") -> str:
    """Format a numeric result as a labelled string."""
    return f"{label}: {value}"


# -- 2. Register bricks --------------------------------------------------------

registry = BrickRegistry()
for _fn in (multiply, round_value, format_result):
    _bf = cast(BrickFunction, _fn)
    registry.register(_bf.__brick_meta__.name, _bf, _bf.__brick_meta__)

# -- 3. Define blueprint in YAML -----------------------------------------------

BLUEPRINT_YAML = """
name: calculate_area
description: "Calculate the area of a rectangle, round it, and format it."
inputs:
  width: "float"
  height: "float"
steps:
  - name: compute_area
    brick: multiply
    params:
      a: ${inputs.width}
      b: ${inputs.height}
    save_as: raw_area

  - name: round_area
    brick: round_value
    params:
      value: ${raw_area}
      decimals: 2
    save_as: rounded_area

  - name: label_result
    brick: format_result
    params:
      value: ${rounded_area}
      label: "Area (m\xb2)"
    save_as: display_string

outputs_map:
  area: "${rounded_area}"
  display: "${display_string}"
"""

# -- 4. Load, validate, and run ------------------------------------------------


def main() -> None:
    """Run the yaml_blueprint example."""
    loader = BlueprintLoader()
    blueprint = loader.load_string(BLUEPRINT_YAML)

    validator = BlueprintValidator(registry=registry)
    validator.validate(blueprint)
    print(f"Blueprint '{blueprint.name}' validated ({len(blueprint.steps)} steps)")

    engine = BlueprintEngine(registry=registry)
    outputs = engine.run(blueprint, inputs={"width": 7.5, "height": 4.2}).outputs

    print("Execution complete")
    print(f"  area    = {outputs['area']}")
    print(f"  display = {outputs['display']}")

    assert outputs["area"] == 31.5  # noqa: S101
    assert outputs["display"] == "Area (m\xb2): 31.5"  # noqa: S101
    print("All assertions passed")


if __name__ == "__main__":
    main()
