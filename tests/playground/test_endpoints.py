"""Happy-path + failure tests for the ``/playground`` FastAPI routes."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from bricks.playground.web.app import app


@pytest.fixture(name="client")
def _client() -> TestClient:
    return TestClient(app)


# ── scenarios ────────────────────────────────────────────────────────────────


def test_list_scenarios_returns_presets(client: TestClient) -> None:
    r = client.get("/playground/scenarios")
    assert r.status_code == 200
    payload = r.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    ids = {s["id"] for s in payload}
    assert "crm-pipeline" in ids
    sample = next(s for s in payload if s["id"] == "crm-pipeline")
    assert sample["name"]
    assert sample["description"]


def test_get_scenario_happy_path(client: TestClient) -> None:
    r = client.get("/playground/scenarios/crm-pipeline")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "crm-pipeline"
    assert body.get("task")
    assert body["expected_output"] is not None


def test_get_scenario_accepts_underscore_id(client: TestClient) -> None:
    """Scenario IDs are normalised — ``crm_pipeline`` also resolves."""
    r = client.get("/playground/scenarios/crm_pipeline")
    assert r.status_code == 200


def test_get_scenario_unknown_returns_404(client: TestClient) -> None:
    r = client.get("/playground/scenarios/does-not-exist")
    assert r.status_code == 404


# ── upload ───────────────────────────────────────────────────────────────────


def test_upload_csv_parses_to_dicts(client: TestClient) -> None:
    csv_body = "id,name\n1,Alice\n2,Bob\n"
    r = client.post("/playground/upload", files={"file": ("t.csv", csv_body, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["row_count"] == 2
    assert body["data"] == [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
    assert body["filename"] == "t.csv"


def test_upload_json_list_counts_rows(client: TestClient) -> None:
    payload = [{"a": 1}, {"a": 2}, {"a": 3}]
    r = client.post(
        "/playground/upload",
        files={"file": ("t.json", json.dumps(payload), "application/json")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["row_count"] == 3
    assert body["data"] == payload


def test_upload_json_object_has_no_row_count(client: TestClient) -> None:
    r = client.post(
        "/playground/upload",
        files={"file": ("t.json", json.dumps({"a": 1}), "application/json")},
    )
    assert r.status_code == 200
    assert r.json()["row_count"] is None


def test_upload_rejects_over_5_mb(client: TestClient) -> None:
    big = "x" * (6 * 1024 * 1024)
    r = client.post("/playground/upload", files={"file": ("big.json", big, "application/json")})
    assert r.status_code == 413


def test_upload_rejects_malformed_json(client: TestClient) -> None:
    r = client.post("/playground/upload", files={"file": ("t.json", "{not-json", "application/json")})
    assert r.status_code == 400


# ── run ──────────────────────────────────────────────────────────────────────


def test_run_anthropic_without_key_returns_400(client: TestClient) -> None:
    """BYOK enforcement: no api_key → 400 Bad Request."""
    r = client.post(
        "/playground/run",
        json={
            "provider": "anthropic",
            "model": "claude-haiku-4-5",
            "task": "count items",
            "data": [{"a": 1}],
        },
    )
    assert r.status_code == 400
    assert "api_key" in r.json()["detail"].lower()


def test_run_anthropic_with_key_returns_501_until_issue_44(client: TestClient) -> None:
    """Until #44 lands, Anthropic / OpenAI / Ollama return 501 with a pointer."""
    r = client.post(
        "/playground/run",
        json={
            "provider": "anthropic",
            "model": "claude-haiku-4-5",
            "api_key": "sk-fake",
            "task": "t",
            "data": [{}],
        },
    )
    assert r.status_code == 501
    assert "#44" in r.json()["detail"]


def test_run_ollama_returns_501_until_issue_44(client: TestClient) -> None:
    r = client.post(
        "/playground/run",
        json={"provider": "ollama", "model": "llama3", "task": "t", "data": [{}]},
    )
    assert r.status_code == 501


def test_run_rejects_unknown_provider(client: TestClient) -> None:
    r = client.post(
        "/playground/run",
        json={"provider": "unknown", "model": "x", "task": "t", "data": []},
    )
    # Pydantic Literal validation → 422.
    assert r.status_code == 422
