"""Tests for SQL filter validation in gizmo_duckdb module."""

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import _validate_filter_expression


class TestFilterValidation:
    """Test suite for filter expression validation."""

    def test_valid_filters_pass(self):
        """Test that valid filter expressions are accepted."""
        valid_filters = [
            "age > 18",
            "status = 1 AND active = true",
            "price BETWEEN 10 AND 100",
            "category IN (1, 2, 3)",
            "name LIKE pattern",
            "value IS NOT NULL",
            "count >= 5 OR count <= 100",
            # Column names containing SQL keywords as substrings should be allowed
            "deleted_at IS NOT NULL",
            "into_status = 1",
            "truncated_value > 0",
            "selecting = true",
            "updated_count > 5",
            "inserted_by = 123",
        ]

        for filter_expr in valid_filters:
            # Should not raise
            _validate_filter_expression(filter_expr)

    def test_empty_filter_passes(self):
        """Test that empty/None filters are accepted."""
        _validate_filter_expression("")
        _validate_filter_expression(None)

    def test_sql_injection_blocked(self):
        """Test that SQL injection attempts are blocked."""
        dangerous_filters = [
            "age > 18; DROP TABLE users",
            "status = 1 OR 1=1--",
            "name = 'admin'",
            "id IN (SELECT id FROM users)",
            "age > 18 UNION SELECT * FROM passwords",
            "1=1; DELETE FROM users",
            "x' OR '1'='1",
            'x" OR "1"="1',
            "/* comment */ DROP TABLE",
            "id = 1 INTO OUTFILE",
        ]

        for filter_expr in dangerous_filters:
            with pytest.raises(ValueError, match="dangerous|quotes|comment|terminator"):
                _validate_filter_expression(filter_expr)

    def test_dangerous_keywords_blocked(self):
        """Test that dangerous SQL keywords are blocked."""
        dangerous_keywords = [
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "CREATE",
            "ALTER",
            "TRUNCATE",
            "EXEC",
            "EXECUTE",
            "UNION",
            "SELECT",
        ]

        for keyword in dangerous_keywords:
            filter_expr = f"age > 18 {keyword} something"
            with pytest.raises(ValueError, match="dangerous keyword"):
                _validate_filter_expression(filter_expr)

    def test_case_insensitive_validation(self):
        """Test that validation is case-insensitive."""
        dangerous_filters = [
            "age > 18 DRoP TABLE users",
            "status = 1 UnIoN SELECT * FROM passwords",
            "id = 1 DeLeTe FROM users",
        ]

        for filter_expr in dangerous_filters:
            with pytest.raises(ValueError):
                _validate_filter_expression(filter_expr)
