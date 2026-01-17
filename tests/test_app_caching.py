"""Tests for caching functionality in TUI app."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.models import TableHandle
from tablesleuth.models.file_ref import FileRef
from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo, RowGroupInfo
from tablesleuth.models.profiling import ColumnProfile
from tablesleuth.services.formats.iceberg import IcebergAdapter
from tablesleuth.tui.app import TableSleuthApp


@pytest.fixture
def app_config() -> AppConfig:
    """Create test app configuration."""
    return AppConfig(
        catalog=CatalogConfig(default=None),
        gizmosql=GizmoConfig(),
    )


@pytest.fixture
def table_handle() -> TableHandle:
    """Create test table handle."""
    return TableHandle(native=None, format_name="parquet")


@pytest.fixture
def adapter() -> IcebergAdapter:
    """Create test adapter."""
    return IcebergAdapter(default_catalog=None)


@pytest.fixture
def sample_file_info() -> ParquetFileInfo:
    """Create sample ParquetFileInfo for testing."""
    columns = [
        ColumnStats(
            name="id",
            physical_type="INT64",
            logical_type="INT64",
            null_count=0,
            min_value=1,
            max_value=100,
            encodings=["PLAIN"],
            compression="SNAPPY",
            num_values=None,
            distinct_count=None,
            total_compressed_size=None,
            total_uncompressed_size=None,
        ),
    ]

    row_groups = [
        RowGroupInfo(
            index=0,
            num_rows=100,
            total_byte_size=512,
            columns=columns,
        )
    ]

    return ParquetFileInfo(
        path="tests/data/test.parquet",
        file_size_bytes=1024,
        num_rows=100,
        num_row_groups=1,
        num_columns=1,
        schema={"id": {"type": "int64", "nullable": False}},
        row_groups=row_groups,
        columns=columns,
        created_by="test",
        format_version="2.0",
    )


@pytest.fixture
def sample_profile() -> ColumnProfile:
    """Create sample ColumnProfile for testing."""
    return ColumnProfile(
        column="id",
        row_count=100,
        non_null_count=100,
        null_count=0,
        distinct_count=100,
        min_value=1,
        max_value=100,
    )


def test_cache_initialization(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that caches are initialized."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert hasattr(app, "_file_metadata_cache")
    assert hasattr(app, "_profile_cache")
    assert isinstance(app._file_metadata_cache, dict)
    assert isinstance(app._profile_cache, dict)
    assert len(app._file_metadata_cache) == 0
    assert len(app._profile_cache) == 0


def test_cache_stats_empty(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test cache stats with empty caches."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    stats = app.get_cache_stats()
    assert stats["metadata_entries"] == 0
    assert stats["profile_entries"] == 0


def test_metadata_cache_storage(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_file_info: ParquetFileInfo,
) -> None:
    """Test storing metadata in cache."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Store in cache
    app._file_metadata_cache["test.parquet"] = sample_file_info

    # Verify storage
    assert len(app._file_metadata_cache) == 1
    assert "test.parquet" in app._file_metadata_cache
    assert app._file_metadata_cache["test.parquet"] == sample_file_info

    # Verify stats
    stats = app.get_cache_stats()
    assert stats["metadata_entries"] == 1


def test_profile_cache_storage(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_profile: ColumnProfile,
) -> None:
    """Test storing profile in cache."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Store in cache
    cache_key = ("test.parquet", "id")
    app._profile_cache[cache_key] = sample_profile

    # Verify storage
    assert len(app._profile_cache) == 1
    assert cache_key in app._profile_cache
    assert app._profile_cache[cache_key] == sample_profile

    # Verify stats
    stats = app.get_cache_stats()
    assert stats["profile_entries"] == 1


def test_invalidate_all_caches(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_file_info: ParquetFileInfo,
    sample_profile: ColumnProfile,
) -> None:
    """Test invalidating all caches."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Populate caches
    app._file_metadata_cache["test.parquet"] = sample_file_info
    app._profile_cache[("test.parquet", "id")] = sample_profile

    # Verify populated
    assert len(app._file_metadata_cache) == 1
    assert len(app._profile_cache) == 1

    # Invalidate all
    app._invalidate_cache(None)

    # Verify cleared
    assert len(app._file_metadata_cache) == 0
    assert len(app._profile_cache) == 0


def test_invalidate_specific_file_cache(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_file_info: ParquetFileInfo,
    sample_profile: ColumnProfile,
) -> None:
    """Test invalidating cache for specific file."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Populate caches for two files
    app._file_metadata_cache["file1.parquet"] = sample_file_info
    app._file_metadata_cache["file2.parquet"] = sample_file_info
    app._profile_cache[("file1.parquet", "id")] = sample_profile
    app._profile_cache[("file2.parquet", "id")] = sample_profile

    # Verify populated
    assert len(app._file_metadata_cache) == 2
    assert len(app._profile_cache) == 2

    # Invalidate file1 only
    app._invalidate_cache("file1.parquet")

    # Verify file1 cleared, file2 remains
    assert len(app._file_metadata_cache) == 1
    assert "file1.parquet" not in app._file_metadata_cache
    assert "file2.parquet" in app._file_metadata_cache

    assert len(app._profile_cache) == 1
    assert ("file1.parquet", "id") not in app._profile_cache
    assert ("file2.parquet", "id") in app._profile_cache


def test_invalidate_multiple_profile_entries(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_profile: ColumnProfile,
) -> None:
    """Test invalidating multiple profile entries for one file."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Populate cache with multiple columns for one file
    app._profile_cache[("test.parquet", "id")] = sample_profile
    app._profile_cache[("test.parquet", "name")] = sample_profile
    app._profile_cache[("test.parquet", "age")] = sample_profile

    # Verify populated
    assert len(app._profile_cache) == 3

    # Invalidate all entries for test.parquet
    app._invalidate_cache("test.parquet")

    # Verify all cleared
    assert len(app._profile_cache) == 0


def test_cache_stats_with_data(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_file_info: ParquetFileInfo,
    sample_profile: ColumnProfile,
) -> None:
    """Test cache stats with populated caches."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Populate caches
    app._file_metadata_cache["file1.parquet"] = sample_file_info
    app._file_metadata_cache["file2.parquet"] = sample_file_info
    app._profile_cache[("file1.parquet", "id")] = sample_profile
    app._profile_cache[("file1.parquet", "name")] = sample_profile
    app._profile_cache[("file2.parquet", "id")] = sample_profile

    # Get stats
    stats = app.get_cache_stats()

    # Verify stats
    assert stats["metadata_entries"] == 2
    assert stats["profile_entries"] == 3


def test_invalidate_nonexistent_file(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test invalidating cache for file that doesn't exist."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise error
    app._invalidate_cache("nonexistent.parquet")

    # Caches should still be empty
    assert len(app._file_metadata_cache) == 0
    assert len(app._profile_cache) == 0
