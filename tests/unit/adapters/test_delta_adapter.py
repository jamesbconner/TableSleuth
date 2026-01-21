"""Unit tests for Delta Lake adapter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tablesleuth.models import FileRef, SnapshotInfo, TableHandle
from tablesleuth.services.formats.delta import DeltaAdapter
from tablesleuth.services.formats.delta_log_parser import AddAction


class TestDeltaAdapter:
    """Test suite for DeltaAdapter."""

    @pytest.fixture
    def temp_delta_table(self) -> Path:
        """Create a minimal Delta table for testing.

        Creates a Delta table with:
        - Protocol and metadata entries (required by delta-rs)
        - Version 0 with a single data file
        - Proper _delta_log structure
        """
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create version 0 file with protocol, metadata, commitInfo, and add action
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            # Protocol entry (required)
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            # Metadata entry (required)
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            # Commit info
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1", "numOutputRows": "100"},
                }
            }
            # Add action
            add_action = {
                "add": {
                    "path": "part-00000.snappy.parquet",
                    "size": 1024,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "stats": '{"numRecords":100}',
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        return temp_dir

    def test_init_without_storage_options(self) -> None:
        """Test initializing adapter without storage options."""
        adapter = DeltaAdapter()
        assert adapter.storage_options == {}

    def test_init_with_storage_options(self) -> None:
        """Test initializing adapter with storage options."""
        storage_options = {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "secret"}
        adapter = DeltaAdapter(storage_options=storage_options)
        assert adapter.storage_options == storage_options

    def test_is_delta_table_valid(self, temp_delta_table: Path) -> None:
        """Test _is_delta_table with a valid Delta table."""
        adapter = DeltaAdapter()
        assert adapter._is_delta_table(str(temp_delta_table)) is True

    def test_is_delta_table_missing_delta_log(self) -> None:
        """Test _is_delta_table with missing _delta_log directory."""
        temp_dir = Path(tempfile.mkdtemp())
        adapter = DeltaAdapter()
        assert adapter._is_delta_table(str(temp_dir)) is False

    def test_is_delta_table_empty_delta_log(self) -> None:
        """Test _is_delta_table with empty _delta_log directory."""
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        adapter = DeltaAdapter()
        assert adapter._is_delta_table(str(temp_dir)) is False

    def test_is_delta_table_nonexistent_path(self) -> None:
        """Test _is_delta_table with non-existent path."""
        adapter = DeltaAdapter()
        assert adapter._is_delta_table("/nonexistent/path") is False

    def test_open_table_valid(self, temp_delta_table: Path) -> None:
        """Test opening a valid Delta table."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))

        assert isinstance(table_handle, TableHandle)
        assert table_handle.format_name == "delta"
        assert table_handle.native is not None

    def test_open_table_nonexistent_path(self) -> None:
        """Test opening a non-existent table path."""
        adapter = DeltaAdapter()
        with pytest.raises(FileNotFoundError, match="Table path not found"):
            adapter.open_table("/nonexistent/path")

    def test_open_table_invalid_delta_table(self) -> None:
        """Test opening a path that is not a valid Delta table."""
        temp_dir = Path(tempfile.mkdtemp())
        adapter = DeltaAdapter()

        with pytest.raises(ValueError, match="Not a valid Delta table"):
            adapter.open_table(str(temp_dir))

    def test_list_snapshots(self, temp_delta_table: Path) -> None:
        """Test listing snapshots from a Delta table."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))
        snapshots = adapter.list_snapshots(table_handle)

        assert len(snapshots) == 1
        assert isinstance(snapshots[0], SnapshotInfo)
        assert snapshots[0].snapshot_id == 0
        assert snapshots[0].operation == "WRITE"

    def test_list_snapshots_multiple_versions(self) -> None:
        """Test listing snapshots from a Delta table with multiple versions.

        Validates that list_snapshots iterates from version 0 to current version
        and builds SnapshotInfo for each version.
        """
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create version 0
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1", "numOutputRows": "100"},
                }
            }
            add_action = {
                "add": {
                    "path": "part-00000.snappy.parquet",
                    "size": 1024,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "stats": '{"numRecords":100}',
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Create version 1
        version_1 = delta_log_dir / "00000000000000000001.json"
        with open(version_1, "w") as f:
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334626000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1", "numOutputRows": "200"},
                }
            }
            add_action = {
                "add": {
                    "path": "part-00001.snappy.parquet",
                    "size": 2048,
                    "modificationTime": 1705334626000,
                    "dataChange": True,
                    "stats": '{"numRecords":200}',
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Create version 2
        version_2 = delta_log_dir / "00000000000000000002.json"
        with open(version_2, "w") as f:
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334627000,
                    "operation": "OPTIMIZE",
                    "operationParameters": {"predicate": "[]"},
                    "operationMetrics": {
                        "numFilesAdded": "1",
                        "numFilesRemoved": "2",
                        "numOutputRows": "300",
                    },
                }
            }
            # Remove previous files
            remove_action_0 = {
                "remove": {
                    "path": "part-00000.snappy.parquet",
                    "deletionTimestamp": 1705334627000,
                    "dataChange": False,
                }
            }
            remove_action_1 = {
                "remove": {
                    "path": "part-00001.snappy.parquet",
                    "deletionTimestamp": 1705334627000,
                    "dataChange": False,
                }
            }
            # Add optimized file
            add_action = {
                "add": {
                    "path": "part-00002-optimized.snappy.parquet",
                    "size": 3072,
                    "modificationTime": 1705334627000,
                    "dataChange": False,
                    "stats": '{"numRecords":300}',
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(remove_action_0) + "\n")
            f.write(json.dumps(remove_action_1) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Test list_snapshots
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_dir))
        snapshots = adapter.list_snapshots(table_handle)

        # Verify all versions are listed
        assert len(snapshots) == 3, "Should list all versions from 0 to current"

        # Verify version 0
        assert snapshots[0].snapshot_id == 0
        assert snapshots[0].operation == "WRITE"
        assert snapshots[0].timestamp_ms == 1705334625000
        assert snapshots[0].parent_id is None
        assert len(snapshots[0].data_files) == 1
        assert snapshots[0].data_files[0].path.endswith("part-00000.snappy.parquet")

        # Verify version 1 - should have cumulative files (version 0 + version 1)
        assert snapshots[1].snapshot_id == 1
        assert snapshots[1].operation == "WRITE"
        assert snapshots[1].timestamp_ms == 1705334626000
        assert snapshots[1].parent_id == 0
        assert len(snapshots[1].data_files) == 2  # Both files from v0 and v1
        file_paths = {f.path for f in snapshots[1].data_files}
        assert any("part-00000.snappy.parquet" in p for p in file_paths)
        assert any("part-00001.snappy.parquet" in p for p in file_paths)

        # Verify version 2 - OPTIMIZE removed 2 files and added 1
        assert snapshots[2].snapshot_id == 2
        assert snapshots[2].operation == "OPTIMIZE"
        assert snapshots[2].timestamp_ms == 1705334627000
        assert snapshots[2].parent_id == 1
        assert len(snapshots[2].data_files) == 1  # Only the optimized file remains
        assert snapshots[2].data_files[0].path.endswith("part-00002-optimized.snappy.parquet")

        # Verify operation metrics are present
        assert "metric_numOutputRows" in snapshots[0].summary
        assert snapshots[0].summary["metric_numOutputRows"] == "100"
        assert "metric_numOutputRows" in snapshots[1].summary
        assert snapshots[1].summary["metric_numOutputRows"] == "200"
        assert "metric_numFilesAdded" in snapshots[2].summary
        assert snapshots[2].summary["metric_numFilesAdded"] == "1"
        assert "metric_numFilesRemoved" in snapshots[2].summary
        assert snapshots[2].summary["metric_numFilesRemoved"] == "2"

    def test_load_snapshot_current_version(self, temp_delta_table: Path) -> None:
        """Test loading the current version (None)."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))
        snapshot = adapter.load_snapshot(table_handle, None)

        assert isinstance(snapshot, SnapshotInfo)
        assert snapshot.snapshot_id == 0
        assert snapshot.operation == "WRITE"

    def test_load_snapshot_specific_version(self, temp_delta_table: Path) -> None:
        """Test loading a specific version."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))
        snapshot = adapter.load_snapshot(table_handle, 0)

        assert isinstance(snapshot, SnapshotInfo)
        assert snapshot.snapshot_id == 0
        assert snapshot.operation == "WRITE"

    def test_load_snapshot_out_of_range(self, temp_delta_table: Path) -> None:
        """Test loading a version that is out of range."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))

        with pytest.raises(ValueError, match="Version .* is out of range"):
            adapter.load_snapshot(table_handle, 999)

    def test_load_snapshot_negative_version(self, temp_delta_table: Path) -> None:
        """Test loading a negative version number."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))

        with pytest.raises(ValueError, match="Version .* is out of range"):
            adapter.load_snapshot(table_handle, -1)

    def test_iter_data_files(self, temp_delta_table: Path) -> None:
        """Test iterating over data files.

        Validates Requirement 13.4: iter_data_files returns iterator over
        snapshot.data_files with FileRef objects.
        """
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))
        snapshot = adapter.load_snapshot(table_handle, 0)

        data_files = list(adapter.iter_data_files(snapshot))

        assert len(data_files) == 1
        assert isinstance(data_files[0], FileRef)
        # Path should be absolute (table_path / relative_path)
        assert data_files[0].path.endswith("part-00000.snappy.parquet")

        # Resolve both paths to handle Windows short path vs long path differences
        # (e.g., RUNNER~1 vs runneradmin on GitHub Actions)
        expected_table_path = temp_delta_table.resolve()
        actual_file_path = Path(data_files[0].path).resolve()
        assert (
            expected_table_path in actual_file_path.parents
            or expected_table_path == actual_file_path.parent
        )

        assert data_files[0].file_size_bytes == 1024
        assert data_files[0].record_count == 100
        assert data_files[0].source == "delta"
        assert data_files[0].content_type == "DATA"

        # Verify it returns an iterator (not just a list)
        data_files_iter = adapter.iter_data_files(snapshot)
        assert hasattr(data_files_iter, "__iter__")
        assert hasattr(data_files_iter, "__next__")

        # Verify iterator can be consumed
        first_file = next(data_files_iter)
        assert first_file.path.endswith("part-00000.snappy.parquet")

    def test_iter_delete_files(self, temp_delta_table: Path) -> None:
        """Test iterating over delete files (should be empty for Delta).

        Validates Requirement 13.5: iter_delete_files returns empty iterator
        since Delta Lake doesn't have separate delete files like Iceberg.
        """
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))
        snapshot = adapter.load_snapshot(table_handle, 0)

        delete_files = list(adapter.iter_delete_files(snapshot))

        assert len(delete_files) == 0

        # Verify it returns an iterator (not just a list)
        delete_files_iter = adapter.iter_delete_files(snapshot)
        assert hasattr(delete_files_iter, "__iter__")
        assert hasattr(delete_files_iter, "__next__")

    def test_snapshot_info_structure(self, temp_delta_table: Path) -> None:
        """Test the structure of SnapshotInfo."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))
        snapshot = adapter.load_snapshot(table_handle, 0)

        assert snapshot.snapshot_id == 0
        assert snapshot.parent_id is None  # First version has no parent
        assert snapshot.timestamp_ms == 1705334625000
        assert snapshot.operation == "WRITE"
        assert "operation" in snapshot.summary
        assert "timestamp" in snapshot.summary
        assert len(snapshot.data_files) == 1
        assert len(snapshot.delete_files) == 0

    def test_snapshot_info_summary_contains_metrics(self, temp_delta_table: Path) -> None:
        """Test that SnapshotInfo summary contains operation metrics."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))
        snapshot = adapter.load_snapshot(table_handle, 0)

        assert "metric_numFiles" in snapshot.summary
        assert snapshot.summary["metric_numFiles"] == "1"
        assert "metric_numOutputRows" in snapshot.summary
        assert snapshot.summary["metric_numOutputRows"] == "100"

    def test_file_ref_extra_metadata(self, temp_delta_table: Path) -> None:
        """Test that FileRef contains extra metadata from add action."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))
        snapshot = adapter.load_snapshot(table_handle, 0)

        file_ref = snapshot.data_files[0]
        assert "modification_time" in file_ref.extra
        assert file_ref.extra["modification_time"] == 1705334625000
        assert "data_change" in file_ref.extra
        assert file_ref.extra["data_change"] is True
        assert "stats" in file_ref.extra
        assert file_ref.extra["stats"]["numRecords"] == 100

    def test_protocol_compliance(self) -> None:
        """Test that DeltaAdapter implements all required protocol methods."""
        adapter = DeltaAdapter()

        # Check that all protocol methods exist
        assert hasattr(adapter, "open_table")
        assert hasattr(adapter, "list_snapshots")
        assert hasattr(adapter, "load_snapshot")
        assert hasattr(adapter, "iter_data_files")
        assert hasattr(adapter, "iter_delete_files")

        # Check that methods are callable
        assert callable(adapter.open_table)
        assert callable(adapter.list_snapshots)
        assert callable(adapter.load_snapshot)
        assert callable(adapter.iter_data_files)
        assert callable(adapter.iter_delete_files)

    def test_open_table_cloud_path_validation(self) -> None:
        """Test that cloud paths skip local validation and delegate to delta-rs."""
        adapter = DeltaAdapter()

        # Cloud paths should not raise FileNotFoundError immediately
        # They should attempt to open with delta-rs, which will fail with appropriate error
        with pytest.raises((ValueError, FileNotFoundError)):
            # This will fail because the S3 path doesn't exist, but it should
            # attempt to open it rather than failing on local path validation
            adapter.open_table("s3://nonexistent-bucket/table/")

    def test_build_snapshot_info_with_all_metadata(self, temp_delta_table: Path) -> None:
        """Test _build_snapshot_info extracts all metadata correctly."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))

        # Access the DeltaTable directly
        dt = table_handle.native
        snapshot = adapter._build_snapshot_info(dt, 0)

        # Verify all required fields are present
        assert snapshot.snapshot_id == 0
        assert snapshot.parent_id is None
        assert snapshot.timestamp_ms == 1705334625000
        assert snapshot.operation == "WRITE"

        # Verify summary contains operation info
        assert snapshot.summary["operation"] == "WRITE"
        assert snapshot.summary["timestamp"] == "1705334625000"

        # Verify summary contains operation parameters
        assert "param_mode" in snapshot.summary
        assert snapshot.summary["param_mode"] == "Append"

        # Verify summary contains operation metrics
        assert "metric_numFiles" in snapshot.summary
        assert snapshot.summary["metric_numFiles"] == "1"
        assert "metric_numOutputRows" in snapshot.summary
        assert snapshot.summary["metric_numOutputRows"] == "100"

        # Verify data files are extracted
        assert len(snapshot.data_files) == 1
        assert snapshot.data_files[0].path.endswith("part-00000.snappy.parquet")
        assert snapshot.data_files[0].file_size_bytes == 1024
        assert snapshot.data_files[0].record_count == 100

    def test_build_snapshot_info_with_user_metadata(self) -> None:
        """Test _build_snapshot_info extracts user metadata and engine info."""
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create version 0 with user metadata and engine info
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1"},
                    "userMetadata": "ETL Job v2.3",
                    "engineInfo": "Apache-Spark/3.5.0 Delta-Standalone/3.0.0",
                }
            }
            add_action = {
                "add": {
                    "path": "part-00000.snappy.parquet",
                    "size": 1024,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_dir))
        dt = table_handle.native
        snapshot = adapter._build_snapshot_info(dt, 0)

        # Verify user metadata is extracted
        assert "userMetadata" in snapshot.summary
        assert snapshot.summary["userMetadata"] == "ETL Job v2.3"

        # Verify engine info is extracted
        assert "engineInfo" in snapshot.summary
        assert snapshot.summary["engineInfo"] == "Apache-Spark/3.5.0 Delta-Standalone/3.0.0"

    def test_build_snapshot_info_with_partition_values(self) -> None:
        """Test _build_snapshot_info extracts partition values correctly."""
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create version 0 with partitioned data
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}},{"name":"date","type":"string","nullable":true,"metadata":{}}]}',
                    "partitionColumns": ["date"],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append", "partitionBy": '["date"]'},
                    "operationMetrics": {"numFiles": "1"},
                }
            }
            add_action = {
                "add": {
                    "path": "date=2024-01-15/part-00000.snappy.parquet",
                    "size": 2048,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "stats": '{"numRecords":200}',
                    "partitionValues": {"date": "2024-01-15"},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_dir))
        dt = table_handle.native
        snapshot = adapter._build_snapshot_info(dt, 0)

        # Verify partition values are extracted
        assert len(snapshot.data_files) == 1
        file_ref = snapshot.data_files[0]
        assert file_ref.partition == {"date": "2024-01-15"}
        assert file_ref.path.endswith(
            "date=2024-01-15/part-00000.snappy.parquet"
        ) or file_ref.path.endswith("date=2024-01-15\\part-00000.snappy.parquet")

    def test_build_snapshot_info_without_commit_info(self) -> None:
        """Test _build_snapshot_info handles missing commit info gracefully."""
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create version 0 without commit info (edge case)
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            add_action = {
                "add": {
                    "path": "part-00000.snappy.parquet",
                    "size": 1024,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(add_action) + "\n")

        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_dir))
        dt = table_handle.native
        snapshot = adapter._build_snapshot_info(dt, 0)

        # Verify it handles missing commit info gracefully
        assert snapshot.snapshot_id == 0
        assert snapshot.operation == "UNKNOWN"
        assert snapshot.timestamp_ms == 0
        assert len(snapshot.data_files) == 1

    def test_build_snapshot_info_with_multiple_files(self) -> None:
        """Test _build_snapshot_info handles multiple add actions."""
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create version 0 with multiple files
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "3", "numOutputRows": "300"},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")

            # Add multiple files
            for i in range(3):
                add_action = {
                    "add": {
                        "path": f"part-{i:05d}.snappy.parquet",
                        "size": 1024 * (i + 1),
                        "modificationTime": 1705334625000,
                        "dataChange": True,
                        "stats": f'{{"numRecords":{100 * (i + 1)}}}',
                        "partitionValues": {},
                    }
                }
                f.write(json.dumps(add_action) + "\n")

        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_dir))
        dt = table_handle.native
        snapshot = adapter._build_snapshot_info(dt, 0)

        # Verify all files are extracted
        assert len(snapshot.data_files) == 3
        assert snapshot.data_files[0].path.endswith("part-00000.snappy.parquet")
        assert snapshot.data_files[0].file_size_bytes == 1024
        assert snapshot.data_files[0].record_count == 100
        assert snapshot.data_files[1].path.endswith("part-00001.snappy.parquet")
        assert snapshot.data_files[1].file_size_bytes == 2048
        assert snapshot.data_files[1].record_count == 200
        assert snapshot.data_files[2].path.endswith("part-00002.snappy.parquet")
        assert snapshot.data_files[2].file_size_bytes == 3072
        assert snapshot.data_files[2].record_count == 300

    def test_get_schema_at_version(self, temp_delta_table: Path) -> None:
        """Test getting schema at a specific version."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))

        schema = adapter.get_schema_at_version(table_handle, 0)

        # Verify schema is returned as dict
        assert isinstance(schema, dict)
        assert "id" in schema
        assert schema["id"] == "integer"

    def test_get_schema_at_version_searches_backwards(self) -> None:
        """Test that get_schema_at_version searches backwards for metadata.

        Delta Lake only writes metaData entries when schema changes, typically
        in version 0. This test verifies that the method searches backwards from
        the requested version to find the most recent metaData entry.
        """
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create version 0 with schema
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}},{"name":"name","type":"string","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")

        # Create version 1 without metadata (typical for subsequent writes)
        version_1 = delta_log_dir / "00000000000000000001.json"
        with open(version_1, "w") as f:
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334626000,
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }
            f.write(json.dumps(commit_info) + "\n")

        # Create version 2 without metadata
        version_2 = delta_log_dir / "00000000000000000002.json"
        with open(version_2, "w") as f:
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334627000,
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }
            f.write(json.dumps(commit_info) + "\n")

        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_dir))

        # Get schema at version 2 - should find schema from version 0
        schema = adapter.get_schema_at_version(table_handle, 2)

        assert isinstance(schema, dict)
        assert "id" in schema
        assert schema["id"] == "integer"
        assert "name" in schema
        assert schema["name"] == "string"

    def test_get_schema_at_version_invalid_version(self, temp_delta_table: Path) -> None:
        """Test getting schema for invalid version number."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table))

        with pytest.raises(ValueError, match="Version .* is out of range"):
            adapter.get_schema_at_version(table_handle, 999)

    def test_get_versions_with_metadata(self) -> None:
        """Test identifying versions with metadata entries."""
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create version 0 with metadata
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")

        # Create version 1 without metadata
        version_1 = delta_log_dir / "00000000000000000001.json"
        with open(version_1, "w") as f:
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334626000,
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }
            f.write(json.dumps(commit_info) + "\n")

        # Create version 2 with metadata (schema change)
        version_2 = delta_log_dir / "00000000000000000002.json"
        with open(version_2, "w") as f:
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}},{"name":"new_column","type":"string","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334627000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334627000,
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")

        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_dir))

        # Get versions with metadata
        versions_with_metadata = adapter.get_versions_with_metadata(table_handle)

        # Should return versions 0 and 2 (both have metadata entries)
        assert 0 in versions_with_metadata
        assert 1 not in versions_with_metadata
        assert 2 in versions_with_metadata

    def test_create_file_ref_without_stats(self) -> None:
        """Test _create_file_ref handles missing stats gracefully."""
        adapter = DeltaAdapter()

        # Create add action without stats
        add_action = AddAction(
            path="test.parquet",
            size=1024,
            modification_time=1705334625000,
            data_change=True,
            stats=None,  # No stats
            partition_values={},
        )

        file_ref = adapter._create_file_ref(add_action, "/tmp/table", None)

        assert file_ref.path.endswith("test.parquet")
        assert file_ref.file_size_bytes == 1024
        assert file_ref.record_count is None  # Should be None when stats missing
        assert file_ref.source == "delta"
        assert file_ref.content_type == "DATA"

    def test_create_file_ref_with_stats(self) -> None:
        """Test _create_file_ref extracts record count from stats."""
        adapter = DeltaAdapter()

        # Create add action with stats
        add_action = AddAction(
            path="test.parquet",
            size=2048,
            modification_time=1705334625000,
            data_change=True,
            stats={"numRecords": 500, "minValues": {"id": 1}, "maxValues": {"id": 500}},
            partition_values={"date": "2024-01-15"},
        )

        file_ref = adapter._create_file_ref(add_action, "/tmp/table", None)

        assert file_ref.path.endswith("test.parquet")
        assert file_ref.file_size_bytes == 2048
        assert file_ref.record_count == 500
        assert file_ref.partition == {"date": "2024-01-15"}
        assert file_ref.extra["stats"]["numRecords"] == 500
        assert file_ref.extra["stats"]["minValues"] == {"id": 1}
        assert file_ref.extra["stats"]["maxValues"] == {"id": 500}
