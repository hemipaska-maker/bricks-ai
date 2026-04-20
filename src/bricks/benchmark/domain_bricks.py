"""Domain bricks for the benchmark: realistic data-processing functions."""

from __future__ import annotations

import operator as op
from typing import Any, cast

from bricks.core import BrickRegistry, brick
from bricks.core.brick import BrickFunction
from bricks.core.models import BrickMeta


@brick(tags=["data", "io"], description="Simulate loading CSV data from a source")
def load_csv_data(source: str) -> dict[str, Any]:
    """Return simulated tabular data for a named source."""
    datasets: dict[str, list[dict[str, Any]]] = {
        "sales": [
            {"product": "Widget A", "revenue": 2500.0, "units": 150, "region": "North"},
            {"product": "Widget B", "revenue": 800.0, "units": 50, "region": "South"},
            {"product": "Widget C", "revenue": 3200.0, "units": 200, "region": "North"},
            {"product": "Widget D", "revenue": 450.0, "units": 30, "region": "East"},
            {"product": "Widget E", "revenue": 1900.0, "units": 120, "region": "West"},
        ],
        "employees": [
            {
                "name": "Alice",
                "department": "Engineering",
                "salary": 95000.0,
                "notes": "Leads the backend team with excellent results",
            },
            {
                "name": "Bob",
                "department": "Marketing",
                "salary": 72000.0,
                "notes": "Manages social media campaigns",
            },
            {
                "name": "Carol",
                "department": "Engineering",
                "salary": 105000.0,
                "notes": "Senior architect for system design and review",
            },
        ],
    }
    rows = datasets.get(source, [])
    columns = list(rows[0].keys()) if rows else []
    return {"rows": rows, "columns": columns, "row_count": len(rows)}


_OPS: dict[str, Any] = {
    ">": op.gt,
    "<": op.lt,
    ">=": op.ge,
    "<=": op.le,
    "==": op.eq,
    "!=": op.ne,
}


@brick(tags=["data", "transform"], description="Filter rows by condition")
def filter_rows(
    data: list[dict[str, Any]],
    column: str,
    filter_operator: str,
    value: Any,
) -> dict[str, Any]:
    """Filter rows where ``column <operator> value`` is true."""
    cmp = _OPS.get(filter_operator)
    if cmp is None:
        raise ValueError(f"Unknown operator: {filter_operator!r}")
    filtered = [row for row in data if cmp(row[column], value)]
    return {"rows": filtered, "row_count": len(filtered)}


@brick(tags=["data", "analytics"], description="Compute stats for a column")
def calculate_stats(data: list[dict[str, Any]], column: str) -> dict[str, Any]:
    """Return descriptive statistics for a numeric column."""
    values = [row[column] for row in data]
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "sum": 0.0, "count": 0}
    total = sum(values)
    count = len(values)
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(total / count, 2),
        "sum": total,
        "count": count,
    }


@brick(tags=["text", "analytics"], description="Count words in a column")
def word_count(data: list[dict[str, Any]], column: str) -> dict[str, int | float]:
    """Return total words and average words per row."""
    counts = [len(str(row.get(column, "")).split()) for row in data]
    total = sum(counts)
    avg = round(total / len(counts), 2) if counts else 0.0
    return {"total_words": total, "avg_per_row": avg}


@brick(tags=["text", "reporting"], description="Generate a text summary")
def generate_summary(title: str, data: dict[str, Any]) -> str:
    """Format a dict as a titled report string."""
    lines = [title]
    for key, val in data.items():
        lines.append(f"  {key}: {val}")
    return "\n".join(lines)


@brick(tags=["text", "formatting"], description="Format a number with affixes")
def format_number(
    value: float,
    decimals: int = 2,
    prefix: str = "",
    suffix: str = "",
) -> str:
    """Return a formatted number string like '$2,533.33'."""
    formatted = f"{value:,.{decimals}f}"
    return f"{prefix}{formatted}{suffix}"


@brick(
    tags=["data", "validation"],
    description="Check that all rows contain required columns",
    destructive=False,
)
def validate_schema(
    data: list[dict[str, Any]],
    required_columns: list[str],
) -> dict[str, Any]:
    """Validate that every row contains the required columns."""
    if not data:
        return {"valid": True, "missing": [], "row_count": 0}
    present = set(data[0].keys())
    missing = [c for c in required_columns if c not in present]
    return {"valid": len(missing) == 0, "missing": missing, "row_count": len(data)}


@brick(tags=["data", "reporting"], description="Merge multiple text reports into one")
def merge_reports(reports: list[str], separator: str = "\n---\n") -> str:
    """Join report strings with a separator."""
    return separator.join(reports)


@brick(tags=["math"], description="Multiply two numbers")
def multiply(a: float, b: float) -> float:
    """Return a * b."""
    return a * b


@brick(tags=["math"], description="Divide a by b")
def divide(a: float, b: float) -> float:
    """Return a / b."""
    return a / b


# ------------------------------------------------------------------
# Registry builder
# ------------------------------------------------------------------

_ALL_BRICKS = [
    load_csv_data,
    filter_rows,
    calculate_stats,
    word_count,
    generate_summary,
    format_number,
    validate_schema,
    merge_reports,
    multiply,
    divide,
]


def build_registry() -> BrickRegistry:
    """Create a BrickRegistry populated with all benchmark domain bricks."""
    registry = BrickRegistry()
    for fn in _ALL_BRICKS:
        typed = cast(BrickFunction, fn)
        meta: BrickMeta = typed.__brick_meta__
        registry.register(typed.__brick_meta__.name, fn, meta)
    return registry
