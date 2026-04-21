"""LLMProvider implementation that talks to the OpenAI SDK directly.

BYOK only — API key is constructor-only and never read from environment.
"""

from __future__ import annotations

import logging
import time

from bricks.llm.base import CompletionResult, LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """LLMProvider that routes completions through the OpenAI Python SDK.

    Uses the Chat Completions API with ``messages=[{role: user, content: prompt}]``
    (plus an optional system message). The API key is required and never
    read from environment variables.
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
            model: OpenAI model identifier (e.g. ``gpt-4o-mini``).
            api_key: BYOK key passed to the SDK client. Required.
            max_tokens: Max output tokens per completion.
            timeout: Per-request timeout in seconds.
        """
        if not api_key:
            raise ValueError("OpenAIProvider requires an api_key (BYOK only, never read from env).")
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.timeout = timeout

    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        """Send a prompt through the OpenAI Chat Completions API."""
        try:
            import openai  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("openai SDK not installed. Install with: pip install bricks[playground]") from exc

        client = openai.OpenAI(api_key=self.api_key, timeout=self.timeout)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        t0 = time.monotonic()
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
        )
        elapsed = time.monotonic() - t0

        text = resp.choices[0].message.content or ""
        usage = resp.usage

        cached = 0
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0

        return CompletionResult(
            text=text,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            model=resp.model or self.model,
            duration_seconds=elapsed,
            estimated=False,
            cached_input_tokens=cached,
        )
