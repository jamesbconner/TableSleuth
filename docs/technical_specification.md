# Table Sleuth - Technical Specification (MVP v1)

## 1. Overview

Table Sleuth is a Python project that inspects Apache Iceberg tables and their underlying Parquet files, and presents the results in a Textual based terminal UI. It is backed by a remote DuckDB instance exposed by a GizmoSQL container for data profiling.

The design is intentionally modular so that later MVPs can:

- Swap out the profiling backend for PySpark.
- Add support for other formats such as Delta Lake and Hudi.
- Integrate with production catalogs such as AWS Glue or Iceberg REST.

## 2. High level architecture

Logical components:

1. **Format metadata layer**
   - Responsible for connecting to a table, reading schemas, partitions, snapshots, manifests, data files, and delete files.
   - MVP v1 implements an Iceberg specific adapter using PyIceberg.

2. **File structure inspector**
   - Reads Parquet file metadata using PyArrow.
   - Produces structured summaries for the TUI to render.

3. **Merge on read analyzer**
   - Consumes snapshot and file metadata and produces:
     - Data file and delete file relationships.
     - Per file and per snapshot merge on read impact metrics.
   - MVP v1 focuses on summary level metrics, not full logical reconstruction of the dataset.

4. **Profiling engine**
   - Abstract interface with a concrete implementation that uses GizmoSQL and DuckDB via Arrow Flight SQL ADBC.
   - Operates on snapshot level views of table data.

5. **Presentation layer (Textual TUI)**
   - Provides a multi panel interface for:
     - Table metadata
     - Snapshot list
     - File list
     - File detail view
     - Merge on read summary
     - Profiling results

6. **Command line entry points**
   - Thin CLI wrappers around the TUI and profiling tools.

## 3. Package layout

Proposed directory structure:

```text
table-sleuth/
  pyproject.toml
  README.md
  table_sleuth/
    __init__.py
    config.py

    # Format abstraction
    formats/
      __init__.py
      base.py           # format neutral interfaces
      iceberg.py        # PyIceberg implementation for MVP v1

    # Metadata and analysis
    metadata/
      __init__.py
      models.py         # dataclasses / pydantic models
      snapshots.py      # snapshot and manifest modeling
      parquet_inspect.py
      mor_analyzer.py   # merge on read analyzer

    # Profiling abstraction and implementations
    profiling/
      __init__.py
      base.py           # ProfilingBackend abstract interface
      gizmo_duckdb.py   # GizmoSQL backed implementation

    # TUI
    tui/
      __init__.py
      app.py            # Textual App subclass
      views/
        __init__.py
        table_overview.py
        snapshots_view.py
        files_view.py
        file_detail_view.py
        mor_summary_view.py
        profile_view.py

    # CLI entry
    cli.py

  docs/
    product_spec.md
    tech_spec.md

  tests/
    test_open_table.py
    test_iceberg_adapter.py
    test_parquet_inspect.py
    test_mor_analyzer.py
    test_profiling_base.py
    test_gizmo_duckdb_profiler.py
    test_tui_smoke.py
```

## 4. Key Technical Decisions

### 4.1 Table formats and naming

- **Project name:** Table Sleuth
- **Python package name:** `table_sleuth`
- **MVP v1 focuses exclusively on Apache Iceberg**
- The architecture is intentionally extensible so additional adapters for Delta Lake and Hudi can be added later with minimal refactoring

We define a format-neutral interface for opening tables and listing snapshots. Each table format (Iceberg, Delta, Hudi) will implement this interface:
```python
# formats/base.py
from typing import Protocol, Iterable
from table_sleuth.metadata.models import TableHandle, SnapshotInfo, FileRef

class TableFormatAdapter(Protocol):
    def open_table(self, identifier: str, catalog_name: str | None = None) -> TableHandle: ...
    def list_snapshots(self, table: TableHandle) -> list[SnapshotInfo]: ...
    def load_snapshot(self, table: TableHandle, snapshot_id: int | None) -> SnapshotInfo: ...
    def iter_data_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]: ...
    def iter_delete_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]: ...
```

`formats.iceberg.IcebergAdapter` implements this interface using PyIceberg for MVP v1.

This structure allows Table Sleuth to grow into a multi-format forensic tool.

### 4.2 Catalog strategy for MVP v1

**Requirement:**

Test against local files and S3 objects using a local catalog, and avoid Glue or REST catalogs in MVP v1.

**Solution:**

- Use a file-based PyIceberg catalog (configured in `~/.pyiceberg.yaml`)
- Allow direct metadata loading from paths (local or S3) using `StaticTable.from_metadata()`

Example `.pyiceberg.yaml` entry:
```yaml
catalog:
  local:
    type: file
    warehouse: "file:/Users/you/iceberg_warehouse"
```

Adapter logic:
```python
# formats/iceberg.py
from pyiceberg.catalog import load_catalog
from pyiceberg.table import StaticTable

class IcebergAdapter(TableFormatAdapter):
    def open_table(self, identifier: str, catalog_name: str | None = None):
        if catalog_name:
            catalog = load_catalog(catalog_name)
            return catalog.load_table(identifier)
        return StaticTable.from_metadata(identifier)
```

This achieves:

- Support for local dev testing (local catalog)
- Ability to inspect any Iceberg table stored in S3 by simply pointing at the root path
- Zero dependency on Glue / REST services for MVP v1
- Clear migration path to deeper catalog support in MVP v2

### 4.3 GizmoSQL-based profiling engine (DuckDB over Arrow Flight SQL)

The user has requested:

> "Use the GizmoData variant of DuckDB (GizmoSQL) running in Docker for column profiling, through an abstraction allowing future swaps (e.g., PySpark)."

GizmoSQL exposes DuckDB as a Flight SQL endpoint.

We use the ADBC Flight SQL driver to query the backend:

```python
from adbc_driver_flightsql import dbapi as flightsql
from adbc_driver_flightsql import DatabaseOptions

class GizmoDuckDbProfiler(ProfilingBackend):
    def __init__(self, uri, username, password, tls_skip_verify=True):
        self.uri = uri
        self.username = username
        self.password = password
        self.tls_skip_verify = tls_skip_verify

    def _connect(self):
        return flightsql.connect(
            uri=self.uri,
            db_kwargs={
                "username": self.username,
                "password": self.password,
                DatabaseOptions.TLS_SKIP_VERIFY.value:
                    "true" if self.tls_skip_verify else "false",
            }
        )
```


**Assumptions:**

- The Docker container mounts local directories used for local Iceberg tables
- The container has AWS credentials for accessing s3:// Parquet files
- Table Sleuth does not start/stop the container; it only connects to it
- Performance expectations are “seconds” for profiling typical analytic columns

This cleanly separates profiling from the rest of the system and avoids embedding DuckDB directly into the Python process.

### 4.4 Profiling abstraction layer

We implement a backend-neutral profiling interface to allow easy swapping of engines (DuckDB → PySpark → Presto → custom backend).
```python
# profiling/base.py
from typing import Protocol, Sequence

class ColumnProfile(BaseModel):
    column: str
    row_count: int
    non_null_count: int
    null_count: int
    distinct_count: int | None
    min_value: object | None
    max_value: object | None

class ProfilingBackend(Protocol):
    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        """Creates a backend-specific SQL view for the snapshot."""

    def profile_single_column(self, view_name: str, column: str, filters: str | None = None) -> ColumnProfile: ...

    def profile_columns(self, view_name: str, columns: Sequence[str], filters: str | None = None) -> dict[str, ColumnProfile]: ...
```

For MVP v1 we will provide:

- `GizmoDuckDbProfiler` as the default runtime implementation
- `NullProfiler` for tests
- Future implementations (e.g. `SparkProfiler`) will plug in seamlessly

The TUI never imports GizmoSQL directly. It depends solely on `ProfilingBackend`.

### 4.5 Parquet structure inspector

Uses `pyarrow.parquet.ParquetFile` to extract:

- Schema (physical + logical)
- Row groups
- Row group row counts
- Column-level statistics
- Encodings and compression codecs

The metadata layer defines:
```python
@dataclass
class ColumnStats:
    name: str
    physical_type: str
    logical_type: str | None
    null_count: int
    min_value: object | None
    max_value: object | None
    encodings: list[str]
    compression: str

@dataclass
class ParquetFileInfo:
    path: str
    num_rows: int
    num_row_groups: int
    row_group_sizes: list[int]
    columns: list[ColumnStats]
```

These models provide structured input to the Textual UI without loading entire Parquet files.

### 4.6 Merge-on-read (MoR) analyzer

The MoR analyzer operates purely on Iceberg metadata and does not read data files.

It computes:

- Base file row counts
- Delete file row counts
- Estimated effective row counts
- Delete file counts per base file (position, equality)
- Snapshot-level MoR summary

Models:
```python
@dataclass
class FileMorImpact:
    file_path: str
    base_rows: int
    delete_rows_estimate: int
    effective_rows_estimate: int
    num_position_delete_files: int
    num_equality_delete_files: int

@dataclass
class SnapshotMorSummary:
    snapshot_id: int
    total_base_rows: int
    total_delete_rows_estimate: int
    total_effective_rows_estimate: int
    num_base_files: int
    num_delete_files: int
```

Limitations in MVP v1:

- Equality delete impacts are approximate
- Full logical reconstruction via DuckDB is deferred to MVP v2

This still provides high-value insight into fragmentation and MoR penalties.

### 4.7 Textual-based TUI

A multi-pane TUI will present the metadata in a structured and navigable form.

**Layout Summary:**

- **Header:** table id, snapshot id, storage location
- **Left panel:** snapshot list (DataTable)
- **Right panel (TabView):**
  - Files tab (data/delete files)
  - File detail tab (Parquet metadata)
  - Merge on Read tab (snapshot summary + file impacts)
  - Profile tab (column selection + results)
- **Footer:** keybindings

**Keybindings:**

- `↑/↓`: navigate lists
- `<tab>`: switch tabs
- `Enter`: select snapshot/file
- `p`: profile column
- `q`: quit

Textual is well suited for this level of interactivity.

### 4.8 Async design considerations

Some operations are slow:

- Reading metadata.json from S3

- Gathering large Parquet statistics

- Querying GizmoSQL

**Solution:**

- Use Textual’s async actions for these operations

- Keep UI responsive by showing loading indicators

- Cache results per snapshot to avoid repeated loads

### 4.9 Configuration model

Configuration hierarchy:

1. Environment variables
2. `table_sleuth.toml` (user-level config)
3. Built-in defaults

Example `table_sleuth.toml`:
```toml
[catalog]
default = "local"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmo"
password = "gizmo"
tls_skip_verify = true
```

PyIceberg catalog configuration remains in `~/.pyiceberg.yaml`.

### 4.10 Testing strategy

**Unit tests:**

- Mock Iceberg metadata for snapshot and manifest handling
- Parquet inspector tests using small known Parquet files
- Merge on read analyzer tests for multiple delete scenarios
- Profiling abstraction tests using a fake backend
- TUI smoke tests using textual-dev testing utilities

**Integration tests:**

- docker-compose spin-up of GizmoSQL
- Test profiling of small synthetic datasets
- Verify that snapshot views and column profiles return expected values

**No S3 dependency:**

We use `moto` (mock S3) or a local MinIO instance for S3-based table tests.

### 4.11 Extensibility strategy (post-MVP)

- Format adapter registry to add Delta Lake and Hudi
- Pluggable profiling backends for Spark, Trino, or Athena
- REST/Glue catalog integration for enterprise deployments
- Full MoR logical reconstruction using DuckDB or Spark
- Export to JSON / HTML / Markdown for incident attachments
- Diff views across snapshots (schema diff, file diff, partition diff)

## 5. Textual UI design

### 5.1 Layout

Initial layout:

**Header:**
- Table identifier, snapshot, storage location summary

**Left panel:**
- Snapshot list in a DataTable
- Columns: ID, Timestamp, Operation, Base Files, Delete Files

**Right panel with tabs:**

- **Files tab:**
  - DataTable with data and delete files
  - Columns: Type, Path, Size, Records, Sequence, Delete counts

- **File detail tab:**
  - Basic info section
  - Column stats table

- **Merge on read tab:**
  - SnapshotMorSummary overview
  - Per file impact if needed

- **Profile tab:**
  - Column selection
  - Profile results view for a selected column

**Footer:**
- Keybindings and hints

### 5.2 Data flow

**On app startup:**

1. Resolve table using Iceberg adapter
2. Load snapshots
3. Populate snapshot list

**On snapshot selection:**

1. Use adapter to load snapshot details
2. Build SnapshotInfo
3. Derive data and delete file lists
4. Run merge on read analyzer
5. Populate files table and merge on read summary

**On file selection:**

1. Call Parquet inspector to collect file level metadata
2. Populate file detail tab

**On profile request:**

1. Ask profiling backend to create or refresh a view for the snapshot
2. Call `profile_single_column` or `profile_columns`
3. Populate profile tab with results

All data access operations that hit remote storage or GizmoSQL should be executed asynchronously where practical so that the UI remains responsive.

## 6. Configuration

Configuration sources, in precedence order:

1. **Environment variables**, for fast overrides, for example:
   - `TABLE_SLEUTH_CATALOG_NAME`
   - `TABLE_SLEUTH_GIZMO_URI`
   - `TABLE_SLEUTH_GIZMO_USERNAME`
   - `TABLE_SLEUTH_GIZMO_PASSWORD`

2. **A `table_sleuth.toml`** in the project root or user home directory, with sections:

```toml
[catalog]
default = "local"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true
```

3. **Sensible code defaults** when nothing else is present

PyIceberg catalog configuration will remain in `~/.pyiceberg.yaml` and is not duplicated.

## 7. Testing strategy

**Unit tests:**

- **Iceberg adapter:**
  - Local file based catalog with an on disk test warehouse
  - StaticTable loading from temporary directories

- **Parquet inspector:**
  - Small test Parquet files with known schema and statistics

- **Merge on read analyzer:**
  - SnapshotInfo instances constructed in memory for various edge cases

- **Profiling abstraction:**
  - A fake backend that returns predictable ColumnProfile objects

**Integration tests:**

- A GizmoSQL container started via docker compose for local testing
- A sample dataset (Parquet files) mounted into the container and read through DuckDB

**TUI smoke tests:**

- Use Textual testing helpers to verify that key views render and respond to simple interactions

## 8. Future extensions

Planned next steps beyond MVP v1:

**Glue or REST catalog support:**

- Add a glue or rest catalog mode to the Iceberg adapter
- Support listing tables and namespaces

**Additional formats:**

- Implement DeltaAdapter and HudiAdapter under `formats/`
- Align common metadata models where possible

**Deeper merge on read analysis:**

- Optionally apply delete files fully using DuckDB or Spark and expose more precise statistics

**Export and automation:**

- Add commands for JSON export of metadata and profiling results, useful for attaching to incident tickets or documentation
