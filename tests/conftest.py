"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory) -> Path:
    """Create a temporary directory for test data."""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture(scope="session")
def sample_parquet_file(test_data_dir: Path) -> Path:
    """Create a simple test Parquet file."""
    # Create sample data
    data = {
        "id": list(range(1, 101)),
        "name": [f"user_{i}" for i in range(1, 101)],
        "age": [20 + (i % 50) for i in range(100)],
        "score": [float(i * 1.5) for i in range(100)],
        "active": [i % 2 == 0 for i in range(100)],
    }

    df = pd.DataFrame(data)

    # Write to parquet with multiple row groups
    file_path = test_data_dir / "sample.parquet"
    df.to_parquet(file_path, engine="pyarrow", row_group_size=25)

    return file_path


@pytest.fixture(scope="session")
def nested_parquet_file(test_data_dir: Path) -> Path:
    """Create a Parquet file with nested/complex types."""
    # Create data with nested structures
    data = {
        "id": list(range(1, 51)),
        "user": [{"name": f"user_{i}", "email": f"user{i}@example.com"} for i in range(1, 51)],
        "scores": [[i, i * 2, i * 3] for i in range(1, 51)],
        "metadata": [
            {"created": f"2024-01-{i:02d}", "updated": f"2024-02-{i:02d}"} for i in range(1, 51)
        ],
    }

    # Create PyArrow schema with nested types
    schema = pa.schema(
        [
            ("id", pa.int64()),
            (
                "user",
                pa.struct(
                    [
                        ("name", pa.string()),
                        ("email", pa.string()),
                    ]
                ),
            ),
            ("scores", pa.list_(pa.int64())),
            (
                "metadata",
                pa.struct(
                    [
                        ("created", pa.string()),
                        ("updated", pa.string()),
                    ]
                ),
            ),
        ]
    )

    # Convert to PyArrow table
    table = pa.Table.from_pydict(data, schema=schema)

    # Write to parquet
    file_path = test_data_dir / "nested.parquet"
    pq.write_table(table, file_path, row_group_size=10)

    return file_path


@pytest.fixture(scope="session")
def multi_file_directory(
    test_data_dir: Path, sample_parquet_file: Path, nested_parquet_file: Path
) -> Path:
    """Create a directory with multiple Parquet files."""
    multi_dir = test_data_dir / "multi_files"
    multi_dir.mkdir(exist_ok=True)

    # Create a few more files
    for i in range(3):
        data = {
            "id": list(range(i * 10, (i + 1) * 10)),
            "value": [float(j) for j in range(i * 10, (i + 1) * 10)],
        }
        df = pd.DataFrame(data)
        df.to_parquet(multi_dir / f"file_{i}.parquet", engine="pyarrow")

    return multi_dir
