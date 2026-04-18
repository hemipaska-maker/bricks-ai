"""Tests for bricks.orchestrator.runtime — RuntimeOrchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bricks.ai.composer import ComposeResult
from bricks.boot.config import SystemConfig
from bricks.core.config import StoreConfig
from bricks.core.exceptions import OrchestratorError
from bricks.core.models import ExecutionResult, Verbosity
from bricks.core.registry import BrickRegistry
from bricks.core.selector import AllBricksSelector
from bricks.llm.base import CompletionResult, LLMProvider
from bricks.orchestrator.runtime import RuntimeOrchestrator
from bricks.selector.selector import TieredBrickSelector

# ── Helpers ────────────────────────────────────────────────────────────────

_VALID_YAML = """\
name: test_plan
steps:
  - name: step1
    brick: noop
    params: {}
    save_as: r1
outputs_map:
  result: "${r1.value}"
"""


def _make_registry() -> BrickRegistry:
    """Build a minimal registry with one noop brick."""
    from bricks.core.brick import brick

    @brick(tags=[], category="general", destructive=False)
    def noop() -> dict[str, str]:
        """Noop brick for testing. Returns {value: done}."""
        return {"value": "done"}

    reg = BrickRegistry()
    reg.register("noop", noop, noop.__brick_meta__)
    return reg


def _make_config(
    *,
    categories: list[str] | None = None,
    store_enabled: bool = False,
) -> SystemConfig:
    """Build a minimal SystemConfig for testing."""
    return SystemConfig(
        name="test",
        api_key="test-key",
        brick_categories=categories or [],
        store=StoreConfig(enabled=store_enabled),
    )


def _make_mock_provider() -> LLMProvider:
    """Build a mock LLMProvider that returns a dummy CompletionResult."""
    provider = MagicMock(spec=LLMProvider)
    provider.complete.return_value = CompletionResult(text="")
    return provider


def _make_orchestrator(
    config: SystemConfig | None = None,
    registry: BrickRegistry | None = None,
) -> RuntimeOrchestrator:
    """Create a RuntimeOrchestrator with a mock LLM provider."""
    cfg = config or _make_config()
    reg = registry or _make_registry()
    return RuntimeOrchestrator(cfg, reg, provider=_make_mock_provider())


def _valid_compose_result(cache_hit: bool = False) -> ComposeResult:
    """Build a valid ComposeResult for mocking."""
    return ComposeResult(
        task="test",
        blueprint_yaml=_VALID_YAML,
        is_valid=True,
        api_calls=1,
        total_tokens=100,
        model="claude-haiku-4-5-20251001",
        cache_hit=cache_hit,
    )


def _invalid_compose_result() -> ComposeResult:
    """Build an invalid ComposeResult for mocking."""
    return ComposeResult(
        task="test",
        blueprint_yaml="",
        is_valid=False,
        validation_errors=["brick 'missing' not found"],
        api_calls=2,
        total_tokens=200,
        model="claude-haiku-4-5-20251001",
    )


def _mock_execution() -> ExecutionResult:
    """Build a mock ExecutionResult."""

    return ExecutionResult(
        outputs={"result": "done"},
        steps=[],
        total_duration_ms=10.0,
        blueprint_name="test_plan",
        verbosity=Verbosity.MINIMAL,
    )


# ── TestRuntimeOrchestrator ─────────────────────────────────────────────────


class TestRuntimeOrchestrator:
    """Tests for RuntimeOrchestrator."""

    def test_execute_returns_outputs(self) -> None:
        """execute() returns the blueprint outputs on success."""
        orch = _make_orchestrator()
        orch._composer.compose = MagicMock(return_value=_valid_compose_result())  # type: ignore[assignment]
        orch._engine.run = MagicMock(return_value=_mock_execution())  # type: ignore[assignment]

        result = orch.execute("test task", {})
        assert result["outputs"] == {"result": "done"}

    def test_execute_cache_hit_flag(self) -> None:
        """execute() returns cache_hit=True when composer signals a cache hit."""
        orch = _make_orchestrator()
        orch._composer.compose = MagicMock(return_value=_valid_compose_result(cache_hit=True))  # type: ignore[assignment]
        orch._engine.run = MagicMock(return_value=_mock_execution())  # type: ignore[assignment]

        result = orch.execute("cached task", {})
        assert result["cache_hit"] is True
        assert result["api_calls"] == 1

    def test_execute_invalid_compose_raises(self) -> None:
        """execute() raises OrchestratorError when composition fails."""
        orch = _make_orchestrator()
        orch._composer.compose = MagicMock(return_value=_invalid_compose_result())  # type: ignore[assignment]

        with pytest.raises(OrchestratorError, match="Composition failed"):
            orch.execute("bad task", {})

    def test_execute_tokens_used_reported(self) -> None:
        """execute() reports tokens_used from compose result."""
        orch = _make_orchestrator()
        orch._composer.compose = MagicMock(return_value=_valid_compose_result())  # type: ignore[assignment]
        orch._engine.run = MagicMock(return_value=_mock_execution())  # type: ignore[assignment]

        result = orch.execute("task", {})
        assert result["tokens_used"] == 100

    def test_execute_none_inputs_defaults_to_empty(self) -> None:
        """execute() accepts None as inputs and passes {} to engine."""
        orch = _make_orchestrator()
        orch._composer.compose = MagicMock(return_value=_valid_compose_result())  # type: ignore[assignment]
        orch._engine.run = MagicMock(return_value=_mock_execution())  # type: ignore[assignment]

        result = orch.execute("task", None)
        assert "outputs" in result

    def test_orchestrator_uses_tiered_selector_with_categories(self) -> None:
        """When categories are configured, TieredBrickSelector is used."""
        cfg = _make_config(categories=["math", "data_transformation"])
        orch = RuntimeOrchestrator(cfg, _make_registry(), provider=_make_mock_provider())
        assert isinstance(orch._composer._selector, TieredBrickSelector)

    def test_orchestrator_uses_all_bricks_selector_without_categories(self) -> None:
        """When no categories are configured, AllBricksSelector is used."""
        cfg = _make_config(categories=[])
        orch = RuntimeOrchestrator(cfg, _make_registry(), provider=_make_mock_provider())
        assert isinstance(orch._composer._selector, AllBricksSelector)

    def test_orchestrator_no_store_when_disabled(self) -> None:
        """When store is disabled in config, composer store is None."""
        cfg = _make_config(store_enabled=False)
        orch = RuntimeOrchestrator(cfg, _make_registry(), provider=_make_mock_provider())
        assert orch._composer._store is None

    def test_orchestrator_store_enabled(self) -> None:
        """When store is enabled, composer receives a non-None store."""
        cfg = _make_config(store_enabled=True)
        cfg.store.backend = "memory"
        orch = RuntimeOrchestrator(cfg, _make_registry(), provider=_make_mock_provider())
        assert orch._composer._store is not None

    def test_execute_engine_error_raises_orchestrator_error(self) -> None:
        """execute() wraps engine errors in OrchestratorError."""
        orch = _make_orchestrator()
        orch._composer.compose = MagicMock(return_value=_valid_compose_result())  # type: ignore[assignment]
        orch._engine.run = MagicMock(side_effect=RuntimeError("engine exploded"))  # type: ignore[assignment]

        with pytest.raises(OrchestratorError, match="execution failed"):
            orch.execute("task", {})
