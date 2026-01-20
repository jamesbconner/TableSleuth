"""Unit tests for Delta Lake forensic analysis services."""

from __future__ import annotations

import pytest

from tablesleuth.models import FileRef, SnapshotInfo
from tablesleuth.services.delta_forensics import DeltaForensics


class TestAnalyzeFileSizes:
    """Unit tests for DeltaForensics.analyze_file_sizes method."""

    def test_empty_snapshot(self):
        """Test analyze_file_sizes with empty snapshot (no files)."""
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        assert result["histogram"] == {
            "< 1MB": 0,
            "1-10MB": 0,
            "10-100MB": 0,
            "> 100MB": 0,
        }
        assert result["small_file_count"] == 0
        assert result["small_file_percentage"] == 0.0
        assert result["optimization_opportunity"] == 0
        assert result["min_size_bytes"] == 0
        assert result["max_size_bytes"] == 0
        assert result["median_size_bytes"] == 0
        assert result["total_size_bytes"] == 0
        assert result["total_file_count"] == 0

    def test_single_small_file(self):
        """Test analyze_file_sizes with a single small file."""
        MB = 1024 * 1024
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path="file1.parquet", file_size_bytes=5 * MB),
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        assert result["histogram"]["1-10MB"] == 1
        assert result["small_file_count"] == 1
        assert result["small_file_percentage"] == 100.0
        assert result["optimization_opportunity"] == 0  # 1 * 0.8 = 0.8 -> 0
        assert result["min_size_bytes"] == 5 * MB
        assert result["max_size_bytes"] == 5 * MB
        assert result["median_size_bytes"] == 5 * MB
        assert result["total_size_bytes"] == 5 * MB
        assert result["total_file_count"] == 1

    def test_mixed_file_sizes(self):
        """Test analyze_file_sizes with mixed file sizes across all buckets."""
        MB = 1024 * 1024
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path="tiny.parquet", file_size_bytes=512 * 1024),  # < 1MB
                FileRef(path="small1.parquet", file_size_bytes=2 * MB),  # 1-10MB
                FileRef(path="small2.parquet", file_size_bytes=5 * MB),  # 1-10MB
                FileRef(path="medium.parquet", file_size_bytes=50 * MB),  # 10-100MB
                FileRef(path="large.parquet", file_size_bytes=200 * MB),  # > 100MB
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        assert result["histogram"]["< 1MB"] == 1
        assert result["histogram"]["1-10MB"] == 2
        assert result["histogram"]["10-100MB"] == 1
        assert result["histogram"]["> 100MB"] == 1
        assert result["small_file_count"] == 3  # < 10MB
        assert result["small_file_percentage"] == 60.0  # 3/5 * 100
        assert result["optimization_opportunity"] == 2  # 3 * 0.8 = 2.4 -> 2
        assert result["min_size_bytes"] == 512 * 1024
        assert result["max_size_bytes"] == 200 * MB
        assert result["total_size_bytes"] == (512 * 1024) + (2 * MB) + (5 * MB) + (50 * MB) + (
            200 * MB
        )
        assert result["total_file_count"] == 5

    def test_all_small_files(self):
        """Test analyze_file_sizes when all files are small (< 10MB)."""
        MB = 1024 * 1024
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path=f"small{i}.parquet", file_size_bytes=i * MB)
                for i in range(1, 6)  # 1MB, 2MB, 3MB, 4MB, 5MB
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        assert result["small_file_count"] == 5
        assert result["small_file_percentage"] == 100.0
        assert result["optimization_opportunity"] == 4  # 5 * 0.8 = 4
        assert result["histogram"]["< 1MB"] == 0
        assert result["histogram"]["1-10MB"] == 5
        assert result["histogram"]["10-100MB"] == 0
        assert result["histogram"]["> 100MB"] == 0

    def test_all_large_files(self):
        """Test analyze_file_sizes when all files are large (>= 10MB)."""
        MB = 1024 * 1024
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path="medium1.parquet", file_size_bytes=50 * MB),
                FileRef(path="medium2.parquet", file_size_bytes=75 * MB),
                FileRef(path="large1.parquet", file_size_bytes=150 * MB),
                FileRef(path="large2.parquet", file_size_bytes=250 * MB),
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        assert result["small_file_count"] == 0
        assert result["small_file_percentage"] == 0.0
        assert result["optimization_opportunity"] == 0
        assert result["histogram"]["< 1MB"] == 0
        assert result["histogram"]["1-10MB"] == 0
        assert result["histogram"]["10-100MB"] == 2
        assert result["histogram"]["> 100MB"] == 2

    def test_boundary_values(self):
        """Test analyze_file_sizes with exact boundary values."""
        MB = 1024 * 1024
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path="exactly_1mb.parquet", file_size_bytes=1 * MB),
                FileRef(path="exactly_10mb.parquet", file_size_bytes=10 * MB),
                FileRef(path="exactly_100mb.parquet", file_size_bytes=100 * MB),
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        # Boundary values should be in the higher bucket (>= comparison)
        assert result["histogram"]["< 1MB"] == 0
        assert result["histogram"]["1-10MB"] == 1  # 1MB
        assert result["histogram"]["10-100MB"] == 1  # 10MB
        assert result["histogram"]["> 100MB"] == 1  # 100MB
        assert result["small_file_count"] == 1  # Only < 10MB

    def test_median_calculation_odd_count(self):
        """Test median calculation with odd number of files."""
        MB = 1024 * 1024
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path="file1.parquet", file_size_bytes=10 * MB),
                FileRef(path="file2.parquet", file_size_bytes=20 * MB),
                FileRef(path="file3.parquet", file_size_bytes=30 * MB),
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        assert result["median_size_bytes"] == 20 * MB

    def test_median_calculation_even_count(self):
        """Test median calculation with even number of files."""
        MB = 1024 * 1024
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path="file1.parquet", file_size_bytes=10 * MB),
                FileRef(path="file2.parquet", file_size_bytes=20 * MB),
                FileRef(path="file3.parquet", file_size_bytes=30 * MB),
                FileRef(path="file4.parquet", file_size_bytes=40 * MB),
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        # Median of [10, 20, 30, 40] is (20 + 30) / 2 = 25
        assert result["median_size_bytes"] == 25 * MB

    def test_optimization_opportunity_calculation(self):
        """Test optimization opportunity calculation with various small file counts."""
        MB = 1024 * 1024

        # Test with 10 small files: 10 * 0.8 = 8
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path=f"small{i}.parquet", file_size_bytes=i * MB)
                for i in range(1, 11)  # 1MB to 10MB (but 10MB is not small)
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        # Only files < 10MB are small (1-9MB = 9 files)
        assert result["small_file_count"] == 9
        assert result["optimization_opportunity"] == 7  # 9 * 0.8 = 7.2 -> 7

    def test_percentage_rounding(self):
        """Test that small_file_percentage is properly rounded to 2 decimal places."""
        MB = 1024 * 1024
        snapshot = SnapshotInfo(
            snapshot_id=1,
            parent_id=0,
            timestamp_ms=1705334625000,
            operation="WRITE",
            summary={},
            data_files=[
                FileRef(path="small1.parquet", file_size_bytes=1 * MB),
                FileRef(path="small2.parquet", file_size_bytes=2 * MB),
                FileRef(path="large1.parquet", file_size_bytes=100 * MB),
            ],
        )

        result = DeltaForensics.analyze_file_sizes(snapshot)

        # 2/3 * 100 = 66.666... should be rounded to 66.67
        assert result["small_file_percentage"] == 66.67
