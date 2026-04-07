"""Tests for bricks.mcp — execute_task tool and MCP server handlers."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from bricks.mcp.tool import EXECUTE_TASK_SCHEMA, execute_task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_orchestrator(
    outputs: dict | None = None,
    cache_hit: bool = False,
    api_calls: int = 1,
    tokens_used: int = 100,
    input_tokens: int = 80,
    output_tokens: int = 20,
) -> MagicMock:
    """Return a mock RuntimeOrchestrator with a configured execute() return value."""
    from bricks.orchestrator.runtime import RuntimeOrchestrator

    mock = MagicMock(spec=RuntimeOrchestrator)
    mock.execute.return_value = {
        "outputs": outputs or {"result": 42},
        "cache_hit": cache_hit,
        "api_calls": api_calls,
        "tokens_used": tokens_used,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    return mock


def _mock_orchestrator_verbose() -> MagicMock:
    """Return a mock orchestrator with a verbose execute() return value."""
    from bricks.orchestrator.runtime import RuntimeOrchestrator

    mock = MagicMock(spec=RuntimeOrchestrator)
    mock.execute.return_value = {
        "outputs": {"result": 42},
        "cache_hit": False,
        "api_calls": 1,
        "tokens_used": 100,
        "input_tokens": 80,
        "output_tokens": 20,
        "blueprint_yaml": "name: test\nsteps: []\noutputs_map: {}\n",
        "blueprint_name": "test",
        "model": "claude-haiku-4-5",
        "compose_duration_seconds": 0.5,
        "execution_duration_ms": 10.0,
        "steps": [
            {
                "step": "step1",
                "brick": "add_numbers",
                "inputs": {"a": 1, "b": 2},
                "outputs": {"result": 3},
                "duration_ms": 1.0,
            }
        ],
    }
    return mock


def _make_bricks_engine() -> MagicMock:
    """Create a mock Bricks engine with registry and blueprint_store."""
    from bricks.core.models import BrickMeta
    from bricks.store.blueprint_store import MemoryBlueprintStore

    engine = MagicMock()
    meta = BrickMeta(name="add_numbers", description="Add two numbers", tags=["math"])
    engine.registry.list_all.return_value = [("add_numbers", meta)]
    engine.registry.list_public.return_value = [("add_numbers", meta)]
    engine.blueprint_store = MemoryBlueprintStore()
    engine.execute.return_value = {
        "outputs": {},
        "cache_hit": False,
        "api_calls": 0,
        "tokens_used": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    return engine


@asynccontextmanager
async def _fake_stdio():  # type: ignore[misc]
    """Fake stdio_server context manager for testing."""
    yield MagicMock(), MagicMock()


def _build_fake_server(captured: dict) -> object:
    """Build a FakeServer that captures registered handlers into ``captured``."""

    class _FakeServer:
        def __init__(self, _: str) -> None:
            pass

        def _make_capturer(self, key: str):  # type: ignore[return]
            def decorator(fn):  # type: ignore[return]
                captured[key] = fn
                return fn

            return lambda fn: decorator(fn)

        def list_tools(self):
            return self._make_capturer("list_tools")

        def call_tool(self):
            return self._make_capturer("call_tool")

        def list_resources(self):
            return self._make_capturer("list_resources")

        def read_resource(self):
            return self._make_capturer("read_resource")

        def list_prompts(self):
            return self._make_capturer("list_prompts")

        def get_prompt(self):
            return self._make_capturer("get_prompt")

        def create_initialization_options(self):
            return None

        async def run(self, *_args, **_kwargs):  # type: ignore[return]
            pass

    return _FakeServer("bricks")


def _capture_handlers(engine: MagicMock) -> dict:
    """Run run_mcp_server with a fake server and return all captured handlers."""
    import asyncio

    from bricks.mcp.server import run_mcp_server

    captured: dict = {}

    async def _run() -> None:
        fake = _build_fake_server(captured)
        with (
            patch("mcp.server.Server", return_value=fake),
            patch("mcp.server.stdio.stdio_server", _fake_stdio),
        ):
            await run_mcp_server(engine)

    asyncio.run(_run())
    return captured


# ---------------------------------------------------------------------------
# Original 3 tests (adjusted for new verbose param, functionally equivalent)
# ---------------------------------------------------------------------------


class TestExecuteTaskTool:
    """Tests for the execute_task tool function."""

    def test_execute_task_delegates_to_orchestrator(self) -> None:
        """execute_task calls orchestrator.execute() and returns result."""
        mock_orch = _mock_orchestrator(outputs={"result": 42})
        result = execute_task(mock_orch, "sum values", {"values": [1, 2]})
        mock_orch.execute.assert_called_once_with("sum values", {"values": [1, 2]}, verbose=False)
        assert result["outputs"]["result"] == 42

    def test_execute_task_schema_has_required_task_field(self) -> None:
        """EXECUTE_TASK_SCHEMA declares task as required."""
        assert EXECUTE_TASK_SCHEMA["name"] == "execute_task"
        assert "task" in EXECUTE_TASK_SCHEMA["input_schema"]["required"]

    def test_execute_task_empty_inputs_passes_empty_dict(self) -> None:
        """execute_task with no inputs passes empty dict."""
        mock_orch = _mock_orchestrator(outputs={})
        execute_task(mock_orch, "a task")
        mock_orch.execute.assert_called_once_with("a task", {}, verbose=False)


# ---------------------------------------------------------------------------
# Verbose flag tests
# ---------------------------------------------------------------------------


class TestVerboseFlag:
    """Tests for the verbose parameter."""

    def test_execute_task_verbose_false_returns_base_keys(self) -> None:
        """verbose=False (default) result has all standard keys."""
        mock_orch = _mock_orchestrator()
        result = execute_task(mock_orch, "task")
        for key in ("outputs", "cache_hit", "api_calls", "tokens_used", "input_tokens", "output_tokens"):
            assert key in result

    def test_execute_task_verbose_true_passes_flag(self) -> None:
        """execute_task(verbose=True) passes verbose=True to orchestrator."""
        mock_orch = _mock_orchestrator_verbose()
        execute_task(mock_orch, "task", verbose=True)
        mock_orch.execute.assert_called_once_with("task", {}, verbose=True)

    def test_execute_task_verbose_true_returns_extended_keys(self) -> None:
        """verbose=True result has blueprint_yaml, steps, model, durations."""
        mock_orch = _mock_orchestrator_verbose()
        result = execute_task(mock_orch, "task", verbose=True)
        for key in (
            "blueprint_yaml",
            "blueprint_name",
            "model",
            "compose_duration_seconds",
            "execution_duration_ms",
            "steps",
        ):
            assert key in result

    def test_verbose_steps_have_expected_keys(self) -> None:
        """Each step entry has step, brick, inputs, outputs, duration_ms."""
        mock_orch = _mock_orchestrator_verbose()
        result = execute_task(mock_orch, "task", verbose=True)
        for step in result["steps"]:
            for key in ("step", "brick", "inputs", "outputs", "duration_ms"):
                assert key in step

    def test_schema_has_verbose_field(self) -> None:
        """EXECUTE_TASK_SCHEMA includes the verbose property."""
        props = EXECUTE_TASK_SCHEMA["input_schema"]["properties"]
        assert "verbose" in props
        assert props["verbose"]["type"] == "boolean"


# ---------------------------------------------------------------------------
# Token split tests
# ---------------------------------------------------------------------------


class TestTokenSplit:
    """Tests for input_tokens / output_tokens split."""

    def test_execute_task_returns_input_tokens(self) -> None:
        """Result always includes input_tokens."""
        mock_orch = _mock_orchestrator(input_tokens=80, output_tokens=20, tokens_used=100)
        result = execute_task(mock_orch, "task")
        assert result["input_tokens"] == 80

    def test_execute_task_returns_output_tokens(self) -> None:
        """Result always includes output_tokens."""
        mock_orch = _mock_orchestrator(input_tokens=80, output_tokens=20, tokens_used=100)
        result = execute_task(mock_orch, "task")
        assert result["output_tokens"] == 20

    def test_tokens_used_still_present(self) -> None:
        """tokens_used is preserved (backwards compat)."""
        mock_orch = _mock_orchestrator(tokens_used=100)
        result = execute_task(mock_orch, "task")
        assert result["tokens_used"] == 100


# ---------------------------------------------------------------------------
# Resource tests
# ---------------------------------------------------------------------------


class TestResources:
    """Tests for MCP resource handlers."""

    def test_list_resources_returns_catalog_and_blueprints(self) -> None:
        """list_resources returns catalog and blueprints URIs."""
        import asyncio

        handlers = _capture_handlers(_make_bricks_engine())
        resources = asyncio.run(handlers["list_resources"]())
        uris = [str(r.uri) for r in resources]
        assert any("catalog" in u for u in uris)
        assert any("blueprint" in u for u in uris)

    def test_read_catalog_returns_registered_bricks(self) -> None:
        """bricks://catalog resource lists all registered bricks."""
        import asyncio

        from pydantic.networks import AnyUrl

        handlers = _capture_handlers(_make_bricks_engine())
        result = asyncio.run(handlers["read_resource"](AnyUrl("bricks://catalog")))
        parsed = json.loads(result[0].content)
        assert any(b["name"] == "add_numbers" for b in parsed)

    def test_read_blueprints_returns_empty_for_new_store(self) -> None:
        """bricks://blueprints returns empty list when store has no entries."""
        import asyncio

        from pydantic.networks import AnyUrl

        handlers = _capture_handlers(_make_bricks_engine())
        result = asyncio.run(handlers["read_resource"](AnyUrl("bricks://blueprints")))
        parsed = json.loads(result[0].content)
        assert parsed == []

    def test_read_unknown_resource_raises(self) -> None:
        """read_resource raises ValueError for unknown URIs."""
        import asyncio

        from pydantic.networks import AnyUrl

        handlers = _capture_handlers(_make_bricks_engine())
        with pytest.raises(ValueError, match="Unknown resource"):
            asyncio.run(handlers["read_resource"](AnyUrl("bricks://unknown")))


# ---------------------------------------------------------------------------
# Prompt tests
# ---------------------------------------------------------------------------


class TestPrompts:
    """Tests for MCP prompt handlers."""

    def test_list_prompts_returns_three_templates(self) -> None:
        """list_prompts returns exactly 3 prompt templates."""
        import asyncio

        handlers = _capture_handlers(_make_bricks_engine())
        prompts = asyncio.run(handlers["list_prompts"]())
        assert len(prompts) == 3
        names = {p.name for p in prompts}
        assert names == {"process_csv", "validate_data", "filter_and_aggregate"}

    def test_get_prompt_process_csv(self) -> None:
        """get_prompt('process_csv') renders a message with the description."""
        import asyncio

        handlers = _capture_handlers(_make_bricks_engine())
        result = asyncio.run(handlers["get_prompt"]("process_csv", {"description": "count rows"}))
        text = result.messages[0].content.text
        assert "count rows" in text

    def test_get_prompt_unknown_raises(self) -> None:
        """get_prompt with an unknown name raises ValueError."""
        import asyncio

        handlers = _capture_handlers(_make_bricks_engine())
        with pytest.raises(ValueError, match="Unknown prompt"):
            asyncio.run(handlers["get_prompt"]("nonexistent", {}))


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for structured error responses."""

    def _engine_raises(self, exc: Exception) -> MagicMock:
        engine = MagicMock()
        engine.registry.list_all.return_value = []
        engine.registry.list_public.return_value = []
        engine.blueprint_store = None
        engine.execute.side_effect = exc
        return engine

    def test_validation_error_returns_structured_json(self) -> None:
        """BlueprintValidationError returns structured JSON with retryable=True."""
        import asyncio

        from bricks.core.exceptions import BlueprintValidationError

        exc = BlueprintValidationError("bad blueprint", errors=["missing field x"])
        handlers = _capture_handlers(self._engine_raises(exc))
        result = asyncio.run(handlers["call_tool"]("execute_task", {"task": "do something"}))
        data = json.loads(result[0].text)
        assert data["error"] is True
        assert data["error_type"] == "validation_error"
        assert data["retryable"] is True

    def test_composition_error_returns_retryable_true(self) -> None:
        """OrchestratorError returns structured JSON with retryable=True."""
        import asyncio

        from bricks.core.exceptions import OrchestratorError

        handlers = _capture_handlers(self._engine_raises(OrchestratorError("composition failed")))
        result = asyncio.run(handlers["call_tool"]("execute_task", {"task": "do something"}))
        data = json.loads(result[0].text)
        assert data["error_type"] == "composition_failed"
        assert data["retryable"] is True

    def test_execution_error_returns_retryable_false(self) -> None:
        """BrickExecutionError returns structured JSON with retryable=False."""
        import asyncio

        from bricks.core.exceptions import BrickExecutionError

        exc = BrickExecutionError("add_numbers", "step1", ValueError("oops"))
        handlers = _capture_handlers(self._engine_raises(exc))
        result = asyncio.run(handlers["call_tool"]("execute_task", {"task": "add"}))
        data = json.loads(result[0].text)
        assert data["error_type"] == "execution_failed"
        assert data["retryable"] is False
        assert data["details"]["brick"] == "add_numbers"

    def test_unknown_tool_raises_value_error(self) -> None:
        """call_tool with an unknown name raises ValueError."""
        import asyncio

        engine = MagicMock()
        engine.registry.list_all.return_value = []
        engine.registry.list_public.return_value = []
        engine.blueprint_store = None
        handlers = _capture_handlers(engine)
        with pytest.raises(ValueError, match="Unknown tool"):
            asyncio.run(handlers["call_tool"]("bogus_tool", {"task": "x"}))


# ---------------------------------------------------------------------------
# Logging test
# ---------------------------------------------------------------------------


class TestLogging:
    """Tests for MCP server logging."""

    def test_call_tool_logs_info(self) -> None:
        """call_tool logs at INFO level when execute_task is called."""
        import asyncio

        engine = _make_bricks_engine()
        handlers = _capture_handlers(engine)
        with patch.object(logging.getLogger("bricks.mcp"), "info") as mock_log:
            asyncio.run(handlers["call_tool"]("execute_task", {"task": "hello"}))
            assert mock_log.call_count >= 1
