"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CompletionResult:
    """Result from an LLM completion call.

    Attributes:
        text: The LLM response text.
        input_tokens: Number of input tokens (exact or estimated).
        output_tokens: Number of output tokens (exact or estimated).
        model: Which model actually responded.
        duration_seconds: Wall-clock time for this call.
        estimated: True if tokens are tiktoken estimates; False if from API.
        cached_input_tokens: Number of input tokens served from the prompt
            cache. Unified across providers: Anthropic's
            ``cache_read_input_tokens`` and OpenAI's
            ``prompt_tokens_details.cached_tokens`` both populate this.
            ``0`` when caching is inactive, unsupported, or on a cache miss.
        cache_creation_input_tokens: Anthropic-only counter for tokens that
            were written to the ephemeral prompt cache on this call.
            Surfaces tier-1 cache writes so callers can distinguish first-
            pay writes from subsequent reads. ``0`` for non-Anthropic
            providers.
        cost_usd: Actual dollar cost reported by the provider for this call.
            ``0.0`` when the provider doesn't report cost or tokens were
            estimated rather than measured.
    """

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    duration_seconds: float = 0.0
    estimated: bool = False
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cost_usd: float = 0.0


class LLMProvider(ABC):
    """Abstract LLM backend.

    Implement :meth:`complete` to plug any model into Bricks.

    Example::

        class MyProvider(LLMProvider):
            def complete(self, prompt: str, system: str = "") -> CompletionResult:
                text = my_llm_client.call(system=system, user=prompt)
                return CompletionResult(text=text)
    """

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        """Send a prompt to the LLM and return a CompletionResult.

        Args:
            prompt: The user message to send.
            system: The system prompt that configures model behaviour.

        Returns:
            CompletionResult with response text and token metadata.
        """
