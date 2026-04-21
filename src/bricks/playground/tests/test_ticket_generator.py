"""Tests for bricks.playground.showcase.ticket_generator."""

from __future__ import annotations

from bricks.playground.showcase.ticket_generator import (
    _compute_expected,
    _make_ticket,
    generate_ticket_task,
)


def test_generate_ticket_task_is_deterministic() -> None:
    """Same seed always produces identical task text, data, and expected outputs."""
    task_a = generate_ticket_task(42)
    task_b = generate_ticket_task(42)
    assert task_a.task_text == task_b.task_text
    assert task_a.raw_api_response == task_b.raw_api_response
    assert task_a.expected_outputs == task_b.expected_outputs


def test_generate_ticket_task_different_seeds_differ() -> None:
    """Different seeds produce different datasets."""
    task_42 = generate_ticket_task(42)
    task_99 = generate_ticket_task(99)
    assert task_42.raw_api_response != task_99.raw_api_response


def test_generate_ticket_task_produces_100_tickets() -> None:
    """generate_ticket_task always produces exactly 100 tickets."""
    import json

    task = generate_ticket_task(42)
    # Strip the markdown fences and parse the JSON
    raw = task.raw_api_response.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1])
    data = json.loads(raw)
    assert len(data["tickets"]) == 100


def test_approximately_20_percent_invalid_emails() -> None:
    """Between 15 and 25 of the 100 tickets have invalid emails (i % 5 == 0)."""
    tickets = [_make_ticket(i, 42) for i in range(100)]
    invalid_count = sum(1 for t in tickets if "@" not in t.customer_email)
    assert 15 <= invalid_count <= 25, f"Expected 15-25 invalid emails, got {invalid_count}"


def test_all_priorities_present() -> None:
    """All four priority values appear in the generated dataset."""
    tickets = [_make_ticket(i, 42) for i in range(100)]
    priorities = {t.priority for t in tickets}
    assert priorities == {"low", "medium", "high", "critical"}


def test_all_categories_present() -> None:
    """All three category values appear in the generated dataset."""
    tickets = [_make_ticket(i, 42) for i in range(100)]
    categories = {t.category for t in tickets}
    assert categories == {"billing", "technical", "general"}


def test_expected_outputs_match_manual_calculation() -> None:
    """Expected outputs match independently computed counts."""
    tickets = [_make_ticket(i, 42) for i in range(100)]
    expected = _compute_expected(tickets)

    manual_high = sum(1 for t in tickets if t.priority == "high")
    manual_critical = sum(1 for t in tickets if t.priority == "critical")
    manual_valid_email = sum(1 for t in tickets if "@" in t.customer_email and "." in t.customer_email.split("@")[-1])

    assert expected["high_count"] == manual_high
    assert expected["critical_count"] == manual_critical
    assert expected["total_urgent"] == manual_high + manual_critical
    assert expected["valid_email_count"] == manual_valid_email


def test_expected_outputs_keys() -> None:
    """Expected outputs contain exactly the four required keys."""
    task = generate_ticket_task(42)
    assert set(task.expected_outputs.keys()) == {
        "high_count",
        "critical_count",
        "total_urgent",
        "valid_email_count",
    }


def test_required_bricks_listed() -> None:
    """TicketTask lists the expected stdlib bricks."""
    task = generate_ticket_task(42)
    assert "extract_json_from_str" in task.required_bricks
    assert "is_email_valid" in task.required_bricks
    assert "filter_dict_list" in task.required_bricks
