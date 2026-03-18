"""String bricks: format_result."""

from __future__ import annotations

from bricks.core import brick


@brick(tags=["string"], category="string", destructive=False)
def format_result(label: str, value: float) -> dict[str, str]:
    """Format a labelled numeric result as a display string."""
    return {"display": f"{label}: {value}"}
