"""End-to-end smoke test: compose + execute a simple CRM filter task.

Mocked version runs in CI (no API key needed).
Live version uses ClaudeCodeProvider (run with --live).
"""

from __future__ import annotations

from typing import Any

import pytest
from bricks.llm.base import LLMProvider

# Minimal valid blueprint YAML for filtering active customers
_ACTIVE_FILTER_YAML = """\
name: filter_active_customers
description: Filter customers by status=active
inputs:
  data: []
steps:
  - name: filter
    brick: filter_dict_list
    params:
      items: "${inputs.data}"
      key: status
      value: active
    save_as: filter
outputs_map:
  active_customers: "${filter.result}"
"""

_SAMPLE_CRM_DATA = [
    {"name": "Alice", "status": "active", "plan": "pro"},
    {"name": "Bob", "status": "inactive", "plan": "basic"},
    {"name": "Carol", "status": "active", "plan": "enterprise"},
]


def test_demo_flow_mocked(llm_provider: LLMProvider) -> None:
    """Smoke test: engine executes a pre-built blueprint, returns active_customers."""
    from bricks.core.engine import BlueprintEngine
    from bricks.core.loader import BlueprintLoader
    from bricks.core.registry import BrickRegistry
    from bricks_stdlib import register as _reg

    registry = BrickRegistry()
    _reg(registry)
    engine = BlueprintEngine(registry=registry)
    loader = BlueprintLoader()
    bp_def = loader.load_string(_ACTIVE_FILTER_YAML)
    result = engine.run(bp_def, inputs={"data": _SAMPLE_CRM_DATA})
    active: list[dict[str, Any]] = result.outputs.get("active_customers", [])
    assert isinstance(active, list)
    assert len(active) == 2
    assert all(c["status"] == "active" for c in active)


@pytest.mark.live
def test_demo_flow_live(llm_provider: LLMProvider) -> None:
    """Live smoke test: compose + execute with real LLM (--live flag required)."""
    from bricks.api import Bricks

    engine = Bricks.default(provider=llm_provider)
    result: dict[str, Any] = engine.execute(
        "filter the list of customers where status is active",
        {"data": _SAMPLE_CRM_DATA},
    )
    assert isinstance(result["outputs"], dict)
    assert result["api_calls"] >= 1
