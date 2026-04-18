"""Tests for bricks.llm — LLMProvider ABC and LiteLLMProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bricks.errors import BricksComposeError, BricksConfigError
from bricks.llm.base import LLMProvider
from bricks.llm.litellm_provider import LiteLLMProvider


class TestLLMProviderABC:
    """Tests for the LLMProvider abstract base class."""

    def test_cannot_instantiate_abstract(self) -> None:
        """LLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]


class TestLiteLLMProvider:
    """Tests for LiteLLMProvider."""

    def _mock_litellm_response(self, text: str, in_tok: int = 10, out_tok: int = 5) -> MagicMock:
        """Build a mock litellm response with usage metadata."""
        msg = MagicMock()
        msg.content = text
        choice = MagicMock()
        choice.message = msg
        usage = MagicMock()
        usage.prompt_tokens = in_tok
        usage.completion_tokens = out_tok
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        return resp

    def test_calls_litellm_completion(self) -> None:
        """LiteLLMProvider.complete() returns CompletionResult with correct text."""
        provider = LiteLLMProvider(model="claude-haiku-4-5", api_key="sk-test")
        mock_resp = self._mock_litellm_response("hello")
        with patch("litellm.completion", return_value=mock_resp) as mock_completion:
            result = provider.complete(prompt="hi", system="be helpful")
        mock_completion.assert_called_once()
        assert result.text == "hello"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.estimated is False
        assert result.model == "claude-haiku-4-5"

    def test_auth_error_raises_bricks_config_error(self) -> None:
        """Auth-related LiteLLM errors are converted to BricksConfigError."""
        provider = LiteLLMProvider()
        with (
            patch("litellm.completion", side_effect=Exception("AuthenticationError: invalid api key")),
            pytest.raises(BricksConfigError, match="No API key found"),
        ):
            provider.complete(prompt="hi", system="sys")

    def test_generic_error_raises_bricks_compose_error(self) -> None:
        """Non-auth LiteLLM errors are converted to BricksComposeError."""
        provider = LiteLLMProvider()
        with (
            patch("litellm.completion", side_effect=Exception("rate limit exceeded")),
            pytest.raises(BricksComposeError, match="LLM call failed"),
        ):
            provider.complete(prompt="hi", system="sys")
