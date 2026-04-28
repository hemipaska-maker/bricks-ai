"""Tests for ``bricks.playground.provider_factory``.

The factory is the single source of truth that both the FastAPI web
routes and the ``bricks playground run`` CLI use to construct an
``LLMProvider``. Pre-PR the CLI hardcoded ``LiteLLMProvider`` and
broke on every bundled preset (which all declare ``model: claudecode``).
This suite locks down inference, key resolution, and construction
behaviour so the two surfaces can't drift again.
"""

from __future__ import annotations

import pytest

from bricks.playground.provider_factory import (
    SUPPORTED_PROVIDERS,
    build_provider,
    infer_provider,
    resolve_api_key,
)

# ── infer_provider ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claudecode", "claude_code"),
        ("claude-code", "claude_code"),
        ("claude_code", "claude_code"),
        ("ClaudeCode", "claude_code"),
        ("ollama/llama3", "ollama"),
        ("ollama/mistral:7b", "ollama"),
        ("gpt-4o-mini", "openai"),
        ("gpt-4", "openai"),
        ("o1-preview", "openai"),
        ("o3-mini", "openai"),
        ("claude-haiku-4-5", "anthropic"),
        ("claude-sonnet-4-5", "anthropic"),
        ("claude-opus-4-7", "anthropic"),
    ],
)
def test_infer_provider_recognises_known_aliases(model: str, expected: str) -> None:
    """Each model alias maps to the right provider so the CLI can pick a
    provider when the user only supplied the scenario's ``model`` field."""
    assert infer_provider(model) == expected


def test_infer_provider_rejects_unknown_with_helpful_message() -> None:
    """Unknown aliases produce a ValueError that names the supported set
    so the user knows which providers exist without re-reading docs."""
    with pytest.raises(ValueError) as exc_info:
        infer_provider("gemini/gemini-2.0-flash")
    msg = str(exc_info.value)
    assert "gemini/gemini-2.0-flash" in msg
    assert "--provider" in msg
    for p in SUPPORTED_PROVIDERS:
        assert p in msg


# ── resolve_api_key ─────────────────────────────────────────────────────────


def test_resolve_api_key_returns_empty_for_no_key_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """``claude_code`` and ``ollama`` never need an API key, even if env
    vars are set — the resolver returns "" so the CLI doesn't accidentally
    pass a stale key into a provider that doesn't want one."""
    monkeypatch.setenv("BRICKS_API_KEY", "should-be-ignored")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-ignored")
    assert resolve_api_key("claude_code", explicit="explicit-key") == ""
    assert resolve_api_key("ollama") == ""


def test_resolve_api_key_explicit_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit ``--api-key`` flag takes precedence over both env vars."""
    monkeypatch.setenv("BRICKS_API_KEY", "umbrella")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-specific")
    assert resolve_api_key("anthropic", explicit="explicit") == "explicit"


def test_resolve_api_key_umbrella_wins_over_provider_specific(monkeypatch: pytest.MonkeyPatch) -> None:
    """``BRICKS_API_KEY`` is the provider-agnostic umbrella — it should
    win over the provider-specific env var so users can keep one key
    in their shell and switch providers at the CLI."""
    monkeypatch.setenv("BRICKS_API_KEY", "umbrella")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-specific")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-specific")
    assert resolve_api_key("anthropic") == "umbrella"
    assert resolve_api_key("openai") == "umbrella"


def test_resolve_api_key_falls_back_to_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without explicit or umbrella, fall through to the provider's own env."""
    monkeypatch.delenv("BRICKS_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
    assert resolve_api_key("anthropic") == "anth-key"
    assert resolve_api_key("openai") == "oai-key"


def test_resolve_api_key_returns_empty_when_nothing_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Caller decides whether the empty result is fatal — resolver doesn't raise."""
    monkeypatch.delenv("BRICKS_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert resolve_api_key("anthropic") == ""


# ── build_provider ──────────────────────────────────────────────────────────


def test_build_provider_claude_code_needs_no_key() -> None:
    """``ClaudeCodeProvider`` uses the local CLI session — empty key is fine."""
    p = build_provider(provider="claude_code", model="", api_key="")
    assert type(p).__name__ == "ClaudeCodeProvider"


def test_build_provider_anthropic_requires_key() -> None:
    """Without BYOK the factory raises a ValueError naming the env vars
    so a CLI caller's error message points the user at the right knob."""
    with pytest.raises(ValueError) as exc_info:
        build_provider(provider="anthropic", model="claude-haiku-4-5", api_key="")
    msg = str(exc_info.value)
    assert "anthropic" in msg
    assert "ANTHROPIC_API_KEY" in msg
    assert "BRICKS_API_KEY" in msg


def test_build_provider_unknown_raises() -> None:
    """An unknown provider name fails fast with the supported-set listing."""
    with pytest.raises(ValueError) as exc_info:
        build_provider(provider="nope", model="x")
    msg = str(exc_info.value)
    assert "nope" in msg
    for p in SUPPORTED_PROVIDERS:
        assert p in msg
