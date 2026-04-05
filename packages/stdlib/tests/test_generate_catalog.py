"""Tests for packages/stdlib/scripts/generate_catalog.py."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

# Add scripts directory to path so we can import generate_catalog
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from bricks_stdlib.math_numeric import divide  # noqa: E402
from generate_catalog import (  # noqa: E402
    _MODULES,
    _collect_bricks_by_category,
    _extract_brick_metadata,
    _extract_docstring_sections,
    _generate_markdown,
    _param_description,
    _return_description,
    generate_catalog,
)


def test_extract_brick_metadata_returns_none_for_plain_callable() -> None:
    def plain() -> None:
        pass

    assert _extract_brick_metadata(plain) is None


def test_extract_brick_metadata_returns_dict_for_brick() -> None:
    meta = _extract_brick_metadata(divide)
    assert meta is not None
    assert meta["name"] == "divide"
    assert "a" in [p["name"] for p in meta["params"]]
    assert "b" in [p["name"] for p in meta["params"]]


def test_collect_bricks_by_category_covers_all_modules() -> None:
    by_cat = _collect_bricks_by_category(_MODULES)
    all_names = {b["name"] for bricks in by_cat.values() for b in bricks}
    assert "divide" in all_names
    assert "base64_encode" in all_names
    assert "is_email_valid" in all_names
    assert "filter_dict_list" in all_names


def test_collect_bricks_no_duplicates() -> None:
    by_cat = _collect_bricks_by_category(_MODULES)
    all_names = [b["name"] for bricks in by_cat.values() for b in bricks]
    assert len(all_names) == len(set(all_names))


def test_generate_markdown_contains_header() -> None:
    by_cat = _collect_bricks_by_category(_MODULES)
    md = _generate_markdown(by_cat)
    assert "# Brick Catalog (Auto-Generated)" in md
    assert "Generated:" in md


def test_generate_markdown_contains_brick_names() -> None:
    by_cat = _collect_bricks_by_category(_MODULES)
    md = _generate_markdown(by_cat)
    assert "### divide" in md
    assert "### base64_encode" in md
    assert "### is_email_valid" in md


def test_generate_markdown_contains_input_output_sections() -> None:
    by_cat = _collect_bricks_by_category(_MODULES)
    md = _generate_markdown(by_cat)
    assert "**Input:**" in md
    assert "**Output:**" in md
    assert "`result`" in md


def test_generate_catalog_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "BRICK_CATALOG.md"
    count = generate_catalog(output)
    assert output.exists()
    assert count > 0
    content = output.read_text(encoding="utf-8")
    assert "# Brick Catalog (Auto-Generated)" in content


def test_generate_catalog_documents_expected_brick_count(tmp_path: Path) -> None:
    output = tmp_path / "BRICK_CATALOG.md"
    count = generate_catalog(output)
    # stdlib has at least 70 bricks
    assert count >= 70


def test_extract_docstring_sections_parses_args() -> None:
    doc = "Summary.\n\nArgs:\n    x: The input.\n    y: Another param.\n\nReturns:\n    The result.\n"
    sections = _extract_docstring_sections(doc)
    assert "x" in sections["args"]
    assert "y" in sections["args"]
    assert "result" in sections["returns"]


def test_param_description_extracts_correctly() -> None:
    doc = inspect.getdoc(divide) or ""
    desc = _param_description("a", doc)
    assert isinstance(desc, str)


def test_return_description_extracts_correctly() -> None:
    doc = inspect.getdoc(divide) or ""
    desc = _return_description(doc)
    assert isinstance(desc, str)


@pytest.mark.parametrize(
    "brick_name",
    [
        "divide",
        "base64_encode",
        "is_email_valid",
        "flatten_list",
        "parse_date",
        "filter_dict_list",
        "unique_values",
    ],
)
def test_catalog_contains_each_brick(brick_name: str, tmp_path: Path) -> None:
    output = tmp_path / "BRICK_CATALOG.md"
    generate_catalog(output)
    content = output.read_text(encoding="utf-8")
    assert f"### {brick_name}" in content
