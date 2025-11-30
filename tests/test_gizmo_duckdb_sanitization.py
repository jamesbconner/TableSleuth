"""Tests for GizmoDuckDbProfiler SQL injection prevention and sanitization."""

import pytest

from table_sleuth.services.profiling.gizmo_duckdb import (
    GizmoDuckDbProfiler,
    _sanitize_identifier,
    _validate_filter_expression,
)


class TestSanitizeIdentifier:
    """Test SQL identifier sanitization."""

    def test_valid_identifiers(self):
        """Test that valid identifiers pass through unchanged."""
        assert _sanitize_identifier("column_name") == "column_name"
        assert _sanitize_identifier("_private") == "_private"
        assert _sanitize_identifier("Column123") == "Column123"
        assert _sanitize_identifier("table_name_2") == "table_name_2"

    def test_invalid_identifiers_raise(self):
        """Test that invalid identifiers raise ValueError."""
        # Starts with number
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("123column")

        # Contains special characters
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("column-name")

        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("column.name")

        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("column name")

        # SQL injection attempts
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("column; DROP TABLE users")

        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("column' OR '1'='1")


class TestValidateFilterExpression:
    """Test filter expression validation."""

    def test_valid_filters(self):
        """Test that valid filter expressions pass validation."""
        # These should not raise
        _validate_filter_expression("age > 18")
        _validate_filter_expression("status = active")
        _validate_filter_expression("price < 100 AND quantity > 0")
        _validate_filter_expression("date >= 20240101")
        _validate_filter_expression("")  # Empty filter is valid
        _validate_filter_expression(None)  # None is valid

    def test_dangerous_keywords_raise(self):
        """Test that dangerous SQL keywords raise ValueError."""
        # SQL injection keywords (without statement terminators)
        with pytest.raises(ValueError, match="dangerous keyword"):
            _validate_filter_expression("status = active DELETE FROM table")

        with pytest.raises(ValueError, match="dangerous keyword"):
            _validate_filter_expression("price < 100 UNION SELECT * FROM passwords")

        with pytest.raises(ValueError, match="dangerous keyword"):
            _validate_filter_expression("EXEC sp_executesql")

        with pytest.raises(ValueError, match="dangerous keyword"):
            _validate_filter_expression("age > 18 DROP TABLE users")

    def test_sql_comments_raise(self):
        """Test that SQL comments raise ValueError."""
        with pytest.raises(ValueError, match="SQL comment"):
            _validate_filter_expression("age > 18 -- comment")

        with pytest.raises(ValueError, match="SQL comment"):
            _validate_filter_expression("age > 18 /* comment */")

    def test_statement_terminators_raise(self):
        """Test that statement terminators raise ValueError."""
        with pytest.raises(ValueError, match="statement terminator"):
            _validate_filter_expression("age > 18; DELETE FROM users")

    def test_quotes_raise(self):
        """Test that quotes raise ValueError."""
        with pytest.raises(ValueError, match="quotes"):
            _validate_filter_expression("name = 'John'")

        with pytest.raises(ValueError, match="quotes"):
            _validate_filter_expression('name = "John"')

    def test_column_names_with_keyword_substrings(self):
        """Test that column names containing keyword substrings are allowed."""
        # These should NOT raise because keywords are not standalone words
        _validate_filter_expression("deleted_at > 20240101")  # contains 'delete'
        _validate_filter_expression("into_status = 1")  # contains 'into'
        _validate_filter_expression("truncated_value < 100")  # contains 'truncate'
        _validate_filter_expression("selecting = true")  # contains 'select'


class TestRegisterIcebergTable:
    """Test Iceberg table registration."""

    def test_register_iceberg_table_basic(self):
        """Test basic Iceberg table registration."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        profiler.register_iceberg_table(
            "snapshot_tests.table_snap_123",
            "/path/to/metadata.json",
        )

        assert hasattr(profiler, "_iceberg_tables")
        assert "snapshot_tests.table_snap_123" in profiler._iceberg_tables
        metadata_loc, snapshot_id = profiler._iceberg_tables["snapshot_tests.table_snap_123"]
        assert metadata_loc == "/path/to/metadata.json"
        assert snapshot_id is None

    def test_register_iceberg_table_with_snapshot(self):
        """Test Iceberg table registration with specific snapshot."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        profiler.register_iceberg_table_with_snapshot(
            "snapshot_tests.table_snap_123",
            "/path/to/metadata.json",
            snapshot_id=12345,
        )

        assert "snapshot_tests.table_snap_123" in profiler._iceberg_tables
        metadata_loc, snapshot_id = profiler._iceberg_tables["snapshot_tests.table_snap_123"]
        assert metadata_loc == "/path/to/metadata.json"
        assert snapshot_id == 12345

    def test_register_iceberg_table_cleans_file_prefix(self):
        """Test that file:// prefix is removed from metadata location."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        profiler.register_iceberg_table(
            "test_table",
            "file:///path/to/metadata.json",
        )

        metadata_loc, _ = profiler._iceberg_tables["test_table"]
        assert metadata_loc == "/path/to/metadata.json"
        assert not metadata_loc.startswith("file://")

    def test_register_iceberg_table_empty_identifier_raises(self):
        """Test that empty table identifier raises ValueError."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        with pytest.raises(ValueError, match="table_identifier and metadata_location are required"):
            profiler.register_iceberg_table("", "/path/to/metadata.json")

    def test_register_iceberg_table_empty_metadata_raises(self):
        """Test that empty metadata location raises ValueError."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        with pytest.raises(ValueError, match="table_identifier and metadata_location are required"):
            profiler.register_iceberg_table("test_table", "")


class TestRegisterCatalogDeprecated:
    """Test deprecated register_catalog method."""

    def test_register_catalog_raises_runtime_error(self):
        """Test that register_catalog raises RuntimeError with deprecation message."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        with pytest.raises(RuntimeError, match="register_catalog\\(\\) is deprecated"):
            profiler.register_catalog("/path/to/catalog.db", "test_catalog")


class TestReplaceIcebergTables:
    """Test Iceberg table reference replacement in queries."""

    def test_replace_iceberg_tables_basic(self):
        """Test basic table reference replacement."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        profiler.register_iceberg_table("test_table", "/path/to/metadata.json")

        query = "SELECT * FROM test_table"
        modified = profiler._replace_iceberg_tables(query)

        assert "iceberg_scan('/path/to/metadata.json')" in modified
        assert "test_table" not in modified

    def test_replace_iceberg_tables_with_snapshot(self):
        """Test table reference replacement with snapshot ID."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        profiler.register_iceberg_table_with_snapshot(
            "test_table",
            "/path/to/metadata.json",
            snapshot_id=12345,
        )

        query = "SELECT * FROM test_table"
        modified = profiler._replace_iceberg_tables(query)

        assert "iceberg_scan('/path/to/metadata.json', version => 12345)" in modified

    def test_replace_iceberg_tables_escapes_quotes(self):
        """Test that single quotes in paths are properly escaped."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        # Path with single quote (unusual but possible)
        profiler.register_iceberg_table("test_table", "/path/to/user's/metadata.json")

        query = "SELECT * FROM test_table"
        modified = profiler._replace_iceberg_tables(query)

        # Single quotes should be doubled for SQL escaping
        assert "iceberg_scan('/path/to/user''s/metadata.json')" in modified

    def test_replace_iceberg_tables_no_tables_registered(self):
        """Test that query is unchanged when no tables are registered."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        query = "SELECT * FROM some_table"
        modified = profiler._replace_iceberg_tables(query)

        assert modified == query

    def test_replace_iceberg_tables_multiple_tables(self):
        """Test replacement of multiple table references."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        profiler.register_iceberg_table("table_a", "/path/to/a.json")
        profiler.register_iceberg_table("table_b", "/path/to/b.json")

        query = "SELECT * FROM table_a JOIN table_b ON table_a.id = table_b.id"
        modified = profiler._replace_iceberg_tables(query)

        assert "iceberg_scan('/path/to/a.json')" in modified
        assert "iceberg_scan('/path/to/b.json')" in modified
        assert "table_a" not in modified
        assert "table_b" not in modified


class TestRegisterSnapshotView:
    """Test snapshot view registration."""

    def test_register_snapshot_view_validates_snapshot_id(self):
        """Test that negative snapshot IDs raise ValueError."""
        from table_sleuth.models import SnapshotInfo

        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        # Create snapshot with negative ID
        snapshot = SnapshotInfo(
            snapshot_id=-1,
            parent_id=None,
            timestamp_ms=1234567890000,
            operation="append",
            summary={},
            data_files=[],
        )

        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            profiler.register_snapshot_view(snapshot)

    def test_register_snapshot_view_requires_data_files(self):
        """Test that snapshots without data files raise ValueError."""
        from table_sleuth.models import SnapshotInfo

        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        # Create snapshot with no data files
        snapshot = SnapshotInfo(
            snapshot_id=12345,
            parent_id=None,
            timestamp_ms=1234567890000,
            operation="append",
            summary={},
            data_files=[],  # Empty!
        )

        with pytest.raises(ValueError, match="has no data files"):
            profiler.register_snapshot_view(snapshot)


class TestTLSConfiguration:
    """Test TLS configuration handling."""

    def test_tls_enabled_with_grpc_tls_uri(self):
        """Test that TLS is enabled for grpc+tls:// URIs."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            tls_skip_verify=True,
        )

        # URI should indicate TLS
        assert profiler._uri.startswith("grpc+tls://")
        assert profiler._tls_skip_verify is True

    def test_tls_disabled_with_grpc_uri(self):
        """Test that TLS is disabled for grpc:// URIs."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337",
            username="test_user",
            password="test_pass",
            tls_skip_verify=False,
        )

        # URI should indicate no TLS
        assert profiler._uri.startswith("grpc://")
        assert not profiler._uri.startswith("grpc+tls://")
