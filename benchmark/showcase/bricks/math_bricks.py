"""Math bricks: multiply and round_value."""

from __future__ import annotations

from bricks.core import brick


@brick(tags=["math"], category="math", destructive=False)
def multiply(a: float, b: float) -> dict[str, float]:
    """Multiply two numbers and return the result."""
    return {"result": a * b}


@brick(tags=["math"], category="math", destructive=False)
def round_value(value: float, decimals: int = 2) -> dict[str, float]:
    """Round a float to the specified number of decimal places."""
    return {"result": round(value, decimals)}


@brick(tags=["math"], category="math", destructive=False)
def add(a: float, b: float) -> dict[str, float]:
    """Add two numbers and return the result."""
    return {"result": a + b}


@brick(tags=["math"], category="math", destructive=False)
def subtract(a: float, b: float) -> dict[str, float]:
    """Subtract b from a and return the result."""
    return {"result": a - b}
