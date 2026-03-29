"""LLMProvider implementation that routes through the Claude Code CLI."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from bricks.llm.base import LLMProvider

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

    Example::

        provider = ClaudeCodeProvider()
        response = provider.complete("Say hello", system="You are helpful.")
    """

    def __init__(self, timeout: int = 60) -> None:
        """Initialise provider.

        Args:
            timeout: Maximum seconds to wait for a ``claude -p`` response.
        """
        self.timeout = timeout

    def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt through ``claude -p`` and return the response.

        Args:
            prompt: The user message to send.
            system: Optional system prompt prepended before the user message.

        Returns:
            The model's text response, stripped of leading/trailing whitespace.

        Raises:
            RuntimeError: If the ``claude`` process exits with a non-zero code.
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
        result = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude -p failed: {result.stderr}")
        return result.stdout.strip()
