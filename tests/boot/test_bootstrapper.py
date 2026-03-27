"""Tests for bricks.boot — SystemBootstrapper and SystemConfig."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bricks.boot.bootstrapper import SystemBootstrapper
from bricks.boot.config import SystemConfig
from bricks.llm.base import LLMProvider

# ── Helpers ────────────────────────────────────────────────────────────────


def _write(tmp_path: Path, filename: str, content: str) -> Path:
    """Write content to a temp file and return its path."""
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ── TestSystemConfig ────────────────────────────────────────────────────────


class TestSystemConfig:
    """Tests for the SystemConfig model."""

    def test_defaults(self) -> None:
        """SystemConfig has safe defaults for all optional fields."""
        cfg = SystemConfig(name="test")
        assert cfg.description == ""
        assert cfg.brick_categories == []
        assert cfg.tags == []
        assert cfg.api_key == ""
        assert cfg.max_selector_results == 20

    def test_store_default_disabled(self) -> None:
        """StoreConfig defaults to disabled."""
        cfg = SystemConfig(name="test")
        assert cfg.store.enabled is False


# ── TestBootstrapperYaml ────────────────────────────────────────────────────


class TestBootstrapperYaml:
    """Tests for YAML config bootstrapping (no LLM call)."""

    def test_yaml_parses_name(self, tmp_path: Path) -> None:
        """Bootstrap from agent.yaml returns correct name."""
        p = _write(tmp_path, "agent.yaml", "name: crm_processor\n")
        cfg = SystemBootstrapper().bootstrap(p)
        assert cfg.name == "crm_processor"

    def test_yaml_parses_all_fields(self, tmp_path: Path) -> None:
        """All fields in agent.yaml round-trip correctly."""
        yaml_content = """\
name: my_agent
description: "Processes CRM data"
brick_categories:
  - data_transformation
  - math
tags:
  - aggregation
model: claude-haiku-4-5-20251001
max_selector_results: 10
store:
  enabled: true
  backend: memory
"""
        p = _write(tmp_path, "agent.yaml", yaml_content)
        cfg = SystemBootstrapper().bootstrap(p)
        assert cfg.name == "my_agent"
        assert cfg.description == "Processes CRM data"
        assert cfg.brick_categories == ["data_transformation", "math"]
        assert cfg.tags == ["aggregation"]
        assert cfg.model == "claude-haiku-4-5-20251001"
        assert cfg.max_selector_results == 10
        assert cfg.store.enabled is True

    def test_yaml_no_llm_call(self, tmp_path: Path) -> None:
        """YAML config does not make any LLM calls."""
        p = _write(tmp_path, "agent.yaml", "name: silent\n")
        mock_prov = MagicMock(spec=LLMProvider)
        SystemBootstrapper(provider=mock_prov).bootstrap(p)
        mock_prov.complete.assert_not_called()

    def test_yml_extension_supported(self, tmp_path: Path) -> None:
        """Bootstrap works with .yml extension as well as .yaml."""
        p = _write(tmp_path, "config.yml", "name: yml_test\n")
        cfg = SystemBootstrapper().bootstrap(p)
        assert cfg.name == "yml_test"

    def test_yaml_missing_name_uses_stem(self, tmp_path: Path) -> None:
        """Missing name field falls back to the file stem."""
        p = _write(tmp_path, "my_agent.yaml", "description: no name here\n")
        cfg = SystemBootstrapper().bootstrap(p)
        assert cfg.name == "my_agent"


# ── TestBootstrapperMarkdown ────────────────────────────────────────────────


class TestBootstrapperMarkdown:
    """Tests for Markdown config bootstrapping (one LLM call)."""

    def _mock_provider(self, json_text: str) -> MagicMock:
        """Return a mock LLMProvider that returns json_text."""
        mock_prov = MagicMock(spec=LLMProvider)
        mock_prov.complete.return_value = json_text
        return mock_prov

    def test_md_extracts_categories_and_tags(self, tmp_path: Path) -> None:
        """Bootstrap from .md makes one LLM call and extracts categories/tags."""
        p = _write(
            tmp_path,
            "skill.md",
            "# CRM Processor\nFilters and aggregates CRM customer data.\n",
        )
        mock_prov = self._mock_provider('{"categories": ["data_transformation"], "tags": ["filtering"]}')
        cfg = SystemBootstrapper(provider=mock_prov).bootstrap(p)
        assert cfg.brick_categories == ["data_transformation"]
        assert cfg.tags == ["filtering"]

    def test_md_extracts_title_as_name(self, tmp_path: Path) -> None:
        """The H1 heading in the .md file becomes the config name."""
        p = _write(tmp_path, "skill.md", "# My Agent\nDoes things.\n")
        mock_prov = self._mock_provider('{"categories": [], "tags": []}')
        cfg = SystemBootstrapper(provider=mock_prov).bootstrap(p)
        assert cfg.name == "My Agent"

    def test_md_llm_parse_failure_falls_back(self, tmp_path: Path) -> None:
        """Malformed JSON from LLM → empty categories/tags, no crash."""
        p = _write(tmp_path, "skill.md", "# Agent\nSome description.\n")
        mock_prov = self._mock_provider("not valid json at all")
        cfg = SystemBootstrapper(provider=mock_prov).bootstrap(p)
        assert cfg.brick_categories == []
        assert cfg.tags == []

    def test_md_no_title_uses_stem(self, tmp_path: Path) -> None:
        """No H1 heading → file stem used as name."""
        p = _write(tmp_path, "my_skill.md", "No heading here.\n")
        mock_prov = self._mock_provider('{"categories": [], "tags": []}')
        cfg = SystemBootstrapper(provider=mock_prov).bootstrap(p)
        assert cfg.name == "my_skill"


# ── TestBootstrapperErrors ──────────────────────────────────────────────────


class TestBootstrapperErrors:
    """Tests for bootstrapper error handling."""

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """Non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            SystemBootstrapper().bootstrap(tmp_path / "missing.yaml")

    def test_unsupported_extension_raises(self, tmp_path: Path) -> None:
        """Unsupported file extension raises ValueError."""
        p = _write(tmp_path, "config.toml", "name = 'test'\n")
        with pytest.raises(ValueError, match="Unsupported config format"):
            SystemBootstrapper().bootstrap(p)
