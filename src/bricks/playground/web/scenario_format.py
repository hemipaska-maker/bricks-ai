"""Portable YAML scenario format for Bricks Benchmark.

A ScenarioDefinition describes a complete benchmark task in a single file:
what data to use, what to compute, and optionally what to expect.

The format supports three mutually exclusive data sources:

- ``data``: inline list of records (easiest for sharing)
- ``data_file``: path to a JSON file with the records
- ``dataset_id``: one of the built-in dataset IDs (e.g. ``'crm-customers'``)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScenarioDefinition:
    """A portable benchmark scenario that can be loaded from or saved to YAML.

    Attributes:
        name: Short human-readable name for this scenario.
        description: One-sentence description of what the scenario measures.
        task_text: Natural language task description passed to both engines.
        data: Inline list of records (mutually exclusive with data_file/dataset_id).
        data_file: Relative path to a JSON file containing records.
        dataset_id: ID of a built-in dataset (e.g. ``'crm-customers'``).
        expected_outputs: Optional ground-truth dict for correctness checking.
        required_bricks: Optional list of stdlib brick names expected to appear.
        model: LLM model string (default: ``'claudecode'``).
    """

    name: str
    description: str
    task_text: str
    data: list[dict[str, Any]] | None = None
    data_file: str | None = None
    dataset_id: str | None = None
    expected_outputs: dict[str, Any] | None = None
    required_bricks: list[str] = field(default_factory=list)
    model: str = "claudecode"
