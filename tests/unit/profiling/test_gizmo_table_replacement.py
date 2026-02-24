"""Tests for table reference replacement logic in GizmoDuckDbProfiler."""

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler


class TestReplaceTableRef:
    """Tests for the _replace_table_ref helper method."""

    def test_replace_bare_identifier(self) -> None:
        """Test replacing bare table identifier."""
        query = "SELECT * FROM my_table WHERE id = 1"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my_table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        assert result == "SELECT * FROM iceberg_scan('s3://bucket/metadata.json') WHERE id = 1"

    def test_replace_double_quoted_identifier(self) -> None:
        """Test replacing double-quoted table identifier."""
        query = 'SELECT * FROM "my_table" WHERE id = 1'
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my_table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        # Quoted identifiers are replaced with the scan call wrapped in the same quotes
        assert result == 'SELECT * FROM "iceberg_scan(\'s3://bucket/metadata.json\')" WHERE id = 1'

    def test_replace_single_quoted_identifier(self) -> None:
        """Test replacing single-quoted table identifier."""
        query = "SELECT * FROM 'my_table' WHERE id = 1"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my_table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        # Quoted identifiers are replaced with the scan call wrapped in the same quotes
        assert result == "SELECT * FROM 'iceberg_scan('s3://bucket/metadata.json')' WHERE id = 1"

    def test_replace_case_insensitive(self) -> None:
        """Test that replacement is case-insensitive."""
        query = "SELECT * FROM MY_TABLE WHERE id = 1"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my_table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        assert result == "SELECT * FROM iceberg_scan('s3://bucket/metadata.json') WHERE id = 1"

    def test_replace_multiple_occurrences(self) -> None:
        """Test replacing multiple occurrences of the same table."""
        query = "SELECT * FROM my_table t1 JOIN my_table t2 ON t1.id = t2.parent_id"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my_table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        expected = (
            "SELECT * FROM iceberg_scan('s3://bucket/metadata.json') t1 "
            "JOIN iceberg_scan('s3://bucket/metadata.json') t2 ON t1.id = t2.parent_id"
        )
        assert result == expected

    def test_replace_with_special_chars_in_table_name(self) -> None:
        """Test replacing table names with special regex characters."""
        query = "SELECT * FROM my.table WHERE id = 1"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my.table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        assert result == "SELECT * FROM iceberg_scan('s3://bucket/metadata.json') WHERE id = 1"

    def test_no_replacement_for_partial_match(self) -> None:
        """Test that partial matches are not replaced."""
        query = "SELECT * FROM my_table_extended WHERE id = 1"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my_table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        # Should not replace because my_table_extended is not an exact match
        assert result == "SELECT * FROM my_table_extended WHERE id = 1"

    def test_replace_with_read_parquet(self) -> None:
        """Test replacing with read_parquet function."""
        query = "SELECT * FROM delta_table WHERE id = 1"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "delta_table", "read_parquet(['s3://bucket/file1.parquet', 's3://bucket/file2.parquet'])"
        )
        assert (
            result
            == "SELECT * FROM read_parquet(['s3://bucket/file1.parquet', 's3://bucket/file2.parquet']) WHERE id = 1"
        )

    def test_replace_with_snapshot_version(self) -> None:
        """Test replacing with iceberg_scan with version parameter."""
        query = "SELECT COUNT(*) FROM snapshot_a"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "snapshot_a", "iceberg_scan('s3://bucket/metadata.json', version => 123)"
        )
        assert result == "SELECT COUNT(*) FROM iceberg_scan('s3://bucket/metadata.json', version => 123)"

    def test_replace_in_complex_query(self) -> None:
        """Test replacement in a complex query with multiple clauses."""
        query = """
        SELECT t1.id, t2.name
        FROM my_table t1
        LEFT JOIN my_table t2 ON t1.parent_id = t2.id
        WHERE t1.status = 'active'
        ORDER BY t1.id
        """
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my_table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        assert "iceberg_scan('s3://bucket/metadata.json') t1" in result
        assert "iceberg_scan('s3://bucket/metadata.json') t2" in result
        assert "my_table" not in result

    def test_no_replacement_when_table_not_present(self) -> None:
        """Test that query is unchanged when table is not present."""
        query = "SELECT * FROM other_table WHERE id = 1"
        result = GizmoDuckDbProfiler._replace_table_ref(
            query, "my_table", "iceberg_scan('s3://bucket/metadata.json')"
        )
        assert result == query
