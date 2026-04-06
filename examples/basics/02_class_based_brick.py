"""02 — Class-based Brick: typed Input/Output schemas via BaseBrick.

Demonstrates:
- Defining a brick as a class with BaseBrick, BrickModel, and a Meta inner class
- Wrapping the class-based brick for registry use (keyword-arg interface)
- Running it via a programmatic blueprint

Run::

    python examples/basics/02_class_based_brick.py
"""

from __future__ import annotations

from typing import Any, ClassVar

from bricks.core.brick import BaseBrick, BrickModel
from bricks.core.engine import BlueprintEngine
from bricks.core.models import BlueprintDefinition, BrickMeta, StepDefinition
from bricks.core.registry import BrickRegistry


class ConvertTemperature(BaseBrick):
    """Convert a temperature value between Celsius and Fahrenheit."""

    class Meta:
        """Brick metadata."""

        name = "convert_temperature"
        tags: ClassVar[list[str]] = ["math", "conversion"]
        destructive = False
        idempotent = True
        description = "Convert temperature between Celsius and Fahrenheit"

    class Input(BrickModel):
        """Input schema."""

        temperature: float
        from_unit: str
        to_unit: str

    class Output(BrickModel):
        """Output schema."""

        result: float

    def execute(self, inputs: BrickModel, metadata: BrickMeta) -> dict[str, Any]:
        """Convert temperature units.

        Args:
            inputs: Validated input data.
            metadata: Brick metadata.

        Returns:
            Dict with converted temperature under ``result``.
        """
        temp: float = getattr(inputs, "temperature", 0.0)
        from_unit: str = getattr(inputs, "from_unit", "celsius")
        to_unit: str = getattr(inputs, "to_unit", "fahrenheit")
        if from_unit.lower() == "celsius" and to_unit.lower() == "fahrenheit":
            converted = (temp * 9 / 5) + 32
        elif from_unit.lower() == "fahrenheit" and to_unit.lower() == "celsius":
            converted = (temp - 32) * 5 / 9
        else:
            converted = temp
        return {"result": round(converted, 2)}


# Register via a thin keyword-arg wrapper ------------------------------------


def _convert_wrapper(temperature: float, from_unit: str, to_unit: str) -> dict[str, Any]:
    """Keyword-arg wrapper around ConvertTemperature.execute."""
    brick_instance = ConvertTemperature()
    inputs = ConvertTemperature.Input(temperature=temperature, from_unit=from_unit, to_unit=to_unit)
    return brick_instance.execute(inputs, BrickMeta(name="convert_temperature"))


registry = BrickRegistry()
registry.register(
    "convert_temperature",
    _convert_wrapper,
    BrickMeta(name="convert_temperature", tags=["math", "conversion"], description="Convert Celsius ↔ Fahrenheit"),
)

blueprint = BlueprintDefinition(
    name="celsius_to_fahrenheit",
    description="Convert body temperature from Celsius to Fahrenheit",
    inputs={"celsius": "float"},
    steps=[
        StepDefinition(
            name="convert",
            brick="convert_temperature",
            params={"temperature": "${inputs.celsius}", "from_unit": "celsius", "to_unit": "fahrenheit"},
            save_as="converted",
        ),
    ],
    outputs_map={"fahrenheit": "${converted.result}"},
)

engine = BlueprintEngine(registry=registry)
outputs = engine.run(blueprint, inputs={"celsius": 37.0}).outputs

print(f"37.0 C -> {outputs['fahrenheit']} F")  # -> 98.6
assert outputs["fahrenheit"] == 98.6  # noqa: S101
print("OK")
