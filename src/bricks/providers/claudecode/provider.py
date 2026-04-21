"""LLMProvider implementation that routes through the Claude Code CLI."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path

from bricks.llm.base import CompletionResult, LLMProvider

logger = logging.getLogger(__name__)

# Common git-bash locations on Windows
_GIT_BASH_CANDIDATES = [
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Git/bin/bash.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Git/bin/bash.exe",
    Path("C:/Program Files/Git/bin/bash.exe"),
]


def _find_git_bash() -> str | None:
    """Return path to git-bash exe, or None if not found."""
    for candidate in _GIT_BASH_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


class ClaudeCodeProvider(LLMProvider):
    """LLMProvider that routes through Claude Code CLI (claude -p).

    Uses the host Claude Code session's plan — no API key needed.
    Only works when running inside a Claude Code session.

    Prompt is delivered via stdin (not as a CLI argument) to avoid OS
    argument-length limits on large prompts.

    Example::

        provider = ClaudeCodeProvider()
        response = provider.complete("Say hello", system="You are helpful.")
    """

    def __init__(self, timeout: int = 120, model: str | None = None) -> None:
        """Initialise provider.

        Args:
            timeout: Maximum seconds to wait for a ``claude -p`` response.
            model: Optional model alias to pass as ``--model`` (e.g.
                ``"sonnet"``, ``"opus"``, ``"haiku"``). ``None`` lets
                Claude Code pick its default.
        """
        self.timeout = timeout
        self.model = model

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using tiktoken, fallback to char/4.

        Args:
            text: The text to estimate tokens for.

        Returns:
            Estimated token count.
        """
        try:
            import tiktoken  # noqa: PLC0415

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:  # ImportError, OSError, network errors, etc.
            return len(text) // 4

    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        """Send a prompt through ``claude -p`` and return a CompletionResult.

        Invokes ``claude -p --output-format json`` and parses the structured
        response to report real token usage and cost. Falls back to tiktoken
        estimation if the CLI ever returns non-JSON output.

        Args:
            prompt: The user message to send.
            system: Optional system prompt prepended before the user message.

        Returns:
            CompletionResult with response text, real token counts, and cost
            when the CLI returns JSON; estimated counts otherwise.

        Raises:
            RuntimeError: If the ``claude`` process exits with a non-zero code
                or the parsed response has ``is_error: true``.
            subprocess.TimeoutExpired: If the process exceeds ``self.timeout``.
        """
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        # Remove CLAUDECODE to allow nested invocation inside an active session.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        # On Windows, Claude CLI requires CLAUDE_CODE_GIT_BASH_PATH to locate
        # git-bash. Set it explicitly if not already present.
        if "CLAUDE_CODE_GIT_BASH_PATH" not in env:
            git_bash = _find_git_bash()
            if git_bash:
                env["CLAUDE_CODE_GIT_BASH_PATH"] = git_bash

        cmd = ["claude", "-p", "--output-format", "json"]
        if self.model:
            cmd.extend(["--model", self.model])

        logger.info("Sending prompt to claude -p (%d chars, timeout=%ds)", len(full_prompt), self.timeout)
        logger.debug("Full prompt:\n%s", full_prompt)

        t0 = time.monotonic()
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                input=full_prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
                env=env,
            )
        except subprocess.TimeoutExpired:
            logger.error("claude -p timed out after %ds", self.timeout)
            raise

        elapsed = time.monotonic() - t0
        if result.returncode != 0:
            logger.error("claude -p failed (rc=%d): %s", result.returncode, result.stderr)
            raise RuntimeError(f"claude -p failed: {result.stderr}")

        logger.info("claude -p responded (%d chars, %.1fs)", len(result.stdout), elapsed)
        logger.debug("Raw response:\n%s", result.stdout)

        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.warning("claude -p returned non-JSON; falling back to tiktoken estimate")
            return CompletionResult(
                text=result.stdout.strip(),
                input_tokens=self._estimate_tokens(full_prompt),
                output_tokens=self._estimate_tokens(result.stdout),
                model=self.model or "claude-code",
                duration_seconds=elapsed,
                estimated=True,
            )

        if parsed.get("is_error"):
            raise RuntimeError(parsed.get("result", "unknown error"))

        usage = parsed.get("usage", {})
        model_usage = parsed.get("modelUsage", {})
        model_name = next(iter(model_usage), self.model or "claude-code")

        return CompletionResult(
            text=parsed.get("result", "").strip(),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model=model_name,
            duration_seconds=elapsed,
            estimated=False,
            cached_input_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            cost_usd=parsed.get("total_cost_usd", 0.0),
        )
