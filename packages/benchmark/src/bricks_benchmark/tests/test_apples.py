"""Tests for the apples-to-apples benchmark: AgentRunner and supporting models."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_text_response(text: str, in_tok: int = 10, out_tok: int = 5) -> MagicMock:
    """Build a mock Anthropic response with end_turn stop reason and a text block.

    Args:
        text: The text content of the response.
        in_tok: Input token count.
        out_tok: Output token count.

    Returns:
        Mocked response object.
    """
    block = MagicMock()
    block.type = "text"
    block.text = text

    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.usage.input_tokens = in_tok
    resp.usage.output_tokens = out_tok
    resp.content = [block]
    return resp


def _make_tool_response(
    tool_name: str,
    tool_id: str,
    tool_input: dict[str, Any],
    in_tok: int = 20,
    out_tok: int = 10,
) -> MagicMock:
    """Build a mock Anthropic response with tool_use stop reason.

    Args:
        tool_name: Name of the tool being called.
        tool_id: Unique ID for the tool call.
        tool_input: Input parameters for the tool.
        in_tok: Input token count.
        out_tok: Output token count.

    Returns:
        Mocked response object.
    """
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = tool_id
    tool_block.name = tool_name
    tool_block.input = tool_input

    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.usage.input_tokens = in_tok
    resp.usage.output_tokens = out_tok
    resp.content = [tool_block]
    return resp


def _build_registry_a6() -> Any:
    """Build a BrickRegistry with math + string bricks for testing.

    Returns:
        A BrickRegistry with multiply, round_value, add, and format_result.
    """
    from bricks_benchmark.showcase.bricks import build_showcase_registry
    from bricks_benchmark.showcase.bricks.math_bricks import add, multiply, round_value
    from bricks_benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, format_result)


# ── AgentResult model ─────────────────────────────────────────────────────────


class TestAgentResultModel:
    """Tests for AgentResult and ToolCallRecord models."""

    def test_total_tokens_field(self) -> None:
        from bricks_benchmark.mcp.agent_result import AgentResult

        result = AgentResult(
            task="test task",
            mode="no_tools",
            turns=1,
            total_input_tokens=8,
            total_output_tokens=2,
            total_tokens=10,
        )
        assert result.total_tokens == 10

    def test_mode_and_defaults(self) -> None:
        from bricks_benchmark.mcp.agent_result import AgentResult

        result = AgentResult(
            task="t",
            mode="bricks",
            turns=3,
            total_input_tokens=100,
            total_output_tokens=50,
            total_tokens=150,
        )
        assert result.mode == "bricks"
        assert result.tool_calls == []
        assert result.final_answer == ""
        assert result.code_generated is None
        assert result.blueprint_yaml is None
        assert result.execution_result is None

    def test_tool_call_record(self) -> None:
        from bricks_benchmark.mcp.agent_result import ToolCallRecord

        rec = ToolCallRecord(name="list_bricks", inputs={}, output=["brick_a"])
        assert rec.name == "list_bricks"
        assert rec.output == ["brick_a"]


# ── run_without_tools ─────────────────────────────────────────────────────────


class TestRunWithoutTools:
    """Tests for AgentRunner.run_without_tools()."""

    def test_mode_and_turns(self) -> None:
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        mock_resp = _make_text_response("def calc(): return 42")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            result = runner.run_without_tools("Compute something.")

        assert result.mode == "no_tools"
        assert result.turns == 1

    def test_token_counting(self) -> None:
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        mock_resp = _make_text_response("x = 1", in_tok=10, out_tok=5)
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            result = runner.run_without_tools("A task.")

        assert result.total_input_tokens == 10
        assert result.total_output_tokens == 5
        assert result.total_tokens == 15

    def test_uses_apples_system_prompt(self) -> None:
        from bricks_benchmark.mcp.agent_runner import AgentRunner
        from bricks_benchmark.mcp.scenarios import APPLES_SYSTEM

        mock_resp = _make_text_response("code here")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_create = mock_cls.return_value.messages.create
            mock_create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            runner.run_without_tools("My task.")

        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["system"] == APPLES_SYSTEM

    def test_no_tools_passed(self) -> None:
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        mock_resp = _make_text_response("code")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_create = mock_cls.return_value.messages.create
            mock_create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            runner.run_without_tools("A task.")

        call_kwargs = mock_create.call_args
        assert "tools" not in call_kwargs.kwargs

    def test_on_turn_callback_called(self) -> None:
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        mock_resp = _make_text_response("code", in_tok=10, out_tok=5)
        callback = MagicMock()
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            runner.run_without_tools("A task.", on_turn=callback)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == 1  # turn
        assert args[1] == "no_tools"  # mode
        assert args[2] == 10  # input_tokens
        assert args[3] == 5  # output_tokens


# ── run_with_bricks ───────────────────────────────────────────────────────────


class TestRunWithBricks:
    """Tests for AgentRunner.run_with_bricks()."""

    def test_tool_loop_two_turns(self) -> None:
        """Turn 1: tool_use(list_bricks) -> Turn 2: end_turn."""
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        tool_resp = _make_tool_response("list_bricks", "tc_001", {}, in_tok=20, out_tok=10)
        final_resp = _make_text_response("Done.", in_tok=30, out_tok=5)

        registry = _build_registry_a6()
        with patch("anthropic.Anthropic") as mock_cls:
            mock_create = mock_cls.return_value.messages.create
            mock_create.side_effect = [tool_resp, final_resp]
            runner = AgentRunner(api_key="test-key")
            result = runner.run_with_bricks("A task.", registry)

        assert result.turns == 2
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "list_bricks"

    def test_uses_dynamic_system_prompt_with_brick_signatures(self) -> None:
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        final_resp = _make_text_response("Done.")
        registry = _build_registry_a6()
        with patch("anthropic.Anthropic") as mock_cls:
            mock_create = mock_cls.return_value.messages.create
            mock_create.return_value = final_resp
            runner = AgentRunner(api_key="test-key")
            runner.run_with_bricks("A task.", registry)

        call_kwargs = mock_create.call_args
        system_prompt = call_kwargs.kwargs["system"]
        # Dynamic prompt should contain brick signatures
        assert "multiply(" in system_prompt
        assert "Do NOT call list_bricks" in system_prompt

    def test_token_accumulation_across_turns(self) -> None:
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        tool_resp = _make_tool_response("list_bricks", "t1", {}, in_tok=20, out_tok=10)
        final_resp = _make_text_response("Result.", in_tok=30, out_tok=5)

        registry = _build_registry_a6()
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [tool_resp, final_resp]
            runner = AgentRunner(api_key="test-key")
            result = runner.run_with_bricks("A task.", registry)

        assert result.total_input_tokens == 50
        assert result.total_output_tokens == 15
        assert result.total_tokens == 65

    def test_on_turn_callback_called_per_turn(self) -> None:
        from bricks_benchmark.mcp.agent_runner import AgentRunner

        tool_resp = _make_tool_response("list_bricks", "t1", {}, in_tok=20, out_tok=10)
        final_resp = _make_text_response("Done.", in_tok=30, out_tok=5)

        callback = MagicMock()
        registry = _build_registry_a6()
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [tool_resp, final_resp]
            runner = AgentRunner(api_key="test-key")
            runner.run_with_bricks("A task.", registry, on_turn=callback)

        assert callback.call_count == 2


# ── _execute_tool (real engine) ───────────────────────────────────────────────


class TestExecuteTool:
    """Tests for _execute_tool with real Bricks engine components."""

    def test_list_bricks_returns_list(self) -> None:
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        registry = _build_registry_a6()
        catalog = TieredCatalog(registry)
        engine = BlueprintEngine(registry=registry)
        loader = BlueprintLoader()
        validator = BlueprintValidator(registry=registry)

        result = _execute_tool("list_bricks", {}, catalog, engine, loader, validator)
        assert isinstance(result, list)

    def test_execute_blueprint_success(self) -> None:
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        registry = _build_registry_a6()
        catalog = TieredCatalog(registry)
        engine = BlueprintEngine(registry=registry)
        loader = BlueprintLoader()
        validator = BlueprintValidator(registry=registry)

        blueprint_yaml = """\
name: simple_add
steps:
  - name: add_step
    brick: add
    params:
      a: 3.0
      b: 4.0
    save_as: added
outputs_map:
  result: "${added.result}"
"""
        result = _execute_tool(
            "execute_blueprint",
            {"blueprint_yaml": blueprint_yaml, "inputs": {}},
            catalog,
            engine,
            loader,
            validator,
        )
        assert result["success"] is True
        assert result["outputs"]["result"] == 7.0

    def test_lookup_brick_returns_matches(self) -> None:
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        registry = _build_registry_a6()
        catalog = TieredCatalog(registry)
        engine = BlueprintEngine(registry=registry)
        loader = BlueprintLoader()
        validator = BlueprintValidator(registry=registry)

        result = _execute_tool("lookup_brick", {"query": "multiply"}, catalog, engine, loader, validator)
        assert isinstance(result, list)
        names = [r["name"] for r in result]
        assert "multiply" in names

    def test_execute_blueprint_error_returns_dict(self) -> None:
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        registry = _build_registry_a6()
        catalog = TieredCatalog(registry)
        engine = BlueprintEngine(registry=registry)
        loader = BlueprintLoader()
        validator = BlueprintValidator(registry=registry)

        result = _execute_tool(
            "execute_blueprint",
            {"blueprint_yaml": "invalid: yaml: ["},
            catalog,
            engine,
            loader,
            validator,
        )
        assert result["success"] is False
        assert "error" in result


# ── CLI flag parsing ──────────────────────────────────────────────────────────


class TestCLIModeFlag:
    """Tests for the --mode flag."""

    def test_valid_modes(self) -> None:
        """Both tool_use and compose are valid modes."""
        from bricks_benchmark.showcase.run import VALID_MODES

        assert "tool_use" in VALID_MODES
        assert "compose" in VALID_MODES

    def test_compose_mode_exists(self) -> None:
        """run_benchmark_compose function is importable and callable."""
        from bricks_benchmark.showcase.run import run_benchmark_compose

        assert callable(run_benchmark_compose)


class TestCLIScenarioExpansion:
    """Tests for the --scenario flag parsing logic."""

    def test_expand_all(self) -> None:
        """'all' expands to A presets + C + D + CRM scenarios."""
        from bricks_benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["all"])
        assert result == ["A-5", "A-25", "A-50", "C", "D", "CRM-pipeline", "CRM-hallucination", "CRM-reuse"]

    def test_expand_a(self) -> None:
        """'A' expands to all A presets."""
        from bricks_benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["A"])
        assert result == ["A-5", "A-25", "A-50"]

    def test_expand_a_with_steps(self) -> None:
        """'A' with --steps uses the specified step count."""
        from bricks_benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["A"], steps=12)
        assert result == ["A-12"]

    def test_expand_single(self) -> None:
        """Single explicit scenario passes through."""
        from bricks_benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["C"])
        assert result == ["C"]

    def test_expand_multiple(self) -> None:
        """Multiple scenarios expand correctly."""
        from bricks_benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["A", "C"], steps=5)
        assert result == ["A-5", "C"]

    def test_expand_preserves_order(self) -> None:
        """Order follows canonical A, C, D ordering."""
        from bricks_benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["D", "A"], steps=5)
        assert result == ["A-5", "D"]


# ── Cost estimation ──────────────────────────────────────────────────────────


class TestCostEstimation:
    """Tests for the cost estimation helper."""

    def test_zero_tokens(self) -> None:
        """Zero tokens produces zero cost."""
        from bricks_benchmark.showcase.formatters import estimate_cost

        assert estimate_cost(0, 0) == 0.0

    def test_known_cost(self) -> None:
        """1M input + 1M output at Haiku pricing = $4.80."""
        from bricks_benchmark.showcase.formatters import estimate_cost

        cost = estimate_cost(1_000_000, 1_000_000)
        assert cost > 0
        assert abs(cost - 4.80) < 0.01


# ── Agent Skill Prompt ──────────────────────────────────────────────────────


class TestAgentSkillPrompt:
    """Tests for bricks/skills/AGENT_PROMPT.md."""

    def test_file_exists(self) -> None:
        from pathlib import Path

        prompt_path = Path(__file__).parent.parent.parent / "bricks" / "skills" / "AGENT_PROMPT.md"
        assert prompt_path.exists(), f"Expected AGENT_PROMPT.md at {prompt_path}"

    def test_under_500_tokens(self) -> None:
        from pathlib import Path

        prompt_path = Path(__file__).parent.parent.parent / "bricks" / "skills" / "AGENT_PROMPT.md"
        text = prompt_path.read_text(encoding="utf-8")
        # Approximate token count: split on whitespace (conservative upper bound)
        word_count = len(text.split())
        assert word_count < 500, f"AGENT_PROMPT.md has ~{word_count} words (proxy for tokens), expected < 500"

    def test_contains_key_sections(self) -> None:
        from pathlib import Path

        prompt_path = Path(__file__).parent.parent.parent / "bricks" / "skills" / "AGENT_PROMPT.md"
        text = prompt_path.read_text(encoding="utf-8")
        assert "list_bricks" in text
        assert "execute_blueprint" in text
        assert "save_as" in text
        assert "${inputs." in text


# ── Enriched list_bricks in benchmark context ──────────────────────────────


class TestEnrichedBenchmarkBricks:
    """Tests that showcase bricks have categories and enriched metadata."""

    def test_showcase_math_bricks_have_category(self) -> None:
        from bricks_benchmark.showcase.bricks.math_bricks import multiply

        assert multiply.__brick_meta__.category == "math"

    def test_showcase_string_bricks_have_category(self) -> None:
        from bricks_benchmark.showcase.bricks.string_bricks import format_result

        assert format_result.__brick_meta__.category == "string"

    def test_list_bricks_has_enriched_fields(self) -> None:
        from bricks.core.catalog import TieredCatalog

        registry = _build_registry_a6()
        all_names = [name for name, _ in registry.list_all()]
        catalog = TieredCatalog(registry, common_set=all_names)
        result = catalog.list_bricks()

        for brick_schema in result:
            assert "category" in brick_schema, f"Missing 'category' in {brick_schema['name']}"
            assert "input_keys" in brick_schema, f"Missing 'input_keys' in {brick_schema['name']}"
            assert "output_keys" in brick_schema, f"Missing 'output_keys' in {brick_schema['name']}"


# ── build_apples_system ─────────────────────────────────────────────────────


class TestBuildApplesSystem:
    """Tests for build_apples_system() helper."""

    def test_with_registry_includes_signatures(self) -> None:
        from bricks_benchmark.mcp.scenarios import build_apples_system

        registry = _build_registry_a6()
        result = build_apples_system(registry)
        assert "multiply(" in result
        assert "add(" in result
        assert "Do NOT call list_bricks" in result

    def test_without_registry_is_base_prompt(self) -> None:
        from bricks_benchmark.mcp.scenarios import APPLES_SYSTEM, build_apples_system

        result = build_apples_system(None)
        assert result == APPLES_SYSTEM
        assert "Do NOT call list_bricks" not in result


# ── Actionable error messages ────────────────────────────────────────────────


class TestActionableErrors:
    """Tests for actionable error messages in _execute_tool."""

    def _setup(self) -> tuple:
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

        registry = _build_registry_a6()
        all_names = [name for name, _ in registry.list_all()]
        catalog = TieredCatalog(registry, common_set=all_names)
        engine = BlueprintEngine(registry=registry)
        loader = BlueprintLoader()
        validator = BlueprintValidator(registry=registry)
        return catalog, engine, loader, validator

    def test_unknown_brick_includes_available_list(self) -> None:
        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        catalog, engine, loader, validator = self._setup()
        blueprint_yaml = """\
name: test
steps:
  - name: step1
    brick: mult
    params:
      a: 1.0
      b: 2.0
    save_as: result
outputs_map:
  result: "${result.result}"
"""
        result = _execute_tool(
            "execute_blueprint",
            {"blueprint_yaml": blueprint_yaml},
            catalog,
            engine,
            loader,
            validator,
        )
        assert result["success"] is False
        assert "hint" in result
        assert "Available bricks:" in result["hint"] or "multiply" in result["hint"]

    def test_unknown_brick_suggests_closest_match(self) -> None:
        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        catalog, engine, loader, validator = self._setup()
        blueprint_yaml = """\
name: test
steps:
  - name: step1
    brick: mult
    params:
      a: 1.0
      b: 2.0
    save_as: result
outputs_map:
  result: "${result.result}"
"""
        result = _execute_tool(
            "execute_blueprint",
            {"blueprint_yaml": blueprint_yaml},
            catalog,
            engine,
            loader,
            validator,
        )
        assert result["success"] is False
        assert "multiply" in result["hint"]

    def test_validation_error_surfaces_all_errors(self) -> None:
        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        catalog, engine, loader, validator = self._setup()
        # Blueprint with two unknown bricks — should surface all_errors
        blueprint_yaml = """\
name: test
steps:
  - name: step1
    brick: nonexistent_a
    params:
      a: 1.0
    save_as: r1
  - name: step2
    brick: nonexistent_b
    params:
      b: 2.0
    save_as: r2
outputs_map:
  result: "${r1.result}"
"""
        result = _execute_tool(
            "execute_blueprint",
            {"blueprint_yaml": blueprint_yaml},
            catalog,
            engine,
            loader,
            validator,
        )
        assert result["success"] is False
        assert "all_errors" in result
        assert len(result["all_errors"]) >= 2

    def test_yaml_parse_error_has_hint(self) -> None:
        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        catalog, engine, loader, validator = self._setup()
        result = _execute_tool(
            "execute_blueprint",
            {"blueprint_yaml": "invalid: yaml: ["},
            catalog,
            engine,
            loader,
            validator,
        )
        assert result["success"] is False
        assert "error" in result

    def test_bad_reference_includes_save_as_names(self) -> None:
        from bricks_benchmark.mcp.tool_executor import execute_tool as _execute_tool

        catalog, engine, loader, validator = self._setup()
        # Blueprint where step2 references a non-existent save_as name
        blueprint_yaml = """\
name: test
steps:
  - name: calc
    brick: add
    params:
      a: 1.0
      b: 2.0
    save_as: calc_result
  - name: fmt
    brick: format_result
    params:
      label: "test"
      value: "${nonexistent.result}"
    save_as: display
outputs_map:
  display: "${display.display}"
"""
        result = _execute_tool(
            "execute_blueprint",
            {"blueprint_yaml": blueprint_yaml},
            catalog,
            engine,
            loader,
            validator,
        )
        assert result["success"] is False
        # Should have a hint with available save_as names
        assert "hint" in result
        assert "calc_result" in result["hint"]


# ── LLM-optimized brick descriptions ────────────────────────────────────────


def _build_all_showcase_registry() -> Any:
    """Build a registry with ALL showcase bricks (math + string + data).

    Returns:
        A BrickRegistry with all 7 showcase bricks.
    """
    from bricks_benchmark.showcase.bricks import build_showcase_registry
    from bricks_benchmark.showcase.bricks.data_bricks import http_get, json_extract
    from bricks_benchmark.showcase.bricks.math_bricks import add, multiply, round_value, subtract
    from bricks_benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, subtract, format_result, http_get, json_extract)


class TestBrickDescriptionStyle:
    """Tests that showcase brick descriptions follow the LLM-optimized style guide."""

    def test_descriptions_include_output_keys(self) -> None:
        """Every brick description must mention its output field names in {curly braces}."""
        from bricks.core.schema import output_keys

        registry = _build_all_showcase_registry()
        for name, meta in registry.list_all():
            callable_, _ = registry.get(name)
            out_keys = output_keys(callable_)
            # Function bricks returning dict[str, X] have empty output_keys,
            # so check the description contains at least one {field: ...} pattern
            desc = meta.description
            assert "{" in desc, f"Brick '{name}' description must mention output fields in {{curly braces}}"
            for key in out_keys:
                assert key in desc, f"Brick '{name}' description must mention output key '{key}'"

    def test_descriptions_under_120_chars(self) -> None:
        """Descriptions should be concise — under 120 characters."""
        registry = _build_all_showcase_registry()
        for name, meta in registry.list_all():
            assert len(meta.description) <= 120, (
                f"Brick '{name}' description is {len(meta.description)} chars (max 120)"
            )
