"""CRM Pipeline — full data pipeline using real CRM benchmark data.

Uses the deterministic CRM generator (50 records) to show a complete pipeline:
  1. Generate 50 CRM customer records
  2. Demo mode: extract JSON → filter active customers → count
  3. Live mode: natural language task → AI composes → executes → verifies

The same seed always produces the same data and the same expected outputs.

Demo mode (no API key):
    python examples/end_to_end/crm_pipeline.py

Live mode:
    ANTHROPIC_API_KEY=sk-ant-... python examples/end_to_end/crm_pipeline.py
"""

from __future__ import annotations

import json
import os

_live = bool(os.getenv("BRICKS_MODEL") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))

# Pre-composed blueprint for demo mode
_DEMO_YAML = """
name: crm_active_filter
description: "Parse CRM JSON, filter active customers, count them."
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
    save_as: active_customers
  - name: count_active
    brick: count_dict_list
    params:
      items: "${active_customers.result}"
    save_as: active_count
outputs_map:
  active_count: "${active_count.result}"
"""

# Fallback inline data (5 records) used when bricks.playground is not installed
_FALLBACK_DATA = json.dumps(
    {
        "customers": [
            {"id": "c1", "name": "Alice", "status": "active", "plan": "pro", "monthly_revenue": 99.0},
            {"id": "c2", "name": "Bob", "status": "inactive", "plan": "basic", "monthly_revenue": 9.0},
            {"id": "c3", "name": "Carol", "status": "active", "plan": "enterprise", "monthly_revenue": 299.0},
            {"id": "c4", "name": "Dave", "status": "suspended", "plan": "pro", "monthly_revenue": 99.0},
            {"id": "c5", "name": "Eve", "status": "active", "plan": "basic", "monthly_revenue": 9.0},
        ]
    }
)


def _load_data() -> tuple[str, int]:
    """Return (raw_json_string, expected_active_count).

    Uses the benchmark CRM generator when available; falls back to inline data.
    """
    try:
        from bricks.playground.showcase.crm_generator import generate_crm_task

        task = generate_crm_task(seed=42)
        raw = task.raw_api_response.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1])
        data = json.loads(raw)
        active_count = sum(1 for c in data["customers"] if c["status"] == "active")
        print(f"  Using benchmark CRM generator: {len(data['customers'])} records")
        return raw, active_count
    except ImportError:
        data = json.loads(_FALLBACK_DATA)
        active_count = sum(1 for c in data["customers"] if c["status"] == "active")
        print(f"  bricks.playground not installed — using {len(data['customers'])} inline records")
        return _FALLBACK_DATA, active_count


def run_demo(raw_data: str, expected_active: int) -> None:
    """Demo mode: pre-composed blueprint, no API key needed."""
    from bricks.api import _build_default_registry
    from bricks.core.engine import BlueprintEngine
    from bricks.core.loader import BlueprintLoader

    registry = _build_default_registry()
    blueprint = BlueprintLoader().load_string(_DEMO_YAML)
    outputs = BlueprintEngine(registry=registry).run(blueprint, inputs={"raw_data": raw_data}).outputs

    print(f"  Active customers: {outputs['active_count']}")
    assert outputs["active_count"] == expected_active, (  # noqa: S101
        f"Expected {expected_active}, got {outputs['active_count']}"
    )
    print("  OK — result verified")


def run_live(raw_data: str) -> None:
    """Live mode: AI composes and executes the pipeline."""
    from bricks import Bricks
    from bricks.llm.litellm_provider import LiteLLMProvider

    model = os.getenv("BRICKS_MODEL", "claude-haiku-4-5")
    provider = LiteLLMProvider(model=model)
    engine = Bricks.default(provider=provider)

    task = (
        "You are given a JSON object with a 'customers' list. "
        "Filter to keep only customers where status is 'active'. "
        "Count them and return active_count."
    )
    result = engine.execute(task, inputs={"raw_data": raw_data})
    outputs = result["outputs"]
    print(f"  Active customers: {outputs.get('active_count', '(not returned)')}")
    print(f"  Cache hit: {result['cache_hit']} | Tokens used: {result['tokens_used']}")
    print("  Run again → 0 tokens (cached blueprint)")


if __name__ == "__main__":
    raw_data, expected_active = _load_data()

    if _live:
        model = os.getenv("BRICKS_MODEL", "claude-haiku-4-5")
        print(f"Running in LIVE mode (model: {model})")
        run_live(raw_data)
    else:
        print("Running in DEMO mode (set BRICKS_MODEL + API key for live mode)")
        run_demo(raw_data, expected_active)
