"""Data models for Apache Iceberg metadata."""

from __future__ import annotations

from dataclasses import dataclass

from pyiceberg.table import Table


@dataclass
class IcebergTableInfo:
    """Information about an Iceberg table.

    Attributes:
        metadata_location: Path to the table's metadata file
        format_version: Iceberg format version (1 or 2)
        table_uuid: Unique identifier for the table
        location: Base path for table data files
        current_snapshot_id: ID of the current snapshot, if any
        properties: Table properties as key-value pairs
        native_table: PyIceberg Table object for direct access
    """

    metadata_location: str
    format_version: int
    table_uuid: str
    location: str
    current_snapshot_id: int | None
    properties: dict[str, str]
    native_table: Table


@dataclass
class IcebergSnapshotInfo:
    """Information about an Iceberg snapshot.

    Represents a point-in-time view of an Iceberg table with all its data
    and delete files. Includes derived metrics for merge-on-read analysis.

    Attributes:
        snapshot_id: Unique identifier for this snapshot
        parent_snapshot_id: ID of the parent snapshot, if any
        timestamp_ms: Snapshot creation time in milliseconds since epoch
        operation: Operation type (APPEND, OVERWRITE, DELETE, etc.)
        summary: Summary statistics from snapshot metadata
        manifest_list: Path to the manifest list file
        schema_id: ID of the schema used by this snapshot
        total_records: Total number of records in the table
        total_data_files: Number of data files
        total_delete_files: Number of delete files
        total_size_bytes: Total size of all files in bytes
        position_deletes: Number of position delete records
        equality_deletes: Number of equality delete records
    """

    snapshot_id: int
    parent_snapshot_id: int | None
    timestamp_ms: int
    operation: str
    summary: dict[str, str]
    manifest_list: str
    schema_id: int
    total_records: int
    total_data_files: int
    total_delete_files: int
    total_size_bytes: int
    position_deletes: int
    equality_deletes: int

    @property
    def has_deletes(self) -> bool:
        """Check if snapshot has delete files.

        Returns:
            True if the snapshot contains any delete files
        """
        return self.total_delete_files > 0

    @property
    def delete_ratio(self) -> float:
        """Calculate percentage of deleted records.

        Returns:
            Percentage of records that are deleted (0-100)
        """
        if self.total_records == 0:
            return 0.0
        deleted = self.position_deletes + self.equality_deletes
        return (deleted / self.total_records) * 100

    @property
    def read_amplification(self) -> float:
        """Calculate read amplification factor.

        Read amplification is the ratio of total files that must be read
        (data + delete files) to the number of data files. Higher values
        indicate more merge-on-read overhead.

        Returns:
            Read amplification factor (>= 1.0)
        """
        if self.total_data_files == 0:
            return 1.0
        total_files = self.total_data_files + self.total_delete_files
        return total_files / self.total_data_files


@dataclass
class SchemaField:
    """Schema field information.

    Attributes:
        field_id: Unique field identifier
        name: Field name
        field_type: Field data type as string
        required: Whether the field is required
        doc: Optional field documentation
    """

    field_id: int
    name: str
    field_type: str
    required: bool
    doc: str | None


@dataclass
class SchemaInfo:
    """Schema information.

    Attributes:
        schema_id: Unique schema identifier
        fields: List of schema fields
    """

    schema_id: int
    fields: list[SchemaField]


@dataclass
class PartitionField:
    """Partition field information.

    Attributes:
        field_id: Unique partition field identifier
        source_id: Source column field ID
        name: Partition field name
        transform: Transform function (identity, bucket, truncate, year, month, day, hour)
    """

    field_id: int
    source_id: int
    name: str
    transform: str


@dataclass
class PartitionSpecInfo:
    """Partition specification information.

    Attributes:
        spec_id: Unique partition spec identifier
        fields: List of partition fields
    """

    spec_id: int
    fields: list[PartitionField]


@dataclass
class SortField:
    """Sort field information.

    Attributes:
        source_id: Source column field ID
        transform: Transform function applied before sorting
        direction: Sort direction (ASC or DESC)
        null_order: Null ordering (NULLS FIRST or NULLS LAST)
    """

    source_id: int
    transform: str
    direction: str
    null_order: str


@dataclass
class SortOrderInfo:
    """Sort order information.

    Attributes:
        order_id: Unique sort order identifier
        fields: List of sort fields
    """

    order_id: int
    fields: list[SortField]


@dataclass
class IcebergSnapshotDetails:
    """Detailed information about a snapshot.

    Attributes:
        snapshot_info: Basic snapshot information
        data_files: List of data file references
        delete_files: List of delete file references
        schema: Schema information
        partition_spec: Partition specification
        sort_order: Sort order, if any
    """

    snapshot_info: IcebergSnapshotInfo
    data_files: list
    delete_files: list
    schema: SchemaInfo
    partition_spec: PartitionSpecInfo
    sort_order: SortOrderInfo | None


@dataclass
class SnapshotComparison:
    """Comparison between two snapshots.

    Provides detailed metrics about changes between two snapshots,
    including file changes, record changes, size changes, and MOR metrics.

    Attributes:
        snapshot_a: First snapshot (typically earlier)
        snapshot_b: Second snapshot (typically later)
        data_files_added: Number of data files added
        data_files_removed: Number of data files removed
        delete_files_added: Number of delete files added
        delete_files_removed: Number of delete files removed
        records_added: Number of records added
        records_deleted: Number of records deleted
        records_delta: Net change in record count
        size_added_bytes: Bytes added
        size_removed_bytes: Bytes removed
        size_delta_bytes: Net change in size
        delete_ratio_change: Change in delete ratio percentage
        read_amplification_change: Change in read amplification factor
    """

    snapshot_a: IcebergSnapshotInfo
    snapshot_b: IcebergSnapshotInfo
    data_files_added: int
    data_files_removed: int
    delete_files_added: int
    delete_files_removed: int
    records_added: int
    records_deleted: int
    records_delta: int
    size_added_bytes: int
    size_removed_bytes: int
    size_delta_bytes: int
    delete_ratio_change: float
    read_amplification_change: float

    @property
    def needs_compaction(self) -> bool:
        """Determine if compaction is recommended.

        Compaction is recommended if:
        - Delete ratio exceeds 10%
        - Read amplification exceeds 1.2x

        Returns:
            True if compaction is recommended
        """
        return self.snapshot_b.delete_ratio > 10.0 or self.snapshot_b.read_amplification > 1.2

    @property
    def compaction_recommendation(self) -> str:
        """Get compaction recommendation message.

        Returns:
            Human-readable recommendation message
        """
        if not self.needs_compaction:
            return "No compaction needed"

        reasons = []
        if self.snapshot_b.delete_ratio > 10.0:
            reasons.append(f"Delete ratio is {self.snapshot_b.delete_ratio:.1f}%")
        if self.snapshot_b.read_amplification > 1.2:
            reasons.append(f"Read amplification is {self.snapshot_b.read_amplification:.2f}x")

        return f"⚠️  Compaction recommended: {', '.join(reasons)}"


@dataclass
class QueryPerformanceMetrics:
    """Performance metrics for a query execution.

    Attributes:
        execution_time_ms: Total query execution time in milliseconds
        files_scanned: Number of files scanned
        bytes_scanned: Total bytes scanned
        rows_scanned: Total rows scanned (before filtering)
        rows_returned: Rows returned (after filtering)
        memory_peak_mb: Peak memory usage in megabytes
    """

    execution_time_ms: float
    files_scanned: int
    bytes_scanned: int
    rows_scanned: int
    rows_returned: int
    memory_peak_mb: float

    @property
    def scan_efficiency(self) -> float:
        """Calculate scan efficiency percentage.

        Scan efficiency is the ratio of rows returned to rows scanned.
        Lower values indicate more wasted work due to filtering or deletes.

        Returns:
            Scan efficiency as percentage (0-100)
        """
        if self.rows_scanned == 0:
            return 100.0
        return (self.rows_returned / self.rows_scanned) * 100


@dataclass
class PerformanceComparison:
    """Comparison of query performance between two snapshots.

    Attributes:
        query: SQL query that was executed
        table_a_name: Name of first snapshot table
        table_b_name: Name of second snapshot table
        metrics_a: Performance metrics for first snapshot
        metrics_b: Performance metrics for second snapshot
        snapshot_a_info: Full snapshot info for snapshot A (optional)
        snapshot_b_info: Full snapshot info for snapshot B (optional)
    """

    query: str
    table_a_name: str
    table_b_name: str
    metrics_a: QueryPerformanceMetrics
    metrics_b: QueryPerformanceMetrics
    snapshot_a_info: IcebergSnapshotInfo | None = None
    snapshot_b_info: IcebergSnapshotInfo | None = None

    @property
    def execution_time_delta_pct(self) -> float:
        """Calculate execution time change percentage.

        Returns:
            Percentage change in execution time (positive = slower)
        """
        if self.metrics_a.execution_time_ms == 0:
            return 0.0
        delta = self.metrics_b.execution_time_ms - self.metrics_a.execution_time_ms
        return (delta / self.metrics_a.execution_time_ms) * 100

    @property
    def files_scanned_delta_pct(self) -> float:
        """Calculate files scanned change percentage.

        Returns:
            Percentage change in files scanned
        """
        if self.metrics_a.files_scanned == 0:
            return 0.0
        delta = self.metrics_b.files_scanned - self.metrics_a.files_scanned
        return (delta / self.metrics_a.files_scanned) * 100

    @property
    def analysis(self) -> str:
        """Generate comprehensive analysis of performance differences.

        Considers multiple factors:
        - Data volume (file count, record count, size)
        - Delete files and MOR overhead
        - Scan efficiency
        - Read amplification

        Returns:
            Human-readable analysis of performance differences
        """
        lines = []

        # Determine which snapshot is slower
        if abs(self.execution_time_delta_pct) < 10:
            lines.append("• Query performance is similar between snapshots")
        else:
            slower_name = (
                self.table_b_name if self.execution_time_delta_pct > 0 else self.table_a_name
            )
            faster_name = (
                self.table_a_name if self.execution_time_delta_pct > 0 else self.table_b_name
            )
            pct_diff = abs(self.execution_time_delta_pct)

            slower_metrics = self.metrics_b if self.execution_time_delta_pct > 0 else self.metrics_a
            faster_metrics = self.metrics_a if self.execution_time_delta_pct > 0 else self.metrics_b

            slower_snapshot = (
                self.snapshot_b_info if self.execution_time_delta_pct > 0 else self.snapshot_a_info
            )
            faster_snapshot = (
                self.snapshot_a_info if self.execution_time_delta_pct > 0 else self.snapshot_b_info
            )

            lines.append(f"• Query is {pct_diff:.1f}% slower on {slower_name}")

            # Analyze contributing factors
            factors = []

            # Factor 1: Data volume (files scanned)
            if slower_metrics.files_scanned > faster_metrics.files_scanned:
                file_diff = slower_metrics.files_scanned - faster_metrics.files_scanned
                file_pct = (
                    (file_diff / faster_metrics.files_scanned * 100)
                    if faster_metrics.files_scanned > 0
                    else 0
                )
                factors.append(f"  - {file_diff} more files to scan (+{file_pct:.1f}%)")

            # Factor 2: Data size
            if slower_metrics.bytes_scanned > faster_metrics.bytes_scanned:
                size_diff_mb = (slower_metrics.bytes_scanned - faster_metrics.bytes_scanned) / (
                    1024 * 1024
                )
                if size_diff_mb > 1:
                    factors.append(f"  - {size_diff_mb:.1f} MB more data to read")

            # Factor 3: MOR overhead (delete files)
            if slower_snapshot and faster_snapshot:
                slower_deletes = slower_snapshot.total_delete_files
                faster_deletes = faster_snapshot.total_delete_files

                if slower_deletes > faster_deletes:
                    delete_diff = slower_deletes - faster_deletes
                    if slower_deletes > 0:
                        # Calculate read amplification impact
                        slower_amp = slower_snapshot.read_amplification
                        faster_amp = faster_snapshot.read_amplification

                        if slower_amp > faster_amp:
                            factors.append(
                                f"  - MOR overhead: {slower_deletes} delete files "
                                f"(read amplification: {slower_amp:.2f}x vs {faster_amp:.2f}x)"
                            )
                        else:
                            factors.append(f"  - {delete_diff} more delete files to process")

                # Factor 4: Delete ratio impact on scan efficiency
                if slower_snapshot.delete_ratio > faster_snapshot.delete_ratio:
                    ratio_diff = slower_snapshot.delete_ratio - faster_snapshot.delete_ratio
                    if ratio_diff > 5:
                        factors.append(
                            f"  - Higher delete ratio: {slower_snapshot.delete_ratio:.1f}% vs "
                            f"{faster_snapshot.delete_ratio:.1f}% "
                            f"({slower_snapshot.position_deletes + slower_snapshot.equality_deletes:,} deleted records)"
                        )

                # Factor 5: Record count difference
                if slower_snapshot.total_records > faster_snapshot.total_records:
                    record_diff = slower_snapshot.total_records - faster_snapshot.total_records
                    record_pct = (
                        (record_diff / faster_snapshot.total_records * 100)
                        if faster_snapshot.total_records > 0
                        else 0
                    )
                    if record_pct > 10:
                        factors.append(f"  - {record_diff:,} more records (+{record_pct:.1f}%)")

            # Factor 6: Scan efficiency
            eff_delta = slower_metrics.scan_efficiency - faster_metrics.scan_efficiency
            if eff_delta < -5:
                factors.append(
                    f"  - Lower scan efficiency: {slower_metrics.scan_efficiency:.1f}% vs "
                    f"{faster_metrics.scan_efficiency:.1f}%"
                )

            # Add factors to output
            if factors:
                lines.append("  Contributing factors:")
                lines.extend(factors)
            else:
                lines.append("  (performance difference may be due to query execution variance)")

        # Additional insights
        if self.snapshot_a_info and self.snapshot_b_info:
            # Check if compaction would help
            slower_snapshot = (
                self.snapshot_b_info if self.execution_time_delta_pct > 0 else self.snapshot_a_info
            )

            if slower_snapshot.delete_ratio > 10 or slower_snapshot.read_amplification > 1.5:
                lines.append("")
                lines.append("💡 Recommendation:")
                if slower_snapshot.delete_ratio > 10:
                    lines.append(
                        f"  - Consider compaction to remove {slower_snapshot.position_deletes + slower_snapshot.equality_deletes:,} "
                        f"deleted records ({slower_snapshot.delete_ratio:.1f}% of table)"
                    )
                if slower_snapshot.read_amplification > 1.5:
                    lines.append(
                        f"  - High read amplification ({slower_snapshot.read_amplification:.2f}x) indicates "
                        f"merge-on-read overhead"
                    )

        return "\n".join(lines)
