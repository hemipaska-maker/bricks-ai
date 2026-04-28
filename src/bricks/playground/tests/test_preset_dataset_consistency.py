"""Tests that bundled playground presets' ``expected_outputs`` match their datasets.

Closes the regression-prevention ask in issue #73. The user-facing
playground demos are the most-visible surface of Bricks; if a preset's
``expected_outputs`` doesn't match what the bundled data actually
produces, both BricksEngine and RawLLMEngine compute the *correct*
answer relative to the data and the UI shows them both as "failed",
reading as "Bricks can't even do a join".

Each parametrised case re-implements the preset's task in plain
Python and asserts the YAML's ``expected_outputs`` matches. The
re-implementation is the test's independent statement of the demo's
contract — if a future maintainer edits the dataset OR the expected
outputs without updating the other, this test fails with the
mismatched key named.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
import yaml

_PRESETS_DIR = Path(__file__).parent.parent / "web" / "presets"
_DATASETS_DIR = Path(__file__).parent.parent / "web" / "datasets"

# Inline-data presets carry their data inside the YAML; dataset-id
# presets reference one of the bundled JSON files. The dataset_id
# values used in the YAML are kebab-case; the JSON filenames use
# snake_case, so a tiny lookup map keeps the test honest.
_DATASET_ID_TO_FILE = {
    "crm-customers": "crm_customers.json",
    "orders-customers": "orders_customers.json",
    "support-tickets": "support_tickets.json",
}


def _load_preset(name: str) -> dict[str, Any]:
    """Read and parse one preset YAML file by stem."""
    return yaml.safe_load((_PRESETS_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def _load_dataset(dataset_id: str) -> Any:
    """Read and parse one bundled dataset JSON, returning the inner ``data`` field.

    Bundled datasets wrap their content in ``{"data": ...}``; the playground's
    runtime resolves that wrapper before passing data to the engine, so the
    test asserts against the unwrapped shape.
    """
    raw = json.loads((_DATASETS_DIR / _DATASET_ID_TO_FILE[dataset_id]).read_text(encoding="utf-8"))
    return raw["data"]


# ── per-preset re-implementations of the task ───────────────────────────────


def _expected_crm_pipeline() -> dict[str, Any]:
    """CRM Pipeline: filter active customers, count + sum + avg revenue."""
    customers = _load_dataset("crm-customers")
    if isinstance(customers, dict):
        customers = customers.get("customers", customers)
    active = [c for c in customers if c.get("status") == "active"]
    total = sum(float(c.get("monthly_revenue", 0)) for c in active)
    return {
        "active_count": len(active),
        "total_active_revenue": round(total, 2),
        "avg_active_revenue": round(total / max(1, len(active)), 2),
    }


def _expected_cross_dataset_join() -> dict[str, Any]:
    """Orders Customer Join: join, filter completed, group revenue by plan."""
    data = _load_dataset("orders-customers")
    customers = {c["id"]: c for c in data["customers"]}
    completed = [o for o in data["orders"] if o.get("status") == "completed"]
    rev: dict[str, float] = defaultdict(float)
    for order in completed:
        plan = customers.get(order["customer_id"], {}).get("plan", "")
        rev[plan] += float(order.get("amount", 0))
    return {
        "total_completed": len(completed),
        "basic_revenue": round(rev["basic"], 2),
        "pro_revenue": round(rev["pro"], 2),
        "enterprise_revenue": round(rev["enterprise"], 2),
    }


def _expected_ticket_pipeline() -> dict[str, Any]:
    """Support Ticket Pipeline: filter open+high, count by category."""
    data = _load_dataset("support-tickets")
    tickets = data["tickets"] if isinstance(data, dict) else data
    open_high = [t for t in tickets if t.get("priority") == "high" and t.get("status") == "open"]
    by_cat: dict[str, int] = defaultdict(int)
    for ticket in open_high:
        by_cat[ticket.get("category", "")] += 1
    return {
        "open_high_count": len(open_high),
        "billing_count": by_cat["billing"],
        "technical_count": by_cat["technical"],
        "general_count": by_cat["general"],
    }


def _expected_custom_example() -> dict[str, Any]:
    """Inline-data preset: filter stock > 0, count + sum(price*stock)."""
    products = _load_preset("custom_example")["data"]
    available = [p for p in products if p.get("stock", 0) > 0]
    return {
        "available_count": len(available),
        "total_value": round(sum(p["price"] * p["stock"] for p in available), 2),
    }


# ── parametrised assertion ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("preset_name", "compute"),
    [
        ("crm_pipeline", _expected_crm_pipeline),
        ("cross_dataset_join", _expected_cross_dataset_join),
        ("ticket_pipeline", _expected_ticket_pipeline),
        ("custom_example", _expected_custom_example),
    ],
)
def test_preset_expected_outputs_match_dataset(
    preset_name: str,
    compute: Any,
) -> None:
    """The YAML ``expected_outputs`` must equal what the bundled data computes.

    If this fails, either the data drifted or the expected_outputs
    drifted — the playground UI will mark the engine as failing on a
    correctly-computed answer, reading as "Bricks broke this scenario".
    """
    preset = _load_preset(preset_name)
    declared: dict[str, Any] = preset.get("expected_outputs", {})
    actual = compute()

    # For each declared key, the data-derived value must match. Floats
    # use a small tolerance to absorb rounding inside the round() call —
    # the playground's correctness checker uses a similar tolerance, so
    # this matches what an end-user would see.
    for key, expected_val in declared.items():
        actual_val = actual.get(key)
        if isinstance(expected_val, float):
            assert actual_val == pytest.approx(expected_val, abs=0.01), (
                f"{preset_name}: expected_outputs[{key!r}] = {expected_val} "
                f"but data produces {actual_val} — preset and dataset drifted apart"
            )
        else:
            assert actual_val == expected_val, (
                f"{preset_name}: expected_outputs[{key!r}] = {expected_val} "
                f"but data produces {actual_val} — preset and dataset drifted apart"
            )
