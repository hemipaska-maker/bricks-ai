"""Math bricks: multiply and round_value."""

from __future__ import annotations

from bricks.core import brick


@brick(tags=["math"], category="math", destructive=False)
def multiply(a: float, b: float) -> dict[str, float]:
    """Multiply a * b. Returns {result: a*b}."""
    return {"result": a * b}


@brick(tags=["math"], category="math", destructive=False)
def round_value(value: float, decimals: int = 2) -> dict[str, float]:
    """Round value to N decimal places (default decimals=2). Returns {result: rounded_value}."""
    return {"result": round(value, decimals)}


@brick(tags=["math"], category="math", destructive=False)
def add(a: float, b: float) -> dict[str, float]:
    """Add a + b. Returns {result: a+b}."""
    return {"result": a + b}


@brick(tags=["math"], category="math", destructive=False)
def subtract(a: float, b: float) -> dict[str, float]:
    """Subtract b from a. Returns {result: a-b}."""
    return {"result": a - b}
