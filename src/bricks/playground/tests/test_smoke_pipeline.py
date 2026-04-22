"""Smoke tests for the full DSL → FlowDefinition → execute pipeline.

These tests run in CI with zero external dependencies (no LLM, no network).
They verify the end-to-end path that Mission 070 fixed: DSL string parsed
into a FlowDefinition, then executed with real bricks and real data.

If these tests break, the YAML-roundtrip bug (Mission 070) has been
reintroduced — bricks are receiving None instead of real runtime data.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from bricks.ai.composer import BlueprintComposer, ComposeResult
from bricks.core.brick import BrickFunction, brick
from bricks.core.dsl import FlowDefinition
from bricks.core.engine import BlueprintEngine
from bricks.core.registry import BrickRegistry


def _make_registry() -> BrickRegistry:
    """Build a BrickRegistry with two inline test bricks.

    Both bricks return ``{"result": value}`` so ``${step_name.result}``
    references resolve correctly in the blueprint.

    Returns:
        Registry containing ``count_chars`` and ``repeat_text`` bricks.
    """
    registry = BrickRegistry()

    @brick(description="Count characters in text. Returns {result: count}.")
    def count_chars(text: str) -> dict:  # type: ignore[type-arg]
        """Count chars."""
        return {"result": len(text)}

    @brick(description="Repeat text N times. Returns {result: repeated}.")
    def repeat_text(text: str, times: int) -> dict:  # type: ignore[type-arg]
        """Repeat text."""
        return {"result": text * times}

    for fn in (count_chars, repeat_text):
        typed = cast(BrickFunction, fn)
        registry.register(typed.__brick_meta__.name, typed, typed.__brick_meta__)

    return registry


class TestSmokePipeline:
    """Full pipeline smoke tests: DSL → FlowDefinition → execute → output."""

    def test_smoke_compose_to_execute(self) -> None:
        """DSL string → FlowDefinition → execute with real bricks → correct output.

        Bypasses the LLM by calling _parse_dsl_response() directly. Verifies
        that step params receive real input values (not None from the @flow
        structural trace), and that the pipeline produces the expected output.

        If the YAML-roundtrip bug (Mission 070) is reintroduced, count_chars
        will receive None and raise AttributeError, failing this test.
        """
        dsl_code = """\
@flow
def count_pipeline(raw_text):
    result = step.count_chars(text=raw_text)
    return result
"""
        # _parse_dsl_response bypasses the LLM — no provider needed
        composer = BlueprintComposer.__new__(BlueprintComposer)
        composer._provider = MagicMock()
        from bricks.core.selector import AllBricksSelector

        composer._selector = AllBricksSelector()
        composer._store = None

        flow_def = composer._parse_dsl_response(dsl_code)
        assert isinstance(flow_def, FlowDefinition)

        registry = _make_registry()
        engine = BlueprintEngine(registry=registry)

        # If re-tracing is broken (params are None), count_chars raises
        # AttributeError("'NoneType' object has no attribute '__len__'").
        result = flow_def.execute(engine=engine, raw_text="hello")

        assert "result" in result, f"Expected 'result' key in outputs, got: {result}"
        assert result["result"] == 5, f"Expected 5 chars in 'hello', got: {result['result']}"

    def test_compose_result_exec_outputs_survive_to_engine(self) -> None:
        """Regression: BricksEngine.solve reads ``exec_outputs`` from ComposeResult.

        After #27 the composer's HealerChain owns runtime execution; solve()
        just forwards an executor closure and trusts ``exec_outputs``. This
        test pins that contract — in particular, the YAML-roundtrip path
        must never be re-introduced (loader.load_string must not be called).
        """
        from bricks.playground.showcase.engine import BricksEngine

        mock_flow_def = MagicMock(spec=FlowDefinition)

        mock_compose_result = MagicMock(spec=ComposeResult)
        mock_compose_result.is_valid = True
        mock_compose_result.flow_def = mock_flow_def
        mock_compose_result.blueprint_yaml = "name: placeholder"
        mock_compose_result.dsl_code = "@flow\ndef placeholder():\n    return None\n"
        mock_compose_result.total_input_tokens = 0
        mock_compose_result.total_output_tokens = 0
        mock_compose_result.model = "test-model"
        mock_compose_result.exec_outputs = {"active_count": 5}
        mock_compose_result.exec_error = ""
        mock_compose_result.heal_attempts = []

        engine = BricksEngine.__new__(BricksEngine)
        engine._composer = MagicMock()
        engine._composer.compose.return_value = mock_compose_result
        engine._engine = MagicMock()
        engine._loader = MagicMock()
        engine._registry = MagicMock()

        result = engine.solve("count active customers", '{"data": []}')

        # compose() must have been called with an executor closure.
        kwargs = engine._composer.compose.call_args.kwargs
        assert "executor" in kwargs and callable(kwargs["executor"])
        engine._loader.load_string.assert_not_called()
        assert result.outputs == {"active_count": 5}

    def test_direct_flow_execution_with_real_bricks(self) -> None:
        """Full pipeline: pre-written DSL → FlowDefinition → execute with real registry.

        No LLM. No mocked engine. Uses inline bricks and a dict-return flow to
        verify the multi-output path introduced in Mission 072. Asserts that both
        output keys are remapped correctly and hold real computed values.
        """
        dsl_code = """\
@flow
def multi_pipeline(raw_text):
    char_count = step.count_chars(text=raw_text)
    repeated = step.repeat_text(text=raw_text, times=2)
    return {"char_count": char_count, "doubled": repeated}
"""
        composer = BlueprintComposer.__new__(BlueprintComposer)
        composer._provider = MagicMock()
        from bricks.core.selector import AllBricksSelector

        composer._selector = AllBricksSelector()
        composer._store = None

        flow_def = composer._parse_dsl_response(dsl_code)
        assert isinstance(flow_def, FlowDefinition)

        registry = _make_registry()
        engine = BlueprintEngine(registry=registry)

        result = flow_def.execute(inputs={"raw_text": "hello"}, engine=engine)

        assert "char_count" in result, f"Expected 'char_count' in outputs, got: {result}"
        assert "doubled" in result, f"Expected 'doubled' in outputs, got: {result}"
        assert result["char_count"] == 5, f"Expected 5, got: {result['char_count']}"
        assert result["doubled"] == "hellohello", f"Expected 'hellohello', got: {result['doubled']}"
