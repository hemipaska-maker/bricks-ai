"""LiteLLM-backed LLM provider — supports any model string LiteLLM accepts."""

from __future__ import annotations

import time

from bricks.errors import BricksComposeError, BricksConfigError
from bricks.llm.base import CompletionResult, LLMProvider


class LiteLLMProvider(LLMProvider):
    """LLM provider backed by LiteLLM.

    Supports any model string that LiteLLM accepts:

    - ``claude-haiku-4-5`` → reads ``ANTHROPIC_API_KEY``
    - ``gpt-4o-mini`` → reads ``OPENAI_API_KEY``
    - ``gemini/gemini-2.0-flash`` → reads ``GOOGLE_API_KEY``

    LiteLLM resolves the API key from environment automatically.
    Pass ``api_key=`` only when you need to override the environment.

    Args:
        model: LiteLLM model string.  Defaults to ``claude-haiku-4-5``.
        api_key: Explicit API key.  Leave empty to use environment variables.
    """

    def __init__(self, model: str = "claude-haiku-4-5", api_key: str = "") -> None:
        """Initialise the provider.

        Args:
            model: LiteLLM model string.
            api_key: Optional explicit API key; empty string means use env var.
        """
        self._model = model
        self._api_key: str | None = api_key or None  # None → LiteLLM reads from env

    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        """Call the LLM and return a CompletionResult with real token counts.

        Args:
            prompt: User message.
            system: System prompt.

        Returns:
            CompletionResult with response text, real token counts, and timing.

        Raises:
            ImportError: If ``litellm`` is not installed (``pip install bricks[ai]``).
            BricksConfigError: If no API key is found for the model.
            BricksComposeError: If the LLM call fails for any other reason.
        """
        try:
            import litellm  # noqa: PLC0415  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("The 'litellm' package is required. Install with: pip install bricks[ai]") from exc

        t0 = time.monotonic()
        try:
            response = litellm.completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                api_key=self._api_key,
            )
            content = response.choices[0].message.content
            text = str(content) if content is not None else ""
            usage = getattr(response, "usage", None)
            in_tok = int(getattr(usage, "prompt_tokens", 0) or 0)
            out_tok = int(getattr(usage, "completion_tokens", 0) or 0)
            return CompletionResult(
                text=text,
                input_tokens=in_tok,
                output_tokens=out_tok,
                model=self._model,
                duration_seconds=time.monotonic() - t0,
                estimated=False,
            )
        except ImportError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "auth" in msg or "api key" in msg or "api_key" in msg or "unauthorized" in msg:
                raise BricksConfigError(
                    "No API key found. Set ANTHROPIC_API_KEY (or the appropriate key for your model)"
                    " or pass api_key= to Bricks.default()"
                ) from exc
            raise BricksComposeError(f"LLM call failed: {exc}") from exc
