"""String bricks: format_result."""

from __future__ import annotations

from bricks.core import brick


@brick(tags=["string"], category="string", destructive=False)
def format_result(label: str, value: float) -> dict[str, str]:
    """Format as 'label: value' display string. Returns {display: str} — NOTE: output key is 'display', not 'result'."""
    return {"display": f"{label}: {value}"}
