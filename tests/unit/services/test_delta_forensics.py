"""Unit tests for Delta Lake forensic analysis services."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from tablesleuth.models.file_ref import FileRef
from tablesleuth.models.snapshot import SnapshotInfo
from tablesleuth.services.delta_forensics import DeltaForensics
from tablesleuth.services.formats.delta_log_parser import AddAction, CommitInfo, RemoveAction


class TestAnalyzeFileSizes:
    """Tests for analyze_file_sizes method."""

    def test_analyze_file_sizes_with_mixed_files(self) -> None:
        """Test file size analysis with files of various sizes."""
        mb = 1024 * 1024

        # Create snapshot with files of different sizes
        data_files = [
            FileRef("small1.parquet", 500_000, None, "delta", "DATA"),  # < 1MB
            FileRef("small2.parquet", 5 * mb, None, "delta", "DATA"),  # 1-10MB
            FileRef("medium.parquet", 50 * mb, None, "delta", "DATA"),  # 10-100MB
            FileRef("large.parquet", 150 * mb, None, "delta", "DATA"),  # > 100MB
        ]

        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        # Verify histogram
        assert result["histogram"]["< 1MB"] == 1
        assert result["histogram"]["1-10MB"] == 1
        assert result["histogram"]["10-100MB"] == 1
        assert result["histogram"]["> 100MB"] == 1

        # Verify small file detection (< 10MB)
        assert result["small_file_count"] == 2
        assert result["small_file_percentage"] == 50.0

        # Verify optimization opportunity (80% of small files)
        assert result["optimization_opportunity"] == 1  # int(2 * 0.8) = 1

        # Verify statistics
        assert result["min_size_bytes"] == 500_000
        assert result["max_size_bytes"] == 150 * mb
        assert result["total_file_count"] == 4
        assert result["total_size_bytes"] == sum(f.file_size_bytes for f in data_files)

    def test_analyze_file_sizes_empty_snapshot(self) -> None:
        """Test file size analysis with no files."""
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[],
            delete_files=[],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        # All values should be zero
        assert result["histogram"]["< 1MB"] == 0
        assert result["small_file_count"] == 0
        assert result["small_file_percentage"] == 0.0
        assert result["optimization_opportunity"] == 0
        assert result["total_file_count"] == 0

    def test_analyze_file_sizes_all_small_files(self) -> None:
        """Test file size analysis with all small files."""
        mb = 1024 * 1024

        data_files = [
            FileRef(f"small{i}.parquet", 2 * mb, None, "delta", "DATA") for i in range(10)
        ]

        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        # All files should be in 1-10MB bucket
        assert result["histogram"]["1-10MB"] == 10
        assert result["small_file_count"] == 10
        assert result["small_file_percentage"] == 100.0
        assert result["optimization_opportunity"] == 8  # 80% of 10


class TestAnalyzeStorageWaste:
    """Tests for analyze_storage_waste method."""

    def test_analyze_storage_waste_with_tombstones(self, tmp_path: Path) -> None:
        """Test storage waste analysis with tombstoned files."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version 0: add 3 files
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_actions_v0 = [
            {
                "add": {
                    "path": "file1.parquet",
                    "size": 10_000_000,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            },
            {
                "add": {
                    "path": "file2.parquet",
                    "size": 20_000_000,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            },
            {
                "add": {
                    "path": "file3.parquet",
                    "size": 30_000_000,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            },
        ]

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            for action in add_actions_v0:
                f.write(json.dumps(action) + "\n")

        # Create version 1: remove file1
        version_1 = {
            "commitInfo": {
                "timestamp": 1705420000000,  # ~1 day later
                "operation": "DELETE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        remove_action = {
            "remove": {
                "path": "file1.parquet",
                "deletionTimestamp": 1705420000000,
                "dataChange": True,
                "size": 10_000_000,
            }
        }

        with open(delta_log_path / "00000000000000000001.json", "w") as f:
            f.write(json.dumps(version_1) + "\n")
            f.write(json.dumps(remove_action) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)

        # Analyze storage waste
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=1)

        # Verify active files (file2 and file3)
        assert result["active_files"]["count"] == 2
        assert result["active_files"]["total_size_bytes"] == 50_000_000

        # Verify tombstone files (file1)
        assert result["tombstone_files"]["count"] == 1
        assert result["tombstone_files"]["total_size_bytes"] == 10_000_000

        # Verify waste percentage
        total = 60_000_000
        expected_waste = (10_000_000 / total) * 100
        assert abs(result["waste_percentage"] - expected_waste) < 0.01

        # Verify total storage
        assert result["total_storage_bytes"] == 60_000_000

    def test_analyze_storage_waste_no_tombstones(self, tmp_path: Path) -> None:
        """Test storage waste analysis with no tombstoned files."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version 0: add files only
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_action = {
            "add": {
                "path": "file1.parquet",
                "size": 10_000_000,
                "modificationTime": 1705334625000,
                "dataChange": True,
                "partitionValues": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)

        # Analyze storage waste
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=0)

        # No tombstones
        assert result["tombstone_files"]["count"] == 0
        assert result["tombstone_files"]["total_size_bytes"] == 0
        assert result["waste_percentage"] == 0.0


class TestAnalyzeDMLOperation:
    """Tests for analyze_dml_operation method."""

    def test_analyze_merge_operation(self) -> None:
        """Test DML analysis for MERGE operation."""
        commit_info = {
            "operation": "MERGE",
            "operationParameters": {"predicate": "target.id = source.id"},
        }

        operation_metrics = {
            "num_bytes_added": 100_000_000,
            "num_bytes_removed": 80_000_000,
            "num_output_bytes": 100_000_000,
            "num_added_files": 5,
            "num_removed_files": 4,
            "num_target_rows_matched_updated": 1000,
            "num_target_rows_matched_deleted": 500,
            "num_target_rows_inserted": 2000,
            "num_target_rows_updated": 1000,
            "num_target_rows_deleted": 500,
        }

        result = DeltaForensics.analyze_dml_operation(commit_info, operation_metrics)

        # Verify operation type
        assert result["operation_type"] == "MERGE"

        # Verify rewrite amplification
        # bytes_rewritten = 100M, bytes_changed = |100M - 80M| = 20M
        # amplification = 100M / 20M = 5.0
        assert result["rewrite_amplification"] == 5.0

        # Verify rows affected (inserted + updated + deleted)
        assert result["rows_affected"] == 3500

        # Verify files rewritten
        assert result["files_rewritten"] == 5  # max(5 added, 4 removed)

        # Verify efficiency score (100 / 5.0 = 20)
        assert result["efficiency_score"] == 20.0

        # Not inefficient (< 10x)
        assert result["is_inefficient"] is False

        # Verify MERGE-specific metrics
        assert "merge_metrics" in result
        assert result["merge_metrics"]["rows_matched"] == 1500
        assert result["merge_metrics"]["rows_inserted"] == 2000
        assert result["merge_metrics"]["merge_predicate"] == "target.id = source.id"

    def test_analyze_update_operation_high_amplification(self) -> None:
        """Test DML analysis for UPDATE with high amplification."""
        commit_info = {"operation": "UPDATE", "operationParameters": {}}

        operation_metrics = {
            "num_bytes_added": 1_000_000_000,  # 1GB rewritten
            "num_bytes_removed": 900_000_000,  # 900MB removed
            "num_output_bytes": 1_000_000_000,
            "num_added_files": 10,
            "num_removed_files": 10,
            "num_target_rows_updated": 100,  # Only 100 rows updated!
        }

        result = DeltaForensics.analyze_dml_operation(commit_info, operation_metrics)

        # Verify high amplification
        # bytes_changed = |1000M - 900M| = 100M
        # amplification = 1000M / 100M = 10.0
        assert result["rewrite_amplification"] == 10.0

        # Should NOT be flagged as inefficient (threshold is > 10x, not >=)
        assert result["is_inefficient"] is False

        # Efficiency score at threshold
        assert result["efficiency_score"] == 10.0

    def test_analyze_update_operation_very_high_amplification(self) -> None:
        """Test DML analysis for UPDATE with very high amplification."""
        commit_info = {"operation": "UPDATE", "operationParameters": {}}

        operation_metrics = {
            "num_bytes_added": 1_000_000_000,  # 1GB rewritten
            "num_bytes_removed": 950_000_000,  # 950MB removed
            "num_output_bytes": 1_000_000_000,
            "num_added_files": 10,
            "num_removed_files": 10,
            "num_target_rows_updated": 100,
        }

        result = DeltaForensics.analyze_dml_operation(commit_info, operation_metrics)

        # Verify very high amplification
        # bytes_changed = |1000M - 950M| = 50M
        # amplification = 1000M / 50M = 20.0
        assert result["rewrite_amplification"] == 20.0

        # Should be flagged as inefficient (> 10x)
        assert result["is_inefficient"] is True

        # Very low efficiency score
        assert result["efficiency_score"] == 5.0

    def test_analyze_delete_operation(self) -> None:
        """Test DML analysis for DELETE operation."""
        commit_info = {"operation": "DELETE", "operationParameters": {}}

        operation_metrics = {
            "num_bytes_added": 50_000_000,
            "num_bytes_removed": 100_000_000,
            "num_output_bytes": 50_000_000,
            "num_added_files": 2,
            "num_removed_files": 5,
            "num_deleted_rows": 10000,
        }

        result = DeltaForensics.analyze_dml_operation(commit_info, operation_metrics)

        # Verify operation type
        assert result["operation_type"] == "DELETE"

        # Verify rows affected
        assert result["rows_affected"] == 10000

        # No MERGE-specific metrics
        assert "merge_metrics" not in result


class TestAnalyzeZOrderEffectiveness:
    """Tests for analyze_zorder_effectiveness method."""

    def test_analyze_zorder_with_provided_columns(self, tmp_path: Path) -> None:
        """Test Z-order analysis with explicitly provided columns."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version 0: OPTIMIZE with zOrderBy
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "OPTIMIZE",
                "operationParameters": {"zOrderBy": '["user_id", "date"]'},
                "operationMetrics": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 0

        # Analyze with provided columns
        result = DeltaForensics.analyze_zorder_effectiveness(
            mock_table, zorder_columns=["user_id", "date"]
        )

        # Verify columns
        assert result["zorder_columns"] == ["user_id", "date"]

        # Verify last optimize version
        assert result["last_optimize_version"] == 0

        # Verify versions since optimize
        assert result["versions_since_optimize"] == 0

        # Verify recommendation
        assert result["recommendation"] in ["good", "degraded", "needs_reoptimization"]

    def test_analyze_zorder_no_optimize_found(self, tmp_path: Path) -> None:
        """Test Z-order analysis when no OPTIMIZE operation exists."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version 0: WRITE (not OPTIMIZE)
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 0

        # Analyze without columns (auto-detect)
        result = DeltaForensics.analyze_zorder_effectiveness(mock_table)

        # No Z-order columns found
        assert result["zorder_columns"] == []

        # No optimize version found
        assert result["last_optimize_version"] is None

        # Overall effectiveness should be 0
        assert result["overall_effectiveness"] == 0.0


class TestAnalyzeCheckpointHealth:
    """Tests for analyze_checkpoint_health method."""

    def test_analyze_checkpoint_health_with_checkpoint(self, tmp_path: Path) -> None:
        """Test checkpoint health analysis with existing checkpoint."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create checkpoint file
        checkpoint_file = delta_log_path / "00000000000000000010.checkpoint.parquet"
        checkpoint_file.write_bytes(b"mock checkpoint data" * 1000)

        # Create some JSON files after checkpoint
        for i in range(11, 15):
            version_file = delta_log_path / f"{i:020d}.json"
            version_file.write_text('{"commitInfo": {}}')

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 14

        # Analyze checkpoint health
        result = DeltaForensics.analyze_checkpoint_health(mock_table)

        # Verify checkpoint found
        assert result["last_checkpoint_version"] == 10

        # Verify log tail length (versions 11-14 = 4 files)
        assert result["log_tail_length"] == 4

        # Verify checkpoint file size
        assert result["checkpoint_file_size_bytes"] > 0

        # Verify health status
        assert result["health_status"] in ["healthy", "degraded", "critical"]

    def test_analyze_checkpoint_health_no_checkpoint(self, tmp_path: Path) -> None:
        """Test checkpoint health analysis with no checkpoint."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create only JSON files (no checkpoint)
        for i in range(20):
            version_file = delta_log_path / f"{i:020d}.json"
            version_file.write_text('{"commitInfo": {}}')

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 19

        # Analyze checkpoint health
        result = DeltaForensics.analyze_checkpoint_health(mock_table)

        # No checkpoint found
        assert result["last_checkpoint_version"] is None

        # Log tail is entire history
        assert result["log_tail_length"] == 20

        # Should be critical
        assert result["health_status"] == "critical"

        # Should have issues
        assert len(result["issues"]) > 0


class TestGenerateRecommendations:
    """Tests for generate_recommendations method."""

    def test_generate_recommendations_small_files(self, tmp_path: Path) -> None:
        """Test recommendations for tables with many small files."""
        mb = 1024 * 1024

        # Create snapshot with 60% small files
        data_files = [
            FileRef(f"small{i}.parquet", 2 * mb, None, "delta", "DATA") for i in range(6)
        ] + [FileRef(f"large{i}.parquet", 50 * mb, None, "delta", "DATA") for i in range(4)]

        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        # Create mock Delta table
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version file
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")

        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 0

        # Generate recommendations
        recommendations = DeltaForensics.generate_recommendations(mock_table, snapshot)

        # Should recommend OPTIMIZE
        optimize_recs = [r for r in recommendations if r["type"] == "OPTIMIZE"]
        assert len(optimize_recs) > 0
        assert optimize_recs[0]["priority"] == "high"
        assert "60.0%" in optimize_recs[0]["reason"]

    def test_generate_recommendations_no_issues(self, tmp_path: Path) -> None:
        """Test recommendations for healthy table."""
        mb = 1024 * 1024

        # Create snapshot with all large files
        data_files = [
            FileRef(f"large{i}.parquet", 50 * mb, None, "delta", "DATA") for i in range(10)
        ]

        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        # Create mock Delta table
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version file
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")

        # Create checkpoint
        checkpoint_file = delta_log_path / "00000000000000000000.checkpoint.parquet"
        checkpoint_file.write_bytes(b"mock checkpoint")

        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 0

        # Generate recommendations
        recommendations = DeltaForensics.generate_recommendations(mock_table, snapshot)

        # Should have minimal or no recommendations
        high_priority = [r for r in recommendations if r["priority"] == "high"]
        assert len(high_priority) == 0


class TestAnalyzePartitionDistribution:
    """Tests for analyze_partition_distribution method."""

    def test_analyze_partition_distribution_with_skew(self) -> None:
        """Test partition analysis with skewed distribution."""
        mb = 1024 * 1024

        # Create files with skewed partition distribution
        # Partition A: 11 files (skewed, 11 > 5*2)
        # Partition B: 3 files (normal)
        # Partition C: 2 files (normal)
        # Average will be (11+3+2)/3 = 5.33
        data_files = []

        for i in range(11):
            data_files.append(
                FileRef(
                    f"date=2024-01-01/file{i}.parquet",
                    10 * mb,
                    1000,
                    "delta",
                    "DATA",
                    partition={"date": "2024-01-01"},
                )
            )

        for i in range(3):
            data_files.append(
                FileRef(
                    f"date=2024-01-02/file{i}.parquet",
                    10 * mb,
                    1000,
                    "delta",
                    "DATA",
                    partition={"date": "2024-01-02"},
                )
            )

        for i in range(2):
            data_files.append(
                FileRef(
                    f"date=2024-01-03/file{i}.parquet",
                    10 * mb,
                    1000,
                    "delta",
                    "DATA",
                    partition={"date": "2024-01-03"},
                )
            )

        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        # Analyze partition distribution
        result = DeltaForensics.analyze_partition_distribution(snapshot, ["date"])

        # Debug: print actual results
        print(f"Files per partition: {result['files_per_partition']}")
        print(f"Skewed partitions: {result['skewed_partitions']}")
        print(f"Hot partitions: {result['hot_partitions']}")

        # Verify partition columns
        assert result["partition_columns"] == ["date"]

        # Verify partition count
        assert result["partition_count"] == 3

        # Verify files per partition (check actual keys)
        assert len(result["files_per_partition"]) == 3

        # Find the partition with 11 files
        partition_with_11_files = [k for k, v in result["files_per_partition"].items() if v == 11]
        assert len(partition_with_11_files) == 1

        # Verify statistics
        assert result["statistics"]["min_files_per_partition"] == 2
        assert result["statistics"]["max_files_per_partition"] == 11
        # Average is (11+3+2)/3 = 5.33
        assert 5.0 <= result["statistics"]["avg_files_per_partition"] <= 5.5

        # Verify skew detection
        # Average is ~5.33, so 11 > 5.33*2 (10.66) means skewed
        # But 11 < 5.33*3 (16) means not hot
        assert len(result["skewed_partitions"]) > 0 or len(result["hot_partitions"]) > 0

        # Verify skew ratio (11 / 5.33 = ~2.06)
        assert result["skew_ratio"] >= 2.0

        # Verify recommendation
        assert result["recommendation"] is not None

    def test_analyze_partition_distribution_no_partitions(self) -> None:
        """Test partition analysis with non-partitioned table."""
        mb = 1024 * 1024

        # Create files without partitions
        data_files = [FileRef(f"file{i}.parquet", 10 * mb, None, "delta", "DATA") for i in range(5)]

        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        # Analyze partition distribution
        result = DeltaForensics.analyze_partition_distribution(snapshot)

        # Should return empty analysis
        assert result["partition_count"] == 0
        assert result["files_per_partition"] == {}
        assert result["recommendation"] is None


class TestTrackRewriteAmplification:
    """Tests for track_rewrite_amplification method."""

    def test_track_rewrite_amplification_increasing_trend(self, tmp_path: Path) -> None:
        """Test amplification tracking with increasing trend."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create 5 UPDATE operations with DECREASING amplification
        # (as bytes_removed increases, amplification decreases)
        for i in range(5):
            version_file = delta_log_path / f"{i:020d}.json"

            # Amplification decreases: 5x, 3.33x, 2.5x, 2x, 1.67x
            bytes_added = 100_000_000
            bytes_removed = 100_000_000 - (20_000_000 * (i + 1))

            version_data = {
                "commitInfo": {
                    "timestamp": 1705334625000 + (i * 3600000),  # 1 hour apart
                    "operation": "UPDATE",
                    "operationParameters": {},
                    "operationMetrics": {
                        "numBytesAdded": str(bytes_added),
                        "numBytesRemoved": str(bytes_removed),
                        "numOutputBytes": str(bytes_added),
                        "numAddedFiles": "5",
                        "numRemovedFiles": "5",
                        "numTargetRowsUpdated": "1000",
                    },
                }
            }

            with open(version_file, "w") as f:
                f.write(json.dumps(version_data) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 4

        # Track amplification
        result = DeltaForensics.track_rewrite_amplification(mock_table, max_versions=10)

        # Verify DML operations collected
        assert len(result["dml_operations"]) == 5

        # Verify trend detection (should be decreasing since amplification goes down)
        assert result["trend"] == "decreasing"

        # Verify highest amplification (first operation has highest)
        assert result["highest_amplification"] is not None
        assert result["highest_amplification"]["rewrite_amplification"] == 5.0

        # Verify average
        # Amplifications: 5.0, 3.33, 2.5, 2.0, 1.67 (approximately)
        assert result["average_amplification"] > 0

        # No recommendation for decreasing trend (getting better)
        # Recommendation only for increasing or extreme operations
        assert (
            result["recommendation"] is None or "decreasing" not in result["recommendation"].lower()
        )

    def test_track_rewrite_amplification_no_dml_operations(self, tmp_path: Path) -> None:
        """Test amplification tracking with no DML operations."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create only WRITE operations (not DML)
        for i in range(3):
            version_file = delta_log_path / f"{i:020d}.json"

            version_data = {
                "commitInfo": {
                    "timestamp": 1705334625000 + (i * 3600000),
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }

            with open(version_file, "w") as f:
                f.write(json.dumps(version_data) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 2

        # Track amplification
        result = DeltaForensics.track_rewrite_amplification(mock_table)

        # Should return empty results
        assert len(result["dml_operations"]) == 0
        assert result["trend"] == "stable"
        assert result["highest_amplification"] is None
        assert result["average_amplification"] == 0.0
        assert result["recommendation"] is None

    def test_track_rewrite_amplification_extreme_operations(self, tmp_path: Path) -> None:
        """Test amplification tracking with extreme amplification."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create UPDATE with 25x amplification
        version_file = delta_log_path / "00000000000000000000.json"

        version_data = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "UPDATE",
                "operationParameters": {},
                "operationMetrics": {
                    "numBytesAdded": "1000000000",  # 1GB
                    "numBytesRemoved": "960000000",  # 960MB
                    "numOutputBytes": "1000000000",
                    "numAddedFiles": "10",
                    "numRemovedFiles": "10",
                    "numTargetRowsUpdated": "100",
                },
            }
        }

        with open(version_file, "w") as f:
            f.write(json.dumps(version_data) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 0

        # Track amplification
        result = DeltaForensics.track_rewrite_amplification(mock_table)

        # Verify extreme operation detected
        assert len(result["extreme_operations"]) == 1
        assert result["extreme_operations"][0]["rewrite_amplification"] == 25.0

        # Verify recommendation
        assert result["recommendation"] is not None
        assert "extreme" in result["recommendation"].lower()


class TestAnalyzeStorageWasteEdgeCases:
    """Tests for edge cases in analyze_storage_waste method."""

    def test_analyze_storage_waste_with_file_uri_prefix(self, tmp_path: Path) -> None:
        """Test storage waste analysis with file:/// URI prefix."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version 0
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_action = {
            "add": {
                "path": "file1.parquet",
                "size": 10_000_000,
                "modificationTime": 1705334625000,
                "dataChange": True,
                "partitionValues": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Create mock DeltaTable with file:/// prefix
        mock_table = Mock()
        mock_table.table_uri = f"file:///{table_path}"

        # Analyze storage waste
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=0)

        # Should successfully parse despite file:/// prefix
        assert result["active_files"]["count"] == 1
        assert result["active_files"]["total_size_bytes"] == 10_000_000

    def test_analyze_storage_waste_with_file_double_slash_uri(self, tmp_path: Path) -> None:
        """Test storage waste analysis with file:// URI prefix."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version 0
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_action = {
            "add": {
                "path": "file1.parquet",
                "size": 10_000_000,
                "modificationTime": 1705334625000,
                "dataChange": True,
                "partitionValues": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Create mock DeltaTable with file:// prefix
        mock_table = Mock()
        mock_table.table_uri = f"file://{table_path}"

        # Analyze storage waste
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=0)

        # Should successfully parse despite file:// prefix
        assert result["active_files"]["count"] == 1

    def test_analyze_storage_waste_with_file_backslash_uri(self, tmp_path: Path) -> None:
        """Test storage waste analysis with file:\\ URI prefix (Windows)."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version 0
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_action = {
            "add": {
                "path": "file1.parquet",
                "size": 10_000_000,
                "modificationTime": 1705334625000,
                "dataChange": True,
                "partitionValues": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Create mock DeltaTable with file:\ prefix (Windows style)
        mock_table = Mock()
        mock_table.table_uri = f"file:\\{table_path}"

        # Analyze storage waste
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=0)

        # Should successfully parse despite file:\ prefix
        assert result["active_files"]["count"] == 1

    def test_analyze_storage_waste_with_missing_version_file(self, tmp_path: Path) -> None:
        """Test storage waste analysis when version file doesn't exist."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create version 0 and 2, but skip version 1
        for version in [0, 2]:
            version_file = delta_log_path / f"{version:020d}.json"
            version_data = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }

            add_action = {
                "add": {
                    "path": f"file{version}.parquet",
                    "size": 10_000_000,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }

            with open(version_file, "w") as f:
                f.write(json.dumps(version_data) + "\n")
                f.write(json.dumps(add_action) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)

        # Analyze storage waste (should skip missing version 1)
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=2)

        # Should have files from versions 0 and 2
        assert result["active_files"]["count"] == 2
        assert result["active_files"]["total_size_bytes"] == 20_000_000

    def test_analyze_storage_waste_with_file_resurrection(self, tmp_path: Path) -> None:
        """Test storage waste when a file is removed then re-added."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Version 0: Add file
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_action_v0 = {
            "add": {
                "path": "file1.parquet",
                "size": 10_000_000,
                "modificationTime": 1705334625000,
                "dataChange": True,
                "partitionValues": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            f.write(json.dumps(add_action_v0) + "\n")

        # Version 1: Remove file
        version_1 = {
            "commitInfo": {
                "timestamp": 1705420000000,
                "operation": "DELETE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        remove_action = {
            "remove": {
                "path": "file1.parquet",
                "deletionTimestamp": 1705420000000,
                "dataChange": True,
                "size": 10_000_000,
            }
        }

        with open(delta_log_path / "00000000000000000001.json", "w") as f:
            f.write(json.dumps(version_1) + "\n")
            f.write(json.dumps(remove_action) + "\n")

        # Version 2: Re-add same file (resurrection)
        version_2 = {
            "commitInfo": {
                "timestamp": 1705506400000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_action_v2 = {
            "add": {
                "path": "file1.parquet",
                "size": 10_000_000,
                "modificationTime": 1705506400000,
                "dataChange": True,
                "partitionValues": {},
            }
        }

        with open(delta_log_path / "00000000000000000002.json", "w") as f:
            f.write(json.dumps(version_2) + "\n")
            f.write(json.dumps(add_action_v2) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)

        # Analyze storage waste
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=2)

        # File should be in active (resurrected), not tombstoned
        assert result["active_files"]["count"] == 1
        assert result["tombstone_files"]["count"] == 0

    def test_analyze_storage_waste_with_remove_action_not_in_active(self, tmp_path: Path) -> None:
        """Test storage waste when remove action references file not in active set."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Version 0: Only remove action (file was added in earlier version we didn't parse)
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "DELETE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        remove_action = {
            "remove": {
                "path": "old_file.parquet",
                "deletionTimestamp": 1705334625000,
                "dataChange": True,
                "size": 15_000_000,  # Size is provided
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            f.write(json.dumps(remove_action) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)

        # Analyze storage waste
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=0)

        # File should be in tombstones even though it wasn't in active
        assert result["tombstone_files"]["count"] == 1
        assert result["tombstone_files"]["total_size_bytes"] == 15_000_000

    def test_analyze_storage_waste_with_parse_error(self, tmp_path: Path) -> None:
        """Test storage waste analysis when version file has parse error."""
        # Create mock Delta table structure
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Version 0: Valid file
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_action = {
            "add": {
                "path": "file1.parquet",
                "size": 10_000_000,
                "modificationTime": 1705334625000,
                "dataChange": True,
                "partitionValues": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Version 1: Invalid JSON (will cause parse error)
        with open(delta_log_path / "00000000000000000001.json", "w") as f:
            f.write("{ invalid json }\n")

        # Version 2: Valid file
        version_2 = {
            "commitInfo": {
                "timestamp": 1705506400000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        add_action_v2 = {
            "add": {
                "path": "file2.parquet",
                "size": 20_000_000,
                "modificationTime": 1705506400000,
                "dataChange": True,
                "partitionValues": {},
            }
        }

        with open(delta_log_path / "00000000000000000002.json", "w") as f:
            f.write(json.dumps(version_2) + "\n")
            f.write(json.dumps(add_action_v2) + "\n")

        # Create mock DeltaTable
        mock_table = Mock()
        mock_table.table_uri = str(table_path)

        # Analyze storage waste (should skip version 1 with parse error)
        result = DeltaForensics.analyze_storage_waste(mock_table, current_version=2)

        # Should have files from versions 0 and 2 (version 1 skipped)
        assert result["active_files"]["count"] == 2
        assert result["active_files"]["total_size_bytes"] == 30_000_000


class TestGenerateRecommendationsEdgeCases:
    """Tests for edge cases in generate_recommendations method."""

    def test_generate_recommendations_with_storage_waste(self, tmp_path: Path) -> None:
        """Test recommendations when table has significant storage waste."""
        mb = 1024 * 1024

        # Create snapshot with normal file sizes
        data_files = [FileRef(f"file{i}.parquet", 50 * mb, None, "delta", "DATA") for i in range(5)]

        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        # Create mock Delta table with tombstones
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Version 0: Add files
        version_0 = {
            "commitInfo": {
                "timestamp": 1705334625000,
                "operation": "WRITE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        with open(delta_log_path / "00000000000000000000.json", "w") as f:
            f.write(json.dumps(version_0) + "\n")
            for i in range(10):
                add_action = {
                    "add": {
                        "path": f"file{i}.parquet",
                        "size": 50 * mb,
                        "modificationTime": 1705334625000,
                        "dataChange": True,
                        "partitionValues": {},
                    }
                }
                f.write(json.dumps(add_action) + "\n")

        # Version 1: Remove 5 files (50% waste)
        version_1 = {
            "commitInfo": {
                "timestamp": 1705420000000,
                "operation": "DELETE",
                "operationParameters": {},
                "operationMetrics": {},
            }
        }

        with open(delta_log_path / "00000000000000000001.json", "w") as f:
            f.write(json.dumps(version_1) + "\n")
            for i in range(5):
                remove_action = {
                    "remove": {
                        "path": f"file{i}.parquet",
                        "deletionTimestamp": 1705420000000,
                        "dataChange": True,
                        "size": 50 * mb,
                    }
                }
                f.write(json.dumps(remove_action) + "\n")

        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 1

        # Generate recommendations
        recommendations = DeltaForensics.generate_recommendations(mock_table, snapshot)

        # Should recommend VACUUM
        vacuum_recs = [r for r in recommendations if r["type"] == "VACUUM"]
        assert len(vacuum_recs) > 0
        assert vacuum_recs[0]["priority"] == "high"

    def test_generate_recommendations_with_no_checkpoint(self, tmp_path: Path) -> None:
        """Test recommendations when table has no checkpoint."""
        mb = 1024 * 1024

        # Create snapshot
        data_files = [FileRef(f"file{i}.parquet", 50 * mb, None, "delta", "DATA") for i in range(5)]

        snapshot = SnapshotInfo(
            snapshot_id=20,  # Many versions
            parent_id=19,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=data_files,
            delete_files=[],
        )

        # Create mock Delta table with many versions but no checkpoint
        table_path = tmp_path / "test_table"
        delta_log_path = table_path / "_delta_log"
        delta_log_path.mkdir(parents=True)

        # Create 20 version files (no checkpoint)
        for i in range(21):
            version_file = delta_log_path / f"{i:020d}.json"
            version_data = {
                "commitInfo": {
                    "timestamp": 1705334625000 + (i * 3600000),
                    "operation": "WRITE",
                    "operationParameters": {},
                    "operationMetrics": {},
                }
            }

            with open(version_file, "w") as f:
                f.write(json.dumps(version_data) + "\n")

        mock_table = Mock()
        mock_table.table_uri = str(table_path)
        mock_table.version.return_value = 20

        # Generate recommendations
        recommendations = DeltaForensics.generate_recommendations(mock_table, snapshot)

        # Should recommend CHECKPOINT
        checkpoint_recs = [r for r in recommendations if r["type"] == "CHECKPOINT"]
        assert len(checkpoint_recs) > 0
        assert checkpoint_recs[0]["priority"] == "high"
