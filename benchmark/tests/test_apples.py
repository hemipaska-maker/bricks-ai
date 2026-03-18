"""Tests for the apples-to-apples benchmark: AgentRunner and supporting models."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_text_response(text: str, in_tok: int = 10, out_tok: int = 5) -> MagicMock:
    """Build a mock Anthropic response that returns end_turn with a text block."""
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
    """Build a mock Anthropic response that issues a tool_use call."""
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
    """Build a BrickRegistry with A-6 bricks (math + string)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, format_result)


# ── AgentResult model ─────────────────────────────────────────────────────────


class TestAgentResultModel:
    """Tests for AgentResult and ToolCallRecord models."""

    def test_total_tokens_field(self) -> None:
        from benchmark.mcp.agent_result import AgentResult

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
        from benchmark.mcp.agent_result import AgentResult

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
        from benchmark.mcp.agent_result import ToolCallRecord

        rec = ToolCallRecord(name="list_bricks", inputs={}, output=["brick_a"])
        assert rec.name == "list_bricks"
        assert rec.output == ["brick_a"]


# ── run_without_tools ─────────────────────────────────────────────────────────


class TestRunWithoutTools:
    """Tests for AgentRunner.run_without_tools()."""

    def test_mode_and_turns(self) -> None:
        from benchmark.mcp.agent_runner import AgentRunner

        mock_resp = _make_text_response("def calc(): return 42")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            result = runner.run_without_tools("Compute something.")

        assert result.mode == "no_tools"
        assert result.turns == 1

    def test_token_counting(self) -> None:
        from benchmark.mcp.agent_runner import AgentRunner

        mock_resp = _make_text_response("x = 1", in_tok=10, out_tok=5)
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            result = runner.run_without_tools("A task.")

        assert result.total_input_tokens == 10
        assert result.total_output_tokens == 5
        assert result.total_tokens == 15

    def test_uses_apples_system_prompt(self) -> None:
        from benchmark.mcp.agent_runner import AgentRunner
        from benchmark.mcp.scenarios import APPLES_SYSTEM

        mock_resp = _make_text_response("code here")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_create = mock_cls.return_value.messages.create
            mock_create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            runner.run_without_tools("My task.")

        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["system"] == APPLES_SYSTEM

    def test_no_tools_passed(self) -> None:
        from benchmark.mcp.agent_runner import AgentRunner

        mock_resp = _make_text_response("code")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_create = mock_cls.return_value.messages.create
            mock_create.return_value = mock_resp
            runner = AgentRunner(api_key="test-key")
            runner.run_without_tools("A task.")

        call_kwargs = mock_create.call_args
        assert "tools" not in call_kwargs.kwargs

    def test_on_turn_callback_called(self) -> None:
        from benchmark.mcp.agent_runner import AgentRunner

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
        from benchmark.mcp.agent_runner import AgentRunner

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

    def test_uses_apples_system_prompt_with_tools(self) -> None:
        from benchmark.mcp.agent_runner import AgentRunner
        from benchmark.mcp.scenarios import APPLES_SYSTEM

        final_resp = _make_text_response("Done.")
        registry = _build_registry_a6()
        with patch("anthropic.Anthropic") as mock_cls:
            mock_create = mock_cls.return_value.messages.create
            mock_create.return_value = final_resp
            runner = AgentRunner(api_key="test-key")
            runner.run_with_bricks("A task.", registry)

        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["system"] == APPLES_SYSTEM

    def test_token_accumulation_across_turns(self) -> None:
        from benchmark.mcp.agent_runner import AgentRunner

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
        from benchmark.mcp.agent_runner import AgentRunner

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
        from benchmark.mcp.agent_runner import _execute_tool
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

        registry = _build_registry_a6()
        catalog = TieredCatalog(registry)
        engine = BlueprintEngine(registry=registry)
        loader = BlueprintLoader()
        validator = BlueprintValidator(registry=registry)

        result = _execute_tool("list_bricks", {}, catalog, engine, loader, validator)
        assert isinstance(result, list)

    def test_execute_blueprint_success(self) -> None:
        from benchmark.mcp.agent_runner import _execute_tool
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

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
        from benchmark.mcp.agent_runner import _execute_tool
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

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
        from benchmark.mcp.agent_runner import _execute_tool
        from bricks.core.catalog import TieredCatalog
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.validation import BlueprintValidator

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


class TestCLIScenarioExpansion:
    """Tests for the --scenario flag parsing logic."""

    def test_expand_all(self) -> None:
        from benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["all"])
        assert result == ["A2-3", "A2-6", "A2-12", "C2", "D2"]

    def test_expand_a2(self) -> None:
        from benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["A2"])
        assert result == ["A2-3", "A2-6", "A2-12"]

    def test_expand_single(self) -> None:
        from benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["A2-3"])
        assert result == ["A2-3"]

    def test_expand_multiple(self) -> None:
        from benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["A2-3", "C2"])
        assert result == ["A2-3", "C2"]

    def test_expand_dedup(self) -> None:
        from benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["A2-3", "A2"])
        assert result == ["A2-3", "A2-6", "A2-12"]

    def test_expand_preserves_order(self) -> None:
        from benchmark.showcase.run import expand_scenarios

        result = expand_scenarios(["D2", "A2-3"])
        assert result == ["A2-3", "D2"]


# ── Cost estimation ──────────────────────────────────────────────────────────


class TestCostEstimation:
    """Tests for the cost estimation helper."""

    def test_zero_tokens(self) -> None:
        from benchmark.showcase.run import _estimate_cost

        assert _estimate_cost(0, 0) == 0.0

    def test_known_cost(self) -> None:
        from benchmark.showcase.run import _estimate_cost

        # 1M input + 1M output
        cost = _estimate_cost(1_000_000, 1_000_000)
        assert cost > 0
        # Haiku pricing: $0.80/M input + $4.00/M output = $4.80
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
        from benchmark.showcase.bricks.math_bricks import multiply

        assert multiply.__brick_meta__.category == "math"

    def test_showcase_string_bricks_have_category(self) -> None:
        from benchmark.showcase.bricks.string_bricks import format_result

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
