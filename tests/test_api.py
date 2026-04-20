"""Tests for bricks/api.py — Bricks public Python API."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bricks.api import Bricks
from bricks.core.exceptions import OrchestratorError

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_mock_config(name: str = "test") -> MagicMock:
    """Return a minimal SystemConfig mock."""
    cfg = MagicMock()
    cfg.name = name
    cfg.api_key = ""
    cfg.model_copy.return_value = cfg
    return cfg


def _make_mock_orchestrator(outputs: dict[str, Any] | None = None) -> MagicMock:
    """Return a RuntimeOrchestrator mock."""
    orch = MagicMock()
    orch.execute.return_value = {
        "outputs": outputs or {"result": 42},
        "cache_hit": False,
        "api_calls": 1,
        "tokens_used": 500,
    }
    return orch


# ── tests ────────────────────────────────────────────────────────────────────


def test_from_config_boots_without_llm_call(tmp_path: Path) -> None:
    """from_config() calls bootstrap() once and makes zero direct LLM calls."""
    yaml_file = tmp_path / "agent.yaml"
    yaml_file.write_text("name: test\n", encoding="utf-8")

    mock_config = _make_mock_config()

    with (
        patch("bricks.api.SystemBootstrapper") as mock_boot_cls,
        patch("bricks.api.RuntimeOrchestrator") as mock_orch_cls,
        patch("bricks.api._build_default_registry"),
    ):
        mock_boot_cls.return_value.bootstrap.return_value = mock_config
        mock_orch_cls.return_value = _make_mock_orchestrator()

        Bricks.from_config(yaml_file)

        mock_boot_cls.assert_called_once_with(api_key="")
        mock_boot_cls.return_value.bootstrap.assert_called_once_with(yaml_file)


def test_from_skill_boots_with_one_llm_call(tmp_path: Path) -> None:
    """from_skill() calls bootstrap() with the .md path."""
    skill_file = tmp_path / "skill.md"
    skill_file.write_text("# My Agent\nProcesses data.", encoding="utf-8")

    mock_config = _make_mock_config()

    with (
        patch("bricks.api.SystemBootstrapper") as mock_boot_cls,
        patch("bricks.api.RuntimeOrchestrator") as mock_orch_cls,
        patch("bricks.api._build_default_registry"),
    ):
        mock_boot_cls.return_value.bootstrap.return_value = mock_config
        mock_orch_cls.return_value = _make_mock_orchestrator()

        Bricks.from_skill(skill_file, api_key="sk-test", model="claude-haiku-4-5-20251001")

        mock_boot_cls.assert_called_once_with(api_key="sk-test", model="claude-haiku-4-5-20251001")
        mock_boot_cls.return_value.bootstrap.assert_called_once_with(skill_file)


def test_execute_returns_orchestrator_result(tmp_path: Path) -> None:
    """execute() passes task + inputs through to the orchestrator and returns its result."""
    yaml_file = tmp_path / "agent.yaml"
    yaml_file.write_text("name: test\n", encoding="utf-8")

    mock_config = _make_mock_config()
    expected = {"outputs": {"total": 99.0}, "cache_hit": True, "api_calls": 0, "tokens_used": 0}

    with (
        patch("bricks.api.SystemBootstrapper") as mock_boot_cls,
        patch("bricks.api.RuntimeOrchestrator") as mock_orch_cls,
        patch("bricks.api._build_default_registry"),
    ):
        mock_boot_cls.return_value.bootstrap.return_value = mock_config
        mock_orch = MagicMock()
        mock_orch.execute.return_value = expected
        mock_orch_cls.return_value = mock_orch

        engine = Bricks.from_config(yaml_file)
        result = engine.execute("sum values", inputs={"values": [1, 2, 3]})

        mock_orch.execute.assert_called_once_with("sum values", {"values": [1, 2, 3]}, verbose=False)
        assert result == expected


def test_from_config_uses_stdlib_registry_by_default(tmp_path: Path) -> None:
    """from_config() without a custom registry calls _build_default_registry()."""
    yaml_file = tmp_path / "agent.yaml"
    yaml_file.write_text("name: test\n", encoding="utf-8")

    mock_config = _make_mock_config()

    with (
        patch("bricks.api.SystemBootstrapper") as mock_boot_cls,
        patch("bricks.api.RuntimeOrchestrator") as mock_orch_cls,
        patch("bricks.api._build_default_registry") as mock_stdlib,
    ):
        mock_boot_cls.return_value.bootstrap.return_value = mock_config
        mock_orch_cls.return_value = MagicMock()
        mock_stdlib.return_value = MagicMock()

        Bricks.from_config(yaml_file)

        mock_stdlib.assert_called_once()
        # RuntimeOrchestrator should have been given the stdlib registry
        _, kwargs = mock_orch_cls.call_args
        positional = mock_orch_cls.call_args.args
        passed_registry = positional[1] if len(positional) > 1 else kwargs.get("registry")
        assert passed_registry is mock_stdlib.return_value


def test_from_config_accepts_custom_registry(tmp_path: Path) -> None:
    """from_config() passes a custom registry to RuntimeOrchestrator."""
    yaml_file = tmp_path / "agent.yaml"
    yaml_file.write_text("name: test\n", encoding="utf-8")

    mock_config = _make_mock_config()

    with (
        patch("bricks.api.SystemBootstrapper") as mock_boot_cls,
        patch("bricks.api.RuntimeOrchestrator") as mock_orch_cls,
        patch("bricks.api._build_default_registry") as mock_stdlib,
    ):
        mock_boot_cls.return_value.bootstrap.return_value = mock_config
        mock_orch_cls.return_value = MagicMock()
        custom_registry = MagicMock()

        Bricks.from_config(yaml_file, registry=custom_registry)

        mock_stdlib.assert_not_called()
        positional = mock_orch_cls.call_args.args
        kwargs = mock_orch_cls.call_args.kwargs
        passed_registry = positional[1] if len(positional) > 1 else kwargs.get("registry")
        assert passed_registry is custom_registry


def test_default_returns_bricks_instance() -> None:
    """Bricks.default() returns a Bricks instance."""
    from bricks.llm.base import LLMProvider

    mock_prov = MagicMock(spec=LLMProvider)
    result = Bricks.default(provider=mock_prov)
    assert isinstance(result, Bricks)


def test_default_uses_bricks_model_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bricks.default() reads BRICKS_MODEL env var for the model."""
    from unittest.mock import patch as _patch

    monkeypatch.setenv("BRICKS_MODEL", "gpt-4o-mini")
    captured: dict[str, str] = {}

    def fake_litellm_init(self_inner: Any, model: str = "claude-haiku-4-5", api_key: str = "") -> None:
        captured["model"] = model
        self_inner._model = model
        self_inner._api_key = api_key or None

    with _patch("bricks.llm.litellm_provider.LiteLLMProvider.__init__", fake_litellm_init):
        Bricks.default()

    assert captured.get("model") == "gpt-4o-mini"


def test_execute_propagates_orchestrator_error(tmp_path: Path) -> None:
    """OrchestratorError raised inside the orchestrator surfaces from execute()."""
    yaml_file = tmp_path / "agent.yaml"
    yaml_file.write_text("name: test\n", encoding="utf-8")

    mock_config = _make_mock_config()

    with (
        patch("bricks.api.SystemBootstrapper") as mock_boot_cls,
        patch("bricks.api.RuntimeOrchestrator") as mock_orch_cls,
        patch("bricks.api._build_default_registry"),
    ):
        mock_boot_cls.return_value.bootstrap.return_value = mock_config
        mock_orch = MagicMock()
        mock_orch.execute.side_effect = OrchestratorError("Composition failed")
        mock_orch_cls.return_value = mock_orch

        engine = Bricks.from_config(yaml_file)

        with pytest.raises(OrchestratorError, match="Composition failed"):
            engine.execute("do something")
