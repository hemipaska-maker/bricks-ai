"""Support ticket data generator — deterministic 100-record dataset.

Implements BENCH_001: a support-ticket scenario with email validation, PII
redaction, priority filtering, and count aggregation.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

_PRIORITIES = ["low", "medium", "high", "critical"]
_CATEGORIES = ["billing", "technical", "general"]

_PII_MESSAGES = [
    "Please call me at 555-{a:03d}-{b:04d} or email user{i}@example.com to resolve this.",
    "My SSN is {a:03d}-{b:02d}-{c:04d}. Need urgent help with my account.",
    "Reach me at (555) {a:03d}-{b:04d}. My backup is backup{i}@example.com.",
    "Call 555-{a:03d}-{b:04d} — also try agent{i}@support.example.com.",
    "I am having trouble. Contact me: {i}support@domain.com or 555-{a:03d}-{b:04d}.",
]


class SupportTicket(BaseModel):
    """A single support ticket record."""

    id: int
    customer_email: str
    message: str
    timestamp: str
    priority: str  # "low" | "medium" | "high" | "critical"
    category: str  # "billing" | "technical" | "general"


class TicketTask(BaseModel):
    """A support-ticket benchmark task with expected outputs."""

    task_text: str
    raw_api_response: str  # markdown-fenced JSON string
    expected_outputs: dict[str, Any]
    required_bricks: list[str]


def _make_ticket(i: int, seed: int) -> SupportTicket:
    """Generate a single support ticket deterministically from index and seed.

    Args:
        i: Ticket index (0-based).
        seed: Random seed for reproducibility.

    Returns:
        A fully populated SupportTicket.
    """
    combined = (i * 31 + seed) % 1000

    priority = _PRIORITIES[combined % 4]
    category = _CATEGORIES[combined % 3]

    # ~20 % invalid emails: every 5th ticket (i % 5 == 0)
    email = f"invalid-email-{i}" if i % 5 == 0 else f"user{i}@example-{combined % 10}.com"

    # Deterministic PII-containing message
    msg_template = _PII_MESSAGES[combined % len(_PII_MESSAGES)]
    a = (combined * 7 + i) % 1000
    b = (combined * 13 + i) % 10000
    c = (combined * 3 + i) % 10000
    message = msg_template.format(i=i, a=a, b=b, c=c)

    # Deterministic ISO timestamp: spread over 2024
    day = (combined % 365) + 1
    hour = combined % 24
    timestamp = f"2024-{(day // 30) + 1:02d}-{(day % 28) + 1:02d}T{hour:02d}:00:00"

    return SupportTicket(
        id=i + 1,
        customer_email=email,
        message=message,
        timestamp=timestamp,
        priority=priority,
        category=category,
    )


def _compute_expected(tickets: list[SupportTicket]) -> dict[str, Any]:
    """Compute ground-truth expected outputs for a list of tickets.

    Args:
        tickets: List of generated SupportTicket records.

    Returns:
        Dict with ``high_count``, ``critical_count``, ``total_urgent``,
        and ``valid_email_count``.
    """
    high_count = sum(1 for t in tickets if t.priority == "high")
    critical_count = sum(1 for t in tickets if t.priority == "critical")
    # Valid email: must contain "@" and a "." after "@"
    valid_email_count = sum(1 for t in tickets if "@" in t.customer_email and "." in t.customer_email.split("@")[-1])
    return {
        "high_count": high_count,
        "critical_count": critical_count,
        "total_urgent": high_count + critical_count,
        "valid_email_count": valid_email_count,
    }


def generate_ticket_task(seed: int = 42) -> TicketTask:
    """Generate a deterministic support-ticket benchmark task.

    Produces 100 tickets with ~20 % invalid emails, PII in messages, all four
    priorities, and all three categories.  The same seed always produces the
    same tickets and the same expected outputs.

    Args:
        seed: Integer seed for deterministic generation (default 42).

    Returns:
        A :class:`TicketTask` ready for benchmarking.
    """
    tickets = [_make_ticket(i, seed) for i in range(100)]
    expected = _compute_expected(tickets)

    records = [t.model_dump() for t in tickets]
    raw_json = json.dumps({"tickets": records}, indent=2)
    raw_api_response = f"```json\n{raw_json}\n```"

    task_text = (
        "You are given a JSON array of support tickets under the key 'tickets'. "
        "Each ticket has: id, customer_email, message, timestamp, priority, category.\n\n"
        "Perform the following steps:\n"
        "1. Parse the JSON from raw_api_response using extract_json_from_str.\n"
        "2. For each ticket, validate the customer_email using is_email_valid and "
        "count how many are valid. Store as valid_email_count.\n"
        "3. Filter the tickets list to keep only those with priority 'high' or 'critical' "
        "using filter_dict_list.\n"
        "4. Count how many filtered tickets have priority 'high'. Store as high_count.\n"
        "5. Count how many filtered tickets have priority 'critical'. Store as critical_count.\n"
        "6. Compute total_urgent = high_count + critical_count.\n\n"
        "Return exactly these four keys: high_count, critical_count, total_urgent, valid_email_count."
    )

    return TicketTask(
        task_text=task_text,
        raw_api_response=raw_api_response,
        expected_outputs=expected,
        required_bricks=[
            "extract_json_from_str",
            "is_email_valid",
            "filter_dict_list",
            "count_dict_list",
        ],
    )
