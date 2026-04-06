"""04 — Nested Blueprints: a parent blueprint calls a child blueprint as a step.

Demonstrates:
- Writing child and parent blueprints in YAML
- Using a ``blueprint:`` step (not a ``brick:`` step) in the parent
- Saving the child blueprint to a temp file so the parent can reference it

Run::

    python examples/basics/04_nested_blueprints.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from bricks.core import BlueprintEngine, BlueprintLoader, BrickRegistry, brick

# 1. Bricks used by the child blueprint ---------------------------------------


@brick(tags=["math"], description="Multiply two numbers")
def multiply(a: float, b: float) -> dict[str, float]:
    """Return {result: a * b}."""
    return {"result": a * b}


@brick(tags=["math"], description="Round a float to N decimal places")
def round_value(value: float, decimals: int = 2) -> dict[str, float]:
    """Return {result: rounded}."""
    return {"result": round(value, decimals)}


@brick(tags=["format"], description="Format a label+value pair for display")
def format_result(label: str, value: float) -> dict[str, str]:
    """Return {display: 'label: value'}."""
    return {"display": f"{label}: {value}"}


# 2. Blueprint YAML strings ---------------------------------------------------

CHILD_YAML = """
name: compute_area
description: "Compute and round room area."
inputs:
  width: float
  height: float
steps:
  - name: area
    brick: multiply
    params:
      a: "${inputs.width}"
      b: "${inputs.height}"
    save_as: raw_area
  - name: rounded
    brick: round_value
    params:
      value: "${raw_area.result}"
      decimals: 2
    save_as: area_rounded
outputs_map:
  area: "${area_rounded.result}"
"""

PARENT_YAML_TEMPLATE = """
name: room_area_display
description: "Compute area via sub-blueprint and format for display."
inputs:
  width: float
  height: float
steps:
  - name: sub_area
    blueprint: "{child_path}"
    params:
      width: "${{inputs.width}}"
      height: "${{inputs.height}}"
    save_as: area_result
  - name: display
    brick: format_result
    params:
      label: "Room area (m\u00b2)"
      value: "${{area_result.area}}"
    save_as: formatted
outputs_map:
  display: "${{formatted.display}}"
  area: "${{area_result.area}}"
"""


def main() -> None:
    """Run the nested-blueprint demo."""
    registry = BrickRegistry()
    for fn in (multiply, round_value, format_result):
        registry.register(fn.__brick_meta__.name, fn, fn.__brick_meta__)

    loader = BlueprintLoader()
    engine = BlueprintEngine(registry=registry, loader=loader)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        tmp.write(CHILD_YAML)
        child_path = Path(tmp.name)

    try:
        parent_yaml = PARENT_YAML_TEMPLATE.format(child_path=child_path.as_posix())
        parent_bp = loader.load_string(parent_yaml)
        outputs = engine.run(parent_bp, inputs={"width": 7.5, "height": 4.2}).outputs
        print(f"Area:    {outputs['area']} m\u00b2")
        print(f"Display: {outputs['display']}")
        assert outputs["area"] == 31.5  # noqa: S101
        print("OK")
    finally:
        child_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
