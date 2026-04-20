"""Tests for ClaudeCodeProvider."""

from __future__ import annotations

import shutil

import pytest

from bricks.providers.claudecode import ClaudeCodeProvider

_CLAUDE_AVAILABLE = shutil.which("claude") is not None


@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude CLI not available")
def test_simple_completion_returns_result() -> None:
    """complete() returns a CompletionResult with non-empty text."""
    provider = ClaudeCodeProvider()
    response = provider.complete("Reply with the single word HELLO and nothing else.")
    assert isinstance(response.text, str)
    assert len(response.text) > 0
    assert response.input_tokens > 0
    assert response.output_tokens > 0
    assert response.estimated is True
    assert response.model == "claude-code"


@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude CLI not available")
def test_system_prompt_is_included() -> None:
    """System prompt is prepended to the user message."""
    provider = ClaudeCodeProvider()
    response = provider.complete(
        prompt="What is your task?",
        system="Your only task is to reply with the word BRICKS.",
    )
    assert isinstance(response.text, str)
    assert len(response.text) > 0


@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude CLI not available")
def test_timeout_is_respected() -> None:
    """Timeout parameter is accepted without error on a fast prompt."""
    provider = ClaudeCodeProvider(timeout=120)
    response = provider.complete("Say OK")
    assert isinstance(response.text, str)
