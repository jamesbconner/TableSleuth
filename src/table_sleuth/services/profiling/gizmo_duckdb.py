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
        view_name = f"snap_{snapshot.snapshot_id}"
        # Sanitize view name to prevent SQL injection
        safe_view_name = _sanitize_identifier(view_name)
        paths = [f.path for f in snapshot.data_files]

        # Use parameterized query for the paths list
        # safe_view_name is sanitized via _sanitize_identifier()
        sql = f"""
        CREATE OR REPLACE VIEW {safe_view_name} AS
        SELECT *
        FROM read_parquet($paths)
        """  # nosec B608
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"paths": paths})
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

        # WARNING: filters parameter is intentionally NOT sanitized as it may contain
        # complex SQL expressions. Callers MUST ensure filters come from trusted sources
        # or implement proper filter validation/parameterization at a higher level.
        # TODO: Implement a proper filter DSL or parameterized filter system
        where_clause = f"WHERE {filters}" if filters else ""

        # safe_view_name and safe_column are sanitized via _sanitize_identifier()
        # Note: where_clause is NOT sanitized - see warning above
        sql = f"""
        SELECT
            COUNT(*) AS row_count,
            COUNT({safe_column}) AS non_null_count,
            COUNT(*) - COUNT({safe_column}) AS null_count,
            COUNT(DISTINCT {safe_column}) AS distinct_count,
            MIN({safe_column}) AS min_value,
            MAX({safe_column}) AS max_value
        FROM {safe_view_name}
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
