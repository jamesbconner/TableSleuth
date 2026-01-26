from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Any, Optional

from adbc_driver_flightsql import DatabaseOptions
from adbc_driver_flightsql import dbapi as flightsql

from tablesleuth.models import ColumnProfile, SnapshotInfo
from tablesleuth.models.iceberg import QueryPerformanceMetrics
from tablesleuth.utils.path_utils import is_s3_path

from .backend_base import ProfilingBackend

logger = logging.getLogger(__name__)


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


def _clean_file_path(path: str) -> str:
    """Remove file:// prefix from paths if present.

    Args:
        path: File path that may include file:// prefix

    Returns:
        Cleaned path without file:// prefix
    """
    if path.startswith("file://"):
        return path[7:]
    return path


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
        self._registered_catalogs: dict[str, str] = {}  # catalog_name -> catalog_path

    def _connect(self) -> Any:
        """Create a FlightSQL connection.

        Returns:
            FlightSQL connection object
        """
        # Determine if we should use TLS based on URI scheme
        # grpc:// = plain (no TLS), grpc+tls:// = TLS
        use_tls = self._uri.startswith("grpc+tls://")

        db_kwargs = {
            "username": self._username,
            "password": self._password,
        }

        # Only add TLS options if using TLS
        if use_tls:
            db_kwargs[DatabaseOptions.TLS_SKIP_VERIFY.value] = (
                "true" if self._tls_skip_verify else "false"
            )

        return flightsql.connect(
            uri=self._uri,
            db_kwargs=db_kwargs,
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

        # Clean file paths (remove file:// prefix if present)
        cleaned_paths = [_clean_file_path(path) for path in file_paths]

        # Store the cleaned file paths mapping for this view name
        if not hasattr(self, "_view_paths"):
            self._view_paths = {}
        self._view_paths[safe_view_name] = cleaned_paths

        return safe_view_name

    def profile_single_column(
        self,
        view_name: str,
        column: str,
        filters: str | None = None,
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
                escaped_path = file_paths[0].replace("'", "''")
                from_clause = f"read_parquet('{escaped_path}')"
            else:
                escaped_paths = [path.replace("'", "''") for path in file_paths]
                paths_list = ", ".join(f"'{p}'" for p in escaped_paths)
                from_clause = f"read_parquet([{paths_list}])"
        else:
            # Fallback: assume view_name is a table/view name
            from_clause = safe_view_name

        # First, detect if column is numeric by checking its type
        type_check_sql = f"""
        SELECT typeof({safe_column}) AS col_type
        FROM {from_clause}
        WHERE {safe_column} IS NOT NULL
        LIMIT 1
        """  # nosec B608

        is_numeric = False
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(type_check_sql)
            type_row = cur.fetchone()
            if type_row:
                col_type = type_row[0].upper()
                is_numeric = col_type in (
                    "TINYINT",
                    "SMALLINT",
                    "INTEGER",
                    "BIGINT",
                    "HUGEINT",
                    "FLOAT",
                    "DOUBLE",
                    "DECIMAL",
                )

        # Build SQL query with conditional numeric statistics
        if is_numeric:
            # safe_view_name and safe_column are sanitized via _sanitize_identifier()
            # filters is validated via _validate_filter_expression()
            sql = f"""
            SELECT
                COUNT(*) AS row_count,
                COUNT({safe_column}) AS non_null_count,
                COUNT(*) - COUNT({safe_column}) AS null_count,
                COUNT(DISTINCT {safe_column}) AS distinct_count,
                MIN({safe_column}) AS min_value,
                MAX({safe_column}) AS max_value,
                AVG({safe_column}) AS average,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {safe_column}) AS median,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {safe_column}) AS q1,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {safe_column}) AS q3,
                STDDEV({safe_column}) AS std_dev,
                VARIANCE({safe_column}) AS variance
            FROM {from_clause}
            {where_clause}
            """  # nosec B608
        else:
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

        # Get mode (most frequent value) with separate query
        mode = None
        mode_count = None
        try:
            mode_sql = f"""
            SELECT {safe_column}, COUNT(*) AS frequency
            FROM {from_clause}
            WHERE {safe_column} IS NOT NULL
            {where_clause.replace("WHERE", "AND") if where_clause else ""}
            GROUP BY {safe_column}
            ORDER BY frequency DESC
            LIMIT 1
            """  # nosec B608

            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(mode_sql)
                mode_row = cur.fetchone()
                if mode_row:
                    mode = mode_row[0]
                    mode_count = mode_row[1]
        except Exception as e:
            # Mode calculation failed, leave as None
            logger.debug(f"Could not calculate mode: {e}")

        # Build ColumnProfile with extended fields
        if is_numeric and len(row) > 6:
            return ColumnProfile(
                column=column,
                row_count=row[0],
                non_null_count=row[1],
                null_count=row[2],
                distinct_count=row[3],
                min_value=row[4],
                max_value=row[5],
                is_numeric=True,
                average=row[6],
                median=row[7],
                mode=mode,
                mode_count=mode_count,
                q1=row[8],
                q3=row[9],
                std_dev=row[10],
                variance=row[11],
            )
        else:
            return ColumnProfile(
                column=column,
                row_count=row[0],
                non_null_count=row[1],
                null_count=row[2],
                distinct_count=row[3],
                min_value=row[4],
                max_value=row[5],
                is_numeric=False,
                mode=mode,
                mode_count=mode_count,
            )

    def profile_columns(
        self,
        view_name: str,
        columns: Sequence[str],
        filters: str | None = None,
    ) -> dict[str, ColumnProfile]:
        return {col: self.profile_single_column(view_name, col, filters) for col in columns}

    def clear_views(self) -> None:
        """Clear all registered view-to-file mappings.

        This removes all stored file path mappings, forcing views to be
        re-registered on next use. Useful when refreshing or invalidating caches.
        """
        if hasattr(self, "_view_paths"):
            self._view_paths.clear()

    def register_iceberg_table(self, table_identifier: str, metadata_location: str) -> None:
        """Register an Iceberg table for querying.

        Note: DuckDB's Iceberg extension reads tables directly from metadata files,
        not through PyIceberg catalogs.

        Args:
            table_identifier: Full table identifier (e.g., "snapshot_tests.table_snap_123")
            metadata_location: Path to the Iceberg metadata JSON file

        Raises:
            ValueError: If table_identifier or metadata_location is invalid
        """
        self.register_iceberg_table_with_snapshot(table_identifier, metadata_location, None)

    def register_iceberg_table_with_snapshot(
        self, table_identifier: str, metadata_location: str, snapshot_id: int | None = None
    ) -> None:
        """Register an Iceberg table with a specific snapshot for querying.

        Note: DuckDB's Iceberg extension reads tables directly from metadata files,
        not through PyIceberg catalogs.

        Args:
            table_identifier: Full table identifier (e.g., "snapshot_tests.table_snap_123")
            metadata_location: Path to the Iceberg metadata JSON file
            snapshot_id: Optional snapshot ID to query (None for current snapshot)

        Raises:
            ValueError: If table_identifier or metadata_location is invalid
        """
        if not table_identifier or not metadata_location:
            raise ValueError("table_identifier and metadata_location are required")

        # Clean metadata location (remove file:// prefix if present)
        clean_metadata_location = _clean_file_path(metadata_location)

        # Store the mapping with snapshot info
        if not hasattr(self, "_iceberg_tables"):
            self._iceberg_tables: dict[str, tuple[str, int | None]] = {}

        self._iceberg_tables[table_identifier] = (clean_metadata_location, snapshot_id)
        logger.debug(
            f"Registered Iceberg table {table_identifier} -> {clean_metadata_location}"
            + (f" (snapshot {snapshot_id})" if snapshot_id else "")
        )

    def execute_query_with_metrics(self, query: str) -> tuple[Any, QueryPerformanceMetrics]:
        """Execute query and return results plus detailed metrics.

        For Iceberg tables, this method replaces table references with iceberg_scan()
        function calls using the registered metadata locations.

        Args:
            query: SQL query to execute

        Returns:
            Tuple of (query results, performance metrics)

        Raises:
            RuntimeError: If query execution fails
        """
        import time

        try:
            # Replace Iceberg table references with iceberg_scan() calls
            modified_query = self._replace_iceberg_tables(query)

            with self._connect() as conn, conn.cursor() as cur:
                # Install and load Iceberg extension
                try:
                    cur.execute("INSTALL iceberg")
                    cur.execute("LOAD iceberg")
                except Exception as e:
                    logger.warning(f"Failed to install/load Iceberg extension: {e}")

                # Execute query and measure time
                start_time = time.time()
                cur.execute(modified_query)
                results = cur.fetchall()
                execution_time_ms = (time.time() - start_time) * 1000

                # Get EXPLAIN ANALYZE output for detailed metrics
                explain_query = f"EXPLAIN ANALYZE {modified_query}"
                cur.execute(explain_query)
                explain_output = cur.fetchall()

                # Debug: Log the explain output to see what we're getting
                logger.debug(f"EXPLAIN ANALYZE output: {explain_output}")

                # Parse metrics from EXPLAIN ANALYZE output
                metrics = self._parse_explain_analyze(
                    explain_output, execution_time_ms, modified_query
                )

                return results, metrics

        except Exception as e:
            raise RuntimeError(f"Query execution failed: {e}") from e

    def _replace_iceberg_tables(self, query: str) -> str:
        """Replace Iceberg table references with iceberg_scan() calls.

        Args:
            query: Original SQL query

        Returns:
            Modified query with iceberg_scan() calls
        """
        if not hasattr(self, "_iceberg_tables") or not self._iceberg_tables:
            return query

        modified_query = query
        for table_id, table_info in self._iceberg_tables.items():
            # Unpack table info tuple
            metadata_loc, snapshot_id = table_info

            # Escape single quotes in metadata location to prevent SQL injection
            # SQL standard: escape single quotes by doubling them
            escaped_metadata_loc = metadata_loc.replace("'", "''")

            # Build iceberg_scan() call with optional snapshot parameter
            # Validate snapshot_id is actually an integer to prevent SQL injection
            if snapshot_id is not None:
                if not isinstance(snapshot_id, int):
                    raise ValueError(f"snapshot_id must be an integer, got {type(snapshot_id)}")
                scan_call = f"iceberg_scan('{escaped_metadata_loc}', version => {snapshot_id})"
            else:
                scan_call = f"iceberg_scan('{escaped_metadata_loc}')"

            # Replace table references with iceberg_scan()
            # Handle both quoted and unquoted table names
            patterns = [
                rf"\b{re.escape(table_id)}\b",  # Unquoted
                rf'"{re.escape(table_id)}"',  # Double quoted
                rf"'{re.escape(table_id)}'",  # Single quoted
            ]

            for pattern in patterns:
                modified_query = re.sub(pattern, scan_call, modified_query, flags=re.IGNORECASE)

        if modified_query != query:
            logger.debug(
                f"Replaced Iceberg tables in query:\nOriginal: {query}\nModified: {modified_query}"
            )

        return modified_query

    def explain_analyze(self, query: str) -> str:
        """Get query execution plan with timing information.

        Args:
            query: SQL query to analyze

        Returns:
            Formatted execution plan text

        Raises:
            RuntimeError: If EXPLAIN ANALYZE fails
        """
        try:
            with self._connect() as conn, conn.cursor() as cur:
                explain_query = f"EXPLAIN ANALYZE {query}"
                cur.execute(explain_query)
                rows = cur.fetchall()

                # Format output as text
                return "\n".join(str(row[0]) for row in rows)

        except Exception as e:
            raise RuntimeError(f"EXPLAIN ANALYZE failed: {e}") from e

    def _parse_explain_analyze(
        self, explain_output: list, execution_time_ms: float, query: str
    ) -> QueryPerformanceMetrics:
        """Parse EXPLAIN ANALYZE output to extract metrics.

        Args:
            explain_output: Raw EXPLAIN ANALYZE output
            execution_time_ms: Measured execution time
            query: Original query (for fallback file count extraction)

        Returns:
            QueryPerformanceMetrics object
        """
        import re

        # Default values
        files_scanned = 0
        bytes_scanned = 0
        rows_scanned = 0
        rows_returned = 0
        memory_peak_mb = 0.0

        # Parse explain output
        explain_text = "\n".join(str(row[0]) for row in explain_output)

        # DuckDB EXPLAIN ANALYZE patterns
        # Look for PARQUET_SCAN or ICEBERG_SCAN with file counts
        scan_patterns = [
            r"PARQUET_SCAN.*?(\d+)\s+Files",
            r"ICEBERG_SCAN.*?(\d+)\s+Files",
            r"Scanning\s+(\d+)\s+files?",
        ]
        for pattern in scan_patterns:
            match = re.search(pattern, explain_text, re.IGNORECASE | re.DOTALL)
            if match:
                files_scanned = max(files_scanned, int(match.group(1)))

        # Look for rows scanned (from scan operators - before filtering)
        scan_row_patterns = [
            r"(?:PARQUET_SCAN|ICEBERG_SCAN).*?(\d+)\s+Rows",
            r"(?:PARQUET_SCAN|ICEBERG_SCAN).*?Cardinality:\s*(\d+)",
        ]
        for pattern in scan_row_patterns:
            match = re.search(pattern, explain_text, re.IGNORECASE | re.DOTALL)
            if match:
                rows_scanned = max(rows_scanned, int(match.group(1)))

        # Look for rows returned (final result - after filtering)
        result_row_patterns = [
            r"Result:\s*(\d+)\s+rows?",
            r"RESULT.*?(\d+)\s+Rows",
            r"RESULT.*?Cardinality:\s*(\d+)",
        ]
        for pattern in result_row_patterns:
            match = re.search(pattern, explain_text, re.IGNORECASE | re.DOTALL)
            if match:
                rows_returned = max(rows_returned, int(match.group(1)))

        # If we didn't find distinct values, use rows_returned as fallback for rows_scanned
        if rows_scanned == 0 and rows_returned > 0:
            rows_scanned = rows_returned

        # Look for bytes scanned - aggregate all occurrences using max
        bytes_patterns = [
            r"(\d+(?:\.\d+)?)\s*(MB|GB|KB|Bytes)",
        ]
        for pattern in bytes_patterns:
            for match in re.finditer(pattern, explain_text, re.IGNORECASE):
                value = float(match.group(1))
                unit = match.group(2).upper()
                current_bytes = 0
                if unit == "BYTES":
                    current_bytes = int(value)
                elif unit == "KB":
                    current_bytes = int(value * 1024)
                elif unit == "MB":
                    current_bytes = int(value * 1024 * 1024)
                elif unit == "GB":
                    current_bytes = int(value * 1024 * 1024 * 1024)
                bytes_scanned = max(bytes_scanned, current_bytes)

        # Fallback: If files_scanned is still 0, try to extract from iceberg_scan() calls in query
        if files_scanned == 0:
            # Look for iceberg_scan calls with metadata locations
            # Pattern matches: iceberg_scan('path') or iceberg_scan('path', version => 12345)
            # Handles SQL-escaped single quotes ('') in paths
            iceberg_scan_pattern = r"iceberg_scan\('((?:[^']|'')+)'(?:,\s*version\s*=>\s*(\d+))?\)"
            for match in re.finditer(iceberg_scan_pattern, query, re.IGNORECASE):
                # Unescape SQL single quotes ('' -> ')
                metadata_location = match.group(1).replace("''", "'")
                snapshot_id = match.group(2) if match.group(2) else None

                # Try to get file count from Iceberg metadata
                try:
                    file_count = self._get_iceberg_file_count(metadata_location, snapshot_id)
                    files_scanned += file_count
                    logger.debug(
                        f"Fallback: Got {file_count} files from Iceberg metadata "
                        f"for {metadata_location}"
                    )
                except Exception as e:
                    logger.debug(f"Could not get file count from Iceberg metadata: {e}")

        return QueryPerformanceMetrics(
            execution_time_ms=execution_time_ms,
            files_scanned=files_scanned,
            bytes_scanned=bytes_scanned,
            rows_scanned=rows_scanned,
            rows_returned=rows_returned,
            memory_peak_mb=memory_peak_mb,
        )

    def _get_iceberg_file_count(self, metadata_location: str, snapshot_id: str | None) -> int:
        """Get file count from Iceberg metadata.

        Args:
            metadata_location: Path to Iceberg metadata JSON file
            snapshot_id: Optional snapshot ID to query specific snapshot

        Returns:
            Number of data files in the snapshot

        Raises:
            Exception: If metadata cannot be read or parsed
        """
        import json

        from tablesleuth.services.filesystem import FileSystem

        # Read metadata file
        fs = FileSystem()

        if is_s3_path(metadata_location):
            with fs.open_file(metadata_location, "rb") as file_obj:
                metadata = json.load(file_obj)
        else:
            with open(metadata_location) as f:
                metadata = json.load(f)

        # Get current snapshot or specific snapshot
        if snapshot_id:
            target_snapshot_id = int(snapshot_id)
            snapshot = None
            for snap in metadata.get("snapshots", []):
                if snap["snapshot-id"] == target_snapshot_id:
                    snapshot = snap
                    break
            if not snapshot:
                raise ValueError(f"Snapshot {snapshot_id} not found in metadata")
        else:
            current_snapshot_id = metadata.get("current-snapshot-id")
            if not current_snapshot_id:
                return 0
            snapshot = None
            for snap in metadata.get("snapshots", []):
                if snap["snapshot-id"] == current_snapshot_id:
                    snapshot = snap
                    break
            if not snapshot:
                return 0

        # Get manifest list and count files
        manifest_list_path = snapshot.get("manifest-list")
        if not manifest_list_path:
            return 0

        # For now, return summary stats if available
        summary = snapshot.get("summary", {})
        total_data_files = summary.get("total-data-files")
        if total_data_files:
            return int(total_data_files)

        # If summary not available, would need to read manifest list
        # This is a simplified version - full implementation would parse manifests
        logger.debug("Could not get file count from snapshot summary")
        return 0
