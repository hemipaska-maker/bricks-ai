"""Tests for bricks.core.schema."""

from __future__ import annotations

import pytest

from bricks.core.brick import brick
from bricks.core.exceptions import BrickNotFoundError
from bricks.core.models import BlueprintDefinition, StepDefinition
from bricks.core.registry import BrickRegistry
from bricks.core.schema import blueprint_schema, brick_schema, registry_schema


def _make_reg() -> BrickRegistry:
    """Create a registry with an 'add' brick for testing."""
    reg = BrickRegistry()

    @brick(tags=["math"], description="Add two numbers", destructive=False)
    def add(a: int, b: int) -> int:
        return a + b

    reg.register("add", add, add.__brick_meta__)
    return reg


class TestBrickSchema:
    def test_schema_has_expected_keys(self) -> None:
        """brick_schema returns correct metadata fields."""
        reg = _make_reg()
        schema = brick_schema("add", reg)
        assert schema["name"] == "add", f"Expected 'add', got {schema['name']!r}"
        assert schema["description"] == "Add two numbers", f"Expected 'Add two numbers', got {schema['description']!r}"
        assert schema["tags"] == ["math"], f"Expected ['math'], got {schema['tags']!r}"
        assert schema["destructive"] is False, f"Expected False, got {schema['destructive']!r}"
        assert "parameters" in schema, "Expected 'parameters' key in schema"

    def test_schema_parameters_have_correct_structure(self) -> None:
        """Parameters dict includes correct type and required info."""
        reg = _make_reg()
        schema = brick_schema("add", reg)
        params = schema["parameters"]
        assert "a" in params, "Expected 'a' in parameters"
        assert "b" in params, "Expected 'b' in parameters"
        assert params["a"]["required"] is True, "Expected parameter 'a' to be required"

    def test_schema_raises_for_unknown_brick(self) -> None:
        """BrickNotFoundError raised when brick is not registered."""
        reg = BrickRegistry()
        with pytest.raises(BrickNotFoundError):
            brick_schema("nonexistent", reg)

    def test_schema_idempotent_field(self) -> None:
        """brick_schema includes idempotent field from metadata."""
        reg = _make_reg()
        schema = brick_schema("add", reg)
        assert "idempotent" in schema, "Expected 'idempotent' key in schema"

    def test_schema_parameter_type_annotation(self) -> None:
        """Parameter type annotation is captured as a string."""
        reg = _make_reg()
        schema = brick_schema("add", reg)
        params = schema["parameters"]
        # int annotation should be present as a string form
        assert "int" in params["a"]["type"], f"Expected 'int' in type annotation, got {params['a']['type']!r}"


class TestRegistrySchema:
    def test_registry_schema_returns_list(self) -> None:
        """registry_schema returns a list with one entry per brick."""
        reg = _make_reg()
        schemas = registry_schema(reg)
        assert isinstance(schemas, list), f"Expected list, got {type(schemas).__name__}"
        assert len(schemas) == 1, f"Expected length 1, got {len(schemas)}"
        assert schemas[0]["name"] == "add", f"Expected 'add', got {schemas[0]['name']!r}"

    def test_empty_registry_returns_empty_list(self) -> None:
        """registry_schema returns empty list for empty registry."""
        reg = BrickRegistry()
        assert registry_schema(reg) == [], f"Expected [], got {registry_schema(reg)!r}"

    def test_registry_schema_sorted_by_name(self) -> None:
        """registry_schema results are sorted alphabetically by brick name."""
        reg = BrickRegistry()

        @brick(description="Zebra")
        def zebra_brick(x: int) -> int:
            return x

        @brick(description="Alpha")
        def alpha_brick(x: int) -> int:
            return x

        reg.register("zebra_brick", zebra_brick, zebra_brick.__brick_meta__)
        reg.register("alpha_brick", alpha_brick, alpha_brick.__brick_meta__)

        schemas = registry_schema(reg)
        assert schemas[0]["name"] == "alpha_brick", f"Expected 'alpha_brick' first, got {schemas[0]['name']!r}"
        assert schemas[1]["name"] == "zebra_brick", f"Expected 'zebra_brick' second, got {schemas[1]['name']!r}"


class TestBlueprintSchema:
    def test_blueprint_schema_has_expected_keys(self) -> None:
        """blueprint_schema returns correct top-level keys."""
        bp = BlueprintDefinition(
            name="my_bp",
            description="A test blueprint",
            inputs={"x": "int"},
            steps=[
                StepDefinition(
                    name="s1",
                    brick="add",
                    params={"a": "${inputs.x}", "b": 1},
                )
            ],
            outputs_map={"result": "${s1}"},
        )
        schema = blueprint_schema(bp)
        assert schema["name"] == "my_bp", f"Expected 'my_bp', got {schema['name']!r}"
        assert schema["description"] == "A test blueprint", (
            f"Expected 'A test blueprint', got {schema['description']!r}"
        )
        assert schema["inputs"] == {"x": "int"}, f"Expected {{'x': 'int'}}, got {schema['inputs']!r}"
        assert len(schema["steps"]) == 1, f"Expected length 1, got {len(schema['steps'])}"
        assert schema["steps"][0]["name"] == "s1", f"Expected 's1', got {schema['steps'][0]['name']!r}"
        assert schema["outputs_map"] == {"result": "${s1}"}, "Expected outputs_map mismatch"

    def test_blueprint_schema_step_fields(self) -> None:
        """blueprint_schema step entries include all required step fields."""
        bp = BlueprintDefinition(
            name="test_bp",
            steps=[
                StepDefinition(
                    name="step1",
                    brick="some_brick",
                    params={"key": "value"},
                    save_as="step1_result",
                )
            ],
        )
        schema = blueprint_schema(bp)
        step = schema["steps"][0]
        assert step["name"] == "step1", f"Expected 'step1', got {step['name']!r}"
        assert step["brick"] == "some_brick", f"Expected 'some_brick', got {step['brick']!r}"
        assert step["params"] == {"key": "value"}, "Expected params mismatch"
        assert step["save_as"] == "step1_result", f"Expected 'step1_result', got {step['save_as']!r}"

    def test_blueprint_schema_empty_blueprint(self) -> None:
        """blueprint_schema works with a blueprint that has no steps."""
        bp = BlueprintDefinition(name="empty_bp")
        schema = blueprint_schema(bp)
        assert schema["name"] == "empty_bp", f"Expected 'empty_bp', got {schema['name']!r}"
        assert schema["steps"] == [], f"Expected [], got {schema['steps']!r}"
        assert schema["inputs"] == {}, f"Expected {{}}, got {schema['inputs']!r}"
        assert schema["outputs_map"] == {}, f"Expected {{}}, got {schema['outputs_map']!r}"
