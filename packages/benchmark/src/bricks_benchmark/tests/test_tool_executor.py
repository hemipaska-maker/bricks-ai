"""Tests for the extracted tool executor module."""

from __future__ import annotations

from typing import Any

from bricks_benchmark.mcp.tool_executor import (
    execute_tool,
    extract_save_as_names,
    fuzzy_match,
    validation_hint,
)


def _build_registry() -> Any:
    """Build a test BrickRegistry with math + string bricks."""
    from bricks_benchmark.showcase.bricks import build_showcase_registry
    from bricks_benchmark.showcase.bricks.math_bricks import add, multiply, round_value
    from bricks_benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, format_result)


def _build_components() -> tuple:
    """Build all components needed for execute_tool.

    Returns:
        Tuple of (catalog, engine, loader, validator).
    """
    from bricks.core.catalog import TieredCatalog
    from bricks.core.engine import BlueprintEngine
    from bricks.core.loader import BlueprintLoader
    from bricks.core.validation import BlueprintValidator

    registry = _build_registry()
    all_names = [name for name, _ in registry.list_all()]
    catalog = TieredCatalog(registry, common_set=all_names)
    engine = BlueprintEngine(registry=registry)
    loader = BlueprintLoader()
    validator = BlueprintValidator(registry=registry)
    return catalog, engine, loader, validator


class TestExecuteTool:
    """Tests for execute_tool function."""

    def test_list_bricks(self) -> None:
        """list_bricks returns a list."""
        catalog, engine, loader, validator = _build_components()
        result = execute_tool("list_bricks", {}, catalog, engine, loader, validator)
        assert isinstance(result, list)

    def test_lookup_brick(self) -> None:
        """lookup_brick returns matching bricks."""
        catalog, engine, loader, validator = _build_components()
        result = execute_tool("lookup_brick", {"query": "add"}, catalog, engine, loader, validator)
        assert isinstance(result, list)
        names = [r["name"] for r in result]
        assert "add" in names

    def test_execute_blueprint_success(self) -> None:
        """Valid blueprint executes successfully."""
        catalog, engine, loader, validator = _build_components()
        yaml = (
            "name: t\nsteps:\n  - name: s\n    brick: add\n"
            "    params:\n      a: 1.0\n      b: 2.0\n    save_as: r\n"
            'outputs_map:\n  result: "${r.result}"'
        )
        result = execute_tool("execute_blueprint", {"blueprint_yaml": yaml}, catalog, engine, loader, validator)
        assert result["success"] is True
        assert result["outputs"]["result"] == 3.0

    def test_execute_blueprint_error(self) -> None:
        """Invalid YAML returns error dict."""
        catalog, engine, loader, validator = _build_components()
        result = execute_tool("execute_blueprint", {"blueprint_yaml": "bad["}, catalog, engine, loader, validator)
        assert result["success"] is False

    def test_unknown_tool(self) -> None:
        """Unknown tool name returns error dict."""
        catalog, engine, loader, validator = _build_components()
        result = execute_tool("unknown_tool", {}, catalog, engine, loader, validator)
        assert "error" in result


class TestFuzzyMatch:
    """Tests for fuzzy_match helper."""

    def test_prefix_match(self) -> None:
        """Prefix match finds the right brick."""
        assert fuzzy_match("mult", ["multiply", "add"]) == "multiply"

    def test_substring_match(self) -> None:
        """Substring match finds the right brick."""
        assert fuzzy_match("round", ["round_value", "add"]) == "round_value"

    def test_no_match(self) -> None:
        """No match returns None."""
        assert fuzzy_match("xyz", ["multiply", "add"]) is None


class TestExtractSaveAsNames:
    """Tests for extract_save_as_names helper."""

    def test_extracts_names(self) -> None:
        """Extracts save_as values from YAML."""
        yaml = "save_as: result1\nsave_as: result2"
        assert extract_save_as_names(yaml) == ["result1", "result2"]

    def test_empty_yaml(self) -> None:
        """Empty YAML returns empty list."""
        assert extract_save_as_names("") == []


class TestValidationHint:
    """Tests for validation_hint helper."""

    def test_brick_not_found_hint(self) -> None:
        """Brick not found error generates a hint with available bricks."""
        errors = ["Step 'step1': brick 'mult' not found in registry"]
        result = validation_hint(errors, ["multiply", "add"], [])
        assert "multiply" in result

    def test_fallback_hint(self) -> None:
        """Unknown error pattern generates fallback hint."""
        result = validation_hint(["something unknown"], ["add"], [])
        assert "Fix all errors" in result
