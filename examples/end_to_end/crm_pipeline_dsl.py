"""CRM Pipeline — Python DSL version.

This is the DSL equivalent of ``crm_pipeline.py``. Instead of writing YAML,
the pipeline is defined in Python using ``step``, ``for_each``, and the
``@flow`` decorator.

Run this example::

    python examples/end_to_end/crm_pipeline_dsl.py
"""

from __future__ import annotations

from bricks import flow, for_each, step
from bricks.core.brick import brick
from bricks.core.registry import BrickRegistry

# ---------------------------------------------------------------------------
# Register CRM bricks
# ---------------------------------------------------------------------------

registry = BrickRegistry()


@brick(description="Normalize a contact record: strip whitespace, title-case name")
def normalize_contact(record: dict) -> dict:  # type: ignore[type-arg]
    """Normalize a contact record."""
    return {
        "name": str(record.get("name", "")).strip().title(),
        "email": str(record.get("email", "")).strip().lower(),
        "phone": str(record.get("phone", "")).strip(),
    }


@brick(description="Score a contact record: returns score 0-100")
def score_contact(record: dict) -> dict:  # type: ignore[type-arg]
    """Score a contact by completeness."""
    score = 0
    if record.get("name"):
        score += 40
    if record.get("email"):
        score += 40
    if record.get("phone"):
        score += 20
    return {"record": record, "score": score}


@brick(description="Aggregate scored contacts into a summary")
def aggregate_contacts(results: list) -> dict:  # type: ignore[type-arg]
    """Aggregate scored contacts into pipeline summary."""
    total = len(results)
    high_quality = sum(1 for r in results if r.get("score", 0) >= 80)
    return {
        "total": total,
        "high_quality": high_quality,
        "low_quality": total - high_quality,
    }


for fn in (normalize_contact, score_contact, aggregate_contacts):
    registry.register(fn.__name__, fn, fn.__brick_meta__)  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Define the pipeline using the Python DSL
# ---------------------------------------------------------------------------


@flow
def crm_pipeline(records: None) -> None:
    """Clean CRM records, score them, and aggregate the results."""
    normalized = for_each(records, do=lambda r: step.normalize_contact(record=r))
    scored = for_each(normalized, do=lambda r: step.score_contact(record=r))
    return step.aggregate_contacts(results=scored)


# ---------------------------------------------------------------------------
# Show the generated blueprint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== CRM Pipeline (Python DSL) ===")
    print(f"Name:      {crm_pipeline.name}")
    print(f"DAG nodes: {len(crm_pipeline.dag.nodes)}")
    print()

    bp = crm_pipeline.to_blueprint()
    print("=== Generated Blueprint ===")
    for s in bp.steps:
        print(f"  {s.name}  →  brick: {s.brick}")
    print()

    print("=== YAML Export ===")
    print(crm_pipeline.to_yaml())
