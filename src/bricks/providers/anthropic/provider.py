"""LLMProvider implementation that talks to the Anthropic SDK directly.

BYOK only — the API key is passed in at construction and never read from
environment variables.
"""

from __future__ import annotations

import logging
import time

from bricks.llm.base import CompletionResult, LLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """LLMProvider that routes completions through the Anthropic Python SDK.

    The API key is required and is passed only via the constructor. This
    provider never inspects ``os.environ`` — BYOK flow for the Playground.

    Example::

        provider = AnthropicProvider(model="claude-haiku-4-5", api_key=key)
        response = provider.complete("Say hello.")
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ) -> None:
        """Initialise the provider.

        Args:
            model: Anthropic model identifier (e.g. ``claude-haiku-4-5``).
            api_key: BYOK key passed to the SDK client. Required.
            max_tokens: Max output tokens per completion.
            timeout: Per-request timeout in seconds.
        """
        if not api_key:
            raise ValueError("AnthropicProvider requires an api_key (BYOK only, never read from env).")
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.timeout = timeout

    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        """Send a prompt through the Anthropic Messages API."""
        try:
            import anthropic  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("anthropic SDK not installed. Install with: pip install bricks[playground]") from exc

        client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)

        t0 = time.monotonic()
        msg = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system or anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.monotonic() - t0

        text_parts = [block.text for block in msg.content if getattr(block, "type", None) == "text"]
        text = "".join(text_parts)

        usage = msg.usage
        return CompletionResult(
            text=text,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            model=msg.model or self.model,
            duration_seconds=elapsed,
            estimated=False,
            cached_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )
