# Table Sleuth - Product Specification (MVP v1)

## 1. Vision

Table Sleuth is a forensics focused explorer for open table formats. It lets data platform engineers inspect table level and file level metadata, understand merge on read behavior, and profile data using a fast analytics engine.

MVP v1 targets Apache Iceberg tables accessed through a local catalog and direct metadata files, with a Textual based TUI and a GizmoSQL backed DuckDB profiling service. Later MVPs will add Glue based catalogs and additional formats such as Delta Lake and Hudi.

## 2. Goals for MVP v1

1. Inspect Apache Iceberg tables located on local storage or S3 using a local file catalog and direct metadata access.
2. Provide a Textual based terminal UI that surfaces:
   - Table level metadata
   - Snapshot history
   - File level details (data files and delete files)
   - Basic merge on read impact metrics
3. Integrate with a GizmoSQL DuckDB server running in Docker for:
   - Column level profiling of snapshot data
   - Performance profiling to measure merge-on-read query overhead
4. Abstract the profiling engine so that a different backend such as PySpark can be substituted in a future MVP without changing the TUI.

## 3. Non goals for MVP v1

- No write operations on Iceberg tables. Table Sleuth is read only in MVP v1.
- No Glue, REST, or Hive catalogs for production. Only local file based and StaticTable style metadata access.
- No Delta or Hudi support yet, although the abstraction for format specific metadata will be designed with them in mind.
- No distributed compute. Profiling is single node via GizmoSQL backed DuckDB.

## 4. Target users and personas

- **Data Platform Engineer**
  Responsible for Iceberg table health, storage layout, and performance. Needs to understand how snapshots, delete files, and Parquet file structures impact query behavior.

- **Analytics Engineer / Senior Data Engineer**
  Investigates data anomalies and quality issues. Needs to quickly profile columns and see how data has changed across snapshots.

- **Site Reliability Engineer for Data Platform**
  Helps debug incidents related to data availability and query performance. Needs to understand whether a table is heavily fragmented or overrun by delete files.

## 5. User stories and acceptance criteria

### Story 1 - Inspect a local Iceberg table

**As** a data platform engineer
**I want** to point Table Sleuth at a local Iceberg table managed by a local catalog
**So that** I can see its schema, snapshots, and file level metadata

**Acceptance criteria**

1. Given a configured local file catalog, when I launch the TUI with `table-sleuth-tui --catalog local my_db.my_table`, the app opens without error.
2. The top level view shows:
   - Table identifier
   - Table location
   - Format version
   - Current snapshot id
3. A snapshots panel lists at least:
   - Snapshot id
   - Timestamp
   - Operation (append, overwrite, delete, etc.)
4. Selecting a snapshot populates a files panel with:
   - Data files and delete files
   - File path
   - File size in bytes
   - Record count
   - Content type (data, position deletes, equality deletes)

### Story 2 - Inspect an Iceberg table directly from S3 metadata

**As** a data platform engineer
**I want** to open an Iceberg table by pointing at an S3 location or metadata file
**So that** I can perform forensics without needing a full Glue or REST catalog

**Acceptance criteria**

1. When I launch `table-sleuth-tui s3://bucket/path/to/table`, and the path is a valid Iceberg table root, the app loads snapshot and file metadata via `StaticTable` or equivalent.
2. When I launch `table-sleuth-tui s3://bucket/path/to/table/metadata/00001-...metadata.json`, the app loads that specific metadata file and resolves the table state correctly.
3. If the path is not a valid Iceberg table, the app displays a clear error message instead of a stack trace.

### Story 3 - View file level Parquet structure

**As** a data platform engineer
**I want** to inspect the Parquet structure of a single data file in a snapshot
**So that** I can understand row group layout and column level statistics

**Acceptance criteria**

1. When I select a data file in the files panel, a details view appears for that file.
2. The file details view shows at minimum:
   - Number of rows
   - Number of row groups
   - Row count per row group
3. For each column in the file, the view shows:
   - Column name
   - Physical type
   - Logical type (if present)
   - Null count
   - Min and max values if available from statistics
4. If column statistics are not available for specific types, the UI indicates that they are not available rather than displaying incorrect values.

### Story 4 - Basic merge on read impact summary

**As** a data platform engineer
**I want** a quick summary of how delete files affect a snapshot
**So that** I can determine whether merge on read is likely to hurt query performance

**Acceptance criteria**

1. For a selected snapshot, a merge on read summary view shows:
   - Number of base data files
   - Number of delete files, broken down by delete type
   - Total base row count (sum of data file record counts)
   - Total delete row count (sum of delete file record counts)
   - Estimated effective row count (base rows minus delete rows), clearly labeled as an estimate
2. For each data file, the files panel shows:
   - How many delete files are associated with that file, based on partition or other metadata linkage that MVP supports
3. The UI clearly indicates that merge on read numbers are estimates for equality deletes unless full application is performed.

### Story 5 - Run column level profiling through GizmoSQL

**As** an analytics engineer
**I want** to profile a column in a snapshot using a DuckDB backed profiling engine
**So that** I can quickly understand distributions, null rates, and distinct counts

**Acceptance criteria**

1. Given a running GizmoSQL Docker container configured to access the same storage as the table data, the user can configure connection settings in a simple config file or environment variables.
2. In the TUI, when I select a snapshot and a column, I can trigger a profile action.
3. The profile result view shows at minimum:
   - Row count
   - Non null count
   - Null count
   - Distinct count
   - Min and max values for numeric and date like types
4. If the profiling backend is unavailable, the UI displays a clear error and does not block other parts of the application.
5. Profiling logic is routed through an abstraction so that the implementation details of GizmoSQL are not tied directly into the TUI widget code.

### Story 6 - Performance profiling for merge-on-read queries

**As** a data platform engineer
**I want** to measure the performance impact of merge-on-read operations on query execution
**So that** I can understand whether delete files are causing query slowdowns and decide when to compact

**Acceptance criteria**

1. For a selected snapshot, I can trigger a performance profile that executes a representative query (e.g., `SELECT COUNT(*) WHERE <filter>`) with and without delete file application.
2. The performance profile view shows:
   - Query execution time with merge-on-read (full delete application)
   - Query execution time without delete application (base data only)
   - Performance overhead percentage
   - Number of delete files applied
   - Total rows scanned vs. rows returned after deletes
3. The profiling can be run with different filter predicates to test various query patterns.
4. Results include timing breakdown:
   - Data file scan time
   - Delete file scan time
   - Merge operation time
   - Total query time
5. The UI clearly indicates that performance measurements are approximate and may vary based on cache state and system load.
6. Performance profiling is optional and can be disabled if the profiling backend doesn't support it.

### Story 7 - Profiling backend abstraction

**As** a data platform architect
**I want** the profiling engine to be abstracted behind an interface
**So that** I can add a PySpark based implementation in a future MVP without rewriting the UI

**Acceptance criteria**

1. The profiling component is expressed as an interface or abstract class with methods such as:
   - `profile_snapshot_columns(snapshot_handle, columns, filters)`
   - `profile_single_column(snapshot_handle, column, filters)`
   - `profile_query_performance(snapshot_handle, query, with_deletes, without_deletes)`
2. A concrete `GizmoDuckDbProfiler` is implemented and registered as the default implementation for MVP v1.
3. No Textual widget imports the GizmoSQL or Flight SQL client directly. Widgets talk only to the profiling abstraction.
4. Unit tests exist that verify the behaviors of the profiling interface using a fake or stub implementation.

## 6. Success metrics for MVP v1

- Engineers can successfully inspect at least three different Iceberg tables in local testing:
  - A small local dev table
  - A medium table with delete files
  - An S3 backed table with multiple snapshots
- Column profiling can be executed against at least one test dataset through GizmoSQL with profiles returning in a few seconds.
- Performance profiling successfully measures merge-on-read overhead on tables with delete files, showing measurable timing differences between queries with and without delete application.
- Early users report that merge on read summaries, performance profiling, and file level views help them reason about performance or data anomalies that were previously opaque.
- Performance profiling helps engineers make data-driven decisions about when to trigger table compaction.
