"""Tests for bricks.benchmark.showcase.run."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from bricks.benchmark.showcase.run import expand_scenarios, validate_model_env


class TestExpandScenarios:
    """Tests for expand_scenarios()."""

    def test_all_expands_to_all_scenarios(self) -> None:
        """'all' expands to all CRM + ticket scenarios in order."""
        result = expand_scenarios(["all"])
        assert result == ["CRM-pipeline", "CRM-hallucination", "CRM-reuse", "TICKET-pipeline"]

    def test_single_scenario(self) -> None:
        """Single scenario name returns just that scenario."""
        assert expand_scenarios(["CRM-pipeline"]) == ["CRM-pipeline"]

    def test_multiple_scenarios_preserve_order(self) -> None:
        """Multiple scenarios are returned in canonical order."""
        result = expand_scenarios(["CRM-reuse", "CRM-pipeline"])
        assert result == ["CRM-pipeline", "CRM-reuse"]

    def test_default_is_all(self) -> None:
        """expand_scenarios(['all']) produces all four scenarios."""
        assert len(expand_scenarios(["all"])) == 4

    def test_deduplication(self) -> None:
        """Duplicate scenario names are deduplicated."""
        result = expand_scenarios(["CRM-pipeline", "CRM-pipeline"])
        assert result == ["CRM-pipeline"]


class TestValidateModelEnv:
    """Tests for validate_model_env()."""

    def test_ollama_skipped_silently(self) -> None:
        """Ollama models do not warn regardless of env state."""
        with patch.dict(os.environ, {}, clear=True):
            validate_model_env("ollama/llama3")  # must not raise or warn

    def test_claudecode_skipped_silently(self) -> None:
        """'claudecode' model does not warn regardless of env state."""
        with patch.dict(os.environ, {}, clear=True):
            validate_model_env("claudecode")  # must not raise or warn

    def test_warns_when_anthropic_key_missing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Warns when ANTHROPIC_API_KEY is missing for a claude model."""
        with patch.dict(os.environ, {}, clear=True):
            validate_model_env("claude-haiku-4-5")
        assert any("ANTHROPIC_API_KEY" in r.message for r in caplog.records)

    def test_no_warning_when_key_present(self, caplog: pytest.LogCaptureFixture) -> None:
        """No warning when the expected API key is present."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=False):
            validate_model_env("claude-haiku-4-5")
        assert not any("ANTHROPIC_API_KEY" in r.message for r in caplog.records)

    def test_warns_for_gpt_without_openai_key(self, caplog: pytest.LogCaptureFixture) -> None:
        """Warns when OPENAI_API_KEY is missing for a gpt model."""
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            validate_model_env("gpt-4o-mini")
        assert any("OPENAI_API_KEY" in r.message for r in caplog.records)

    def test_warns_for_gemini_without_google_key(self, caplog: pytest.LogCaptureFixture) -> None:
        """Warns when GOOGLE_API_KEY is missing for a gemini model."""
        env = {k: v for k, v in os.environ.items() if k != "GOOGLE_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            validate_model_env("gemini/gemini-2.0-flash")
        assert any("GOOGLE_API_KEY" in r.message for r in caplog.records)
