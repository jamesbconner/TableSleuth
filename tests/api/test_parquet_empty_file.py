"""Tests for Parquet sample endpoint with empty files."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; run with --extra web")
pytest.importorskip("httpx", reason="httpx not installed; run with --extra web")

from fastapi.testclient import TestClient  # noqa: E402

from tablesleuth.api.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def test_sample_empty_parquet_file() -> None:
    """Test that /parquet/sample handles empty Parquet files gracefully."""
    with TemporaryDirectory() as tmpdir:
        # Create an empty Parquet file with schema but no rows
        schema = pa.schema([("id", pa.int64()), ("name", pa.string())])
        empty_table = pa.Table.from_pydict({"id": [], "name": []}, schema=schema)

        file_path = Path(tmpdir) / "empty.parquet"
        pq.write_table(empty_table, file_path)

        # Request sample from empty file
        response = client.post(
            "/api/parquet/sample", json={"path": str(file_path), "num_rows": 100}
        )

        assert response.status_code == 200
        data = response.json()

        # Should return empty sample with schema
        assert data["columns"] == ["id", "name"]
        assert data["rows"] == []
        assert data["total_rows_in_file"] == 0
        assert data["sampled_rows"] == 0


def test_sample_parquet_file_with_rows() -> None:
    """Test that /parquet/sample still works correctly with non-empty files."""
    with TemporaryDirectory() as tmpdir:
        # Create a Parquet file with data
        schema = pa.schema([("id", pa.int64()), ("name", pa.string())])
        table = pa.Table.from_pydict(
            {"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]}, schema=schema
        )

        file_path = Path(tmpdir) / "data.parquet"
        pq.write_table(table, file_path)

        # Request sample
        response = client.post("/api/parquet/sample", json={"path": str(file_path), "num_rows": 3})

        assert response.status_code == 200
        data = response.json()

        # Should return first 3 rows
        assert data["columns"] == ["id", "name"]
        assert len(data["rows"]) == 3
        assert data["rows"][0] == [1, "a"]
        assert data["rows"][1] == [2, "b"]
        assert data["rows"][2] == [3, "c"]
        assert data["total_rows_in_file"] == 5
        assert data["sampled_rows"] == 3


def test_sample_parquet_file_fewer_rows_than_requested() -> None:
    """Test sampling when file has fewer rows than requested."""
    with TemporaryDirectory() as tmpdir:
        # Create a small Parquet file
        schema = pa.schema([("value", pa.int64())])
        table = pa.Table.from_pydict({"value": [1, 2]}, schema=schema)

        file_path = Path(tmpdir) / "small.parquet"
        pq.write_table(table, file_path)

        # Request more rows than available
        response = client.post(
            "/api/parquet/sample", json={"path": str(file_path), "num_rows": 100}
        )

        assert response.status_code == 200
        data = response.json()

        # Should return all available rows
        assert data["columns"] == ["value"]
        assert len(data["rows"]) == 2
        assert data["total_rows_in_file"] == 2
        assert data["sampled_rows"] == 2
