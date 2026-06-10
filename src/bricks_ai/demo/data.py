"""Demo data: inline CRM dataset, blueprint YAML, variant generator, and metrics."""

from __future__ import annotations

import dataclasses
from typing import Any

# ---------------------------------------------------------------------------
# Sample dataset (Act 1)
# ---------------------------------------------------------------------------

SAMPLE_CRM: list[dict[str, Any]] = [
    {"name": "Alice", "email": "alice@test.com", "status": "active", "plan": "pro", "monthly_revenue": 99.0},
    {"name": "Bob", "email": "bob@test.com", "status": "inactive", "plan": "basic", "monthly_revenue": 29.0},
    {"name": "Carol", "email": "carol@test.com", "status": "active", "plan": "enterprise", "monthly_revenue": 499.0},
    {"name": "Dave", "email": "dave@test.com", "status": "suspended", "plan": "pro", "monthly_revenue": 99.0},
    {"name": "Eve", "email": "eve@test.com", "status": "active", "plan": "basic", "monthly_revenue": 29.0},
]

EXPECTED_ACTIVE_REVENUE: float = 627.0  # Alice (99) + Carol (499) + Eve (29)

# ---------------------------------------------------------------------------
# Pre-composed blueprint YAML (used in demo mode and shown in live mode)
# ---------------------------------------------------------------------------

DEMO_BLUEPRINT_YAML: str = """\
name: crm_active_revenue
description: "Filter active customers and sum their monthly revenue."
inputs:
  customers: list
steps:
  - name: filter_active
    brick: filter_dict_list
    params:
      items: "${inputs.customers}"
      key: status
      value: active
    save_as: active
  - name: sum_revenue
    brick: calculate_aggregates
    params:
      items: "${active.result}"
      field: monthly_revenue
      operation: sum
    save_as: revenue
outputs_map:
  total_active_revenue: "${revenue.result}"
"""

DEMO_TASK_TEXT: str = (
    "Filter the 'customers' list to keep only those with status 'active'. "
    "Sum their monthly_revenue field. Return the total as total_active_revenue."
)

# Prompt sent to raw LLM in Act 2 for direct comparison
RAW_LLM_PROMPT_TEMPLATE: str = (
    "Given this customer data: {data}\n"
    "Filter to only active customers and compute the sum of their monthly_revenue.\n"
    'Return ONLY a JSON object like {{"total_active_revenue": 123.0}} with no other text.'
)

# ---------------------------------------------------------------------------
# Variant datasets for Act 2 (5 deterministic datasets)
# ---------------------------------------------------------------------------


def generate_variants() -> list[tuple[list[dict[str, Any]], float]]:
    """Return 5 (customers_list, expected_active_revenue) pairs for Act 2.

    Returns:
        List of (customers, expected_revenue) tuples, deterministic.
    """
    return [
        (
            [
                {"name": "A1", "status": "active", "monthly_revenue": 100.0},
                {"name": "A2", "status": "inactive", "monthly_revenue": 50.0},
                {"name": "A3", "status": "active", "monthly_revenue": 200.0},
            ],
            300.0,
        ),
        (
            [
                {"name": "B1", "status": "active", "monthly_revenue": 75.0},
                {"name": "B2", "status": "active", "monthly_revenue": 75.0},
                {"name": "B3", "status": "suspended", "monthly_revenue": 99.0},
            ],
            150.0,
        ),
        (
            [
                {"name": "C1", "status": "inactive", "monthly_revenue": 200.0},
                {"name": "C2", "status": "active", "monthly_revenue": 350.0},
                {"name": "C3", "status": "active", "monthly_revenue": 50.0},
            ],
            400.0,
        ),
        (
            [
                {"name": "D1", "status": "active", "monthly_revenue": 999.0},
                {"name": "D2", "status": "suspended", "monthly_revenue": 29.0},
                {"name": "D3", "status": "inactive", "monthly_revenue": 49.0},
            ],
            999.0,
        ),
        (
            [
                {"name": "E1", "status": "active", "monthly_revenue": 150.0},
                {"name": "E2", "status": "active", "monthly_revenue": 250.0},
                {"name": "E3", "status": "active", "monthly_revenue": 100.0},
            ],
            500.0,
        ),
    ]


# Pre-written simulated LLM responses for demo mode Act 2
# Variants 0, 2, 4 are correct; variants 1 and 3 are wrong (LLM hallucinated).
SIMULATED_LLM_RESPONSES: list[float] = [
    300.0,  # variant 0: correct  (expected 300.0)
    175.0,  # variant 1: WRONG    (expected 150.0)
    400.0,  # variant 2: correct  (expected 400.0)
    28.0,  # variant 3: WRONG    (expected 999.0)
    500.0,  # variant 4: correct  (expected 500.0)
]

# Pre-calculated token estimates for demo mode Act 3
DEMO_COMPOSE_TOKENS: int = 3_000
DEMO_BRICKS_RUN_TOKENS: int = 0  # cached → always 0
DEMO_LLM_PER_RUN_TOKENS: int = 3_000  # realistic per-run estimate

# ---------------------------------------------------------------------------
# Metrics accumulator (shared across acts)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class DemoMetrics:
    """Token and correctness metrics accumulated across all acts.

    Attributes:
        compose_tokens: Tokens spent composing the blueprint (Act 1).
        bricks_run_tokens: Total tokens for Bricks runs in Act 2 (0 on cache hits).
        llm_run_tokens: Total tokens for raw LLM runs in Act 2.
        bricks_correct: Number of correct Bricks results in Act 2.
        llm_correct: Number of correct raw LLM results in Act 2.
        num_variants: Number of variant datasets used in Act 2.
        live: True if running with a real LLM provider.
    """

    compose_tokens: int = 0
    bricks_run_tokens: int = 0
    llm_run_tokens: int = 0
    bricks_correct: int = 0
    llm_correct: int = 0
    num_variants: int = 5
    live: bool = False
