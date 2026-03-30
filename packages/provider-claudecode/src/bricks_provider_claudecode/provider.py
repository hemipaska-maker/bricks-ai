"""LLMProvider implementation that routes through the Claude Code CLI."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

from bricks.llm.base import LLMProvider

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

    def __init__(self, timeout: int = 120) -> None:
        """Initialise provider.

        Args:
            timeout: Maximum seconds to wait for a ``claude -p`` response.
        """
        self.timeout = timeout

    def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt through ``claude -p`` and return the response.

        The full prompt is passed via stdin to avoid OS argument-length limits.

        Args:
            prompt: The user message to send.
            system: Optional system prompt prepended before the user message.

        Returns:
            The model's text response, stripped of leading/trailing whitespace.

        Raises:
            RuntimeError: If the ``claude`` process exits with a non-zero code.
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

        logger.info("Sending prompt to claude -p (%d chars, timeout=%ds)", len(full_prompt), self.timeout)
        logger.debug("Full prompt:\n%s", full_prompt)

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                ["claude", "-p"],  # noqa: S607
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
        return result.stdout.strip()
