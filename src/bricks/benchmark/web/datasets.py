"""Dataset loader for the Bricks Benchmark web API.

Loads built-in datasets from the ``web/datasets/`` directory and serves them
via the ``/api/datasets`` endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATASETS_DIR = Path(__file__).parent / "datasets"


def _summarise_data(data: Any) -> tuple[int, list[Any]]:
    """Return (row_count, preview) for list or multi-table dict data.

    Args:
        data: Either a list of records or a dict of table-name → list.

    Returns:
        Tuple of total row count and first 3 rows of the primary table.
    """
    if isinstance(data, list):
        return len(data), data[:3]
    if isinstance(data, dict):
        first_list = next((v for v in data.values() if isinstance(v, list)), [])
        total = sum(len(v) for v in data.values() if isinstance(v, list))
        return total, first_list[:3]
    return 0, []


class DatasetLoader:
    """Loads and serves built-in benchmark datasets from JSON files.

    Each dataset file contains an ``id``, ``name``, ``description``, ``fields``,
    and ``data`` (list of records).
    """

    def __init__(self) -> None:
        """Load all dataset JSON files from the datasets directory."""
        self._datasets: dict[str, dict[str, Any]] = {}
        for path in sorted(_DATASETS_DIR.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._datasets[raw["id"]] = raw

    def list_datasets(self) -> list[dict[str, Any]]:
        """Return all datasets with preview (first 3 rows) and full data JSON string.

        Supports both list data (``data: [...]``) and multi-table data
        (``data: {"table": [...], ...}``).

        Returns:
            List of dataset dicts, each with:
            ``id``, ``name``, ``description``, ``row_count``, ``fields``,
            ``preview`` (first 3 rows of primary table), ``full_data`` (full JSON string).
        """
        result: list[dict[str, Any]] = []
        for ds in self._datasets.values():
            data = ds["data"]
            row_count, preview = _summarise_data(data)
            result.append(
                {
                    "id": ds["id"],
                    "name": ds["name"],
                    "description": ds["description"],
                    "row_count": row_count,
                    "fields": ds["fields"],
                    "preview": preview,
                    "full_data": json.dumps(data),
                }
            )
        return result

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Return a single dataset by ID, or None if not found.

        Args:
            dataset_id: The dataset identifier (e.g. ``'crm-customers'``).

        Returns:
            Dataset dict with full data, or ``None`` if the ID is unknown.
        """
        return self._datasets.get(dataset_id)
