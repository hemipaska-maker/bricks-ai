"""LLMProvider implementation that talks to a local Ollama server over HTTP."""

from __future__ import annotations

import logging
import time

from bricks.llm.base import CompletionResult, LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLMProvider that calls a local Ollama server (default ``localhost:11434``).

    Ollama handles auth locally — no key required. Fails with a clear error
    message if the server isn't running.
    """

    def __init__(
        self,
        model: str,
        *,
        host: str = "http://localhost:11434",
        timeout: float = 300.0,
    ) -> None:
        """Initialise the provider.

        Args:
            model: Ollama model name (e.g. ``llama3``, ``mistral``).
            host: Base URL of the Ollama server.
            timeout: Per-request timeout in seconds.
        """
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        """POST ``/api/generate`` with ``stream=false`` and return the response."""
        try:
            import httpx  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("httpx not installed. Install with: pip install bricks[playground]") from exc

        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        t0 = time.monotonic()
        try:
            response = httpx.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.host}. Is the server running? Start it with: `ollama serve`"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}") from exc
        elapsed = time.monotonic() - t0

        data = response.json()
        return CompletionResult(
            text=str(data.get("response", "")),
            input_tokens=int(data.get("prompt_eval_count", 0) or 0),
            output_tokens=int(data.get("eval_count", 0) or 0),
            model=str(data.get("model", self.model)),
            duration_seconds=elapsed,
            estimated=False,
        )
