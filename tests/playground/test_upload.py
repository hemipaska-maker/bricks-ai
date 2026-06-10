"""Extra upload-path coverage for ``POST /playground/upload``."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from bricks_ai.playground.web.app import app


@pytest.fixture(name="client")
def _client() -> TestClient:
    return TestClient(app)


def test_csv_with_100_rows_parses_cleanly(client: TestClient) -> None:
    """Design.md §11 acceptance: 100-row CSV uploads + previews correctly."""
    header = "id,name,value"
    rows = [f"{i},item-{i},{i * 3.5}" for i in range(1, 101)]
    body = "\n".join([header, *rows])
    r = client.post("/playground/upload", files={"file": ("big.csv", body, "text/csv")})
    assert r.status_code == 200
    payload = r.json()
    assert payload["row_count"] == 100
    assert payload["data"][0] == {"id": "1", "name": "item-1", "value": "3.5"}
    assert payload["data"][-1]["id"] == "100"


def test_csv_with_bom_is_accepted(client: TestClient) -> None:
    """UTF-8 BOM on CSVs (Excel export) should not break parsing."""
    body = "\ufeffid,name\n1,Alice\n"
    r = client.post("/playground/upload", files={"file": ("bom.csv", body.encode("utf-8"), "text/csv")})
    assert r.status_code == 200
    assert r.json()["data"] == [{"id": "1", "name": "Alice"}]


def test_json_dict_has_row_count_none(client: TestClient) -> None:
    r = client.post(
        "/playground/upload",
        files={"file": ("t.json", json.dumps({"a": 1, "b": 2}), "application/json")},
    )
    assert r.status_code == 200
    assert r.json()["row_count"] is None


def test_json_nested_list_row_count(client: TestClient) -> None:
    payload = [{"rows": [1, 2]}, {"rows": [3, 4]}, {"rows": [5, 6]}]
    r = client.post(
        "/playground/upload",
        files={"file": ("nested.json", json.dumps(payload), "application/json")},
    )
    assert r.status_code == 200
    assert r.json()["row_count"] == 3


def test_oversize_5mb_is_rejected(client: TestClient) -> None:
    big = "x" * (5 * 1024 * 1024 + 1)
    r = client.post("/playground/upload", files={"file": ("big.json", big, "application/json")})
    assert r.status_code == 413
    assert "5 MB" in r.json()["detail"]


def test_malformed_json_returns_400(client: TestClient) -> None:
    r = client.post("/playground/upload", files={"file": ("bad.json", "{not-json", "application/json")})
    assert r.status_code == 400
