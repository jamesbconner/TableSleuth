"""Tests for Parquet sample endpoint serialization of complex types."""

from decimal import Decimal
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


def test_sample_parquet_with_decimal_columns() -> None:
    """Test that Parquet files with Decimal columns are serialized correctly."""
    with TemporaryDirectory() as tmpdir:
        # Create a Parquet file with Decimal column
        schema = pa.schema([("id", pa.int64()), ("price", pa.decimal128(10, 2))])
        table = pa.Table.from_pydict(
            {
                "id": [1, 2, 3],
                "price": [Decimal("19.99"), Decimal("29.99"), Decimal("39.99")],
            },
            schema=schema,
        )

        file_path = Path(tmpdir) / "decimal_data.parquet"
        pq.write_table(table, file_path)

        # Request sample
        response = client.post("/api/parquet/sample", json={"path": str(file_path), "num_rows": 10})

        assert response.status_code == 200
        data = response.json()

        # Decimals should be serialized as strings
        assert data["columns"] == ["id", "price"]
        assert len(data["rows"]) == 3
        assert data["rows"][0] == [1, "19.99"]
        assert data["rows"][1] == [2, "29.99"]
        assert data["rows"][2] == [3, "39.99"]


def test_sample_parquet_with_binary_columns() -> None:
    """Test that Parquet files with binary columns are serialized correctly."""
    with TemporaryDirectory() as tmpdir:
        # Create a Parquet file with binary column
        schema = pa.schema([("id", pa.int64()), ("data", pa.binary())])
        table = pa.Table.from_pydict({"id": [1, 2], "data": [b"hello", b"world"]}, schema=schema)

        file_path = Path(tmpdir) / "binary_data.parquet"
        pq.write_table(table, file_path)

        # Request sample
        response = client.post("/api/parquet/sample", json={"path": str(file_path), "num_rows": 10})

        assert response.status_code == 200
        data = response.json()

        # Binary data should be serialized as strings
        assert data["columns"] == ["id", "data"]
        assert len(data["rows"]) == 2
        # Binary values are converted to string representation
        assert isinstance(data["rows"][0][1], str)
        assert isinstance(data["rows"][1][1], str)


def test_sample_parquet_with_date_columns() -> None:
    """Test that Parquet files with date columns are serialized correctly."""
    with TemporaryDirectory() as tmpdir:
        # Create a Parquet file with date column
        from datetime import date

        schema = pa.schema([("id", pa.int64()), ("created_date", pa.date32())])
        table = pa.Table.from_pydict(
            {"id": [1, 2], "created_date": [date(2024, 1, 1), date(2024, 12, 31)]}, schema=schema
        )

        file_path = Path(tmpdir) / "date_data.parquet"
        pq.write_table(table, file_path)

        # Request sample
        response = client.post("/api/parquet/sample", json={"path": str(file_path), "num_rows": 10})

        assert response.status_code == 200
        data = response.json()

        # Dates should be serialized as strings
        assert data["columns"] == ["id", "created_date"]
        assert len(data["rows"]) == 2
        assert isinstance(data["rows"][0][1], str)
        assert isinstance(data["rows"][1][1], str)


def test_sample_parquet_with_timestamp_columns() -> None:
    """Test that Parquet files with timestamp columns are serialized correctly."""
    with TemporaryDirectory() as tmpdir:
        # Create a Parquet file with timestamp column
        from datetime import datetime

        schema = pa.schema([("id", pa.int64()), ("timestamp", pa.timestamp("us"))])
        table = pa.Table.from_pydict(
            {
                "id": [1, 2],
                "timestamp": [datetime(2024, 1, 1, 12, 0, 0), datetime(2024, 12, 31, 23, 59, 59)],
            },
            schema=schema,
        )

        file_path = Path(tmpdir) / "timestamp_data.parquet"
        pq.write_table(table, file_path)

        # Request sample
        response = client.post("/api/parquet/sample", json={"path": str(file_path), "num_rows": 10})

        assert response.status_code == 200
        data = response.json()

        # Timestamps should be serialized as strings
        assert data["columns"] == ["id", "timestamp"]
        assert len(data["rows"]) == 2
        assert isinstance(data["rows"][0][1], str)
        assert isinstance(data["rows"][1][1], str)


def test_sample_parquet_with_mixed_types() -> None:
    """Test that Parquet files with mixed column types are serialized correctly."""
    with TemporaryDirectory() as tmpdir:
        # Create a Parquet file with various column types
        schema = pa.schema(
            [
                ("int_col", pa.int64()),
                ("float_col", pa.float64()),
                ("string_col", pa.string()),
                ("bool_col", pa.bool_()),
                ("decimal_col", pa.decimal128(10, 2)),
            ]
        )
        table = pa.Table.from_pydict(
            {
                "int_col": [1, 2],
                "float_col": [1.5, 2.5],
                "string_col": ["a", "b"],
                "bool_col": [True, False],
                "decimal_col": [Decimal("10.50"), Decimal("20.75")],
            },
            schema=schema,
        )

        file_path = Path(tmpdir) / "mixed_data.parquet"
        pq.write_table(table, file_path)

        # Request sample
        response = client.post("/api/parquet/sample", json={"path": str(file_path), "num_rows": 10})

        assert response.status_code == 200
        data = response.json()

        # Check that all types are properly serialized
        assert data["columns"] == ["int_col", "float_col", "string_col", "bool_col", "decimal_col"]
        assert len(data["rows"]) == 2

        # Primitives should remain as-is
        assert data["rows"][0][0] == 1  # int
        assert data["rows"][0][1] == 1.5  # float
        assert data["rows"][0][2] == "a"  # string
        assert data["rows"][0][3] is True  # bool

        # Decimal should be serialized as string
        assert data["rows"][0][4] == "10.50"
        assert data["rows"][1][4] == "20.75"


def test_sample_parquet_with_null_values() -> None:
    """Test that null values are preserved correctly."""
    with TemporaryDirectory() as tmpdir:
        # Create a Parquet file with null values
        schema = pa.schema([("id", pa.int64()), ("value", pa.decimal128(10, 2))])
        table = pa.Table.from_pydict(
            {"id": [1, 2, 3], "value": [Decimal("10.00"), None, Decimal("30.00")]}, schema=schema
        )

        file_path = Path(tmpdir) / "null_data.parquet"
        pq.write_table(table, file_path)

        # Request sample
        response = client.post("/api/parquet/sample", json={"path": str(file_path), "num_rows": 10})

        assert response.status_code == 200
        data = response.json()

        # Null values should remain as None (null in JSON)
        assert data["rows"][0] == [1, "10.00"]
        assert data["rows"][1] == [2, None]
        assert data["rows"][2] == [3, "30.00"]
