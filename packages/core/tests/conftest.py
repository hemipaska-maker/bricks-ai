"""Shared test fixtures for the Bricks test suite."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from bricks.core.brick import BrickFunction, brick
from bricks.core.models import BrickMeta
from bricks.core.registry import BrickRegistry
from bricks.llm.base import LLMProvider


def pytest_addoption(parser: Any) -> None:
    """Register --live flag for live integration tests."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run live integration tests using ClaudeCodeProvider",
    )


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Skip all @pytest.mark.live tests unless --live flag is passed."""
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="live test — run with --live to enable")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip_live)


@pytest.fixture()
def llm_provider(request: pytest.FixtureRequest) -> LLMProvider:
    """Return mock provider by default; ClaudeCodeProvider with --live flag."""
    if request.config.getoption("--live"):
        try:
            from bricks_provider_claudecode import ClaudeCodeProvider

            return ClaudeCodeProvider()  # type: ignore[return-value]
        except ImportError:
            pytest.skip("bricks-provider-claudecode not installed")
    mock: LLMProvider = MagicMock(spec=LLMProvider)
    return mock


@pytest.fixture()
def math_registry() -> BrickRegistry:
    """Registry with real add and multiply bricks."""
    reg = BrickRegistry()

    @brick(description="Add two numbers")
    def add(a: float, b: float) -> float:
        return a + b

    @brick(description="Multiply two numbers")
    def multiply(a: float, b: float) -> float:
        return a * b

    for fn in (add, multiply):
        typed = cast(BrickFunction, fn)
        reg.register(typed.__brick_meta__.name, typed, typed.__brick_meta__)
    return reg


@pytest.fixture()
def stub_registry_factory() -> Callable[..., BrickRegistry]:
    """Factory fixture: call with brick names to get a registry with stubs."""

    def _make(*brick_names: str) -> BrickRegistry:
        reg = BrickRegistry()
        for name in brick_names:
            reg.register(name, lambda: None, BrickMeta(name=name))
        return reg

    return _make
