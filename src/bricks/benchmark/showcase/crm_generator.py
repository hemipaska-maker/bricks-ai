"""CRM data generator — deterministic 50-record dataset for benchmark scenarios."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


class CRMRecord(BaseModel):
    """A single CRM customer record."""

    id: int
    name: str
    email: str
    status: str  # "active" | "inactive" | "suspended"
    plan: str  # "basic" | "pro" | "enterprise"
    monthly_revenue: float
    signup_date: str


class CRMTask(BaseModel):
    """A CRM benchmark task with expected outputs."""

    task_text: str
    raw_api_response: str  # markdown-fenced JSON string
    expected_outputs: dict[str, Any]
    required_bricks: list[str]


_STATUSES = ["active", "inactive", "suspended"]
_PLANS = ["basic", "pro", "enterprise"]
_PLAN_REVENUE: dict[str, float] = {"basic": 29.0, "pro": 99.0, "enterprise": 499.0}

_FIRST_NAMES = [
    "Alice",
    "Bob",
    "Carol",
    "Dave",
    "Eve",
    "Frank",
    "Grace",
    "Hank",
    "Iris",
    "Jack",
    "Kim",
    "Leo",
    "Mia",
    "Ned",
    "Olivia",
    "Paul",
    "Quinn",
    "Rose",
    "Sam",
    "Tina",
    "Uma",
    "Vince",
    "Wendy",
    "Xander",
    "Yara",
    "Zoe",
]
_LAST_NAMES = [
    "Smith",
    "Jones",
    "Lee",
    "Brown",
    "Taylor",
    "Wilson",
    "Davis",
    "Miller",
    "Moore",
    "Clark",
]


def _make_record(i: int, seed: int) -> CRMRecord:
    """Generate a single CRM record deterministically from index and seed."""
    combined = (i * 31 + seed) % 1000
    first = _FIRST_NAMES[combined % len(_FIRST_NAMES)]
    last = _LAST_NAMES[(combined // 3) % len(_LAST_NAMES)]
    status = _STATUSES[combined % len(_STATUSES)]
    plan = _PLANS[(combined // 7) % len(_PLANS)]
    base_revenue = _PLAN_REVENUE[plan]
    revenue = round(base_revenue + (combined % 50) * 0.5, 2)
    year = 2020 + (i % 5)
    month = 1 + (combined % 12)
    day = 1 + (combined % 28)
    signup_date = f"{year}-{month:02d}-{day:02d}"
    return CRMRecord(
        id=i + 1,
        name=f"{first} {last}",
        email=f"{first.lower()}.{last.lower()}{i}@example.com",
        status=status,
        plan=plan,
        monthly_revenue=revenue,
        signup_date=signup_date,
    )


def _compute_expected(records: list[CRMRecord]) -> dict[str, Any]:
    """Compute correct aggregate outputs for the active-customer pipeline."""
    active = [r for r in records if r.status == "active"]
    total_revenue = round(sum(r.monthly_revenue for r in active), 2)
    avg_revenue = round(total_revenue / len(active), 2) if active else 0.0
    return {
        "active_count": len(active),
        "total_active_revenue": total_revenue,
        "avg_active_revenue": avg_revenue,
    }


def generate_crm_task(seed: int = 42) -> CRMTask:
    """Generate a CRM benchmark task with 50 deterministic records.

    Args:
        seed: Integer seed for deterministic generation.

    Returns:
        CRMTask with raw API response, expected outputs, and required brick list.
    """
    records = [_make_record(i, seed) for i in range(50)]
    records_dicts = [r.model_dump() for r in records]
    raw_json = json.dumps({"customers": records_dicts}, indent=2)
    raw_api_response = f"```json\n{raw_json}\n```"
    expected = _compute_expected(records)
    return CRMTask(
        task_text=(
            "The input 'raw_api_response' is a markdown-fenced JSON string "
            "containing a dict with key 'customers' — a list of objects with fields: "
            "id, name, email, status (active/inactive/suspended), plan (basic/pro/enterprise), "
            "monthly_revenue (float), signup_date. "
            "Parse the JSON string, filter for status='active', "
            "count the active customers (use count_dict_list, save as 'active_count'), "
            "sum their monthly_revenue "
            "(use calculate_aggregates with operation='sum', save as 'total_active_revenue'), "
            "and compute the average revenue "
            "(use calculate_aggregates with operation='avg', save as 'avg_active_revenue'). "
            "The outputs_map must use exactly these keys: active_count, total_active_revenue, avg_active_revenue."
        ),
        raw_api_response=raw_api_response,
        expected_outputs=expected,
        required_bricks=[
            "extract_json_from_str",
            "filter_dict_list",
            "calculate_aggregates",
            "count_dict_list",
        ],
    )
