"""Tests for MOR (Merge-on-Read) service."""

import pytest

from tablesleuth.models import FileRef, SnapshotInfo
from tablesleuth.services.mor_service import (
    FileMorImpact,
    SnapshotMorSummary,
    _partition_key,
    estimate_mor,
)


def create_snapshot(
    snapshot_id: int,
    data_files: list[FileRef],
    delete_files: list[FileRef],
) -> SnapshotInfo:
    """Helper to create SnapshotInfo with required fields."""
    return SnapshotInfo(
        snapshot_id=snapshot_id,
        parent_id=None,
        timestamp_ms=1700000000000,
        operation="append",
        summary={},
        data_files=data_files,
        delete_files=delete_files,
    )


class TestPartitionKey:
    """Tests for _partition_key helper function."""

    def test_empty_partition(self):
        """Test partition key for empty partition."""
        result = _partition_key({})
        assert result == ""

    def test_single_partition_field(self):
        """Test partition key with single field."""
        result = _partition_key({"year": "2024"})
        assert result == "year=2024"

    def test_multiple_partition_fields(self):
        """Test partition key with multiple fields."""
        result = _partition_key({"year": "2024", "month": "11", "day": "29"})
        # Should be sorted alphabetically
        assert result == "day=29|month=11|year=2024"

    def test_partition_fields_sorted(self):
        """Test that partition fields are sorted consistently."""
        partition1 = {"b": "2", "a": "1", "c": "3"}
        partition2 = {"c": "3", "a": "1", "b": "2"}

        result1 = _partition_key(partition1)
        result2 = _partition_key(partition2)

        # Same partition, different order should produce same key
        assert result1 == result2
        assert result1 == "a=1|b=2|c=3"

    def test_partition_with_numeric_values(self):
        """Test partition key with numeric values."""
        result = _partition_key({"year": 2024, "month": 11})
        assert "year=2024" in result
        assert "month=11" in result


class TestFileMorImpact:
    """Tests for FileMorImpact dataclass."""

    def test_create_file_mor_impact(self):
        """Test creating FileMorImpact instance."""
        impact = FileMorImpact(
            file_path="s3://bucket/data.parquet",
            base_rows=1000,
            delete_rows_estimate=100,
            effective_rows_estimate=900,
            num_position_delete_files=1,
            num_equality_delete_files=0,
        )

        assert impact.file_path == "s3://bucket/data.parquet"
        assert impact.base_rows == 1000
        assert impact.delete_rows_estimate == 100
        assert impact.effective_rows_estimate == 900
        assert impact.num_position_delete_files == 1
        assert impact.num_equality_delete_files == 0


class TestSnapshotMorSummary:
    """Tests for SnapshotMorSummary dataclass."""

    def test_create_snapshot_mor_summary(self):
        """Test creating SnapshotMorSummary instance."""
        file_impact = FileMorImpact(
            file_path="s3://bucket/data.parquet",
            base_rows=1000,
            delete_rows_estimate=100,
            effective_rows_estimate=900,
            num_position_delete_files=1,
            num_equality_delete_files=0,
        )

        summary = SnapshotMorSummary(
            snapshot_id=12345,
            total_base_rows=1000,
            total_delete_rows_estimate=100,
            total_effective_rows_estimate=900,
            num_base_files=1,
            num_delete_files=1,
            file_impacts=[file_impact],
        )

        assert summary.snapshot_id == 12345
        assert summary.total_base_rows == 1000
        assert summary.total_delete_rows_estimate == 100
        assert summary.total_effective_rows_estimate == 900
        assert summary.num_base_files == 1
        assert summary.num_delete_files == 1
        assert len(summary.file_impacts) == 1


class TestEstimateMor:
    """Tests for estimate_mor function."""

    def test_estimate_mor_no_deletes(self):
        """Test MOR estimation with no delete files."""
        snapshot = create_snapshot(
            snapshot_id=1,
            data_files=[
                FileRef(
                    path="s3://bucket/file1.parquet",
                    file_size_bytes=1024,
                    record_count=1000,
                    partition={},
                ),
                FileRef(
                    path="s3://bucket/file2.parquet",
                    file_size_bytes=2048,
                    record_count=2000,
                    partition={},
                ),
            ],
            delete_files=[],
        )

        result = estimate_mor(snapshot)

        assert result.snapshot_id == 1
        assert result.total_base_rows == 3000
        assert result.total_delete_rows_estimate == 0
        assert result.total_effective_rows_estimate == 3000
        assert result.num_base_files == 2
        assert result.num_delete_files == 0
        assert len(result.file_impacts) == 2

    def test_estimate_mor_with_position_deletes(self):
        """Test MOR estimation with position delete files."""
        snapshot = create_snapshot(
            snapshot_id=2,
            data_files=[
                FileRef(
                    path="s3://bucket/data.parquet",
                    file_size_bytes=1024,
                    record_count=1000,
                    partition={"year": "2024"},
                ),
            ],
            delete_files=[
                FileRef(
                    path="s3://bucket/delete.parquet",
                    file_size_bytes=512,
                    record_count=100,
                    partition={"year": "2024"},
                    content_type="POSITION_DELETES",
                ),
            ],
        )

        result = estimate_mor(snapshot)

        assert result.snapshot_id == 2
        assert result.total_base_rows == 1000
        assert result.total_delete_rows_estimate == 100
        assert result.total_effective_rows_estimate == 900
        assert result.num_base_files == 1
        assert result.num_delete_files == 1

        # Check file impact
        impact = result.file_impacts[0]
        assert impact.file_path == "s3://bucket/data.parquet"
        assert impact.base_rows == 1000
        assert impact.delete_rows_estimate == 100
        assert impact.effective_rows_estimate == 900
        assert impact.num_position_delete_files == 1
        assert impact.num_equality_delete_files == 0

    def test_estimate_mor_with_equality_deletes(self):
        """Test MOR estimation with equality delete files."""
        snapshot = create_snapshot(
            snapshot_id=3,
            data_files=[
                FileRef(
                    path="s3://bucket/data.parquet",
                    file_size_bytes=1024,
                    record_count=1000,
                    partition={"year": "2024"},
                ),
            ],
            delete_files=[
                FileRef(
                    path="s3://bucket/eq_delete.parquet",
                    file_size_bytes=256,
                    record_count=50,
                    partition={"year": "2024"},
                    content_type="EQUALITY_DELETES",
                ),
            ],
        )

        result = estimate_mor(snapshot)

        impact = result.file_impacts[0]
        assert impact.num_position_delete_files == 0
        assert impact.num_equality_delete_files == 1
        assert impact.delete_rows_estimate == 50

    def test_estimate_mor_with_mixed_delete_types(self):
        """Test MOR estimation with both position and equality deletes."""
        snapshot = create_snapshot(
            snapshot_id=4,
            data_files=[
                FileRef(
                    path="s3://bucket/data.parquet",
                    file_size_bytes=1024,
                    record_count=1000,
                    partition={"year": "2024"},
                ),
            ],
            delete_files=[
                FileRef(
                    path="s3://bucket/pos_delete.parquet",
                    file_size_bytes=256,
                    record_count=30,
                    partition={"year": "2024"},
                    content_type="POSITION_DELETES",
                ),
                FileRef(
                    path="s3://bucket/eq_delete.parquet",
                    file_size_bytes=256,
                    record_count=20,
                    partition={"year": "2024"},
                    content_type="EQUALITY_DELETES",
                ),
            ],
        )

        result = estimate_mor(snapshot)

        assert result.total_delete_rows_estimate == 50
        assert result.total_effective_rows_estimate == 950

        impact = result.file_impacts[0]
        assert impact.num_position_delete_files == 1
        assert impact.num_equality_delete_files == 1

    def test_estimate_mor_multiple_partitions(self):
        """Test MOR estimation with multiple partitions."""
        snapshot = create_snapshot(
            snapshot_id=5,
            data_files=[
                FileRef(
                    path="s3://bucket/data1.parquet",
                    file_size_bytes=1024,
                    record_count=1000,
                    partition={"year": "2024", "month": "11"},
                ),
                FileRef(
                    path="s3://bucket/data2.parquet",
                    file_size_bytes=1024,
                    record_count=1500,
                    partition={"year": "2024", "month": "12"},
                ),
            ],
            delete_files=[
                FileRef(
                    path="s3://bucket/delete1.parquet",
                    file_size_bytes=256,
                    record_count=100,
                    partition={"year": "2024", "month": "11"},
                    content_type="POSITION_DELETES",
                ),
                FileRef(
                    path="s3://bucket/delete2.parquet",
                    file_size_bytes=256,
                    record_count=200,
                    partition={"year": "2024", "month": "12"},
                    content_type="POSITION_DELETES",
                ),
            ],
        )

        result = estimate_mor(snapshot)

        assert result.total_base_rows == 2500
        assert result.total_delete_rows_estimate == 300
        assert result.total_effective_rows_estimate == 2200
        assert len(result.file_impacts) == 2

        # Each file should only be affected by deletes in its partition
        impact1 = next(i for i in result.file_impacts if "data1" in i.file_path)
        assert impact1.delete_rows_estimate == 100

        impact2 = next(i for i in result.file_impacts if "data2" in i.file_path)
        assert impact2.delete_rows_estimate == 200

    def test_estimate_mor_delete_exceeds_base_rows(self):
        """Test MOR estimation when deletes exceed base rows."""
        snapshot = create_snapshot(
            snapshot_id=6,
            data_files=[
                FileRef(
                    path="s3://bucket/data.parquet",
                    file_size_bytes=1024,
                    record_count=100,
                    partition={},
                ),
            ],
            delete_files=[
                FileRef(
                    path="s3://bucket/delete.parquet",
                    file_size_bytes=512,
                    record_count=200,  # More deletes than base rows
                    partition={},
                    content_type="POSITION_DELETES",
                ),
            ],
        )

        result = estimate_mor(snapshot)

        # Should not go negative
        assert result.total_effective_rows_estimate == 0
        assert result.file_impacts[0].effective_rows_estimate == 0

    def test_estimate_mor_with_none_record_counts(self):
        """Test MOR estimation with None record counts."""
        snapshot = create_snapshot(
            snapshot_id=7,
            data_files=[
                FileRef(
                    path="s3://bucket/data.parquet",
                    file_size_bytes=1024,
                    record_count=None,  # Unknown record count
                    partition={},
                ),
            ],
            delete_files=[
                FileRef(
                    path="s3://bucket/delete.parquet",
                    file_size_bytes=512,
                    record_count=None,  # Unknown record count
                    partition={},
                    content_type="POSITION_DELETES",
                ),
            ],
        )

        result = estimate_mor(snapshot)

        # Should treat None as 0
        assert result.total_base_rows == 0
        assert result.total_delete_rows_estimate == 0
        assert result.total_effective_rows_estimate == 0

    def test_estimate_mor_empty_snapshot(self):
        """Test MOR estimation with empty snapshot."""
        snapshot = create_snapshot(
            snapshot_id=8,
            data_files=[],
            delete_files=[],
        )

        result = estimate_mor(snapshot)

        assert result.snapshot_id == 8
        assert result.total_base_rows == 0
        assert result.total_delete_rows_estimate == 0
        assert result.total_effective_rows_estimate == 0
        assert result.num_base_files == 0
        assert result.num_delete_files == 0
        assert len(result.file_impacts) == 0

    def test_estimate_mor_unmatched_partitions(self):
        """Test MOR estimation when delete files don't match data file partitions."""
        snapshot = create_snapshot(
            snapshot_id=9,
            data_files=[
                FileRef(
                    path="s3://bucket/data.parquet",
                    file_size_bytes=1024,
                    record_count=1000,
                    partition={"year": "2024"},
                ),
            ],
            delete_files=[
                FileRef(
                    path="s3://bucket/delete.parquet",
                    file_size_bytes=256,
                    record_count=100,
                    partition={"year": "2023"},  # Different partition
                    content_type="POSITION_DELETES",
                ),
            ],
        )

        result = estimate_mor(snapshot)

        # Delete file shouldn't affect data file in different partition
        impact = result.file_impacts[0]
        assert impact.delete_rows_estimate == 0
        assert impact.effective_rows_estimate == 1000
        assert impact.num_position_delete_files == 0

    def test_estimate_mor_multiple_files_same_partition(self):
        """Test MOR estimation with multiple data files in same partition."""
        snapshot = create_snapshot(
            snapshot_id=10,
            data_files=[
                FileRef(
                    path="s3://bucket/data1.parquet",
                    file_size_bytes=1024,
                    record_count=1000,
                    partition={"year": "2024"},
                ),
                FileRef(
                    path="s3://bucket/data2.parquet",
                    file_size_bytes=1024,
                    record_count=1500,
                    partition={"year": "2024"},
                ),
            ],
            delete_files=[
                FileRef(
                    path="s3://bucket/delete.parquet",
                    file_size_bytes=256,
                    record_count=100,
                    partition={"year": "2024"},
                    content_type="POSITION_DELETES",
                ),
            ],
        )

        result = estimate_mor(snapshot)

        # Both files should be affected by the same delete file
        assert result.total_base_rows == 2500
        # Delete count is applied to each file (this is an estimate)
        assert result.total_delete_rows_estimate == 200  # 100 per file
        assert len(result.file_impacts) == 2

        for impact in result.file_impacts:
            assert impact.delete_rows_estimate == 100
            assert impact.num_position_delete_files == 1
