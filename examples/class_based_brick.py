"""Example: class-based Brick definition and usage.

This example demonstrates:
- Defining Bricks using BaseBrick with typed Input/Output schemas
- Using BrickModel for input/output validation
- Registering class-based bricks in the registry via wrapper functions
- Running them via BlueprintDefinition built programmatically (no YAML file needed)
"""

from __future__ import annotations

from typing import Any, ClassVar

from bricks.core.brick import BaseBrick, BrickModel
from bricks.core.engine import BlueprintEngine
from bricks.core.models import BlueprintDefinition, BrickMeta, StepDefinition
from bricks.core.registry import BrickRegistry

# -- 1. Define class-based bricks ---------------------------------------------


class ReadTemperature(BaseBrick):
    """Simulates reading a temperature sensor."""

    class Meta:
        """Brick metadata."""

        name = "read_temperature"
        tags: ClassVar[list[str]] = ["hardware", "sensor"]
        destructive = False
        idempotent = True
        description = "Read temperature from a simulated sensor channel"

    class Input(BrickModel):
        """Input schema."""

        channel: int
        unit: str = "celsius"

    class Output(BrickModel):
        """Output schema."""

        temperature: float
        unit: str

    # Simulated temperature readings per channel
    _READINGS: ClassVar[dict[int, float]] = {0: 22.5, 1: 37.0, 2: -5.3, 3: 100.0}

    def execute(self, inputs: BrickModel, metadata: BrickMeta) -> dict[str, Any]:
        """Simulate reading from a sensor channel.

        Args:
            inputs: Validated input data.
            metadata: Brick metadata.

        Returns:
            Dict with temperature and unit.
        """
        channel = getattr(inputs, "channel", 0)
        unit = getattr(inputs, "unit", "celsius")
        temp = self._READINGS.get(channel, 0.0)
        return {"temperature": temp, "unit": unit}


class ConvertTemperature(BaseBrick):
    """Converts temperature between Celsius and Fahrenheit."""

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

        temperature: float
        unit: str

    def execute(self, inputs: BrickModel, metadata: BrickMeta) -> dict[str, Any]:
        """Convert temperature units.

        Args:
            inputs: Validated input data.
            metadata: Brick metadata.

        Returns:
            Dict with converted temperature and target unit.
        """
        temp = getattr(inputs, "temperature", 0.0)
        from_unit = getattr(inputs, "from_unit", "celsius")
        to_unit = getattr(inputs, "to_unit", "fahrenheit")

        if from_unit.lower() == "celsius" and to_unit.lower() == "fahrenheit":
            converted = (temp * 9 / 5) + 32
        elif from_unit.lower() == "fahrenheit" and to_unit.lower() == "celsius":
            converted = (temp - 32) * 5 / 9
        else:
            converted = temp

        return {"temperature": round(converted, 2), "unit": to_unit}


# -- 2. Register bricks via wrapper functions ---------------------------------
#
# The BlueprintEngine calls callable_(**resolved_params) with plain keyword
# arguments from the YAML params dict.  BaseBrick.execute() takes
# (inputs: BrickModel, metadata: BrickMeta), so we register thin wrappers
# that accept keyword args and delegate to execute().


def _build_registry() -> BrickRegistry:
    """Create and populate a BrickRegistry with class-based bricks."""
    registry = BrickRegistry()

    read_brick = ReadTemperature()
    convert_brick = ConvertTemperature()

    def read_temp_wrapper(channel: int, unit: str = "celsius") -> dict[str, Any]:
        """Accept keyword args and delegate to ReadTemperature.execute."""
        inputs = ReadTemperature.Input(channel=channel, unit=unit)
        meta = BrickMeta(name="read_temperature")
        return read_brick.execute(inputs, meta)

    def convert_temp_wrapper(
        temperature: float,
        from_unit: str,
        to_unit: str,
    ) -> dict[str, Any]:
        """Accept keyword args and delegate to ConvertTemperature.execute."""
        inputs = ConvertTemperature.Input(
            temperature=temperature,
            from_unit=from_unit,
            to_unit=to_unit,
        )
        meta = BrickMeta(name="convert_temperature")
        return convert_brick.execute(inputs, meta)

    registry.register(
        "read_temperature",
        read_temp_wrapper,
        BrickMeta(
            name="read_temperature",
            tags=["hardware", "sensor"],
            destructive=False,
            description="Read temperature from a simulated sensor channel",
        ),
    )
    registry.register(
        "convert_temperature",
        convert_temp_wrapper,
        BrickMeta(
            name="convert_temperature",
            tags=["math", "conversion"],
            destructive=False,
            description="Convert temperature between Celsius and Fahrenheit",
        ),
    )
    return registry


# -- 3. Build blueprint programmatically --------------------------------------


def _build_blueprint() -> BlueprintDefinition:
    """Build a blueprint that reads and converts a temperature."""
    return BlueprintDefinition(
        name="temperature_pipeline",
        description="Read temperature from channel 1 and convert to Fahrenheit",
        inputs={"channel": "int"},
        steps=[
            StepDefinition(
                name="read_sensor",
                brick="read_temperature",
                params={"channel": "${inputs.channel}", "unit": "celsius"},
                save_as="sensor_reading",
            ),
            StepDefinition(
                name="convert_to_fahrenheit",
                brick="convert_temperature",
                params={
                    "temperature": "${sensor_reading.temperature}",
                    "from_unit": "celsius",
                    "to_unit": "fahrenheit",
                },
                save_as="fahrenheit_reading",
            ),
        ],
        outputs_map={
            "celsius": "${sensor_reading.temperature}",
            "fahrenheit": "${fahrenheit_reading.temperature}",
        },
    )


# -- 4. Run -------------------------------------------------------------------


def main() -> None:
    """Run the class_based_brick example."""
    registry = _build_registry()
    blueprint = _build_blueprint()

    print(f"Blueprint: {blueprint.name}")
    print(f"Steps: {len(blueprint.steps)}")

    for name, meta in registry.list_all():
        print(f"  Brick: {name} -- {meta.description}")

    engine = BlueprintEngine(registry=registry)
    outputs = engine.run(blueprint, inputs={"channel": 1}).outputs

    print("\nResults for channel 1:")
    print(f"  Celsius:    {outputs['celsius']}C")
    print(f"  Fahrenheit: {outputs['fahrenheit']}F")

    assert outputs["celsius"] == 37.0  # noqa: S101
    assert outputs["fahrenheit"] == 98.6  # noqa: S101
    print("\nAll assertions passed")


if __name__ == "__main__":
    main()
