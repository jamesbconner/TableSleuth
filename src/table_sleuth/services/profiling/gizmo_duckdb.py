from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Dict, Optional

from adbc_driver_flightsql import DatabaseOptions
from adbc_driver_flightsql import dbapi as flightsql

from table_sleuth.models import ColumnProfile, SnapshotInfo

from .backend_base import ProfilingBackend


def _sanitize_identifier(identifier: str) -> str:
    """
    Sanitize SQL identifiers (table/column names) to prevent SQL injection.

    Args:
        identifier: The identifier to sanitize

    Returns:
        Sanitized identifier safe for SQL queries

    Raises:
        ValueError: If identifier contains invalid characters
    """
    # Only allow alphanumeric characters and underscores
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
        raise ValueError(
            f"Invalid identifier '{identifier}': must start with letter/underscore "
            "and contain only alphanumeric characters and underscores"
        )
    return identifier


def _validate_filter_expression(filters: str) -> None:
    """
    Validate filter expressions to prevent SQL injection.

    This is a basic validation that checks for dangerous SQL keywords and patterns.
    For production use, implement a proper filter DSL or use parameterized queries.

    Args:
        filters: The filter expression to validate

    Raises:
        ValueError: If the filter contains potentially dangerous SQL patterns
    """
    if not filters:
        return

    # Convert to lowercase for case-insensitive checking
    filters_lower = filters.lower()

    # Check for SQL comments and statement terminators first (no word boundaries needed)
    dangerous_patterns = [
        ("--", "SQL comment"),
        ("/*", "SQL comment"),
        ("*/", "SQL comment"),
        (";", "statement terminator"),
    ]

    for pattern, description in dangerous_patterns:
        if pattern in filters_lower:
            raise ValueError(
                f"Filter expression contains {description} '{pattern}'. "
                "Filters must only contain safe comparison operators and values."
            )

    # List of dangerous SQL keywords that should not appear as standalone words
    dangerous_keywords = [
        "drop",
        "delete",
        "insert",
        "update",
        "create",
        "alter",
        "truncate",
        "exec",
        "execute",
        "union",
        "select",
        "into",
        "xp_",
        "sp_",
    ]

    for keyword in dangerous_keywords:
        # Use word boundary matching to avoid false positives with column names
        # like 'deleted_at', 'into_status', 'truncated_value', 'selecting'
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, filters_lower):
            raise ValueError(
                f"Filter expression contains dangerous keyword '{keyword}'. "
                "Filters must only contain safe comparison operators and values."
            )

    # Check for quotes (no word boundaries needed)
    if re.search(r"['\"]", filters):
        raise ValueError(
            "Filter expression contains quotes which are not allowed. "
            "Use simple comparison expressions only (e.g., 'column > 100')."
        )


class GizmoDuckDbProfiler(ProfilingBackend):
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        tls_skip_verify: bool = True,
    ) -> None:
        self._uri = uri
        self._username = username
        self._password = password
        self._tls_skip_verify = tls_skip_verify

    def _connect(self):
        return flightsql.connect(
            uri=self._uri,
            db_kwargs={
                "username": self._username,
                "password": self._password,
                DatabaseOptions.TLS_SKIP_VERIFY.value: "true" if self._tls_skip_verify else "false",
            },
        )

    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        """Create a backend-specific view for an Iceberg snapshot.

        Args:
            snapshot: SnapshotInfo with data files

        Returns:
            View name that can be used in subsequent queries

        Raises:
            ValueError: If snapshot ID is invalid or no data files
        """
        # Validate snapshot ID is positive (Iceberg constraint)
        if snapshot.snapshot_id < 0:
            raise ValueError(
                f"Invalid snapshot ID {snapshot.snapshot_id}: "
                "Iceberg snapshot IDs must be non-negative"
            )

        # Handle empty snapshots (schema-only or delete-only operations)
        if not snapshot.data_files:
            raise ValueError(
                f"Snapshot {snapshot.snapshot_id} has no data files. "
                "Cannot create view for empty snapshot. "
                "This may be a schema-only change or delete-only snapshot."
            )

        # Create view name with validated snapshot ID
        view_name = f"snap_{snapshot.snapshot_id}"
        paths = [f.path for f in snapshot.data_files]

        return self.register_file_view(paths, view_name)

    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        """Register Parquet files for profiling.

        Note: While DuckDB supports CREATE VIEW, GizmoSQL's Flight SQL interface
        doesn't persist views across connections. Each connection gets its own
        DuckDB instance. Therefore, this method stores the file paths and returns
        a view name that will be used to construct read_parquet() queries dynamically
        in subsequent profiling calls.

        Args:
            file_paths: List of Parquet file paths (local or remote)
            view_name: Optional view name (auto-generated if None)

        Returns:
            View name that can be used in subsequent queries

        Raises:
            ValueError: If file_paths is empty or view_name is invalid
        """
        if not file_paths:
            raise ValueError("file_paths cannot be empty")

        # Generate view name if not provided
        if view_name is None:
            import hashlib

            # Create a hash of the file paths for a unique view name
            paths_str = "|".join(sorted(file_paths))
            hash_val = hashlib.md5(paths_str.encode(), usedforsecurity=False).hexdigest()[:8]  # noqa: S324
            view_name = f"files_{hash_val}"

        # Sanitize view name to prevent SQL injection
        safe_view_name = _sanitize_identifier(view_name)

        # Store the file paths mapping for this view name
        if not hasattr(self, "_view_paths"):
            self._view_paths = {}
        self._view_paths[safe_view_name] = file_paths

        return safe_view_name

    def profile_single_column(
        self,
        view_name: str,
        column: str,
        filters: Optional[str] = None,
    ) -> ColumnProfile:
        # Sanitize identifiers to prevent SQL injection
        safe_view_name = _sanitize_identifier(view_name)
        safe_column = _sanitize_identifier(column)

        # Validate filter expression to prevent SQL injection
        # This provides basic protection but is not foolproof
        # TODO: Implement a proper filter DSL with full parameterization
        if filters:
            _validate_filter_expression(filters)
            where_clause = f"WHERE {filters}"
        else:
            where_clause = ""

        # Get the file paths for this view name
        if hasattr(self, "_view_paths") and safe_view_name in self._view_paths:
            file_paths = self._view_paths[safe_view_name]
            # Build read_parquet() expression
            if len(file_paths) == 1:
                from_clause = f"read_parquet('{file_paths[0]}')"
            else:
                escaped_paths = [path.replace("'", "''") for path in file_paths]
                paths_list = ", ".join(f"'{p}'" for p in escaped_paths)
                from_clause = f"read_parquet([{paths_list}])"
        else:
            # Fallback: assume view_name is a table/view name
            from_clause = safe_view_name

        # safe_view_name and safe_column are sanitized via _sanitize_identifier()
        # filters is validated via _validate_filter_expression()
        sql = f"""
        SELECT
            COUNT(*) AS row_count,
            COUNT({safe_column}) AS non_null_count,
            COUNT(*) - COUNT({safe_column}) AS null_count,
            COUNT(DISTINCT {safe_column}) AS distinct_count,
            MIN({safe_column}) AS min_value,
            MAX({safe_column}) AS max_value
        FROM {from_clause}
        {where_clause}
        """  # nosec B608

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()

        return ColumnProfile(
            column=column,
            row_count=row[0],
            non_null_count=row[1],
            null_count=row[2],
            distinct_count=row[3],
            min_value=row[4],
            max_value=row[5],
        )

    def profile_columns(
        self,
        view_name: str,
        columns: Sequence[str],
        filters: Optional[str] = None,
    ) -> dict[str, ColumnProfile]:
        return {col: self.profile_single_column(view_name, col, filters) for col in columns}
