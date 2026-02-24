"""Tests for simplified table reference replacement pattern.

Verifies that the single word-boundary pattern correctly handles both
bare and quoted table identifiers.
"""

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler


def test_replace_table_ref_bare_identifier():
    """Test replacement of bare table identifier."""
    query = "SELECT * FROM my_table WHERE x > 5"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == "SELECT * FROM iceberg_scan('/path/to/metadata.json') WHERE x > 5"


def test_replace_table_ref_double_quoted():
    """Test replacement of double-quoted table identifier."""
    query = 'SELECT * FROM "my_table" WHERE x > 5'
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == "SELECT * FROM \"iceberg_scan('/path/to/metadata.json')\" WHERE x > 5"


def test_replace_table_ref_single_quoted():
    """Test replacement of single-quoted table identifier."""
    query = "SELECT * FROM 'my_table' WHERE x > 5"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == "SELECT * FROM 'iceberg_scan('/path/to/metadata.json')' WHERE x > 5"


def test_replace_table_ref_case_insensitive():
    """Test that replacement is case-insensitive."""
    query = "SELECT * FROM MY_TABLE WHERE x > 5"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == "SELECT * FROM iceberg_scan('/path/to/metadata.json') WHERE x > 5"


def test_replace_table_ref_multiple_occurrences():
    """Test replacement of multiple occurrences of the same table."""
    query = "SELECT * FROM my_table t1 JOIN my_table t2 ON t1.id = t2.id"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    expected = "SELECT * FROM iceberg_scan('/path/to/metadata.json') t1 JOIN iceberg_scan('/path/to/metadata.json') t2 ON t1.id = t2.id"
    assert result == expected


def test_replace_table_ref_no_partial_match():
    """Test that partial matches are not replaced (word boundary protection)."""
    query = "SELECT * FROM my_table_extended WHERE x > 5"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    # Should NOT replace because my_table_extended contains my_table but is a different identifier
    assert result == query


def test_replace_table_ref_with_special_chars():
    """Test replacement with table names containing special regex characters."""
    query = "SELECT * FROM my.table WHERE x > 5"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my.table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == "SELECT * FROM iceberg_scan('/path/to/metadata.json') WHERE x > 5"


def test_replace_table_ref_mixed_quotes():
    """Test replacement with mixed quote styles in the same query."""
    query = 'SELECT * FROM "my_table" t1 JOIN my_table t2 ON t1.id = t2.id'
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    expected = "SELECT * FROM \"iceberg_scan('/path/to/metadata.json')\" t1 JOIN iceberg_scan('/path/to/metadata.json') t2 ON t1.id = t2.id"
    assert result == expected


def test_replace_table_ref_in_subquery():
    """Test replacement in subqueries."""
    query = "SELECT * FROM (SELECT * FROM my_table) AS sub"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == "SELECT * FROM (SELECT * FROM iceberg_scan('/path/to/metadata.json')) AS sub"


def test_replace_table_ref_with_alias():
    """Test replacement when table has an alias."""
    query = "SELECT t.* FROM my_table AS t WHERE t.x > 5"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == "SELECT t.* FROM iceberg_scan('/path/to/metadata.json') AS t WHERE t.x > 5"


def test_replace_table_ref_empty_query():
    """Test replacement with empty query."""
    query = ""
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == ""


def test_replace_table_ref_no_match():
    """Test replacement when table name is not in query."""
    query = "SELECT * FROM other_table WHERE x > 5"
    result = GizmoDuckDbProfiler._replace_table_ref(
        query, "my_table", "iceberg_scan('/path/to/metadata.json')"
    )
    assert result == query
