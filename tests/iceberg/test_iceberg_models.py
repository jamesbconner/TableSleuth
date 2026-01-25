"""Tests for Iceberg data models."""

from __future__ import annotations

import pytest

from tablesleuth.models.iceberg import (
    IcebergSnapshotInfo,
    PerformanceComparison,
    QueryPerformanceMetrics,
    SnapshotComparison,
)


class TestIcebergSnapshotInfo:
    """Tests for IcebergSnapshotInfo model."""

    def test_has_deletes_with_delete_files(self):
        """Test has_deletes property when delete files present."""
        snapshot = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=5,
            total_size_bytes=1000000,
            position_deletes=50,
            equality_deletes=0,
        )

        assert snapshot.has_deletes is True

    def test_has_deletes_without_delete_files(self):
        """Test has_deletes property when no delete files."""
        snapshot = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=1000000,
            position_deletes=0,
            equality_deletes=0,
        )

        assert snapshot.has_deletes is False

    def test_delete_ratio_calculation(self):
        """Test delete ratio calculation."""
        snapshot = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="DELETE",
            summary={},
            manifest_list="s3://bucket/manifest.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=5,
            total_size_bytes=1000000,
            position_deletes=100,
            equality_deletes=50,
        )

        # (100 + 50) / 1000 * 100 = 15%
        assert snapshot.delete_ratio == 15.0

    def test_delete_ratio_zero_records(self):
        """Test delete ratio when total records is zero."""
        snapshot = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest.avro",
            schema_id=0,
            total_records=0,
            total_data_files=0,
            total_delete_files=0,
            total_size_bytes=0,
            position_deletes=0,
            equality_deletes=0,
        )

        assert snapshot.delete_ratio == 0.0

    def test_read_amplification_calculation(self):
        """Test read amplification calculation."""
        snapshot = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="DELETE",
            summary={},
            manifest_list="s3://bucket/manifest.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=5,
            total_size_bytes=1000000,
            position_deletes=100,
            equality_deletes=0,
        )

        # (10 + 5) / 10 = 1.5x
        assert snapshot.read_amplification == 1.5

    def test_read_amplification_no_data_files(self):
        """Test read amplification when no data files."""
        snapshot = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest.avro",
            schema_id=0,
            total_records=0,
            total_data_files=0,
            total_delete_files=0,
            total_size_bytes=0,
            position_deletes=0,
            equality_deletes=0,
        )

        assert snapshot.read_amplification == 1.0


class TestSnapshotComparison:
    """Tests for SnapshotComparison model."""

    def test_needs_compaction_high_delete_ratio(self):
        """Test needs_compaction when delete ratio is high."""
        snapshot_a = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest1.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=1000000,
            position_deletes=0,
            equality_deletes=0,
        )

        snapshot_b = IcebergSnapshotInfo(
            snapshot_id=2,
            parent_snapshot_id=1,
            timestamp_ms=2000000,
            operation="DELETE",
            summary={},
            manifest_list="s3://bucket/manifest2.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=5,
            total_size_bytes=1000000,
            position_deletes=150,  # 15% delete ratio
            equality_deletes=0,
        )

        comparison = SnapshotComparison(
            snapshot_a=snapshot_a,
            snapshot_b=snapshot_b,
            data_files_added=0,
            data_files_removed=0,
            delete_files_added=5,
            delete_files_removed=0,
            records_added=0,
            records_deleted=150,
            records_delta=-150,
            size_added_bytes=0,
            size_removed_bytes=0,
            size_delta_bytes=0,
            delete_ratio_change=15.0,
            read_amplification_change=0.5,
        )

        assert comparison.needs_compaction is True

    def test_needs_compaction_high_read_amplification(self):
        """Test needs_compaction when read amplification is high."""
        snapshot_a = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest1.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=1000000,
            position_deletes=0,
            equality_deletes=0,
        )

        snapshot_b = IcebergSnapshotInfo(
            snapshot_id=2,
            parent_snapshot_id=1,
            timestamp_ms=2000000,
            operation="DELETE",
            summary={},
            manifest_list="s3://bucket/manifest2.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=3,  # 1.3x read amplification
            total_size_bytes=1000000,
            position_deletes=50,  # 5% delete ratio
            equality_deletes=0,
        )

        comparison = SnapshotComparison(
            snapshot_a=snapshot_a,
            snapshot_b=snapshot_b,
            data_files_added=0,
            data_files_removed=0,
            delete_files_added=3,
            delete_files_removed=0,
            records_added=0,
            records_deleted=50,
            records_delta=-50,
            size_added_bytes=0,
            size_removed_bytes=0,
            size_delta_bytes=0,
            delete_ratio_change=5.0,
            read_amplification_change=0.3,
        )

        assert comparison.needs_compaction is True

    def test_needs_compaction_low_overhead(self):
        """Test needs_compaction when overhead is low."""
        snapshot_a = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest1.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=1000000,
            position_deletes=0,
            equality_deletes=0,
        )

        snapshot_b = IcebergSnapshotInfo(
            snapshot_id=2,
            parent_snapshot_id=1,
            timestamp_ms=2000000,
            operation="DELETE",
            summary={},
            manifest_list="s3://bucket/manifest2.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=1,  # 1.1x read amplification
            total_size_bytes=1000000,
            position_deletes=30,  # 3% delete ratio
            equality_deletes=0,
        )

        comparison = SnapshotComparison(
            snapshot_a=snapshot_a,
            snapshot_b=snapshot_b,
            data_files_added=0,
            data_files_removed=0,
            delete_files_added=1,
            delete_files_removed=0,
            records_added=0,
            records_deleted=30,
            records_delta=-30,
            size_added_bytes=0,
            size_removed_bytes=0,
            size_delta_bytes=0,
            delete_ratio_change=3.0,
            read_amplification_change=0.1,
        )

        assert comparison.needs_compaction is False

    def test_compaction_recommendation_message(self):
        """Test compaction recommendation message generation."""
        snapshot_a = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest1.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=1000000,
            position_deletes=0,
            equality_deletes=0,
        )

        snapshot_b = IcebergSnapshotInfo(
            snapshot_id=2,
            parent_snapshot_id=1,
            timestamp_ms=2000000,
            operation="DELETE",
            summary={},
            manifest_list="s3://bucket/manifest2.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=5,
            total_size_bytes=1000000,
            position_deletes=150,
            equality_deletes=0,
        )

        comparison = SnapshotComparison(
            snapshot_a=snapshot_a,
            snapshot_b=snapshot_b,
            data_files_added=0,
            data_files_removed=0,
            delete_files_added=5,
            delete_files_removed=0,
            records_added=0,
            records_deleted=150,
            records_delta=-150,
            size_added_bytes=0,
            size_removed_bytes=0,
            size_delta_bytes=0,
            delete_ratio_change=15.0,
            read_amplification_change=0.5,
        )

        recommendation = comparison.compaction_recommendation
        assert "Compaction recommended" in recommendation
        assert "Delete ratio is 15.0%" in recommendation
        assert "Read amplification is 1.50x" in recommendation


class TestQueryPerformanceMetrics:
    """Tests for QueryPerformanceMetrics model."""

    def test_scan_efficiency_calculation(self):
        """Test scan efficiency calculation."""
        metrics = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        # 500 / 1000 * 100 = 50%
        assert metrics.scan_efficiency == 50.0

    def test_scan_efficiency_zero_rows_scanned(self):
        """Test scan efficiency when no rows scanned."""
        metrics = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=10.0,
        )

        assert metrics.scan_efficiency == 100.0


class TestPerformanceComparison:
    """Tests for PerformanceComparison model."""

    def test_execution_time_delta_pct(self):
        """Test execution time delta percentage calculation."""
        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        metrics_b = QueryPerformanceMetrics(
            execution_time_ms=150.0,
            files_scanned=15,
            bytes_scanned=1500000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=60.0,
        )

        comparison = PerformanceComparison(
            query="SELECT * FROM table",
            table_a_name="snap_1",
            table_b_name="snap_2",
            metrics_a=metrics_a,
            metrics_b=metrics_b,
        )

        # (150 - 100) / 100 * 100 = 50%
        assert comparison.execution_time_delta_pct == 50.0

    def test_files_scanned_delta_pct(self):
        """Test files scanned delta percentage calculation."""
        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        metrics_b = QueryPerformanceMetrics(
            execution_time_ms=150.0,
            files_scanned=15,
            bytes_scanned=1500000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=60.0,
        )

        comparison = PerformanceComparison(
            query="SELECT * FROM table",
            table_a_name="snap_1",
            table_b_name="snap_2",
            metrics_a=metrics_a,
            metrics_b=metrics_b,
        )

        # (15 - 10) / 10 * 100 = 50%
        assert comparison.files_scanned_delta_pct == 50.0

    def test_analysis_slower_query(self):
        """Test analysis text for slower query."""
        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        metrics_b = QueryPerformanceMetrics(
            execution_time_ms=150.0,
            files_scanned=15,
            bytes_scanned=1500000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=60.0,
        )

        comparison = PerformanceComparison(
            query="SELECT * FROM table",
            table_a_name="snap_1",
            table_b_name="snap_2",
            metrics_a=metrics_a,
            metrics_b=metrics_b,
        )

        analysis = comparison.analysis
        assert "slower" in analysis.lower()
        assert "snap_2" in analysis
        # New comprehensive analysis format
        assert "5 more files to scan" in analysis
        assert "+50.0%" in analysis

    def test_analysis_with_mor_overhead(self):
        """Test analysis text with MOR overhead."""
        snapshot_a = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest1.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=1000000,
            position_deletes=0,
            equality_deletes=0,
        )

        snapshot_b = IcebergSnapshotInfo(
            snapshot_id=2,
            parent_snapshot_id=1,
            timestamp_ms=2000000,
            operation="DELETE",
            summary={},
            manifest_list="s3://bucket/manifest2.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=5,
            total_size_bytes=1000000,
            position_deletes=150,
            equality_deletes=0,
        )

        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        metrics_b = QueryPerformanceMetrics(
            execution_time_ms=150.0,
            files_scanned=15,
            bytes_scanned=1500000,
            rows_scanned=1000,
            rows_returned=400,
            memory_peak_mb=60.0,
        )

        comparison = PerformanceComparison(
            query="SELECT * FROM table",
            table_a_name="snap_1",
            table_b_name="snap_2",
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            snapshot_a_info=snapshot_a,
            snapshot_b_info=snapshot_b,
        )

        analysis = comparison.analysis
        assert "slower" in analysis.lower()
        assert "snap_2" in analysis
        # Should mention MOR overhead since snapshot_b has delete files
        assert "MOR overhead" in analysis
        assert "5 delete files" in analysis
        assert "read amplification" in analysis.lower()
        # Should also have recommendation
        assert "Recommendation" in analysis or "compaction" in analysis.lower()

    def test_analysis_order_agnostic(self):
        """Test that analysis works regardless of snapshot order."""
        snapshot_a = IcebergSnapshotInfo(
            snapshot_id=2,
            parent_snapshot_id=1,
            timestamp_ms=2000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest2.avro",
            schema_id=0,
            total_records=2000,
            total_data_files=20,
            total_delete_files=0,
            total_size_bytes=2000000,
            position_deletes=0,
            equality_deletes=0,
        )

        snapshot_b = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=1000000,
            operation="APPEND",
            summary={},
            manifest_list="s3://bucket/manifest1.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=1000000,
            position_deletes=0,
            equality_deletes=0,
        )

        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=150.0,
            files_scanned=20,
            bytes_scanned=2000000,
            rows_scanned=2000,
            rows_returned=1000,
            memory_peak_mb=60.0,
        )

        metrics_b = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        comparison = PerformanceComparison(
            query="SELECT * FROM table",
            table_a_name="snap_newer",
            table_b_name="snap_older",
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            snapshot_a_info=snapshot_a,
            snapshot_b_info=snapshot_b,
        )

        analysis = comparison.analysis
        # Should correctly identify snap_newer as slower (even though it's newer)
        assert "slower" in analysis.lower()
        assert "snap_newer" in analysis
        # Should mention data volume differences
        assert "more files" in analysis or "more data" in analysis or "more records" in analysis

    def test_analysis_similar_performance(self):
        """Test analysis text for similar performance."""
        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        metrics_b = QueryPerformanceMetrics(
            execution_time_ms=105.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        comparison = PerformanceComparison(
            query="SELECT * FROM table",
            table_a_name="snap_1",
            table_b_name="snap_2",
            metrics_a=metrics_a,
            metrics_b=metrics_b,
        )

        analysis = comparison.analysis
        assert "similar" in analysis.lower()
