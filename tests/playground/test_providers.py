"""Unit tests for the Playground provider adapters.

All tests mock the underlying SDK / subprocess / HTTP call — no network.
A BYOK test for each keyed provider asserts the API key is carried only
via the constructor, never read from the environment.
"""

from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from bricks.providers.anthropic import AnthropicProvider
from bricks.providers.ollama import OllamaProvider
from bricks.providers.openai import OpenAIProvider

# ── Anthropic ────────────────────────────────────────────────────────────────


def _fake_anthropic_message(text: str = "hi", model: str = "claude-haiku-4-5") -> Any:
    """Build a stand-in for anthropic.types.Message."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        model=model,
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


def test_anthropic_requires_api_key() -> None:
    with pytest.raises(ValueError, match="BYOK"):
        AnthropicProvider(model="claude-haiku-4-5", api_key="")


def test_anthropic_complete_maps_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            captured["messages_kwargs"] = kwargs
            return _fake_anthropic_message("hello there")

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["client_kwargs"] = kwargs
            self.messages = FakeMessages()

    fake_anthropic = SimpleNamespace(Anthropic=FakeClient, NOT_GIVEN=object())
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)

    provider = AnthropicProvider(model="claude-haiku-4-5", api_key="sk-test-xxx")
    result = provider.complete("say hi", system="only say hi")

    assert result.text == "hello there"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.model == "claude-haiku-4-5"
    assert result.estimated is False
    assert captured["client_kwargs"]["api_key"] == "sk-test-xxx"


def test_anthropic_ignores_env_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """BYOK: the provider never reads ANTHROPIC_API_KEY from the environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-leaked-key")

    captured: dict[str, Any] = {}

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            return _fake_anthropic_message()

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["client_kwargs"] = kwargs
            self.messages = FakeMessages()

    fake_anthropic = SimpleNamespace(Anthropic=FakeClient, NOT_GIVEN=object())
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)

    provider = AnthropicProvider(model="claude-haiku-4-5", api_key="sk-byok-xxx")
    provider.complete("hi")

    assert captured["client_kwargs"]["api_key"] == "sk-byok-xxx"
    assert captured["client_kwargs"]["api_key"] != os.environ["ANTHROPIC_API_KEY"]


# ── OpenAI ───────────────────────────────────────────────────────────────────


def _fake_openai_response(text: str = "hi") -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        model="gpt-4o-mini",
        usage=SimpleNamespace(
            prompt_tokens=8,
            completion_tokens=4,
            prompt_tokens_details=SimpleNamespace(cached_tokens=2),
        ),
    )


def test_openai_requires_api_key() -> None:
    with pytest.raises(ValueError, match="BYOK"):
        OpenAIProvider(model="gpt-4o-mini", api_key="")


def test_openai_complete_maps_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            captured["kwargs"] = kwargs
            return _fake_openai_response("openai says hi")

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["client_kwargs"] = kwargs
            self.chat = FakeChat()

    fake_openai = SimpleNamespace(OpenAI=FakeClient)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai)

    provider = OpenAIProvider(model="gpt-4o-mini", api_key="sk-open-xxx")
    result = provider.complete("hi", system="terse")

    assert result.text == "openai says hi"
    assert result.input_tokens == 8
    assert result.output_tokens == 4
    assert result.cached_input_tokens == 2
    assert result.model == "gpt-4o-mini"
    assert captured["client_kwargs"]["api_key"] == "sk-open-xxx"
    assert captured["kwargs"]["messages"][0] == {"role": "system", "content": "terse"}
    assert captured["kwargs"]["messages"][1] == {"role": "user", "content": "hi"}


def test_openai_ignores_env_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """BYOK: the provider never reads OPENAI_API_KEY from the environment."""
    monkeypatch.setenv("OPENAI_API_KEY", "env-leaked-key")

    captured: dict[str, Any] = {}

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            return _fake_openai_response()

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["client_kwargs"] = kwargs
            self.chat = FakeChat()

    fake_openai = SimpleNamespace(OpenAI=FakeClient)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai)

    provider = OpenAIProvider(model="gpt-4o-mini", api_key="sk-byok-xxx")
    provider.complete("hi")

    assert captured["client_kwargs"]["api_key"] == "sk-byok-xxx"
    assert captured["client_kwargs"]["api_key"] != os.environ["OPENAI_API_KEY"]


# ── Ollama ───────────────────────────────────────────────────────────────────


def test_ollama_complete_parses_response() -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> Any:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "response": "ollama says hi",
                "model": "llama3",
                "prompt_eval_count": 12,
                "eval_count": 3,
            },
        )

    with patch("httpx.post", fake_post):
        provider = OllamaProvider(model="llama3")
        result = provider.complete("hi", system="terse")

    assert result.text == "ollama says hi"
    assert result.input_tokens == 12
    assert result.output_tokens == 3
    assert result.model == "llama3"
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["json"]["model"] == "llama3"
    assert captured["json"]["prompt"] == "hi"
    assert captured["json"]["system"] == "terse"
    assert captured["json"]["stream"] is False


def test_ollama_connect_error_is_helpful() -> None:
    import httpx

    def fake_post(*_args: Any, **_kwargs: Any) -> Any:
        raise httpx.ConnectError("cannot connect")

    with patch("httpx.post", fake_post):
        provider = OllamaProvider(model="llama3")
        with pytest.raises(RuntimeError, match="ollama serve"):
            provider.complete("hi")


# ── Claude Code adapter (reuses bricks.providers.claudecode from #47) ────────


def test_claudecode_via_build_provider() -> None:
    """routes._build_provider('claude_code', ...) returns the existing provider."""
    from bricks.playground.web.routes import _build_provider
    from bricks.providers.claudecode import ClaudeCodeProvider

    p = _build_provider("claude_code", "haiku", None)
    assert isinstance(p, ClaudeCodeProvider)
    assert p.model == "haiku"


def test_claudecode_subprocess_mocked() -> None:
    """Smoke: the underlying #47 provider still parses JSON output via subprocess."""
    import json as jsonlib

    from bricks.providers.claudecode import ClaudeCodeProvider

    sample = {
        "is_error": False,
        "result": "hello",
        "total_cost_usd": 0.01,
        "usage": {
            "input_tokens": 5,
            "output_tokens": 2,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        "modelUsage": {"claude-haiku-4-5": {}},
    }
    fake = subprocess.CompletedProcess(args=["claude"], returncode=0, stdout=jsonlib.dumps(sample), stderr="")
    with patch("bricks.providers.claudecode.provider.subprocess.run", return_value=fake):
        provider = ClaudeCodeProvider()
        result = provider.complete("hi")
    assert result.text == "hello"
    assert result.cost_usd == 0.01
    assert result.model == "claude-haiku-4-5"
