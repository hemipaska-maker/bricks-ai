"""Tests for web/scenario_loader.py — load_scenario, export_scenario, round-trip."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from bricks.benchmark.web.scenario_format import ScenarioDefinition
from bricks.benchmark.web.scenario_loader import (
    export_scenario,
    load_scenario,
    scenario_to_benchmark_request,
)

# ── helpers ──────────────────────────────────────────────────────────────────

_INLINE_DATA = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]

_MINIMAL_DOC: dict[str, Any] = {
    "name": "test",
    "description": "test scenario",
    "task_text": "count items",
    "data": _INLINE_DATA,
}


def _write_yaml(tmp_path: Path, doc: dict[str, Any], filename: str = "scenario.yaml") -> Path:
    """Write a YAML doc to a temp file and return the path."""
    path = tmp_path / filename
    path.write_text(yaml.dump(doc), encoding="utf-8")
    return path


# ── load_scenario ─────────────────────────────────────────────────────────────


def test_load_scenario_inline_data(tmp_path: Path) -> None:
    """load_scenario returns ScenarioDefinition with inline data list."""
    path = _write_yaml(tmp_path, _MINIMAL_DOC)
    scenario = load_scenario(path)

    assert scenario.name == "test"
    assert scenario.description == "test scenario"
    assert scenario.task_text == "count items"
    assert scenario.data == _INLINE_DATA
    assert scenario.data_file is None
    assert scenario.dataset_id is None


def test_load_scenario_default_model(tmp_path: Path) -> None:
    """model defaults to 'claudecode' when not specified."""
    path = _write_yaml(tmp_path, _MINIMAL_DOC)
    scenario = load_scenario(path)
    assert scenario.model == "claudecode"


def test_load_scenario_explicit_model(tmp_path: Path) -> None:
    """model is read from YAML when present."""
    doc = {**_MINIMAL_DOC, "model": "gpt-4o-mini"}
    path = _write_yaml(tmp_path, doc)
    scenario = load_scenario(path)
    assert scenario.model == "gpt-4o-mini"


def test_load_scenario_with_expected_outputs(tmp_path: Path) -> None:
    """expected_outputs are loaded when present."""
    doc = {**_MINIMAL_DOC, "expected_outputs": {"count": 2, "total": 3.14}}
    path = _write_yaml(tmp_path, doc)
    scenario = load_scenario(path)
    assert scenario.expected_outputs == {"count": 2, "total": 3.14}


def test_load_scenario_expected_outputs_none_when_absent(tmp_path: Path) -> None:
    """expected_outputs is None when not in YAML."""
    path = _write_yaml(tmp_path, _MINIMAL_DOC)
    scenario = load_scenario(path)
    assert scenario.expected_outputs is None


def test_load_scenario_dataset_id_source(tmp_path: Path) -> None:
    """dataset_id data source is parsed correctly."""
    doc = {
        "name": "ds",
        "description": "uses dataset_id",
        "task_text": "filter",
        "dataset_id": "crm-customers",
    }
    path = _write_yaml(tmp_path, doc)
    scenario = load_scenario(path)
    assert scenario.dataset_id == "crm-customers"
    assert scenario.data is None
    assert scenario.data_file is None


def test_load_scenario_data_file_source(tmp_path: Path) -> None:
    """data_file data source is parsed correctly."""
    doc = {
        "name": "file-test",
        "description": "uses data_file",
        "task_text": "count",
        "data_file": "data.json",
    }
    path = _write_yaml(tmp_path, doc)
    scenario = load_scenario(path)
    assert scenario.data_file == "data.json"


def test_load_scenario_missing_task_text_raises(tmp_path: Path) -> None:
    """Missing task_text raises ValueError with clear message."""
    doc = {"name": "x", "description": "y", "data": []}
    path = _write_yaml(tmp_path, doc)
    with pytest.raises(ValueError, match="task_text"):
        load_scenario(path)


def test_load_scenario_missing_name_raises(tmp_path: Path) -> None:
    """Missing name raises ValueError."""
    doc = {"description": "y", "task_text": "z", "data": []}
    path = _write_yaml(tmp_path, doc)
    with pytest.raises(ValueError, match="name"):
        load_scenario(path)


def test_load_scenario_no_data_source_raises(tmp_path: Path) -> None:
    """Missing data source raises ValueError with clear message."""
    doc = {"name": "x", "description": "y", "task_text": "z"}
    path = _write_yaml(tmp_path, doc)
    with pytest.raises(ValueError, match="data source"):
        load_scenario(path)


def test_load_scenario_multiple_data_sources_raises(tmp_path: Path) -> None:
    """Specifying both data and dataset_id raises ValueError."""
    doc = {
        "name": "x",
        "description": "y",
        "task_text": "z",
        "data": [{"a": 1}],
        "dataset_id": "crm-customers",
    }
    path = _write_yaml(tmp_path, doc)
    with pytest.raises(ValueError, match="multiple"):
        load_scenario(path)


def test_load_scenario_invalid_yaml_raises(tmp_path: Path) -> None:
    """Malformed YAML raises ValueError (not a raw yaml.YAMLError)."""
    path = tmp_path / "bad.yaml"
    path.write_text("name: foo\ndata: [unclosed bracket\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid YAML"):
        load_scenario(path)


# ── export_scenario + round-trip ─────────────────────────────────────────────


def test_export_scenario_round_trip_inline(tmp_path: Path) -> None:
    """export_scenario then load_scenario produces equivalent ScenarioDefinition."""
    original = ScenarioDefinition(
        name="roundtrip",
        description="round-trip test",
        task_text="count items",
        data=_INLINE_DATA,
        expected_outputs={"count": 2},
        required_bricks=["filter_dict_list"],
        model="gpt-4o-mini",
    )
    out = tmp_path / "exported.yaml"
    export_scenario(original, out)
    loaded = load_scenario(out)

    assert loaded.name == original.name
    assert loaded.description == original.description
    assert loaded.task_text == original.task_text
    assert loaded.data == original.data
    assert loaded.expected_outputs == original.expected_outputs
    assert loaded.required_bricks == original.required_bricks
    assert loaded.model == original.model


def test_export_scenario_round_trip_dataset_id(tmp_path: Path) -> None:
    """export/load round-trip works for dataset_id source."""
    original = ScenarioDefinition(
        name="ds-test",
        description="dataset id test",
        task_text="filter",
        dataset_id="support-tickets",
    )
    out = tmp_path / "ds.yaml"
    export_scenario(original, out)
    loaded = load_scenario(out)
    assert loaded.dataset_id == "support-tickets"
    assert loaded.data is None
    assert loaded.data_file is None


def test_export_scenario_omits_none_fields(tmp_path: Path) -> None:
    """expected_outputs and required_bricks are absent from YAML when not set."""
    scenario = ScenarioDefinition(
        name="minimal",
        description="minimal export",
        task_text="count",
        data=[{"x": 1}],
    )
    out = tmp_path / "min.yaml"
    export_scenario(scenario, out)
    doc = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "expected_outputs" not in doc
    assert "required_bricks" not in doc


# ── scenario_to_benchmark_request ────────────────────────────────────────────


def test_scenario_to_request_inline_data(tmp_path: Path) -> None:
    """scenario_to_benchmark_request resolves inline data to JSON string."""
    scenario = ScenarioDefinition(
        name="t",
        description="d",
        task_text="count",
        data=_INLINE_DATA,
    )
    req = scenario_to_benchmark_request(scenario)
    assert req.task_text == "count"
    parsed = json.loads(req.raw_data)
    assert parsed == _INLINE_DATA


def test_scenario_to_request_data_file(tmp_path: Path) -> None:
    """scenario_to_benchmark_request resolves data_file to JSON string."""
    data = [{"key": "value"}]
    data_path = tmp_path / "data.json"
    data_path.write_text(json.dumps(data), encoding="utf-8")

    scenario = ScenarioDefinition(
        name="t",
        description="d",
        task_text="count",
        data_file="data.json",
    )
    req = scenario_to_benchmark_request(scenario, base_dir=tmp_path)
    parsed = json.loads(req.raw_data)
    assert parsed == data


def test_scenario_to_request_dataset_id(tmp_path: Path) -> None:
    """scenario_to_benchmark_request resolves dataset_id to JSON string."""
    scenario = ScenarioDefinition(
        name="t",
        description="d",
        task_text="count",
        dataset_id="crm-customers",
    )
    req = scenario_to_benchmark_request(scenario)
    parsed = json.loads(req.raw_data)
    assert isinstance(parsed, list)
    assert len(parsed) > 0


def test_scenario_to_request_expected_outputs_passed(tmp_path: Path) -> None:
    """expected_outputs forwarded to BenchmarkRequest."""
    scenario = ScenarioDefinition(
        name="t",
        description="d",
        task_text="count",
        data=[{"x": 1}],
        expected_outputs={"count": 1},
    )
    req = scenario_to_benchmark_request(scenario)
    assert req.expected_outputs == {"count": 1}


def test_scenario_to_request_missing_data_file_raises(tmp_path: Path) -> None:
    """ValueError raised when data_file does not exist."""
    scenario = ScenarioDefinition(
        name="t",
        description="d",
        task_text="count",
        data_file="nonexistent.json",
    )
    with pytest.raises(ValueError, match="not found"):
        scenario_to_benchmark_request(scenario, base_dir=tmp_path)
