"""Auto-generate docs/BRICK_CATALOG.md from stdlib brick metadata and docstrings.

Run from the repository root::

    python packages/stdlib/scripts/generate_catalog.py
"""

from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path
from typing import Any

from bricks.core.models import BrickMeta
from bricks_stdlib import (
    data_transformation,
    date_time,
    encoding_security,
    list_operations,
    math_numeric,
    string_processing,
    validation,
)

_MODULES = [
    data_transformation,
    date_time,
    encoding_security,
    list_operations,
    math_numeric,
    string_processing,
    validation,
]


def _extract_brick_metadata(func: Any) -> dict[str, Any] | None:
    """Extract metadata from a brick function.

    Args:
        func: A callable that may have ``__brick_meta__`` attached.

    Returns:
        Dict with brick metadata and signature info, or None if not a brick.
    """
    if not callable(func) or not hasattr(func, "__brick_meta__"):
        return None

    meta: BrickMeta = func.__brick_meta__
    sig = inspect.signature(func)

    params = []
    for param_name, param in sig.parameters.items():
        annotation = param.annotation if param.annotation != inspect.Parameter.empty else "Any"
        default = param.default if param.default != inspect.Parameter.empty else None
        params.append({"name": param_name, "type": str(annotation), "default": default})

    return_annotation = sig.return_annotation
    return_type = "Any" if return_annotation is inspect.Parameter.empty else str(return_annotation)

    return {
        "name": meta.name,
        "description": meta.description,
        "tags": meta.tags,
        "category": meta.category,
        "destructive": meta.destructive,
        "idempotent": meta.idempotent,
        "params": params,
        "return_type": return_type,
        "docstring": inspect.getdoc(func) or "",
    }


def _format_type(type_str: str) -> str:
    """Strip verbose module prefixes from a type annotation string.

    Args:
        type_str: Raw type annotation string.

    Returns:
        Human-readable type string.
    """
    return type_str.replace("typing.", "").replace("builtins.", "")


def _extract_docstring_sections(docstring: str) -> dict[str, str]:
    """Parse Google-style docstring into named sections.

    Args:
        docstring: Full docstring text.

    Returns:
        Dict with keys ``"args"``, ``"returns"``, ``"raises"`` and their content.
    """
    sections: dict[str, str] = {"args": "", "returns": "", "raises": ""}
    current_section: str | None = None
    section_lines: list[str] = []

    for line in docstring.split("\n"):
        stripped = line.strip()
        if stripped in ("Args:", "Returns:", "Raises:"):
            if current_section and section_lines:
                sections[current_section] = "\n".join(section_lines).strip()
                section_lines = []
            current_section = stripped[:-1].lower()
        elif current_section and (line.startswith((" ", "\t")) or stripped == ""):
            section_lines.append(line)

    if current_section and section_lines:
        sections[current_section] = "\n".join(section_lines).strip()

    return sections


def _param_description(param_name: str, docstring: str) -> str:
    """Extract a single parameter's description from a docstring.

    Args:
        param_name: Parameter name to look up.
        docstring: Full docstring.

    Returns:
        Description text, or empty string if not found.
    """
    args_text = _extract_docstring_sections(docstring)["args"]
    lines = args_text.split("\n")
    for i, line in enumerate(lines):
        if param_name in line and ":" in line:
            desc_start = line.split(":", 1)[1].strip()
            parts = [desc_start] if desc_start else []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if not next_line.strip():
                    j += 1
                    continue
                if next_line[0] not in (" ", "\t") or next_line.strip().endswith(":"):
                    break
                parts.append(next_line.strip())
                j += 1
            return " ".join(parts).strip()
    return ""


def _return_description(docstring: str) -> str:
    """Extract the returns description from a docstring.

    Args:
        docstring: Full docstring.

    Returns:
        Returns description text, or empty string.
    """
    returns_text = _extract_docstring_sections(docstring)["returns"]
    return " ".join(line.strip() for line in returns_text.split("\n") if line.strip())


def _collect_bricks_by_category(modules: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """Collect all brick metadata from modules, organised by category.

    Args:
        modules: Stdlib modules to inspect.

    Returns:
        Dict mapping category name → list of brick metadata dicts.
    """
    result: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()

    for module in modules:
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            metadata = _extract_brick_metadata(obj)
            if metadata and metadata["name"] not in seen:
                seen.add(metadata["name"])
                category = metadata["category"]
                result.setdefault(category, []).append(metadata)

    return result


def _generate_markdown(bricks_by_category: dict[str, list[dict[str, Any]]]) -> str:
    """Render the brick catalog as a markdown string.

    Args:
        bricks_by_category: Brick metadata grouped by category.

    Returns:
        Full markdown text for the catalog.
    """
    total = sum(len(v) for v in bricks_by_category.values())
    lines: list[str] = [
        "# Brick Catalog (Auto-Generated)",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"This catalog documents all {total} available stdlib bricks. "
        "Each brick returns a dictionary with a `result` key.",
        "",
    ]

    for category in sorted(bricks_by_category):
        bricks = sorted(bricks_by_category[category], key=lambda b: b["name"])
        lines += [f"## {category.replace('_', ' ').title()}", ""]

        for brick_info in bricks:
            name: str = brick_info["name"]
            description: str = brick_info["description"]
            tags: list[str] = brick_info["tags"]
            params: list[dict[str, Any]] = brick_info["params"]
            return_type: str = brick_info["return_type"]
            docstring: str = brick_info["docstring"]

            lines.append(f"### {name}")
            lines.append("")

            if description:
                lines += [description, ""]

            if tags:
                lines += [f"**Tags:** {', '.join(f'`{t}`' for t in sorted(tags))}", ""]

            if params:
                lines.append("**Input:**")
                lines.append("")
                for param in params:
                    pname: str = param["name"]
                    ptype = _format_type(param["type"])
                    pdesc = _param_description(pname, docstring)
                    default_text = "" if param["default"] is None else f" (default: {param['default']})"
                    desc_suffix = f": {pdesc}" if pdesc else ""
                    lines.append(f"- `{pname}` ({ptype}){default_text}{desc_suffix}")
                lines.append("")

            lines += [
                "**Output:**",
                "",
                f"- `result` ({_format_type(return_type)}): {_return_description(docstring)}",
                "",
                "",
            ]

    return "\n".join(lines)


def generate_catalog(output_path: Path) -> int:
    """Generate BRICK_CATALOG.md and write it to *output_path*.

    Args:
        output_path: Destination file path.

    Returns:
        Total number of bricks documented.
    """
    bricks_by_category = _collect_bricks_by_category(_MODULES)
    catalog_md = _generate_markdown(bricks_by_category)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(catalog_md, encoding="utf-8")
    return sum(len(v) for v in bricks_by_category.values())


def main() -> None:
    """Entry point: generate catalog and print summary."""
    repo_root = Path(__file__).resolve().parents[3]
    output_path = repo_root / "docs" / "BRICK_CATALOG.md"
    bricks_by_category = _collect_bricks_by_category(_MODULES)
    catalog_md = _generate_markdown(bricks_by_category)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(catalog_md, encoding="utf-8")

    total = sum(len(v) for v in bricks_by_category.values())
    print(f"Generated {output_path} ({total} bricks)")
    print("\nBricks by category:")
    for category in sorted(bricks_by_category):
        print(f"  {category}: {len(bricks_by_category[category])} bricks")


if __name__ == "__main__":
    main()
