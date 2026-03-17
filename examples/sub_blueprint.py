"""Sub-blueprint composition example.

Demonstrates a parent blueprint calling a child blueprint as a step.

Blueprint hierarchy:
  parent_blueprint
    └── sub_step  →  child_blueprint (computes area)
    └── format_step  →  format_result brick (formats the output)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from bricks.core import BlueprintEngine, BlueprintLoader, BrickRegistry, brick

# ── Bricks ────────────────────────────────────────────────────────────────────


@brick(tags=["math"], description="Multiply two numbers")
def multiply(a: float, b: float) -> dict[str, float]:
    """Multiply two numbers."""
    return {"result": a * b}


@brick(tags=["math"], description="Round a float to N decimal places")
def round_value(value: float, decimals: int = 2) -> dict[str, float]:
    """Round value to the given number of decimal places."""
    return {"result": round(value, decimals)}


@brick(tags=["format"], description="Format a label+value pair for display")
def format_result(label: str, value: float) -> dict[str, str]:
    """Format a numeric result for display."""
    return {"display": f"{label}: {value}"}


# ── Blueprint YAML strings ─────────────────────────────────────────────────────

CHILD_BLUEPRINT_YAML = """
name: compute_area
description: "Compute and round room area from width and height."
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

PARENT_BLUEPRINT_YAML_TEMPLATE = """
name: room_area_display
description: "Compute room area via sub-blueprint and format for display."
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
      label: "Room area (m²)"
      value: "${{area_result.area}}"
    save_as: formatted
outputs_map:
  display: "${{formatted.display}}"
  area: "${{area_result.area}}"
"""


def main() -> None:
    """Run the sub-blueprint composition demo."""
    registry = BrickRegistry()
    for fn in (multiply, round_value, format_result):
        registry.register(fn.__brick_meta__.name, fn, fn.__brick_meta__)

    loader = BlueprintLoader()
    engine = BlueprintEngine(registry=registry, loader=loader)

    # Write child blueprint to a temp file so the parent can reference it
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        tmp.write(CHILD_BLUEPRINT_YAML)
        child_path = Path(tmp.name)

    try:
        parent_yaml = PARENT_BLUEPRINT_YAML_TEMPLATE.format(
            child_path=child_path.as_posix()
        )
        parent_bp = loader.load_string(parent_yaml)

        inputs = {"width": 7.5, "height": 4.2}
        outputs = engine.run(parent_bp, inputs=inputs)

        print(f"Blueprint: {parent_bp.name!r}")
        print(f"Inputs:    width={inputs['width']}, height={inputs['height']}")
        print(f"Area:      {outputs['area']} m²")
        print(f"Display:   {outputs['display']}")
    finally:
        child_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
