"""Tests for GizmoDuckDB SQL sanitization functions."""

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import (
    _sanitize_identifier,
    _validate_filter_expression,
)


class TestSanitizeIdentifier:
    """Tests for _sanitize_identifier function."""

    def test_valid_identifier_simple(self):
        """Test valid simple identifier."""
        assert _sanitize_identifier("column_name") == "column_name"

    def test_valid_identifier_with_numbers(self):
        """Test valid identifier with numbers."""
        assert _sanitize_identifier("column_123") == "column_123"

    def test_valid_identifier_starts_with_underscore(self):
        """Test valid identifier starting with underscore."""
        assert _sanitize_identifier("_private_column") == "_private_column"

    def test_valid_identifier_uppercase(self):
        """Test valid identifier with uppercase letters."""
        assert _sanitize_identifier("ColumnName") == "ColumnName"

    def test_invalid_identifier_starts_with_number(self):
        """Test invalid identifier starting with number."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("123column")

    def test_invalid_identifier_with_spaces(self):
        """Test invalid identifier with spaces."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("column name")

    def test_invalid_identifier_with_special_chars(self):
        """Test invalid identifier with special characters."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("column-name")

    def test_invalid_identifier_with_sql_injection(self):
        """Test invalid identifier with SQL injection attempt."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("column'; DROP TABLE users--")

    def test_invalid_identifier_empty(self):
        """Test invalid empty identifier."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("")

    def test_invalid_identifier_with_dots(self):
        """Test invalid identifier with dots (table.column)."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _sanitize_identifier("table.column")


class TestValidateFilterExpression:
    """Tests for _validate_filter_expression function."""

    def test_valid_filter_simple_comparison(self):
        """Test valid simple comparison filter."""
        # Should not raise
        _validate_filter_expression("age > 18")

    def test_valid_filter_with_and(self):
        """Test valid filter with AND operator (no quotes)."""
        # Should not raise
        _validate_filter_expression("age > 18 AND status = 1")

    def test_valid_filter_with_or(self):
        """Test valid filter with OR operator (no quotes)."""
        # Should not raise
        _validate_filter_expression("status = 1 OR status = 2")

    def test_invalid_filter_with_drop(self):
        """Test invalid filter with DROP statement."""
        with pytest.raises(ValueError, match="statement terminator"):
            _validate_filter_expression("age > 18; DROP TABLE users")

    def test_invalid_filter_with_delete(self):
        """Test invalid filter with DELETE statement."""
        with pytest.raises(ValueError, match="statement terminator"):
            _validate_filter_expression("age > 18; DELETE FROM users")

    def test_invalid_filter_with_insert(self):
        """Test invalid filter with INSERT statement."""
        with pytest.raises(ValueError, match="statement terminator"):
            _validate_filter_expression("age > 18; INSERT INTO users")

    def test_invalid_filter_with_update(self):
        """Test invalid filter with UPDATE statement."""
        with pytest.raises(ValueError, match="statement terminator"):
            _validate_filter_expression("age > 18; UPDATE users SET")

    def test_invalid_filter_with_exec(self):
        """Test invalid filter with EXEC statement."""
        with pytest.raises(ValueError, match="statement terminator"):
            _validate_filter_expression("age > 18; EXEC sp_executesql")

    def test_invalid_filter_with_semicolon(self):
        """Test invalid filter with semicolon (statement separator)."""
        with pytest.raises(ValueError, match="statement terminator"):
            _validate_filter_expression("age > 18; SELECT * FROM users")

    def test_invalid_filter_with_comment(self):
        """Test invalid filter with SQL comment."""
        with pytest.raises(ValueError, match="SQL comment"):
            _validate_filter_expression("age > 18 -- comment")

    def test_invalid_filter_with_quotes(self):
        """Test invalid filter with quotes."""
        with pytest.raises(ValueError, match="quotes which are not allowed"):
            _validate_filter_expression("status = 'active'")

    def test_empty_filter(self):
        """Test empty filter expression."""
        # Should not raise for empty filter
        _validate_filter_expression("")
