"""Unit tests for Delta Lake transaction log parser."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tablesleuth.services.formats.delta_log_parser import (
    AddAction,
    CommitInfo,
    DeltaLogParser,
    RemoveAction,
)


class TestDeltaLogParser:
    """Test suite for DeltaLogParser."""

    def test_parse_version_file_with_commit_info(self) -> None:
        """Test parsing a version file with commit info."""
        # Create a temporary version file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            commit_data = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "5", "numOutputRows": "1000"},
                    "userMetadata": "Test Job",
                    "engineInfo": "Apache-Spark/3.5.0",
                }
            }
            f.write(json.dumps(commit_data) + "\n")
            temp_path = f.name

        try:
            result = DeltaLogParser.parse_version_file(temp_path)

            assert result["commit_info"] is not None
            commit_info = result["commit_info"]
            assert isinstance(commit_info, CommitInfo)
            assert commit_info.timestamp == 1705334625000
            assert commit_info.operation == "WRITE"
            assert commit_info.operation_parameters == {"mode": "Append"}
            assert commit_info.operation_metrics == {"numFiles": "5", "numOutputRows": "1000"}
            assert commit_info.user_metadata == "Test Job"
            assert commit_info.engine_info == "Apache-Spark/3.5.0"
        finally:
            Path(temp_path).unlink()

    def test_parse_version_file_with_add_actions(self) -> None:
        """Test parsing a version file with add actions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            add_data = {
                "add": {
                    "path": "part-00000.snappy.parquet",
                    "size": 1024,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "stats": '{"numRecords":100,"minValues":{"id":1},"maxValues":{"id":100}}',
                    "partitionValues": {"date": "2024-01-15"},
                }
            }
            f.write(json.dumps(add_data) + "\n")
            temp_path = f.name

        try:
            result = DeltaLogParser.parse_version_file(temp_path)

            assert len(result["add_actions"]) == 1
            add_action = result["add_actions"][0]
            assert isinstance(add_action, AddAction)
            assert add_action.path == "part-00000.snappy.parquet"
            assert add_action.size == 1024
            assert add_action.modification_time == 1705334625000
            assert add_action.data_change is True
            assert add_action.stats is not None
            assert add_action.stats["numRecords"] == 100
            assert add_action.partition_values == {"date": "2024-01-15"}
        finally:
            Path(temp_path).unlink()

    def test_parse_version_file_with_remove_actions(self) -> None:
        """Test parsing a version file with remove actions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            remove_data = {
                "remove": {
                    "path": "part-00001.snappy.parquet",
                    "deletionTimestamp": 1705334625000,
                    "dataChange": True,
                    "size": 2048,
                }
            }
            f.write(json.dumps(remove_data) + "\n")
            temp_path = f.name

        try:
            result = DeltaLogParser.parse_version_file(temp_path)

            assert len(result["remove_actions"]) == 1
            remove_action = result["remove_actions"][0]
            assert isinstance(remove_action, RemoveAction)
            assert remove_action.path == "part-00001.snappy.parquet"
            assert remove_action.deletion_timestamp == 1705334625000
            assert remove_action.data_change is True
            assert remove_action.size == 2048
        finally:
            Path(temp_path).unlink()

    def test_parse_version_file_with_multiple_entries(self) -> None:
        """Test parsing a version file with multiple entries."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            commit_data = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "MERGE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }
            add_data1 = {
                "add": {
                    "path": "part-00000.snappy.parquet",
                    "size": 1024,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            add_data2 = {
                "add": {
                    "path": "part-00001.snappy.parquet",
                    "size": 2048,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            remove_data = {
                "remove": {
                    "path": "part-00002.snappy.parquet",
                    "deletionTimestamp": 1705334625000,
                    "dataChange": True,
                }
            }

            f.write(json.dumps(commit_data) + "\n")
            f.write(json.dumps(add_data1) + "\n")
            f.write(json.dumps(add_data2) + "\n")
            f.write(json.dumps(remove_data) + "\n")
            temp_path = f.name

        try:
            result = DeltaLogParser.parse_version_file(temp_path)

            assert result["commit_info"] is not None
            assert result["commit_info"].operation == "MERGE"
            assert len(result["add_actions"]) == 2
            assert len(result["remove_actions"]) == 1
        finally:
            Path(temp_path).unlink()

    def test_parse_version_file_missing_optional_fields(self) -> None:
        """Test parsing a version file with missing optional fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            commit_data = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    # Missing operationParameters, operationMetrics, userMetadata, engineInfo
                }
            }
            f.write(json.dumps(commit_data) + "\n")
            temp_path = f.name

        try:
            result = DeltaLogParser.parse_version_file(temp_path)

            assert result["commit_info"] is not None
            commit_info = result["commit_info"]
            assert commit_info.timestamp == 1705334625000
            assert commit_info.operation == "WRITE"
            assert commit_info.operation_parameters == {}
            assert commit_info.operation_metrics == {}
            assert commit_info.user_metadata is None
            assert commit_info.engine_info is None
        finally:
            Path(temp_path).unlink()

    def test_parse_version_file_not_found(self) -> None:
        """Test parsing a non-existent version file."""
        with pytest.raises(FileNotFoundError, match="Version file not found"):
            DeltaLogParser.parse_version_file("/nonexistent/path.json")

    def test_parse_version_file_malformed_json(self) -> None:
        """Test parsing a version file with malformed JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }\n")
            temp_path = f.name

        try:
            with pytest.raises(json.JSONDecodeError, match="Malformed JSON"):
                DeltaLogParser.parse_version_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_parse_version_file_malformed_stats_json(self) -> None:
        """Test parsing a version file with malformed stats JSON in add action."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            add_data = {
                "add": {
                    "path": "part-00000.parquet",
                    "size": 1024,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "stats": "{ invalid json }",  # Malformed JSON in stats
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(add_data) + "\n")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Malformed stats JSON in add action"):
                DeltaLogParser.parse_version_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_extract_operation_metrics_basic(self) -> None:
        """Test extracting basic operation metrics."""
        commit_info = {
            "operationMetrics": {
                "numFiles": "5",
                "numOutputRows": "1000",
                "numOutputBytes": "125000",
            }
        }

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics["num_files"] == "5"
        assert metrics["num_output_rows"] == "1000"
        assert metrics["num_output_bytes"] == "125000"

    def test_extract_operation_metrics_merge(self) -> None:
        """Test extracting MERGE operation metrics."""
        commit_info = {
            "operationMetrics": {
                "numTargetRowsInserted": "100",
                "numTargetRowsUpdated": "50",
                "numTargetRowsDeleted": "25",
                "numTargetRowsMatchedUpdated": "40",
                "numTargetRowsMatchedDeleted": "20",
            }
        }

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics["num_target_rows_inserted"] == "100"
        assert metrics["num_target_rows_updated"] == "50"
        assert metrics["num_target_rows_deleted"] == "25"
        assert metrics["num_target_rows_matched_updated"] == "40"
        assert metrics["num_target_rows_matched_deleted"] == "20"

    def test_extract_operation_metrics_empty(self) -> None:
        """Test extracting operation metrics when none are present."""
        commit_info = {"operationMetrics": {}}

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics == {}

    def test_extract_operation_metrics_missing_key(self) -> None:
        """Test extracting operation metrics when operationMetrics key is missing."""
        commit_info: dict[str, dict[str, str]] = {}

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics == {}

    def test_extract_operation_metrics_delete(self) -> None:
        """Test extracting DELETE operation metrics."""
        commit_info = {
            "operationMetrics": {
                "numRemovedFiles": "3",
                "numAddedFiles": "2",
                "numDeletedRows": "150",
                "numCopiedRows": "850",
                "numBytesAdded": "50000",
                "numBytesRemoved": "75000",
            }
        }

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics["num_removed_files"] == "3"
        assert metrics["num_added_files"] == "2"
        assert metrics["num_deleted_rows"] == "150"
        assert metrics["num_copied_rows"] == "850"
        assert metrics["num_bytes_added"] == "50000"
        assert metrics["num_bytes_removed"] == "75000"

    def test_extract_operation_metrics_vacuum(self) -> None:
        """Test extracting VACUUM operation metrics."""
        commit_info = {
            "operationMetrics": {
                "numFilesToDelete": "25",
                "sizeOfDataToDelete": "1000000",
                "numDeletedFiles": "25",
            }
        }

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics["num_files_to_delete"] == "25"
        assert metrics["size_of_data_to_delete"] == "1000000"
        assert metrics["num_deleted_files"] == "25"

    def test_extract_operation_metrics_optimize(self) -> None:
        """Test extracting OPTIMIZE operation metrics."""
        commit_info = {
            "operationMetrics": {
                "numAddedFiles": "5",
                "numRemovedFiles": "50",
                "minFileSize": "10485760",
                "maxFileSize": "134217728",
                "totalFiles": "5",
                "totalSize": "536870912",
            }
        }

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics["num_added_files"] == "5"
        assert metrics["num_removed_files"] == "50"
        assert metrics["min_file_size"] == "10485760"
        assert metrics["max_file_size"] == "134217728"
        assert metrics["total_files"] == "5"
        assert metrics["total_size"] == "536870912"

    def test_extract_operation_metrics_merge_extended(self) -> None:
        """Test extracting extended MERGE operation metrics."""
        commit_info = {
            "operationMetrics": {
                "numTargetRowsInserted": "100",
                "numTargetRowsUpdated": "50",
                "numTargetRowsDeleted": "25",
                "numTargetRowsMatchedUpdated": "40",
                "numTargetRowsMatchedDeleted": "20",
                "numSourceRows": "175",
                "numTargetFilesAdded": "3",
                "numTargetFilesRemoved": "2",
                "numTargetRowsCopied": "500",
            }
        }

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics["num_target_rows_inserted"] == "100"
        assert metrics["num_target_rows_updated"] == "50"
        assert metrics["num_target_rows_deleted"] == "25"
        assert metrics["num_target_rows_matched_updated"] == "40"
        assert metrics["num_target_rows_matched_deleted"] == "20"
        assert metrics["num_source_rows"] == "175"
        assert metrics["num_target_files_added"] == "3"
        assert metrics["num_target_files_removed"] == "2"
        assert metrics["num_target_rows_copied"] == "500"

    def test_extract_operation_metrics_mixed_engines(self) -> None:
        """Test extracting metrics with mixed engine formats."""
        # Simulating metrics that might come from different engines
        commit_info = {
            "operationMetrics": {
                "numFiles": "10",  # Spark format
                "numOutputRows": "1000",  # Spark format
                "numOutputBytes": "125000",  # Spark format
                "numAddedFiles": "5",  # Common format
                "numRemovedFiles": "3",  # Common format
            }
        }

        metrics = DeltaLogParser.extract_operation_metrics(commit_info)

        assert metrics["num_files"] == "10"
        assert metrics["num_output_rows"] == "1000"
        assert metrics["num_output_bytes"] == "125000"
        assert metrics["num_added_files"] == "5"
        assert metrics["num_removed_files"] == "3"
