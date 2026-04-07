"""Load, convert, and export benchmark scenarios from/to YAML files.

Functions
---------
load_scenario(path)
    Parse a YAML scenario file into a ScenarioDefinition.
scenario_to_benchmark_request(scenario)
    Convert a ScenarioDefinition to a BenchmarkRequest for the web API.
export_scenario(scenario, path)
    Write a ScenarioDefinition back to a YAML file (round-trip safe).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from bricks_benchmark.web.scenario_format import ScenarioDefinition
from bricks_benchmark.web.schemas import BenchmarkRequest

# Required keys every valid scenario YAML must contain.
_REQUIRED_KEYS = ("name", "description", "task_text")


def load_scenario(path: Path) -> ScenarioDefinition:
    """Parse a YAML scenario file into a ScenarioDefinition.

    Validates that required keys are present and exactly one data source is
    specified (``data``, ``data_file``, or ``dataset_id``).

    Args:
        path: Absolute or relative path to the ``.yaml`` file.

    Returns:
        Populated ScenarioDefinition.

    Raises:
        ValueError: If the file is missing required keys, contains invalid YAML,
            or specifies zero or multiple data sources.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Scenario {path.name!r}: invalid YAML — {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Scenario {path.name!r}: top-level must be a YAML mapping, got {type(raw).__name__}")

    for key in _REQUIRED_KEYS:
        if not raw.get(key):
            raise ValueError(f"Scenario {path.name!r}: missing required key {key!r}")

    data_sources = [k for k in ("data", "data_file", "dataset_id") if raw.get(k)]
    if not data_sources:
        raise ValueError(
            f"Scenario {path.name!r}: must specify exactly one data source "
            "('data', 'data_file', or 'dataset_id') — none found"
        )
    if len(data_sources) > 1:
        raise ValueError(f"Scenario {path.name!r}: only one data source allowed, but found multiple: {data_sources!r}")

    return ScenarioDefinition(
        name=raw["name"],
        description=raw["description"],
        task_text=raw["task_text"],
        data=raw.get("data"),
        data_file=raw.get("data_file"),
        dataset_id=raw.get("dataset_id"),
        expected_outputs=raw.get("expected_outputs"),
        required_bricks=raw.get("required_bricks") or [],
        model=raw.get("model", "claudecode"),
    )


def _resolve_raw_data(scenario: ScenarioDefinition, base_dir: Path | None = None) -> str:
    """Return the JSON string for the scenario's data source.

    Args:
        scenario: The scenario to resolve data for.
        base_dir: Directory to resolve relative ``data_file`` paths against.
            Defaults to the current working directory.

    Returns:
        JSON-encoded string of the dataset records.

    Raises:
        ValueError: If the data source cannot be resolved.
    """
    if scenario.data is not None:
        return json.dumps(scenario.data)

    if scenario.data_file is not None:
        ref = Path(scenario.data_file)
        if not ref.is_absolute() and base_dir is not None:
            ref = base_dir / ref
        if not ref.exists():
            raise ValueError(f"data_file {scenario.data_file!r} not found at {ref}")
        return ref.read_text(encoding="utf-8")

    if scenario.dataset_id is not None:
        from bricks_benchmark.web.datasets import DatasetLoader

        loader = DatasetLoader()
        ds = loader.get_dataset(scenario.dataset_id)
        if ds is None:
            raise ValueError(f"dataset_id {scenario.dataset_id!r} not found in built-in datasets")
        return json.dumps(ds["data"])

    raise ValueError("ScenarioDefinition has no data source (data, data_file, or dataset_id)")


def scenario_to_benchmark_request(
    scenario: ScenarioDefinition,
    base_dir: Path | None = None,
) -> BenchmarkRequest:
    """Convert a ScenarioDefinition to a BenchmarkRequest for the web API.

    Resolves the data source (inline data, file reference, or built-in dataset)
    into a JSON string suitable for ``POST /api/run``.

    Args:
        scenario: The loaded scenario.
        base_dir: Directory to resolve relative ``data_file`` paths against.

    Returns:
        BenchmarkRequest ready to pass to the ``/api/run`` endpoint.

    Raises:
        ValueError: If the data source cannot be resolved.
    """
    raw_data = _resolve_raw_data(scenario, base_dir=base_dir)
    return BenchmarkRequest(
        task_text=scenario.task_text,
        raw_data=raw_data,
        expected_outputs=scenario.expected_outputs,
        required_bricks=scenario.required_bricks or None,
        model=scenario.model,
    )


def export_scenario(scenario: ScenarioDefinition, path: Path) -> None:
    """Write a ScenarioDefinition to a YAML file.

    The output is round-trip safe: loading the written file produces an
    equivalent ScenarioDefinition.

    Args:
        scenario: The scenario to serialise.
        path: Destination file path. Parent directories must exist.
    """
    doc: dict[str, Any] = {
        "name": scenario.name,
        "description": scenario.description,
        "task_text": scenario.task_text,
        "model": scenario.model,
    }

    if scenario.data is not None:
        doc["data"] = scenario.data
    elif scenario.data_file is not None:
        doc["data_file"] = scenario.data_file
    elif scenario.dataset_id is not None:
        doc["dataset_id"] = scenario.dataset_id

    if scenario.expected_outputs is not None:
        doc["expected_outputs"] = scenario.expected_outputs

    if scenario.required_bricks:
        doc["required_bricks"] = scenario.required_bricks

    path.write_text(yaml.dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
