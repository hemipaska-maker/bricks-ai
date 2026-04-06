"""05 — Brick Discovery: auto-register bricks from a directory.

Demonstrates:
- Writing @brick-decorated functions in separate Python files
- Using BrickDiscovery to scan a directory and register all found bricks
- Listing discovered bricks via registry_schema

Run::

    python examples/basics/05_discovery.py
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

from bricks.core.discovery import BrickDiscovery
from bricks.core.registry import BrickRegistry
from bricks.core.schema import registry_schema


def main() -> None:
    """Run the discovery example."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bricks_dir = Path(tmp_dir)

        # Write brick definitions into temp files
        (bricks_dir / "math_bricks.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["math"], description="Add two floats")
                def add(a: float, b: float) -> float:
                    return a + b

                @brick(tags=["math"], description="Multiply two floats")
                def multiply(a: float, b: float) -> float:
                    return a * b
            """).strip()
        )

        (bricks_dir / "string_bricks.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["string"], description="Convert to uppercase")
                def to_upper(text: str) -> str:
                    return text.upper()
            """).strip()
        )

        # Auto-discover and register all bricks from the directory
        registry = BrickRegistry()
        discovery = BrickDiscovery(registry=registry)
        found = discovery.discover_package(bricks_dir)

        print(f"Discovered {len(found)} bricks: {sorted(found)}")

        for schema in registry_schema(registry):
            tags = ", ".join(schema["tags"]) if schema["tags"] else "none"
            print(f"  {schema['name']} [{tags}] — {schema['description']}")

        # Verify bricks are callable
        add_fn, _ = registry.get("add")
        assert add_fn(a=3.0, b=4.0) == 7.0  # noqa: S101

        to_upper_fn, _ = registry.get("to_upper")
        assert to_upper_fn(text="hello") == "HELLO"  # noqa: S101

        print("OK")


if __name__ == "__main__":
    main()
