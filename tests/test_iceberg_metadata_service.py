"""Tests for IcebergMetadataService.

Note: These tests require a real Iceberg table for integration testing.
For unit tests, we would need to mock PyIceberg components.
"""

from __future__ import annotations

import pytest

from tablesleuth.exceptions import SnapshotNotFoundError, TableLoadError
from tablesleuth.services.iceberg_metadata_service import IcebergMetadataService


class TestIcebergMetadataService:
    """Tests for IcebergMetadataService."""

    def test_load_table_invalid_arguments(self):
        """Test load_table with invalid arguments."""
        service = IcebergMetadataService()

        with pytest.raises(ValueError, match="Must provide either"):
            service.load_table()

    def test_load_table_nonexistent_file(self):
        """Test load_table with nonexistent metadata file."""
        service = IcebergMetadataService()

        with pytest.raises(TableLoadError, match="Metadata file not found"):
            service.load_table(metadata_path="/nonexistent/metadata.json")

    # Integration tests would go here
    # These require a real Iceberg table and are marked as integration tests

    @pytest.mark.integration
    def test_load_table_from_metadata_file(self, iceberg_table_metadata_path):
        """Test loading table from metadata file.

        Args:
            iceberg_table_metadata_path: Fixture providing path to test table metadata
        """
        service = IcebergMetadataService()
        table_info = service.load_table(metadata_path=iceberg_table_metadata_path)

        assert table_info is not None
        assert table_info.table_uuid is not None
        assert table_info.format_version > 0
        assert table_info.location is not None

    @pytest.mark.integration
    def test_list_snapshots(self, iceberg_table_info):
        """Test listing snapshots from a table.

        Args:
            iceberg_table_info: Fixture providing IcebergTableInfo
        """
        service = IcebergMetadataService()
        snapshots = service.list_snapshots(iceberg_table_info)

        assert isinstance(snapshots, list)
        assert len(snapshots) > 0

        # Verify snapshots are sorted by timestamp descending
        for i in range(len(snapshots) - 1):
            assert snapshots[i].timestamp_ms >= snapshots[i + 1].timestamp_ms

        # Verify snapshot structure
        snapshot = snapshots[0]
        assert snapshot.snapshot_id > 0
        assert snapshot.timestamp_ms > 0
        assert snapshot.operation is not None
        assert snapshot.total_records >= 0
        assert snapshot.total_data_files >= 0

    @pytest.mark.integration
    def test_get_snapshot_details(self, iceberg_table_info):
        """Test getting snapshot details.

        Args:
            iceberg_table_info: Fixture providing IcebergTableInfo
        """
        service = IcebergMetadataService()

        # Get first snapshot
        snapshots = service.list_snapshots(iceberg_table_info)
        snapshot_id = snapshots[0].snapshot_id

        # Get details
        details = service.get_snapshot_details(iceberg_table_info, snapshot_id)

        assert details is not None
        assert details.snapshot_info.snapshot_id == snapshot_id
        assert details.schema is not None
        assert details.partition_spec is not None
        assert isinstance(details.data_files, list)
        assert isinstance(details.delete_files, list)

    @pytest.mark.integration
    def test_get_snapshot_details_invalid_id(self, iceberg_table_info):
        """Test getting snapshot details with invalid ID.

        Args:
            iceberg_table_info: Fixture providing IcebergTableInfo
        """
        service = IcebergMetadataService()

        with pytest.raises(SnapshotNotFoundError):
            service.get_snapshot_details(iceberg_table_info, 999999999)

    @pytest.mark.integration
    def test_compare_snapshots(self, iceberg_table_info):
        """Test comparing two snapshots.

        Args:
            iceberg_table_info: Fixture providing IcebergTableInfo
        """
        service = IcebergMetadataService()

        # Get two snapshots
        snapshots = service.list_snapshots(iceberg_table_info)
        if len(snapshots) < 2:
            pytest.skip("Need at least 2 snapshots for comparison test")

        snapshot_a_id = snapshots[1].snapshot_id  # Older
        snapshot_b_id = snapshots[0].snapshot_id  # Newer

        # Compare
        comparison = service.compare_snapshots(iceberg_table_info, snapshot_a_id, snapshot_b_id)

        assert comparison is not None
        assert comparison.snapshot_a.snapshot_id == snapshot_a_id
        assert comparison.snapshot_b.snapshot_id == snapshot_b_id
        assert comparison.records_delta is not None
        assert comparison.compaction_recommendation is not None


# Fixtures for integration tests
@pytest.fixture
def iceberg_table_metadata_path():
    """Provide path to test Iceberg table metadata.

    This should point to a real Iceberg table for integration testing.
    Skip if not available.
    """
    import os

    path = os.getenv("TEST_ICEBERG_METADATA_PATH")
    if not path:
        pytest.skip("TEST_ICEBERG_METADATA_PATH not set")
    return path


@pytest.fixture
def iceberg_table_info(iceberg_table_metadata_path):
    """Provide IcebergTableInfo for testing.

    Args:
        iceberg_table_metadata_path: Path to metadata file
    """
    service = IcebergMetadataService()
    return service.load_table(metadata_path=iceberg_table_metadata_path)
