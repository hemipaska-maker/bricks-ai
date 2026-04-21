"""Support ticket data generator — deterministic 100-record dataset for benchmark scenarios."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


class TicketRecord(BaseModel):
    """A single support ticket record."""

    id: int
    subject: str
    email: str
    priority: str  # "low" | "medium" | "high"
    category: str  # "billing" | "technical" | "general"
    status: str  # "open" | "closed" | "pending"
    created_date: str


class TicketTask(BaseModel):
    """A support ticket benchmark task with expected outputs."""

    task_text: str
    raw_api_response: str
    expected_outputs: dict[str, Any]
    required_bricks: list[str]


_PRIORITIES = ["low", "medium", "high"]
_CATEGORIES = ["billing", "technical", "general"]
_STATUSES = ["open", "closed", "pending"]

_SUBJECTS = [
    "Cannot login to account",
    "Invoice discrepancy",
    "Feature not working",
    "Payment failed",
    "Account suspended",
    "Data export issue",
    "API rate limit exceeded",
    "Password reset not received",
    "Billing cycle question",
    "Integration broken",
]

_DOMAINS = ["gmail.com", "yahoo.com", "company.io", "example.com", "corp.net"]


def _make_ticket(i: int, seed: int) -> TicketRecord:
    """Generate a single ticket record deterministically from index and seed.

    Args:
        i: Record index (0-based).
        seed: Integer seed for deterministic generation.

    Returns:
        A deterministic TicketRecord.
    """
    combined = (i * 37 + seed) % 1000
    subject = _SUBJECTS[combined % len(_SUBJECTS)]
    domain = _DOMAINS[(combined // 3) % len(_DOMAINS)]
    priority = _PRIORITIES[combined % len(_PRIORITIES)]
    category = _CATEGORIES[(combined // 4) % len(_CATEGORIES)]
    status = _STATUSES[(combined // 7) % len(_STATUSES)]
    year = 2024 + (i % 2)
    month = 1 + (combined % 12)
    day = 1 + (combined % 28)
    created_date = f"{year}-{month:02d}-{day:02d}"
    user_num = combined % 500
    return TicketRecord(
        id=i + 1,
        subject=subject,
        email=f"user{user_num}@{domain}",
        priority=priority,
        category=category,
        status=status,
        created_date=created_date,
    )


def _compute_expected(records: list[TicketRecord]) -> dict[str, Any]:
    """Compute expected outputs: high-priority open ticket counts by category.

    Args:
        records: List of ticket records.

    Returns:
        Dict with open_high_count and counts per category for high+open tickets.
    """
    high_open = [r for r in records if r.priority == "high" and r.status == "open"]
    by_category: dict[str, int] = {}
    for r in high_open:
        by_category[r.category] = by_category.get(r.category, 0) + 1
    return {
        "open_high_count": len(high_open),
        "billing_count": by_category.get("billing", 0),
        "technical_count": by_category.get("technical", 0),
        "general_count": by_category.get("general", 0),
    }


def generate_ticket_task(seed: int = 42) -> TicketTask:
    """Generate a support ticket benchmark task with 100 deterministic records.

    Args:
        seed: Integer seed for deterministic generation.

    Returns:
        TicketTask with raw API response, expected outputs, and required brick list.
    """
    records = [_make_ticket(i, seed) for i in range(100)]
    records_dicts = [r.model_dump() for r in records]
    raw_json = json.dumps({"tickets": records_dicts}, indent=2)
    raw_api_response = f"```json\n{raw_json}\n```"
    expected = _compute_expected(records)
    return TicketTask(
        task_text=(
            "The input 'raw_api_response' is a markdown-fenced JSON string "
            "containing a dict with key 'tickets' — a list of objects with fields: "
            "id, subject, email, priority (low/medium/high), category (billing/technical/general), "
            "status (open/closed/pending), created_date. "
            "Parse the JSON string, filter for priority='high' AND status='open', "
            "count the total (save as 'open_high_count'), "
            "then count how many are in each category: "
            "billing (save as 'billing_count'), "
            "technical (save as 'technical_count'), "
            "general (save as 'general_count'). "
            "Use count_dict_list for counting. "
            "The outputs_map must use exactly these keys: "
            "open_high_count, billing_count, technical_count, general_count."
        ),
        raw_api_response=raw_api_response,
        expected_outputs=expected,
        required_bricks=[
            "extract_json_from_str",
            "filter_dict_list",
            "count_dict_list",
        ],
    )
