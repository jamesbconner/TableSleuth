"""Unit tests for GizmoDuckDbProfiler (mocked, no server required)."""

from unittest.mock import Mock, patch

import pytest

from tablesleuth.models import ColumnProfile, FileRef, SnapshotInfo
from tablesleuth.models.iceberg import QueryPerformanceMetrics
from tablesleuth.services.profiling.gizmo_duckdb import (
    GizmoDuckDbProfiler,
    _clean_file_path,
)


class TestCleanFilePath:
    """Tests for _clean_file_path helper function."""

    def test_clean_file_uri(self):
        """Test removing file:// prefix."""
        assert _clean_file_path("file:///path/to/file.parquet") == "/path/to/file.parquet"

    def test_clean_file_uri_windows(self):
        """Test removing file:// prefix from Windows path."""
        assert _clean_file_path("file:///C:/path/to/file.parquet") == "/C:/path/to/file.parquet"

    def test_preserve_s3_path(self):
        """Test S3 paths are preserved."""
        assert _clean_file_path("s3://bucket/file.parquet") == "s3://bucket/file.parquet"

    def test_preserve_regular_path(self):
        """Test regular paths are preserved."""
        assert _clean_file_path("/path/to/file.parquet") == "/path/to/file.parquet"

    def test_empty_string(self):
        """Test empty string handling."""
        assert _clean_file_path("") == ""


class TestGizmoDuckDbProfilerInit:
    """Tests for GizmoDuckDbProfiler initialization."""

    def test_init_with_tls(self):
        """Test initialization with TLS enabled."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            tls_skip_verify=True,
        )

        assert profiler._uri == "grpc+tls://localhost:31337"
        assert profiler._username == "test_user"
        assert profiler._password == "test_pass"
        assert profiler._tls_skip_verify is True

    def test_init_without_tls(self):
        """Test initialization without TLS."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test_user",
            password="test_pass",
            tls_skip_verify=False,
        )

        assert profiler._uri == "grpc://localhost:31337"
        assert profiler._tls_skip_verify is False


class TestRegisterFileView:
    """Tests for register_file_view method."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test",
            password="test",
        )

    def test_register_single_file(self, profiler):
        """Test registering a single file."""
        view_name = profiler.register_file_view(
            ["/path/to/file.parquet"],
            view_name="test_view",
        )

        assert view_name == "test_view"
        assert hasattr(profiler, "_view_paths")
        assert "test_view" in profiler._view_paths
        assert profiler._view_paths["test_view"] == ["/path/to/file.parquet"]

    def test_register_multiple_files(self, profiler):
        """Test registering multiple files."""
        files = ["/path/file1.parquet", "/path/file2.parquet", "/path/file3.parquet"]
        view_name = profiler.register_file_view(files, view_name="multi_view")

        assert view_name == "multi_view"
        assert profiler._view_paths["multi_view"] == files

    def test_register_with_file_uri(self, profiler):
        """Test registering files with file:// prefix."""
        files = ["file:///path/to/file.parquet"]
        view_name = profiler.register_file_view(files, view_name="uri_view")

        # Should clean the file:// prefix
        assert profiler._view_paths["uri_view"] == ["/path/to/file.parquet"]

    def test_register_auto_generated_name(self, profiler):
        """Test auto-generated view name."""
        files = ["/path/to/file.parquet"]
        view_name = profiler.register_file_view(files)

        assert view_name.startswith("files_")
        assert len(view_name) == 14  # "files_" + 8 char hash

    def test_register_empty_files_raises_error(self, profiler):
        """Test registering empty file list raises error."""
        with pytest.raises(ValueError, match="file_paths cannot be empty"):
            profiler.register_file_view([])

    def test_register_invalid_view_name_raises_error(self, profiler):
        """Test invalid view name raises error."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            profiler.register_file_view(["/path/file.parquet"], view_name="invalid-name")

    def test_register_view_name_with_sql_injection(self, profiler):
        """Test view name with SQL injection attempt raises error."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            profiler.register_file_view(
                ["/path/file.parquet"],
                view_name="test'; DROP TABLE users--",
            )

    def test_register_consistent_hash(self, profiler):
        """Test same files produce same hash."""
        files = ["/path/file1.parquet", "/path/file2.parquet"]

        view1 = profiler.register_file_view(files)
        view2 = profiler.register_file_view(files)

        assert view1 == view2


class TestRegisterSnapshotView:
    """Tests for register_snapshot_view method."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test",
            password="test",
        )

    def test_register_snapshot_with_data_files(self, profiler):
        """Test registering snapshot with data files."""
        snapshot = SnapshotInfo(
            snapshot_id=12345,
            parent_id=None,
            timestamp_ms=1700000000000,
            operation="append",
            summary={},
            data_files=[
                FileRef(path="/path/file1.parquet", file_size_bytes=1024),
                FileRef(path="/path/file2.parquet", file_size_bytes=2048),
            ],
            delete_files=[],
        )

        view_name = profiler.register_snapshot_view(snapshot)

        assert view_name == "snap_12345"
        assert hasattr(profiler, "_view_paths")
        assert "snap_12345" in profiler._view_paths

    def test_register_snapshot_negative_id_raises_error(self, profiler):
        """Test negative snapshot ID raises error."""
        snapshot = SnapshotInfo(
            snapshot_id=-1,
            parent_id=None,
            timestamp_ms=1700000000000,
            operation="append",
            summary={},
            data_files=[FileRef(path="/path/file.parquet", file_size_bytes=1024)],
            delete_files=[],
        )

        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            profiler.register_snapshot_view(snapshot)

    def test_register_snapshot_no_data_files_raises_error(self, profiler):
        """Test snapshot with no data files raises error."""
        snapshot = SnapshotInfo(
            snapshot_id=12345,
            parent_id=None,
            timestamp_ms=1700000000000,
            operation="delete",
            summary={},
            data_files=[],
            delete_files=[],
        )

        with pytest.raises(ValueError, match="has no data files"):
            profiler.register_snapshot_view(snapshot)


class TestClearViews:
    """Tests for clear_views method."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test",
            password="test",
        )

    def test_clear_views(self, profiler):
        """Test clearing all registered views."""
        # Register some views
        profiler.register_file_view(["/path/file1.parquet"], "view1")
        profiler.register_file_view(["/path/file2.parquet"], "view2")

        assert len(profiler._view_paths) == 2

        # Clear views
        profiler.clear_views()

        assert len(profiler._view_paths) == 0

    def test_clear_views_when_empty(self, profiler):
        """Test clearing views when none exist."""
        # Should not raise error
        profiler.clear_views()


class TestRegisterIcebergTable:
    """Tests for register_iceberg_table methods."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test",
            password="test",
        )

    def test_register_iceberg_table(self, profiler):
        """Test registering Iceberg table."""
        profiler.register_iceberg_table(
            "db.table",
            "/path/to/metadata.json",
        )

        assert hasattr(profiler, "_iceberg_tables")
        assert "db.table" in profiler._iceberg_tables
        metadata_loc, snapshot_id = profiler._iceberg_tables["db.table"]
        assert metadata_loc == "/path/to/metadata.json"
        assert snapshot_id is None

    def test_register_iceberg_table_with_snapshot(self, profiler):
        """Test registering Iceberg table with specific snapshot."""
        profiler.register_iceberg_table_with_snapshot(
            "db.table",
            "/path/to/metadata.json",
            snapshot_id=12345,
        )

        metadata_loc, snapshot_id = profiler._iceberg_tables["db.table"]
        assert metadata_loc == "/path/to/metadata.json"
        assert snapshot_id == 12345

    def test_register_iceberg_table_cleans_file_uri(self, profiler):
        """Test file:// prefix is cleaned from metadata location."""
        profiler.register_iceberg_table(
            "db.table",
            "file:///path/to/metadata.json",
        )

        metadata_loc, _ = profiler._iceberg_tables["db.table"]
        assert metadata_loc == "/path/to/metadata.json"

    def test_register_iceberg_table_empty_identifier_raises_error(self, profiler):
        """Test empty table identifier raises error."""
        with pytest.raises(ValueError, match="table_identifier and metadata_location are required"):
            profiler.register_iceberg_table("", "/path/metadata.json")

    def test_register_iceberg_table_empty_metadata_raises_error(self, profiler):
        """Test empty metadata location raises error."""
        with pytest.raises(ValueError, match="table_identifier and metadata_location are required"):
            profiler.register_iceberg_table("db.table", "")


class TestReplaceIcebergTables:
    """Tests for _replace_iceberg_tables method."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test",
            password="test",
        )

    def test_replace_iceberg_table_no_snapshot(self, profiler):
        """Test replacing table reference without snapshot."""
        profiler.register_iceberg_table("db.table", "/path/metadata.json")

        query = "SELECT * FROM db.table LIMIT 10"
        result = profiler._replace_iceberg_tables(query)

        assert "iceberg_scan('/path/metadata.json')" in result
        assert "db.table" not in result

    def test_replace_iceberg_table_with_snapshot(self, profiler):
        """Test replacing table reference with snapshot."""
        profiler.register_iceberg_table_with_snapshot(
            "db.table",
            "/path/metadata.json",
            snapshot_id=12345,
        )

        query = "SELECT * FROM db.table LIMIT 10"
        result = profiler._replace_iceberg_tables(query)

        assert "iceberg_scan('/path/metadata.json', version => 12345)" in result

    def test_replace_iceberg_table_escapes_quotes(self, profiler):
        """Test SQL quotes in path are escaped."""
        profiler.register_iceberg_table("db.table", "/path/with'quote/metadata.json")

        query = "SELECT * FROM db.table"
        result = profiler._replace_iceberg_tables(query)

        # Single quotes should be doubled for SQL escaping
        assert "iceberg_scan('/path/with''quote/metadata.json')" in result

    def test_replace_multiple_tables(self, profiler):
        """Test replacing multiple table references."""
        profiler.register_iceberg_table("db.table1", "/path/metadata1.json")
        profiler.register_iceberg_table("db.table2", "/path/metadata2.json")

        query = "SELECT * FROM db.table1 JOIN db.table2 ON table1.id = table2.id"
        result = profiler._replace_iceberg_tables(query)

        assert "iceberg_scan('/path/metadata1.json')" in result
        assert "iceberg_scan('/path/metadata2.json')" in result
        assert "db.table1" not in result
        assert "db.table2" not in result

    def test_replace_no_tables_registered(self, profiler):
        """Test query unchanged when no tables registered."""
        query = "SELECT * FROM db.table"
        result = profiler._replace_iceberg_tables(query)

        assert result == query

    def test_replace_invalid_snapshot_id_raises_error(self, profiler):
        """Test invalid snapshot ID type raises error."""
        # Manually set invalid snapshot_id to test validation
        profiler._iceberg_tables = {"db.table": ("/path/metadata.json", "not_an_int")}

        query = "SELECT * FROM db.table"

        with pytest.raises(ValueError, match="snapshot_id must be an integer"):
            profiler._replace_iceberg_tables(query)


class TestParseExplainAnalyze:
    """Tests for _parse_explain_analyze method."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test",
            password="test",
        )

    def test_parse_explain_with_parquet_scan(self, profiler):
        """Test parsing EXPLAIN output with PARQUET_SCAN."""
        explain_output = [
            ("PARQUET_SCAN 5 Files, 1000 Rows",),
            ("Result: 100 rows",),
        ]

        metrics = profiler._parse_explain_analyze(explain_output, 150.5, "SELECT * FROM table")

        assert metrics.execution_time_ms == 150.5
        assert metrics.files_scanned == 5
        assert metrics.rows_returned == 100

    def test_parse_explain_with_iceberg_scan(self, profiler):
        """Test parsing EXPLAIN output with ICEBERG_SCAN."""
        explain_output = [
            ("ICEBERG_SCAN 10 Files",),
            ("Cardinality: 5000",),
            ("RESULT Cardinality: 500",),
        ]

        metrics = profiler._parse_explain_analyze(explain_output, 200.0, "SELECT * FROM table")

        assert metrics.execution_time_ms == 200.0
        assert metrics.files_scanned == 10
        assert metrics.rows_scanned == 5000
        assert metrics.rows_returned == 500

    def test_parse_explain_with_bytes_scanned(self, profiler):
        """Test parsing bytes scanned from EXPLAIN output."""
        explain_output = [
            ("PARQUET_SCAN 2 Files",),
            ("Size: 10.5 MB",),
        ]

        metrics = profiler._parse_explain_analyze(explain_output, 100.0, "SELECT * FROM table")

        assert metrics.bytes_scanned == int(10.5 * 1024 * 1024)

    def test_parse_explain_empty_output(self, profiler):
        """Test parsing empty EXPLAIN output."""
        metrics = profiler._parse_explain_analyze([], 50.0, "SELECT * FROM table")

        assert metrics.execution_time_ms == 50.0
        assert metrics.files_scanned == 0
        assert metrics.rows_scanned == 0

    def test_parse_explain_fallback_to_query(self, profiler):
        """Test fallback to parsing iceberg_scan from query."""
        # Register table to enable fallback
        profiler.register_iceberg_table("db.table", "/path/metadata.json")

        explain_output = []
        query = "SELECT * FROM iceberg_scan('/path/metadata.json')"

        # Mock _get_iceberg_file_count
        with patch.object(profiler, "_get_iceberg_file_count", return_value=3):
            metrics = profiler._parse_explain_analyze(explain_output, 100.0, query)

        assert metrics.files_scanned == 3


class TestGetIcebergFileCount:
    """Tests for _get_iceberg_file_count method."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test",
            password="test",
        )

    def test_get_file_count_from_summary(self, profiler, tmp_path):
        """Test getting file count from snapshot summary."""
        import json

        # Create mock metadata file with manifest-list (required by implementation)
        metadata = {
            "current-snapshot-id": 12345,
            "snapshots": [
                {
                    "snapshot-id": 12345,
                    "manifest-list": "/path/to/manifest",
                    "summary": {"total-data-files": "5"},
                }
            ],
        }

        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        count = profiler._get_iceberg_file_count(str(metadata_file), None)

        assert count == 5

    def test_get_file_count_specific_snapshot(self, profiler, tmp_path):
        """Test getting file count for specific snapshot."""
        import json

        metadata = {
            "current-snapshot-id": 12345,
            "snapshots": [
                {
                    "snapshot-id": 12345,
                    "manifest-list": "/path/to/manifest1",
                    "summary": {"total-data-files": "5"},
                },
                {
                    "snapshot-id": 67890,
                    "manifest-list": "/path/to/manifest2",
                    "summary": {"total-data-files": "10"},
                },
            ],
        }

        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        count = profiler._get_iceberg_file_count(str(metadata_file), "67890")

        assert count == 10

    def test_get_file_count_no_summary(self, profiler, tmp_path):
        """Test getting file count when summary not available."""
        import json

        metadata = {
            "current-snapshot-id": 12345,
            "snapshots": [
                {
                    "snapshot-id": 12345,
                    "manifest-list": "/path/to/manifest",
                }
            ],
        }

        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        count = profiler._get_iceberg_file_count(str(metadata_file), None)

        assert count == 0

    def test_get_file_count_snapshot_not_found(self, profiler, tmp_path):
        """Test error when snapshot not found."""
        import json

        metadata = {
            "current-snapshot-id": 12345,
            "snapshots": [
                {
                    "snapshot-id": 12345,
                    "summary": {"total-data-files": "5"},
                }
            ],
        }

        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        with pytest.raises(ValueError, match="Snapshot .* not found"):
            profiler._get_iceberg_file_count(str(metadata_file), "99999")
