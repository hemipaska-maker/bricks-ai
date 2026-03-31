"""Tests for bricks.mcp — execute_task tool."""

from __future__ import annotations

from unittest.mock import MagicMock

from bricks.mcp.tool import EXECUTE_TASK_SCHEMA, execute_task


class TestExecuteTaskTool:
    """Tests for the execute_task tool function."""

    def test_execute_task_delegates_to_orchestrator(self) -> None:
        """execute_task calls orchestrator.execute() and returns result."""
        from bricks.orchestrator.runtime import RuntimeOrchestrator

        mock_orch = MagicMock(spec=RuntimeOrchestrator)
        mock_orch.execute.return_value = {
            "outputs": {"result": 42},
            "cache_hit": False,
            "api_calls": 1,
            "tokens_used": 100,
        }
        result = execute_task(mock_orch, "sum values", {"values": [1, 2]})
        mock_orch.execute.assert_called_once_with("sum values", {"values": [1, 2]})
        assert result["outputs"]["result"] == 42

    def test_execute_task_schema_has_required_task_field(self) -> None:
        """EXECUTE_TASK_SCHEMA declares task as required."""
        assert EXECUTE_TASK_SCHEMA["name"] == "execute_task"
        assert "task" in EXECUTE_TASK_SCHEMA["input_schema"]["required"]

    def test_execute_task_empty_inputs_passes_empty_dict(self) -> None:
        """execute_task with no inputs passes empty dict."""
        from bricks.orchestrator.runtime import RuntimeOrchestrator

        mock_orch = MagicMock(spec=RuntimeOrchestrator)
        mock_orch.execute.return_value = {
            "outputs": {},
            "cache_hit": False,
            "api_calls": 0,
            "tokens_used": 0,
        }
        execute_task(mock_orch, "a task")
        mock_orch.execute.assert_called_once_with("a task", {})
