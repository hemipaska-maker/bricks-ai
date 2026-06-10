"""Tests for bricks_ai.skill_boot — markdown skill bootstrapping (one LLM call)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bricks_ai.llm.base import CompletionResult, LLMProvider
from bricks_ai.skill_boot import bootstrap_from_skill

# ── Helpers ────────────────────────────────────────────────────────────────


def _write(tmp_path: Path, filename: str, content: str) -> Path:
    """Write content to a temp file and return its path."""
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


def _mock_provider(json_text: str) -> MagicMock:
    """Return a mock LLMProvider that returns json_text."""
    mock_prov = MagicMock(spec=LLMProvider)
    mock_prov.complete.return_value = CompletionResult(text=json_text)
    return mock_prov


# ── Tests ───────────────────────────────────────────────────────────────────


def test_md_extracts_categories_and_tags(tmp_path: Path) -> None:
    """Bootstrap from .md makes one LLM call and extracts categories/tags."""
    p = _write(
        tmp_path,
        "skill.md",
        "# CRM Processor\nFilters and aggregates CRM customer data.\n",
    )
    mock_prov = _mock_provider('{"categories": ["data_transformation"], "tags": ["filtering"]}')
    cfg = bootstrap_from_skill(p, provider=mock_prov)
    assert cfg.brick_categories == ["data_transformation"]
    assert cfg.tags == ["filtering"]
    mock_prov.complete.assert_called_once()


def test_md_extracts_title_as_name(tmp_path: Path) -> None:
    """The H1 heading in the .md file becomes the config name."""
    p = _write(tmp_path, "skill.md", "# My Agent\nDoes things.\n")
    mock_prov = _mock_provider('{"categories": [], "tags": []}')
    cfg = bootstrap_from_skill(p, provider=mock_prov)
    assert cfg.name == "My Agent"


def test_md_llm_parse_failure_falls_back(tmp_path: Path) -> None:
    """Malformed JSON from LLM → empty categories/tags, no crash."""
    p = _write(tmp_path, "skill.md", "# Agent\nSome description.\n")
    mock_prov = _mock_provider("not valid json at all")
    cfg = bootstrap_from_skill(p, provider=mock_prov)
    assert cfg.brick_categories == []
    assert cfg.tags == []


def test_md_no_title_uses_stem(tmp_path: Path) -> None:
    """No H1 heading → file stem used as name."""
    p = _write(tmp_path, "my_skill.md", "No heading here.\n")
    mock_prov = _mock_provider('{"categories": [], "tags": []}')
    cfg = bootstrap_from_skill(p, provider=mock_prov)
    assert cfg.name == "my_skill"


def test_missing_file_raises(tmp_path: Path) -> None:
    """Non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        bootstrap_from_skill(tmp_path / "missing.md")


def test_non_markdown_extension_raises(tmp_path: Path) -> None:
    """Non-.md extension raises ValueError."""
    p = _write(tmp_path, "agent.yaml", "name: test\n")
    with pytest.raises(ValueError, match="Unsupported skill format"):
        bootstrap_from_skill(p)
