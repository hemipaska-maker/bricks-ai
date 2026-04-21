"""Tests for bricks.playground.web.datasets."""

from __future__ import annotations

import json

import pytest

from bricks.playground.web.datasets import DatasetLoader, _summarise_data


class TestSummariseData:
    """Tests for the _summarise_data helper."""

    def test_list_data_count_and_preview(self) -> None:
        """List data: row_count = len, preview = first 3."""
        data = [{"a": i} for i in range(10)]
        count, preview = _summarise_data(data)
        assert count == 10
        assert preview == [{"a": 0}, {"a": 1}, {"a": 2}]

    def test_list_data_shorter_than_three(self) -> None:
        """List data shorter than 3 rows: preview = all rows."""
        data = [{"x": 1}, {"x": 2}]
        count, preview = _summarise_data(data)
        assert count == 2
        assert preview == [{"x": 1}, {"x": 2}]

    def test_dict_data_totals_and_preview(self) -> None:
        """Dict data: total = sum of all list lengths, preview = first 3 of first list."""
        data = {"orders": [{"id": i} for i in range(5)], "customers": [{"id": i} for i in range(3)]}
        count, preview = _summarise_data(data)
        assert count == 8
        assert len(preview) == 3

    def test_empty_list(self) -> None:
        """Empty list: count = 0, preview = []."""
        count, preview = _summarise_data([])
        assert count == 0
        assert preview == []


class TestDatasetLoader:
    """Tests for DatasetLoader reading real dataset files."""

    @pytest.fixture
    def loader(self) -> DatasetLoader:
        """Create a DatasetLoader instance."""
        return DatasetLoader()

    def test_loads_three_datasets(self, loader: DatasetLoader) -> None:
        """DatasetLoader loads exactly 3 built-in datasets."""
        datasets = loader.list_datasets()
        assert len(datasets) == 3

    def test_dataset_ids_present(self, loader: DatasetLoader) -> None:
        """All expected dataset IDs are present."""
        ids = {ds["id"] for ds in loader.list_datasets()}
        assert "crm-customers" in ids
        assert "support-tickets" in ids
        assert "orders-customers" in ids

    def test_preview_has_at_most_three_rows(self, loader: DatasetLoader) -> None:
        """Each dataset preview contains at most 3 rows."""
        for ds in loader.list_datasets():
            assert len(ds["preview"]) <= 3

    def test_full_data_is_valid_json(self, loader: DatasetLoader) -> None:
        """Each dataset's full_data field is valid JSON."""
        for ds in loader.list_datasets():
            parsed = json.loads(ds["full_data"])
            assert parsed is not None

    def test_crm_dataset_has_expected_fields(self, loader: DatasetLoader) -> None:
        """CRM dataset has the expected field list."""
        ds = loader.get_dataset("crm-customers")
        assert ds is not None
        assert "id" in ds["fields"]
        assert "status" in ds["fields"]
        assert "monthly_revenue" in ds["fields"]

    def test_crm_dataset_row_count(self, loader: DatasetLoader) -> None:
        """CRM dataset has 25 records."""
        ds = loader.get_dataset("crm-customers")
        assert ds is not None
        assert len(ds["data"]) == 25

    def test_ticket_dataset_row_count(self, loader: DatasetLoader) -> None:
        """Support tickets dataset has 100 records."""
        ds = loader.get_dataset("support-tickets")
        assert ds is not None
        assert len(ds["data"]) == 100

    def test_get_dataset_unknown_id_returns_none(self, loader: DatasetLoader) -> None:
        """get_dataset returns None for an unknown dataset ID."""
        assert loader.get_dataset("nonexistent-id") is None

    def test_dataset_has_all_required_keys(self, loader: DatasetLoader) -> None:
        """Each dataset dict has all required keys for the API response."""
        required = {"id", "name", "description", "row_count", "fields", "preview", "full_data"}
        for ds in loader.list_datasets():
            assert required.issubset(ds.keys())
