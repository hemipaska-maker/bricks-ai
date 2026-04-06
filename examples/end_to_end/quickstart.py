"""Quickstart — Bricks in 30 seconds.

Natural language task → AI composes a YAML blueprint → executes deterministically.
Run it again and the blueprint is served from cache: zero LLM tokens.

Demo mode (default, no API key):
    python examples/end_to_end/quickstart.py

Live mode (uses your API key to compose the blueprint):
    ANTHROPIC_API_KEY=sk-ant-... python examples/end_to_end/quickstart.py
"""

from __future__ import annotations

import json
import os

# Five inline CRM records — no external imports needed
_RAW_DATA = json.dumps(
    {
        "customers": [
            {"id": 1, "name": "Alice", "status": "active", "plan": "pro"},
            {"id": 2, "name": "Bob", "status": "inactive", "plan": "basic"},
            {"id": 3, "name": "Carol", "status": "active", "plan": "enterprise"},
            {"id": 4, "name": "Dave", "status": "suspended", "plan": "pro"},
            {"id": 5, "name": "Eve", "status": "active", "plan": "basic"},
        ]
    }
)

# Pre-composed blueprint — what live mode would produce (0 tokens to reuse)
_DEMO_YAML = """
name: filter_active_customers
description: "Extract customers JSON, filter active, count them."
inputs:
  raw_data: str
steps:
  - name: parse
    brick: extract_json_from_str
    params:
      text: "${inputs.raw_data}"
    save_as: parsed
  - name: filter_active
    brick: filter_dict_list
    params:
      items: "${parsed.result.customers}"
      key: status
      value: active
    save_as: active
  - name: tally
    brick: count_dict_list
    params:
      items: "${active.result}"
    save_as: count
outputs_map:
  active_count: "${count.result}"
"""

_live = bool(os.getenv("BRICKS_MODEL") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))


def run_demo() -> dict[str, object]:
    """Run in demo mode using the pre-composed blueprint."""
    from bricks.api import _build_default_registry
    from bricks.core.engine import BlueprintEngine
    from bricks.core.loader import BlueprintLoader

    registry = _build_default_registry()
    blueprint = BlueprintLoader().load_string(_DEMO_YAML)
    return BlueprintEngine(registry=registry).run(blueprint, inputs={"raw_data": _RAW_DATA}).outputs


def run_live() -> dict[str, object]:
    """Run in live mode — composes the blueprint via LLM, then executes."""
    from bricks import Bricks
    from bricks.llm.litellm_provider import LiteLLMProvider

    model = os.getenv("BRICKS_MODEL", "claude-haiku-4-5")
    provider = LiteLLMProvider(model=model)
    engine = Bricks.default(provider=provider)

    task = (
        "Parse the JSON customers list from raw_data. "
        "Filter to keep only active customers. "
        "Count them and return active_count."
    )
    result = engine.execute(task, inputs={"raw_data": _RAW_DATA})
    return result["outputs"]


if __name__ == "__main__":
    if _live:
        model = os.getenv("BRICKS_MODEL", "claude-haiku-4-5")
        print(f"Running in LIVE mode (model: {model})")
        outputs = run_live()
    else:
        print("Running in DEMO mode (set BRICKS_MODEL + provider API key for live composition)")
        outputs = run_demo()

    print(f"\nActive customers: {outputs['active_count']} / 5")
    print("\nRun again -> 0 tokens (blueprint served from cache)")
    assert outputs["active_count"] == 3  # noqa: S101
    print("OK")
