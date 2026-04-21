"""Tests for ``POST /playground/run-stream`` — the SSE variant that drives
the real-time UI in issue #56.

Reuses the happy-path fixture from :mod:`tests.integration.test_showcase_cached`
to avoid needing a live LLM. Asserts phase ordering, the final ``done``
event carries the expected outputs, and compare=True adds raw-LLM frames.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import bricks.playground.web.routes as routes_module
from bricks.llm.base import CompletionResult, LLMProvider
from bricks.playground.web.app import app

_FIXTURE_DIR = Path(__file__).parent.parent / "integration" / "fixtures"
_CRM_RAW = json.dumps(
    {
        "customers": [
            {"id": 1, "status": "active", "monthly_revenue": 100.0},
            {"id": 2, "status": "inactive", "monthly_revenue": 0.0},
            {"id": 3, "status": "active", "monthly_revenue": 50.0},
        ]
    }
)


class _ScriptedProvider(LLMProvider):
    """Minimal fixture-replay provider for this SSE suite."""

    def __init__(self, responses: list[CompletionResult]) -> None:
        self._queue = list(responses)

    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        if not self._queue:
            raise IndexError("scripted provider exhausted")
        return self._queue.pop(0)


def _provider_from_fixture(name: str, extra: int = 0) -> _ScriptedProvider:
    fx = json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))
    responses = [
        CompletionResult(
            text=r["dsl"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            model=r.get("model", ""),
            estimated=False,
        )
        for r in fx["responses"]
    ]
    # Raw-LLM path needs an extra response (a JSON outputs blob).
    for _ in range(extra):
        responses.append(
            CompletionResult(
                text='{"result": 2}',
                input_tokens=10,
                output_tokens=5,
                model=fx["responses"][0].get("model", ""),
                estimated=False,
            )
        )
    return _ScriptedProvider(responses)


def _parse_sse(raw: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    """Return (phase_events, done_payload, error_message) from an SSE body."""
    phases: list[dict[str, Any]] = []
    done: dict[str, Any] | None = None
    err: str | None = None
    for frame in raw.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        event_name: str | None = None
        data_line = ""
        for line in frame.split("\n"):
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_line = line[5:].strip()
        if not data_line:
            continue
        payload = json.loads(data_line)
        if event_name == "done":
            done = payload
        elif event_name == "error":
            err = payload.get("message")
        elif "phase" in payload:
            phases.append(payload)
    return phases, done, err


@pytest.fixture(name="client")
def _client() -> TestClient:
    return TestClient(app)


def test_run_stream_emits_phases_in_order_and_done(client: TestClient) -> None:
    """Happy path: compose_start → compose_done → execute_start → step_*
    pairs → check_done (once per expected key) → ``event: done`` with the
    full RunResponse payload."""
    provider = _provider_from_fixture("crm_pipeline_happy.json")

    with (
        patch.object(routes_module, "_build_provider", return_value=provider),
        client.stream(
            "POST",
            "/playground/run-stream",
            json={
                "provider": "claude_code",
                "model": "haiku",
                "task": "Count active customers",
                "data": json.loads(_CRM_RAW),
                "expected_output": {"result": 2},
            },
        ) as resp,
    ):
        assert resp.status_code == 200
        body = "".join(chunk.decode() for chunk in resp.iter_bytes())

    phases, done, err = _parse_sse(body)
    assert err is None, err
    assert done is not None
    assert done["bricks"]["outputs"] == {"result": 2}

    phase_names = [p["phase"] for p in phases]
    # Phase ordering: compose events come before execute, steps come after
    # execute, and check_done lands last — we assert index relationships
    # rather than exact equality because the count of step_* depends on the
    # shape of the DSL in the fixture.
    assert phase_names[0] == "compose_start"
    assert "compose_done" in phase_names
    assert "execute_start" in phase_names
    assert phase_names.index("compose_start") < phase_names.index("compose_done")
    assert phase_names.index("compose_done") < phase_names.index("execute_start")
    assert any(p == "step_start" for p in phase_names)
    assert any(p == "check_done" for p in phase_names)


def test_run_stream_compare_true_emits_raw_llm_frames(client: TestClient) -> None:
    """compare=True triggers RawLLMEngine; its start/done phases must
    appear in the stream and the final payload must include ``raw_llm``."""
    # compare=True needs one extra provider response (the raw-LLM JSON).
    provider = _provider_from_fixture("crm_pipeline_happy.json", extra=1)

    with (
        patch.object(routes_module, "_build_provider", return_value=provider),
        client.stream(
            "POST",
            "/playground/run-stream",
            json={
                "provider": "claude_code",
                "model": "haiku",
                "task": "Count active customers",
                "data": json.loads(_CRM_RAW),
                "expected_output": {"result": 2},
                "compare": True,
            },
        ) as resp,
    ):
        assert resp.status_code == 200
        body = "".join(chunk.decode() for chunk in resp.iter_bytes())

    phases, done, err = _parse_sse(body)
    assert err is None
    assert done is not None
    assert done.get("raw_llm") is not None
    names = [p["phase"] for p in phases]
    assert "raw_llm_start" in names
    assert "raw_llm_done" in names


def test_run_stream_provider_failure_still_closes_with_done(client: TestClient) -> None:
    """A provider that raises is caught inside ``BricksEngine.solve`` and
    surfaces as a clean ``done`` event with empty outputs — the stream
    closes normally so the frontend can render a failure state without
    seeing a hung connection.
    """

    class _BoomProvider(LLMProvider):
        def complete(self, prompt: str, system: str = "") -> CompletionResult:
            raise RuntimeError("provider is down")

    with (
        patch.object(routes_module, "_build_provider", return_value=_BoomProvider()),
        client.stream(
            "POST",
            "/playground/run-stream",
            json={
                "provider": "claude_code",
                "model": "haiku",
                "task": "whatever",
                "data": {},
            },
        ) as resp,
    ):
        assert resp.status_code == 200
        body = "".join(chunk.decode() for chunk in resp.iter_bytes())

    _, done, err = _parse_sse(body)
    assert err is None, f"unexpected SSE error frame: {err}"
    assert done is not None, "stream should close with a done event even on provider failure"
    # Empty outputs signal the failure to the frontend.
    assert done["bricks"]["outputs"] == {}
