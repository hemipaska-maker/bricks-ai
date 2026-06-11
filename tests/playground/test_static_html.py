"""Snapshot-ish checks for the v2 Playground frontend drop-in."""

from __future__ import annotations

from pathlib import Path

_INDEX = Path(__file__).resolve().parents[2] / "src" / "bricks_ai" / "playground" / "web" / "static" / "index.html"


def test_index_html_exists() -> None:
    """The v2 mockup must be copied into the web static dir."""
    assert _INDEX.is_file(), f"expected {_INDEX} to exist"


def test_index_html_has_title() -> None:
    """The Playground page keeps its <title>."""
    html = _INDEX.read_text(encoding="utf-8")
    assert "<title>Bricks Playground</title>" in html


def test_font_link_keeps_only_allowed_families() -> None:
    """Google Fonts <link> should import only Inter, Instrument Serif, JetBrains Mono."""
    html = _INDEX.read_text(encoding="utf-8")
    link_start = html.find('<link href="https://fonts.googleapis.com/css2?')
    assert link_start != -1, "missing Google Fonts <link>"
    link_end = html.find(">", link_start)
    link = html[link_start : link_end + 1]

    # Allowed families — all three must be present.
    for family in ("Instrument+Serif", "Inter", "JetBrains+Mono"):
        assert family in link, f"expected {family} in font link"

    # Stripped families — none may appear in the <link> tag.
    for family in ("Fraunces", "Space+Grotesk", "Playfair+Display"):
        assert family not in link, f"{family} should have been stripped from the font link"
