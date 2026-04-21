"""Tests for ClaudeCodeProvider."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any
from unittest.mock import patch

import pytest

from bricks.providers.claudecode import ClaudeCodeProvider

_CLAUDE_AVAILABLE = shutil.which("claude") is not None

_SAMPLE_JSON = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 2411,
    "duration_api_ms": 1779,
    "num_turns": 1,
    "result": "hello",
    "session_id": "abc-123",
    "total_cost_usd": 0.161,
    "usage": {
        "input_tokens": 3,
        "cache_creation_input_tokens": 25743,
        "cache_read_input_tokens": 0,
        "output_tokens": 4,
    },
    "modelUsage": {
        "claude-sonnet-4-6": {
            "inputTokens": 3,
            "outputTokens": 4,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 25743,
            "costUSD": 0.161,
            "contextWindow": 200000,
            "maxOutputTokens": 32000,
        }
    },
}


def _mock_run(stdout: str, returncode: int = 0) -> Any:
    """Return a CompletedProcess stand-in with the given stdout."""
    return subprocess.CompletedProcess(
        args=["claude", "-p", "--output-format", "json"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def test_json_output_populates_all_fields() -> None:
    """JSON response maps to real tokens, cost, cache counters."""
    provider = ClaudeCodeProvider()
    with patch(
        "bricks.providers.claudecode.provider.subprocess.run",
        return_value=_mock_run(json.dumps(_SAMPLE_JSON)),
    ):
        response = provider.complete("hi")

    assert response.text == "hello"
    assert response.input_tokens == 3
    assert response.output_tokens == 4
    assert response.cached_input_tokens == 0
    assert response.cache_creation_input_tokens == 25743
    assert response.cost_usd == 0.161
    assert response.model == "claude-sonnet-4-6"
    assert response.estimated is False


def test_is_error_true_raises_runtime_error() -> None:
    """`is_error: true` raises RuntimeError with the error text."""
    payload = {"is_error": True, "result": "boom"}
    provider = ClaudeCodeProvider()
    with (
        patch(
            "bricks.providers.claudecode.provider.subprocess.run",
            return_value=_mock_run(json.dumps(payload)),
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        provider.complete("hi")


def test_malformed_json_falls_back_to_estimate() -> None:
    """Non-JSON output falls back to tiktoken/char estimation."""
    provider = ClaudeCodeProvider()
    with patch(
        "bricks.providers.claudecode.provider.subprocess.run",
        return_value=_mock_run("not-json"),
    ):
        response = provider.complete("hello world")

    assert response.estimated is True
    assert response.text == "not-json"
    assert response.input_tokens > 0
    assert response.output_tokens > 0
    assert response.cost_usd == 0.0
    assert response.model == "claude-code"


def test_malformed_json_fallback_preserves_model_alias() -> None:
    """Fallback uses the configured model alias when set."""
    provider = ClaudeCodeProvider(model="opus")
    with patch(
        "bricks.providers.claudecode.provider.subprocess.run",
        return_value=_mock_run("not-json"),
    ):
        response = provider.complete("hi")

    assert response.estimated is True
    assert response.model == "opus"


def test_model_param_appears_in_command() -> None:
    """`model=` adds `--model <alias>` to the subprocess argv."""
    provider = ClaudeCodeProvider(model="opus")
    with patch(
        "bricks.providers.claudecode.provider.subprocess.run",
        return_value=_mock_run(json.dumps(_SAMPLE_JSON)),
    ) as mock_run:
        provider.complete("hi")

    cmd = mock_run.call_args.args[0]
    assert cmd == ["claude", "-p", "--output-format", "json", "--model", "opus"]


def test_model_param_absent_when_not_set() -> None:
    """Default provider does not pass `--model`."""
    provider = ClaudeCodeProvider()
    with patch(
        "bricks.providers.claudecode.provider.subprocess.run",
        return_value=_mock_run(json.dumps(_SAMPLE_JSON)),
    ) as mock_run:
        provider.complete("hi")

    cmd = mock_run.call_args.args[0]
    assert "--model" not in cmd
    assert cmd == ["claude", "-p", "--output-format", "json"]


@pytest.mark.parametrize(
    "model_key",
    ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
)
def test_per_model_variants(model_key: str) -> None:
    """`result.model` matches whatever key `modelUsage` reports."""
    payload = {
        **_SAMPLE_JSON,
        "modelUsage": {model_key: _SAMPLE_JSON["modelUsage"]["claude-sonnet-4-6"]},
    }
    provider = ClaudeCodeProvider()
    with patch(
        "bricks.providers.claudecode.provider.subprocess.run",
        return_value=_mock_run(json.dumps(payload)),
    ):
        response = provider.complete("hi")

    assert response.model == model_key


def test_nonzero_returncode_raises() -> None:
    """Non-zero CLI exit still raises RuntimeError (pre-JSON-parse path)."""
    provider = ClaudeCodeProvider()
    failed = subprocess.CompletedProcess(
        args=["claude", "-p"],
        returncode=1,
        stdout="",
        stderr="cli crashed",
    )
    with (
        patch(
            "bricks.providers.claudecode.provider.subprocess.run",
            return_value=failed,
        ),
        pytest.raises(RuntimeError, match="cli crashed"),
    ):
        provider.complete("hi")


@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude CLI not available")
def test_simple_completion_returns_result() -> None:
    """complete() returns a CompletionResult with non-empty text."""
    provider = ClaudeCodeProvider()
    response = provider.complete("Reply with the single word HELLO and nothing else.")
    assert isinstance(response.text, str)
    assert len(response.text) > 0
    assert response.input_tokens > 0
    assert response.output_tokens > 0
    assert response.estimated is False
    assert response.model != ""


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
