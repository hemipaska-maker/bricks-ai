"""03 — YAML Blueprint: load a blueprint from a YAML string, validate, and run.

Demonstrates:
- Defining a blueprint in YAML with inputs, steps, and outputs_map
- Loading it with BlueprintLoader
- Validating it with BlueprintValidator
- Executing with BlueprintEngine

Run::

    python examples/basics/03_yaml_blueprint.py
"""

from __future__ import annotations

from typing import cast

from bricks.core.brick import BrickFunction, brick
from bricks.core.engine import BlueprintEngine
from bricks.core.loader import BlueprintLoader
from bricks.core.registry import BrickRegistry
from bricks.core.validation import BlueprintValidator

# 1. Define and register bricks -----------------------------------------------


@brick(tags=["math"], description="Multiply two numbers")
def multiply(a: float, b: float) -> float:
    """Return a * b."""
    return a * b


@brick(tags=["math"], description="Round a float to N decimal places")
def round_value(value: float, decimals: int = 2) -> float:
    """Return value rounded to decimals places."""
    return round(value, decimals)


@brick(tags=["io"], description="Format a float as a labelled string")
def format_result(value: float, label: str = "Result") -> str:
    """Return '{label}: {value}'."""
    return f"{label}: {value}"


registry = BrickRegistry()
for _fn in (multiply, round_value, format_result):
    _bf = cast(BrickFunction, _fn)
    registry.register(_bf.__brick_meta__.name, _bf, _bf.__brick_meta__)

# 2. Blueprint YAML -----------------------------------------------------------

BLUEPRINT_YAML = """
name: calculate_area
description: "Compute rectangle area, round it, and format for display."
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

# 3. Load, validate, execute --------------------------------------------------


def main() -> None:
    """Run the YAML blueprint example."""
    loader = BlueprintLoader()
    blueprint = loader.load_string(BLUEPRINT_YAML)

    validator = BlueprintValidator(registry=registry)
    validator.validate(blueprint)
    print(f"Blueprint '{blueprint.name}' validated ({len(blueprint.steps)} steps)")

    engine = BlueprintEngine(registry=registry)
    outputs = engine.run(blueprint, inputs={"width": 7.5, "height": 4.2}).outputs

    print(f"  area    = {outputs['area']}")
    print(f"  display = {outputs['display']}")
    assert outputs["area"] == 31.5  # noqa: S101
    assert outputs["display"] == "Area (m\xb2): 31.5"  # noqa: S101
    print("OK")


if __name__ == "__main__":
    main()
