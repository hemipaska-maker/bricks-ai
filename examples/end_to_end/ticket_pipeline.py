"""Ticket Pipeline — processing support tickets with validation and filtering.

Uses the deterministic ticket generator (100 records) to show:
  1. Generate 100 support tickets with emails, priorities, and PII in messages
  2. Demo mode: extract JSON → filter high-priority tickets → count them
  3. Live mode: AI composes full pipeline (email validation, PII redaction, priority counts)

This example highlights: validation, string processing, filtering, counting —
different brick categories working together.

Demo mode (no API key):
    python examples/end_to_end/ticket_pipeline.py

Live mode:
    ANTHROPIC_API_KEY=sk-ant-... python examples/end_to_end/ticket_pipeline.py
"""

from __future__ import annotations

import json
import os

_live = bool(os.getenv("BRICKS_MODEL") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))

# Pre-composed blueprint for demo mode
_DEMO_YAML = """
name: filter_high_priority_tickets
description: "Parse tickets JSON, filter high-priority, count them."
inputs:
  raw_data: str
steps:
  - name: parse
    brick: extract_json_from_str
    params:
      text: "${inputs.raw_data}"
    save_as: parsed
  - name: filter_high
    brick: filter_dict_list
    params:
      items: "${parsed.result.tickets}"
      key: priority
      value: high
    save_as: high_tickets
  - name: count_high
    brick: count_dict_list
    params:
      items: "${high_tickets.result}"
    save_as: high_count
outputs_map:
  high_count: "${high_count.result}"
"""

# Fallback inline data (5 records) used when bricks.playground is not installed
_FALLBACK_TICKETS = [
    {
        "id": 1,
        "customer_email": "user1@example.com",
        "message": "Call 555-000-0001.",
        "priority": "high",
        "category": "billing",
    },
    {"id": 2, "customer_email": "invalid-email-2", "message": "Need help.", "priority": "low", "category": "general"},
    {
        "id": 3,
        "customer_email": "user3@example.com",
        "message": "My SSN is 111-22-3333.",
        "priority": "critical",
        "category": "technical",
    },
    {
        "id": 4,
        "customer_email": "user4@example.com",
        "message": "Billing issue.",
        "priority": "high",
        "category": "billing",
    },
    {
        "id": 5,
        "customer_email": "invalid-email-5",
        "message": "Reach me at 555-000-0005.",
        "priority": "medium",
        "category": "general",
    },
]
_FALLBACK_DATA = json.dumps({"tickets": _FALLBACK_TICKETS})


def _load_data() -> tuple[str, int, dict[str, int]]:
    """Return (raw_json_string, high_count, expected_outputs_dict).

    Uses the benchmark ticket generator when available; falls back to inline data.
    """
    try:
        from bricks.playground.showcase.ticket_generator import generate_ticket_task

        task = generate_ticket_task(seed=42)
        raw = task.raw_api_response.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1])
        data = json.loads(raw)
        high_count = sum(1 for t in data["tickets"] if t["priority"] == "high")
        print(f"  Using benchmark ticket generator: {len(data['tickets'])} records")
        return raw, high_count, task.expected_outputs
    except ImportError:
        high_count = sum(1 for t in _FALLBACK_TICKETS if t["priority"] == "high")
        print(f"  bricks.playground not installed — using {len(_FALLBACK_TICKETS)} inline records")
        return _FALLBACK_DATA, high_count, {}


def run_demo(raw_data: str, expected_high: int) -> None:
    """Demo mode: pre-composed blueprint, no API key needed."""
    from bricks.api import _build_default_registry
    from bricks.core.engine import BlueprintEngine
    from bricks.core.loader import BlueprintLoader

    registry = _build_default_registry()
    blueprint = BlueprintLoader().load_string(_DEMO_YAML)
    outputs = BlueprintEngine(registry=registry).run(blueprint, inputs={"raw_data": raw_data}).outputs

    print(f"  High-priority tickets: {outputs['high_count']}")
    assert outputs["high_count"] == expected_high, (  # noqa: S101
        f"Expected {expected_high}, got {outputs['high_count']}"
    )
    print("  OK — result verified")


def run_live(raw_data: str, expected_outputs: dict[str, int]) -> None:
    """Live mode: AI composes full pipeline — validate emails, filter urgent, count."""
    from bricks import Bricks
    from bricks.llm.litellm_provider import LiteLLMProvider

    model = os.getenv("BRICKS_MODEL", "claude-haiku-4-5")
    provider = LiteLLMProvider(model=model)
    engine = Bricks.default(provider=provider)

    try:
        from bricks.playground.showcase.ticket_generator import generate_ticket_task

        task = generate_ticket_task(seed=42)
        task_text = task.task_text
    except ImportError:
        task_text = (
            "Parse the JSON tickets list from raw_data. "
            "Filter to keep only tickets with priority 'high' or 'critical'. "
            "Count them and return high_count and critical_count."
        )

    result = engine.execute(task_text, inputs={"raw_data": raw_data})
    outputs = result["outputs"]
    print(f"  Outputs: {outputs}")
    print(f"  Cache hit: {result['cache_hit']} | Tokens used: {result['tokens_used']}")
    if expected_outputs:
        print(f"  Expected: {expected_outputs}")


if __name__ == "__main__":
    raw_data, expected_high, expected_outputs = _load_data()

    if _live:
        model = os.getenv("BRICKS_MODEL", "claude-haiku-4-5")
        print(f"Running in LIVE mode (model: {model})")
        run_live(raw_data, expected_outputs)
    else:
        print("Running in DEMO mode (set BRICKS_MODEL + API key for live mode)")
        run_demo(raw_data, expected_high)
