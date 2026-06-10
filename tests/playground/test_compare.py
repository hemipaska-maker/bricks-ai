"""Compare-toggle behaviour for ``POST /playground/run`` (design.md §6)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bricks_ai.playground.web.app import app


@pytest.fixture(name="client")
def _client() -> TestClient:
    return TestClient(app)


def _stub_result(text: str = "ok") -> Any:
    """Stand-in for a ``showcase.engine.EngineResult``."""
    return SimpleNamespace(
        outputs={"value": 1},
        raw_response=text,
        tokens_in=5,
        tokens_out=3,
        duration_seconds=0.1,
        model="claude-haiku-4-5",
        error="",
    )


def test_compare_false_skips_raw_llm(client: TestClient) -> None:
    """``compare=false`` (default) must not instantiate ``RawLLMEngine``."""
    bricks_solve = lambda *a, **kw: _stub_result("bricks")  # noqa: E731
    raw_init = lambda *a, **kw: pytest.fail("RawLLMEngine must not be constructed when compare=False")  # noqa: E731

    with (
        patch("bricks_ai.playground.engine.BricksEngine.solve", new=bricks_solve),
        patch("bricks_ai.playground.engine.RawLLMEngine.__init__", new=raw_init),
        patch("bricks_ai.playground.web.routes._build_provider", return_value=object()),
    ):
        r = client.post(
            "/playground/run",
            json={
                "provider": "claude_code",
                "model": "haiku",
                "task": "t",
                "data": [{"x": 1}],
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert "bricks" in body
    assert "raw_llm" not in body  # omitted entirely when compare is False


def test_compare_true_invokes_both_engines(client: TestClient) -> None:
    """``compare=true`` must call both engines and include ``raw_llm`` in the response."""
    called: dict[str, int] = {"bricks": 0, "raw": 0}

    def bricks_solve(self: Any, task: str, data: str) -> Any:
        called["bricks"] += 1
        return _stub_result("bricks-result")

    def raw_solve(self: Any, task: str, data: str) -> Any:
        called["raw"] += 1
        return _stub_result("raw-result")

    with (
        patch("bricks_ai.playground.engine.BricksEngine.solve", new=bricks_solve),
        patch("bricks_ai.playground.engine.RawLLMEngine.solve", new=raw_solve),
        patch("bricks_ai.playground.web.routes._build_provider", return_value=object()),
    ):
        r = client.post(
            "/playground/run",
            json={
                "provider": "claude_code",
                "model": "haiku",
                "task": "t",
                "data": [{"x": 1}],
                "compare": True,
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert called == {"bricks": 1, "raw": 1}
    assert "bricks" in body
    assert body.get("raw_llm") is not None
    # The raw_llm branch reports the raw response verbatim (no blueprint yaml).
    assert body["raw_llm"].get("response") == "raw-result"
    assert body["raw_llm"].get("blueprint_yaml") is None
    # Bricks branch reports the yaml, not a raw response.
    assert body["bricks"].get("blueprint_yaml") == "bricks-result"
    assert body["bricks"].get("response") is None


def test_compare_true_runs_checks_on_both_engines(client: TestClient) -> None:
    """With ``expected_output`` set, both branches populate ``checks``."""

    def bricks_solve(self: Any, task: str, data: str) -> Any:
        return SimpleNamespace(
            outputs={"count": 3},
            raw_response="b",
            tokens_in=1,
            tokens_out=1,
            duration_seconds=0.0,
            model="m",
            error="",
        )

    def raw_solve(self: Any, task: str, data: str) -> Any:
        return SimpleNamespace(
            outputs={"count": 99},
            raw_response="r",
            tokens_in=1,
            tokens_out=1,
            duration_seconds=0.0,
            model="m",
            error="",
        )

    with (
        patch("bricks_ai.playground.engine.BricksEngine.solve", new=bricks_solve),
        patch("bricks_ai.playground.engine.RawLLMEngine.solve", new=raw_solve),
        patch("bricks_ai.playground.web.routes._build_provider", return_value=object()),
    ):
        r = client.post(
            "/playground/run",
            json={
                "provider": "claude_code",
                "model": "haiku",
                "task": "t",
                "data": [{}],
                "expected_output": {"count": 3},
                "compare": True,
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["bricks"]["checks"] == [{"key": "count", "expected": 3, "got": 3, "pass": True}]
    assert body["raw_llm"]["checks"] == [{"key": "count", "expected": 3, "got": 99, "pass": False}]
