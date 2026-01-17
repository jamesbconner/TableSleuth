"""Unit tests for IcebergAdapter core functionality."""

from unittest.mock import Mock, patch

import pytest

from tablesleuth.models import FileRef, SnapshotInfo, TableHandle
from tablesleuth.services.formats.iceberg import IcebergAdapter


class TestIcebergAdapterOpenTable:
    """Tests for open_table method."""

    @pytest.fixture
    def adapter(self):
        """Create IcebergAdapter instance."""
        return IcebergAdapter()

    @patch("tablesleuth.services.formats.iceberg.load_catalog")
    def test_open_table_with_catalog_name(self, mock_load_catalog, adapter):
        """Test opening table with explicit catalog name."""
        mock_catalog = Mock()
        mock_table = Mock()
        mock_load_catalog.return_value = mock_catalog
        mock_catalog.load_table.return_value = mock_table

        result = adapter.open_table("db.table", catalog_name="test_catalog")

        assert isinstance(result, TableHandle)
        assert result.native == mock_table
        assert result.format_name == "iceberg"
        mock_load_catalog.assert_called_once_with("test_catalog")
        mock_catalog.load_table.assert_called_once_with("db.table")

    @patch("tablesleuth.services.formats.iceberg.load_catalog")
    def test_open_table_with_default_catalog(self, mock_load_catalog):
        """Test opening table with default catalog."""
        adapter = IcebergAdapter(default_catalog="default_cat")
        mock_catalog = Mock()
        mock_table = Mock()
        mock_load_catalog.return_value = mock_catalog
        mock_catalog.load_table.return_value = mock_table

        result = adapter.open_table("db.table")

        assert isinstance(result, TableHandle)
        mock_load_catalog.assert_called_once_with("default_cat")
        mock_catalog.load_table.assert_called_once_with("db.table")

    @patch("tablesleuth.services.formats.iceberg.StaticTable")
    def test_open_table_via_metadata_path(self, mock_static_table, adapter):
        """Test opening table via metadata file path."""
        mock_table = Mock()
        mock_static_table.from_metadata.return_value = mock_table

        result = adapter.open_table("/path/to/metadata.json")

        assert isinstance(result, TableHandle)
        assert result.native == mock_table
        mock_static_table.from_metadata.assert_called_once_with("/path/to/metadata.json")

    @patch("tablesleuth.services.formats.iceberg.load_catalog")
    def test_open_table_with_s3_tables_arn(self, mock_load_catalog, adapter):
        """Test opening table with S3 Tables ARN."""
        arn = "arn:aws:s3tables:us-east-1:123456:bucket/my-bucket/table/db.table"
        mock_catalog = Mock()
        mock_table = Mock()
        mock_load_catalog.return_value = mock_catalog
        mock_catalog.load_table.return_value = mock_table

        result = adapter.open_table(arn)

        assert isinstance(result, TableHandle)
        mock_load_catalog.assert_called_once_with("s3tables")
        mock_catalog.load_table.assert_called_once_with("db.table")


class TestIcebergAdapterSnapshots:
    """Tests for snapshot-related methods."""

    @pytest.fixture
    def adapter(self):
        """Create IcebergAdapter instance."""
        return IcebergAdapter()

    @pytest.fixture
    def mock_table(self):
        """Create mock PyIceberg table."""
        table = Mock()
        return table

    @pytest.fixture
    def mock_snapshot(self):
        """Create mock snapshot."""
        snapshot = Mock()
        snapshot.snapshot_id = 12345
        snapshot.parent_snapshot_id = None
        snapshot.timestamp_ms = 1700000000000
        snapshot.operation = "append"

        # Mock summary with additional_properties
        summary = Mock()
        summary.additional_properties = {
            "added-files": "10",
            "added-records": "1000",
        }
        snapshot.summary = summary

        return snapshot

    def test_list_snapshots(self, adapter, mock_table, mock_snapshot):
        """Test listing all snapshots."""
        mock_table.snapshots.return_value = [mock_snapshot]

        # Mock scan to return empty files
        mock_scan = Mock()
        mock_scan.plan_files.return_value = []
        mock_table.scan.return_value = mock_scan

        table_handle = TableHandle(native=mock_table, format_name="iceberg")

        result = adapter.list_snapshots(table_handle)

        assert len(result) == 1
        assert isinstance(result[0], SnapshotInfo)
        assert result[0].snapshot_id == 12345

    def test_load_snapshot_current(self, adapter, mock_table, mock_snapshot):
        """Test loading current snapshot (snapshot_id=None)."""
        mock_table.current_snapshot.return_value = mock_snapshot

        # Mock scan
        mock_scan = Mock()
        mock_scan.plan_files.return_value = []
        mock_table.scan.return_value = mock_scan

        table_handle = TableHandle(native=mock_table, format_name="iceberg")

        result = adapter.load_snapshot(table_handle, snapshot_id=None)

        assert isinstance(result, SnapshotInfo)
        assert result.snapshot_id == 12345
        mock_table.current_snapshot.assert_called_once()

    def test_load_snapshot_by_id(self, adapter, mock_table, mock_snapshot):
        """Test loading specific snapshot by ID."""
        mock_table.snapshots.return_value = [mock_snapshot]

        # Mock scan
        mock_scan = Mock()
        mock_scan.plan_files.return_value = []
        mock_table.scan.return_value = mock_scan

        table_handle = TableHandle(native=mock_table, format_name="iceberg")

        result = adapter.load_snapshot(table_handle, snapshot_id=12345)

        assert isinstance(result, SnapshotInfo)
        assert result.snapshot_id == 12345

    def test_load_snapshot_not_found(self, adapter, mock_table):
        """Test loading non-existent snapshot raises ValueError."""
        mock_table.snapshots.return_value = []

        table_handle = TableHandle(native=mock_table, format_name="iceberg")

        with pytest.raises(ValueError, match="Snapshot 99999 not found"):
            adapter.load_snapshot(table_handle, snapshot_id=99999)


class TestIcebergAdapterFileIterators:
    """Tests for file iterator methods."""

    @pytest.fixture
    def adapter(self):
        """Create IcebergAdapter instance."""
        return IcebergAdapter()

    def test_iter_data_files(self, adapter):
        """Test iterating over data files."""
        data_files = [
            FileRef(path="s3://bucket/file1.parquet", file_size_bytes=1024),
            FileRef(path="s3://bucket/file2.parquet", file_size_bytes=2048),
        ]

        snapshot_info = SnapshotInfo(
            snapshot_id=123,
            parent_id=None,
            timestamp_ms=1700000000000,
            operation="append",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        result = list(adapter.iter_data_files(snapshot_info))

        assert len(result) == 2
        assert result[0].path == "s3://bucket/file1.parquet"
        assert result[1].path == "s3://bucket/file2.parquet"

    def test_iter_delete_files(self, adapter):
        """Test iterating over delete files."""
        delete_files = [
            FileRef(path="s3://bucket/delete1.parquet", file_size_bytes=512),
        ]

        snapshot_info = SnapshotInfo(
            snapshot_id=123,
            parent_id=None,
            timestamp_ms=1700000000000,
            operation="delete",
            summary={},
            data_files=[],
            delete_files=delete_files,
        )

        result = list(adapter.iter_delete_files(snapshot_info))

        assert len(result) == 1
        assert result[0].path == "s3://bucket/delete1.parquet"

    def test_iter_empty_files(self, adapter):
        """Test iterating over empty file lists."""
        snapshot_info = SnapshotInfo(
            snapshot_id=123,
            parent_id=None,
            timestamp_ms=1700000000000,
            operation="append",
            summary={},
            data_files=[],
            delete_files=[],
        )

        data_result = list(adapter.iter_data_files(snapshot_info))
        delete_result = list(adapter.iter_delete_files(snapshot_info))

        assert len(data_result) == 0
        assert len(delete_result) == 0


class TestIcebergAdapterGetDataFiles:
    """Tests for get_data_files method."""

    @pytest.fixture
    def adapter(self):
        """Create IcebergAdapter instance."""
        return IcebergAdapter()

    @patch("tablesleuth.services.formats.iceberg.load_catalog")
    def test_get_data_files_success(self, mock_load_catalog, adapter):
        """Test getting data files from table."""
        # Setup mocks
        mock_catalog = Mock()
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 123

        mock_load_catalog.return_value = mock_catalog
        mock_catalog.load_table.return_value = mock_table
        mock_table.current_snapshot.return_value = mock_snapshot

        # Mock file task
        mock_file = Mock()
        mock_file.file_path = "s3://bucket/data.parquet"
        mock_file.file_size_in_bytes = 1024
        mock_file.record_count = 100
        mock_file.spec_id = 0
        mock_file.partition = None

        mock_file_task = Mock()
        mock_file_task.file = mock_file

        mock_scan = Mock()
        mock_scan.plan_files.return_value = [mock_file_task]
        mock_table.scan.return_value = mock_scan

        result = adapter.get_data_files("db.table", "test_catalog")

        assert len(result) == 1
        assert isinstance(result[0], FileRef)
        assert result[0].path == "s3://bucket/data.parquet"
        assert result[0].file_size_bytes == 1024
        assert result[0].record_count == 100
        assert result[0].source == "iceberg"
        assert result[0].content_type == "DATA"

    @patch("tablesleuth.services.formats.iceberg.load_catalog")
    def test_get_data_files_with_partition(self, mock_load_catalog, adapter):
        """Test getting data files with partition information."""
        mock_catalog = Mock()
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 123

        mock_load_catalog.return_value = mock_catalog
        mock_catalog.load_table.return_value = mock_table
        mock_table.current_snapshot.return_value = mock_snapshot

        # Mock partition
        mock_partition = Mock()
        mock_partition.year = 2024
        mock_partition.month = 1

        mock_file = Mock()
        mock_file.file_path = "s3://bucket/year=2024/month=1/data.parquet"
        mock_file.file_size_in_bytes = 2048
        mock_file.record_count = 200
        mock_file.spec_id = 1
        mock_file.partition = mock_partition

        mock_file_task = Mock()
        mock_file_task.file = mock_file

        mock_scan = Mock()
        mock_scan.plan_files.return_value = [mock_file_task]
        mock_table.scan.return_value = mock_scan

        result = adapter.get_data_files("db.table", "test_catalog")

        assert len(result) == 1
        assert result[0].partition is not None
        assert isinstance(result[0].partition, dict)

    @patch("tablesleuth.services.formats.iceberg.load_catalog")
    def test_get_data_files_with_file_uri(self, mock_load_catalog, adapter):
        """Test getting data files with file:// URI conversion."""
        mock_catalog = Mock()
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 123

        mock_load_catalog.return_value = mock_catalog
        mock_catalog.load_table.return_value = mock_table
        mock_table.current_snapshot.return_value = mock_snapshot

        mock_file = Mock()
        mock_file.file_path = "file:///home/user/data.parquet"
        mock_file.file_size_in_bytes = 512
        mock_file.record_count = 50
        mock_file.spec_id = 0
        mock_file.partition = None

        mock_file_task = Mock()
        mock_file_task.file = mock_file

        mock_scan = Mock()
        mock_scan.plan_files.return_value = [mock_file_task]
        mock_table.scan.return_value = mock_scan

        result = adapter.get_data_files("db.table", "test_catalog")

        assert len(result) == 1
        assert result[0].path == "/home/user/data.parquet"

    @patch("tablesleuth.services.formats.iceberg.load_catalog")
    def test_get_data_files_no_current_snapshot(self, mock_load_catalog, adapter):
        """Test getting data files when no current snapshot exists."""
        mock_catalog = Mock()
        mock_table = Mock()

        mock_load_catalog.return_value = mock_catalog
        mock_catalog.load_table.return_value = mock_table
        mock_table.current_snapshot.return_value = None

        result = adapter.get_data_files("db.table", "test_catalog")

        assert result == []

    @patch("tablesleuth.services.formats.iceberg.load_catalog")
    def test_get_data_files_with_extra_metadata(self, mock_load_catalog, adapter):
        """Test getting data files with extra metadata fields."""
        mock_catalog = Mock()
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 123

        mock_load_catalog.return_value = mock_catalog
        mock_catalog.load_table.return_value = mock_table
        mock_table.current_snapshot.return_value = mock_snapshot

        mock_file = Mock()
        mock_file.file_path = "s3://bucket/data.parquet"
        mock_file.file_size_in_bytes = 1024
        mock_file.record_count = 100
        mock_file.spec_id = 2
        mock_file.sort_order_id = 5
        mock_file.partition = None

        mock_file_task = Mock()
        mock_file_task.file = mock_file

        mock_scan = Mock()
        mock_scan.plan_files.return_value = [mock_file_task]
        mock_table.scan.return_value = mock_scan

        result = adapter.get_data_files("db.table", "test_catalog")

        assert len(result) == 1
        assert result[0].extra["spec_id"] == 2
        assert result[0].extra["sort_order_id"] == 5


class TestIcebergAdapterBuildSnapshotInfo:
    """Tests for _build_snapshot_info method."""

    @pytest.fixture
    def adapter(self):
        """Create IcebergAdapter instance."""
        return IcebergAdapter()

    def test_build_snapshot_info_with_data_files(self, adapter):
        """Test building snapshot info with data files."""
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 456
        mock_snapshot.parent_snapshot_id = 123
        mock_snapshot.timestamp_ms = 1700000000000
        mock_snapshot.operation = "append"

        # Mock summary
        summary = Mock()
        summary.additional_properties = {"added-files": "5"}
        mock_snapshot.summary = summary

        # Mock file
        mock_file = Mock()
        mock_file.file_path = "s3://bucket/file.parquet"
        mock_file.file_size_in_bytes = 2048
        mock_file.record_count = 200
        mock_file.spec_id = 0
        mock_file.partition = None

        mock_file_task = Mock()
        mock_file_task.file = mock_file

        mock_scan = Mock()
        mock_scan.plan_files.return_value = [mock_file_task]
        mock_table.scan.return_value = mock_scan

        result = adapter._build_snapshot_info(mock_table, mock_snapshot)

        assert isinstance(result, SnapshotInfo)
        assert result.snapshot_id == 456
        assert result.parent_id == 123
        assert result.timestamp_ms == 1700000000000
        assert result.operation == "append"
        assert result.summary == {"added-files": "5"}
        assert len(result.data_files) == 1
        assert len(result.delete_files) == 0

    def test_build_snapshot_info_with_partition_error(self, adapter):
        """Test building snapshot info when partition conversion fails."""
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 789
        mock_snapshot.parent_snapshot_id = None
        mock_snapshot.timestamp_ms = 1700000000000
        mock_snapshot.operation = "append"

        summary = Mock()
        summary.additional_properties = {}
        mock_snapshot.summary = summary

        # Create a partition object that will cause vars() to raise TypeError
        class BadPartition:
            def __init__(self):
                pass

        mock_partition = BadPartition()

        mock_file = Mock()
        mock_file.file_path = "s3://bucket/file.parquet"
        mock_file.file_size_in_bytes = 1024
        mock_file.record_count = 100
        mock_file.spec_id = 0
        mock_file.partition = mock_partition

        # Patch vars to raise TypeError for this specific partition
        original_vars = vars

        def patched_vars(obj):
            if isinstance(obj, BadPartition):
                raise TypeError("Cannot get vars")
            return original_vars(obj)

        with patch("builtins.vars", side_effect=patched_vars):
            mock_file_task = Mock()
            mock_file_task.file = mock_file

            mock_scan = Mock()
            mock_scan.plan_files.return_value = [mock_file_task]
            mock_table.scan.return_value = mock_scan

            result = adapter._build_snapshot_info(mock_table, mock_snapshot)

            # Should handle error gracefully with empty partition dict
            assert len(result.data_files) == 1
            assert result.data_files[0].partition == {}

    def test_build_snapshot_info_no_operation(self, adapter):
        """Test building snapshot info when operation is None."""
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 999
        mock_snapshot.parent_snapshot_id = None
        mock_snapshot.timestamp_ms = 1700000000000
        mock_snapshot.operation = None

        summary = Mock()
        summary.additional_properties = {}
        mock_snapshot.summary = summary

        mock_scan = Mock()
        mock_scan.plan_files.return_value = []
        mock_table.scan.return_value = mock_scan

        result = adapter._build_snapshot_info(mock_table, mock_snapshot)

        assert result.operation == "unknown"

    def test_build_snapshot_info_no_summary(self, adapter):
        """Test building snapshot info when summary is None."""
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 888
        mock_snapshot.parent_snapshot_id = None
        mock_snapshot.timestamp_ms = 1700000000000
        mock_snapshot.operation = "append"
        mock_snapshot.summary = None

        mock_scan = Mock()
        mock_scan.plan_files.return_value = []
        mock_table.scan.return_value = mock_scan

        result = adapter._build_snapshot_info(mock_table, mock_snapshot)

        assert result.summary == {}

    def test_build_snapshot_info_summary_no_additional_properties(self, adapter):
        """Test building snapshot info when summary has no additional_properties."""
        mock_table = Mock()
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 777
        mock_snapshot.parent_snapshot_id = None
        mock_snapshot.timestamp_ms = 1700000000000
        mock_snapshot.operation = "append"

        # Summary without additional_properties attribute
        mock_snapshot.summary = Mock(spec=[])

        mock_scan = Mock()
        mock_scan.plan_files.return_value = []
        mock_table.scan.return_value = mock_scan

        result = adapter._build_snapshot_info(mock_table, mock_snapshot)

        assert result.summary == {}

    def test_get_data_files_with_partition_conversion_error(self, adapter):
        """Test get_data_files when partition conversion fails."""
        with patch("tablesleuth.services.formats.iceberg.load_catalog") as mock_load_catalog:
            mock_catalog = Mock()
            mock_table = Mock()
            mock_snapshot = Mock()
            mock_snapshot.snapshot_id = 123

            mock_load_catalog.return_value = mock_catalog
            mock_catalog.load_table.return_value = mock_table
            mock_table.current_snapshot.return_value = mock_snapshot

            # Create partition that will cause vars() to fail
            class BadPartition:
                pass

            mock_partition = BadPartition()

            mock_file = Mock()
            mock_file.file_path = "s3://bucket/data.parquet"
            mock_file.file_size_in_bytes = 1024
            mock_file.record_count = 100
            mock_file.spec_id = 0
            mock_file.partition = mock_partition

            mock_file_task = Mock()
            mock_file_task.file = mock_file

            mock_scan = Mock()
            mock_scan.plan_files.return_value = [mock_file_task]
            mock_table.scan.return_value = mock_scan

            # Patch vars to raise TypeError
            original_vars = vars

            def patched_vars(obj):
                if isinstance(obj, BadPartition):
                    raise TypeError("Cannot get vars")
                return original_vars(obj)

            with patch("builtins.vars", side_effect=patched_vars):
                result = adapter.get_data_files("db.table", "test_catalog")

                # Should handle error gracefully
                assert len(result) == 1
                assert result[0].partition == {}
