"""Tests for LiteLLMProvider prompt-cache wiring.

The provider must:

1. Send the system prompt as a content-block list with
   ``cache_control: {"type": "ephemeral"}`` for Anthropic-family models,
   so Anthropic charges cached rates on the byte-identical system prompt
   composer reuses across every compose call.
2. Send the system prompt as a plain string for everything else — OpenAI
   caches automatically via prefix matching, and Gemini / Ollama don't
   use the same mechanism.
3. Read cache-usage fields back into :class:`CompletionResult`:
   - Anthropic: ``usage.cache_read_input_tokens`` /
     ``cache_creation_input_tokens``.
   - OpenAI: ``usage.prompt_tokens_details.cached_tokens``.

These tests patch ``litellm.completion`` so they don't hit the network.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bricks.llm.litellm_provider import LiteLLMProvider, _is_anthropic_family


@pytest.mark.parametrize(
    "model",
    [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5",
        "openrouter/anthropic/claude-opus-4-7",
        "bedrock/anthropic/claude-haiku-4-5",
        "anthropic/claude-haiku-4-5",
    ],
)
def test_is_anthropic_family_true(model: str) -> None:
    assert _is_anthropic_family(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "gpt-4o-mini",
        "gpt-5",
        "o4-mini",
        "gemini/gemini-2.0-flash",
        "ollama/llama3",
        "mistral/large",
        "",  # empty = non-Anthropic default
    ],
)
def test_is_anthropic_family_false(model: str) -> None:
    assert _is_anthropic_family(model) is False


def _build_response(
    text: str = "ok",
    in_tok: int = 100,
    out_tok: int = 5,
    cache_read: int = 0,
    cache_create: int = 0,
    openai_cached_tokens: int | None = None,
) -> MagicMock:
    """Build a mock litellm.completion response with configurable usage fields."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg

    usage = MagicMock(spec=["prompt_tokens", "completion_tokens"])
    usage.prompt_tokens = in_tok
    usage.completion_tokens = out_tok
    if cache_read:
        usage.cache_read_input_tokens = cache_read
    if cache_create:
        usage.cache_creation_input_tokens = cache_create
    if openai_cached_tokens is not None:
        details = MagicMock(spec=["cached_tokens"])
        details.cached_tokens = openai_cached_tokens
        usage.prompt_tokens_details = details

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


class TestAnthropicFamilyUsesContentBlocks:
    """Anthropic models must get content-block system with cache_control."""

    def test_claude_model_sends_content_block_with_cache_control(self) -> None:
        provider = LiteLLMProvider(model="claude-haiku-4-5-20251001", api_key="test-key")
        with patch("litellm.completion", return_value=_build_response()) as mock_completion:
            provider.complete(prompt="user text", system="SYSTEM_TEXT")

        call = mock_completion.call_args
        messages = call.kwargs["messages"]
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert isinstance(system_msg["content"], list), "Anthropic must get content-block list"
        block = system_msg["content"][0]
        assert block["type"] == "text"
        assert block["text"] == "SYSTEM_TEXT"
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_empty_system_stays_empty_string(self) -> None:
        """An empty system prompt is still an empty string — cache_control only wraps real content."""
        provider = LiteLLMProvider(model="claude-haiku-4-5", api_key="test-key")
        with patch("litellm.completion", return_value=_build_response()) as mock_completion:
            provider.complete(prompt="user text", system="")

        system_msg = mock_completion.call_args.kwargs["messages"][0]
        assert system_msg["content"] == "", "empty system must remain the empty string"

    @pytest.mark.parametrize(
        "model",
        ["openrouter/anthropic/claude-opus-4-7", "bedrock/anthropic/claude-haiku-4-5"],
    )
    def test_pass_through_anthropic_routes_get_cache_control(self, model: str) -> None:
        provider = LiteLLMProvider(model=model, api_key="test-key")
        with patch("litellm.completion", return_value=_build_response()) as mock_completion:
            provider.complete(prompt="x", system="SYS")

        system_msg = mock_completion.call_args.kwargs["messages"][0]
        assert isinstance(system_msg["content"], list)
        assert system_msg["content"][0]["cache_control"] == {"type": "ephemeral"}


class TestNonAnthropicUsesPlainString:
    """OpenAI / Gemini / Ollama keep the legacy plain-string format."""

    @pytest.mark.parametrize(
        "model",
        ["gpt-4o-mini", "gpt-5", "o4-mini", "gemini/gemini-2.0-flash", "ollama/llama3"],
    )
    def test_non_anthropic_plain_string_system(self, model: str) -> None:
        provider = LiteLLMProvider(model=model, api_key="test-key")
        with patch("litellm.completion", return_value=_build_response()) as mock_completion:
            provider.complete(prompt="x", system="SYS")

        system_msg = mock_completion.call_args.kwargs["messages"][0]
        assert system_msg["content"] == "SYS", f"{model} must send plain string"


class TestCacheUsageExtraction:
    """Cache-read / cache-creation counters flow into CompletionResult."""

    def test_anthropic_cache_read_and_create_populate(self) -> None:
        provider = LiteLLMProvider(model="claude-haiku-4-5", api_key="test-key")
        response = _build_response(cache_read=2400, cache_create=0)
        with patch("litellm.completion", return_value=response):
            result = provider.complete(prompt="x", system="SYS")

        assert result.cached_input_tokens == 2400
        assert result.cache_creation_input_tokens == 0

    def test_anthropic_cache_creation_populates_on_first_write(self) -> None:
        provider = LiteLLMProvider(model="claude-haiku-4-5", api_key="test-key")
        response = _build_response(cache_read=0, cache_create=2400)
        with patch("litellm.completion", return_value=response):
            result = provider.complete(prompt="x", system="SYS")

        assert result.cache_creation_input_tokens == 2400
        assert result.cached_input_tokens == 0

    def test_openai_cached_tokens_surface_as_cached_input_tokens(self) -> None:
        provider = LiteLLMProvider(model="gpt-4o-mini", api_key="test-key")
        response = _build_response(openai_cached_tokens=1800)
        with patch("litellm.completion", return_value=response):
            result = provider.complete(prompt="x", system="SYS")

        assert result.cached_input_tokens == 1800
        # Cache creation only applies to Anthropic.
        assert result.cache_creation_input_tokens == 0

    def test_missing_usage_fields_default_to_zero(self) -> None:
        """Providers that don't surface cache fields must not blow up the provider."""
        provider = LiteLLMProvider(model="claude-haiku-4-5", api_key="test-key")
        # Plain response with just prompt/completion tokens.
        response = _build_response()
        with patch("litellm.completion", return_value=response):
            result = provider.complete(prompt="x", system="SYS")

        assert result.cached_input_tokens == 0
        assert result.cache_creation_input_tokens == 0
