"""Live integration tests for full compose + execute pipeline.

Run with: pytest --live -m live
Skipped by default (no --live flag).
"""

from __future__ import annotations

import pytest
from bricks.api import Bricks
from bricks.llm.base import LLMProvider


@pytest.mark.live
def test_full_pipeline(llm_provider: LLMProvider) -> None:
    """Compose a blueprint and execute it with real LLM — end to end."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "filter items where status is active",
        {
            "items": [
                {"name": "A", "status": "active"},
                {"name": "B", "status": "inactive"},
                {"name": "C", "status": "active"},
            ]
        },
    )
    assert isinstance(result["outputs"], dict)
    assert result["api_calls"] >= 1


@pytest.mark.live
def test_reuse_hits_cache(llm_provider: LLMProvider) -> None:
    """Second call with identical task should hit cache when store is enabled."""
    from bricks.boot.config import SystemConfig  # noqa: PLC0415
    from bricks.core.config import StoreConfig  # noqa: PLC0415
    from bricks.core.registry import BrickRegistry  # noqa: PLC0415
    from bricks.orchestrator.runtime import RuntimeOrchestrator  # noqa: PLC0415
    from bricks_stdlib import register as _reg_stdlib  # noqa: PLC0415

    registry = BrickRegistry()
    _reg_stdlib(registry)
    config = SystemConfig(
        name="live-cache-test",
        model="claude-haiku-4-5",
        api_key="",
        store=StoreConfig(enabled=True, backend="memory"),
    )
    orchestrator = RuntimeOrchestrator(config, registry, provider=llm_provider)
    engine = Bricks(orchestrator)
    data = {"items": [{"name": "X", "status": "active"}]}

    result1 = engine.execute("filter items where status is active", data)
    assert result1["api_calls"] >= 1

    result2 = engine.execute("filter items where status is active", data)
    assert result2["cache_hit"] is True
    assert result2["tokens_used"] == 0
