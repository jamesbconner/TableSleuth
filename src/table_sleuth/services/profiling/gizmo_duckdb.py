from __future__ import annotations

from typing import Dict, Sequence, Optional

from adbc_driver_flightsql import dbapi as flightsql
from adbc_driver_flightsql import DatabaseOptions

from table_sleuth.models import SnapshotInfo, ColumnProfile
from .backend_base import ProfilingBackend


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
                DatabaseOptions.TLS_SKIP_VERIFY.value: "true"
                if self._tls_skip_verify
                else "false",
            },
        )

    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        view_name = f"snap_{snapshot.snapshot_id}"
        paths = [f.path for f in snapshot.data_files]

        sql = f"""
        CREATE OR REPLACE VIEW {view_name} AS
        SELECT *
        FROM read_parquet($paths)
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"paths": paths})
        return view_name

    def profile_single_column(
        self,
        view_name: str,
        column: str,
        filters: Optional[str] = None,
    ) -> ColumnProfile:
        where_clause = f"WHERE {filters}" if filters else ""
        sql = f"""
        SELECT
            COUNT(*) AS row_count,
            COUNT({column}) AS non_null_count,
            COUNT(*) - COUNT({column}) AS null_count,
            COUNT(DISTINCT {column}) AS distinct_count,
            MIN({column}) AS min_value,
            MAX({column}) AS max_value
        FROM {view_name}
        {where_clause}
        """

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
    ) -> Dict[str, ColumnProfile]:
        return {
            col: self.profile_single_column(view_name, col, filters)
            for col in columns
        }
