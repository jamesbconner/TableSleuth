"""Tests for SQL injection prevention in GizmoDuckDbProfiler."""

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler


class TestSQLInjectionPrevention:
    """Test SQL injection prevention mechanisms."""

    def test_metadata_location_with_single_quotes_escaped(self):
        """Test that single quotes in metadata locations are properly escaped."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test",
            password="test",
        )

        # Register a table with single quotes in the metadata location
        # This simulates a potential SQL injection attempt
        malicious_metadata = "/path/to/metadata'; DROP TABLE users; --"
        profiler.register_iceberg_table_with_snapshot(
            "test_table",
            malicious_metadata,
            snapshot_id=123,
        )

        # Test that the metadata location is properly escaped in the query
        test_query = "SELECT * FROM test_table"
        modified_query = profiler._replace_iceberg_tables(test_query)

        # The single quotes should be doubled (SQL standard escaping)
        expected_escaped = "/path/to/metadata''; DROP TABLE users; --"
        assert expected_escaped in modified_query
        assert f"iceberg_scan('{expected_escaped}', version => 123)" in modified_query

        # Verify the original malicious string is NOT in the query
        assert malicious_metadata not in modified_query

    def test_metadata_location_without_quotes_unchanged(self):
        """Test that normal metadata locations work correctly."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test",
            password="test",
        )

        # Register a table with a normal metadata location
        normal_metadata = "/path/to/metadata.json"
        profiler.register_iceberg_table_with_snapshot(
            "test_table",
            normal_metadata,
            snapshot_id=456,
        )

        # Test that the query is modified correctly
        test_query = "SELECT * FROM test_table"
        modified_query = profiler._replace_iceberg_tables(test_query)

        # Normal path should be unchanged
        assert f"iceberg_scan('{normal_metadata}', version => 456)" in modified_query

    def test_multiple_single_quotes_escaped(self):
        """Test that multiple single quotes are all properly escaped."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test",
            password="test",
        )

        # Metadata location with multiple single quotes
        metadata_with_quotes = "/path/to/'metadata'/'file'.json"
        profiler.register_iceberg_table_with_snapshot(
            "test_table",
            metadata_with_quotes,
            snapshot_id=789,
        )

        test_query = "SELECT * FROM test_table"
        modified_query = profiler._replace_iceberg_tables(test_query)

        # All single quotes should be doubled
        expected_escaped = "/path/to/''metadata''/''file''.json"
        assert expected_escaped in modified_query

    def test_snapshot_id_not_escaped(self):
        """Test that snapshot_id (integer) is not escaped."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test",
            password="test",
        )

        # Register table with integer snapshot ID
        profiler.register_iceberg_table_with_snapshot(
            "test_table",
            "/path/to/metadata.json",
            snapshot_id=999,
        )

        test_query = "SELECT * FROM test_table"
        modified_query = profiler._replace_iceberg_tables(test_query)

        # Snapshot ID should be directly interpolated (it's an integer)
        assert "version => 999" in modified_query
        assert "version => '999'" not in modified_query  # Should NOT be quoted

    def test_no_snapshot_id_escaping(self):
        """Test metadata escaping when no snapshot ID is provided."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test",
            password="test",
        )

        # Register table without snapshot ID
        metadata_with_quote = "/path/to/metadata's.json"
        profiler.register_iceberg_table_with_snapshot(
            "test_table",
            metadata_with_quote,
            snapshot_id=None,
        )

        test_query = "SELECT * FROM test_table"
        modified_query = profiler._replace_iceberg_tables(test_query)

        # Single quote should be escaped
        expected_escaped = "/path/to/metadata''s.json"
        assert f"iceberg_scan('{expected_escaped}')" in modified_query

    def test_empty_metadata_location(self):
        """Test that empty metadata location raises ValueError."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test",
            password="test",
        )

        # Empty metadata location should raise ValueError
        with pytest.raises(ValueError, match="table_identifier and metadata_location are required"):
            profiler.register_iceberg_table_with_snapshot(
                "test_table",
                "",
                snapshot_id=123,
            )

    def test_identifier_sanitization_prevents_injection(self):
        """Test that table identifiers are sanitized to prevent injection."""
        from tablesleuth.services.profiling.gizmo_duckdb import _sanitize_identifier

        # Valid identifiers should pass
        assert _sanitize_identifier("valid_table") == "valid_table"
        assert _sanitize_identifier("_underscore") == "_underscore"
        assert _sanitize_identifier("Table123") == "Table123"

        # Invalid identifiers should raise ValueError
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("table; DROP TABLE users;")

        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("table' OR '1'='1")

        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("table--comment")

        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("123table")  # Can't start with number
