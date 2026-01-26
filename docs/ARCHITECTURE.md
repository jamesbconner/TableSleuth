# Table Sleuth Architecture

## Overview

Table Sleuth is a Python-based Parquet file forensics and Iceberg table analysis tool built with a layered architecture that separates concerns between presentation, business logic, and data access. The system provides comprehensive inspection of Parquet files and Iceberg tables with support for multiple catalog types (local SQL, AWS Glue, AWS S3 Tables), column profiling via GizmoSQL/DuckDB, and performance testing across Iceberg snapshots.

**Current Version**: 0.5.3

This document provides a comprehensive overview of the system architecture, design patterns, and key technical decisions.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLI Layer                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │ parquet command  │  │ iceberg command  │  │ delta command    │       │
│  │ - Parquet files  │  │ - Snapshot view  │  │ - Version history│       │
│  │ - Directories    │  │ - Comparison     │  │ - Forensics      │       │
│  │ - Iceberg tables │  │ - Performance    │  │ - Optimization   │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
│                                                                         │
│  Modular CLI Structure (v0.5.3+):                                       │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ cli/__init__.py - Auto-loading command discovery             │       │
│  │ cli/helpers.py - Shared utilities                            │       │
│  │ cli/init.py, config_check.py, parquet.py, iceberg.py, delta.py│     │
│  └──────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Presentation Layer (Textual TUI)                  │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ TableSleuthApp - Main Application Orchestrator               │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  Parquet Inspection Views:                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │ File List    │  │ File Detail  │  │ Schema View  │                   │
│  │ - Multi-file │  │ - Metadata   │  │ - Filtering  │                   │
│  │ - Selection  │  │ - Size/rows  │  │ - Types      │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │ Row Groups   │  │ Column Stats │  │ Data Sample  │                   │
│  │ - Breakdown  │  │ - Min/Max    │  │ - Preview    │                   │
│  │ - Compression│  │ - Nulls      │  │ - Filtering  │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
│  ┌──────────────┐                                                       │
│  │ Profile View │                                                       │
│  │ - GizmoSQL   │                                                       │
│  │ - Statistics │                                                       │
│  └──────────────┘                                                       │
│                                                                         │
│  Iceberg Analysis Views:                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │ Iceberg View │  │ Snapshot     │  │ Snapshot     │                   │
│  │ - Snapshots  │  │ Detail       │  │ Comparison   │                   │
│  │ - Navigation │  │ - Files      │  │ - Diff       │                   │
│  │ - Metadata   │  │ - Schema     │  │ - MOR metrics│                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
│  ┌──────────────┐                                                       │
│  │ Performance  │                                                       │
│  │ Testing View │                                                       │
│  │ - Query exec │                                                       │
│  │ - Comparison │                                                       │
│  └──────────────┘                                                       │
│                                                                         │
│  Shared Widgets:                                                        │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ Notifications, Loading Indicators, Modals, Tables        │           │
│  └──────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Service Layer                                  │
│                                                                         │
│  Core Services:                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │ ParquetService   │  │ FileDiscovery    │  │ FilesystemService│       │
│  │ - inspect_file() │  │ Service          │  │ - S3 support     │       │
│  │ - get_schema()   │  │ - Path discovery │  │ - Local files    │       │
│  │ - get_row_groups │  │ - Table files    │  │ - Path handling  │       │
│  │ - get_stats()    │  │ - Recursive scan │  │                  │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
│                                                                         │
│  Delta Lake Services (v0.5.0+):                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │ DeltaAdapter     │  │ DeltaForensics   │  │ DeltaLogFileSystem│      │
│  │ - Table loading  │  │ - File analysis  │  │ - Unified FS API │       │
│  │ - Version history│  │ - Storage waste  │  │ - Local & cloud  │       │
│  │ - File discovery │  │ - DML forensics  │  │ - Version files  │       │
│  │ - Cloud support  │  │ - Optimization   │  │ - Checkpoints    │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
│                                                                         │
│  Iceberg Services:                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │ IcebergAdapter   │  │ IcebergMetadata  │  │ MORService       │       │
│  │ - Catalog mgmt   │  │ Service          │  │ - Delete files   │       │
│  │ - Table loading  │  │ - Snapshot load  │  │ - MOR metrics    │       │
│  │ - File discovery │  │ - Metadata parse │  │ - Overhead calc  │       │
│  │ - S3 Tables ARN  │  │ - Table info     │  │                  │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
│                                                                         │
│  Performance Testing:                                                   │
│  ┌──────────────────┐  ┌──────────────────┐                             │
│  │ SnapshotTest     │  │ SnapshotPerf     │                             │
│  │ Manager          │  │ Analyzer         │                             │
│  │ - Register snaps │  │ - Query exec     │                             │
│  │ - Namespace mgmt │  │ - Metrics        │                             │
│  │ - Cleanup        │  │ - Comparison     │                             │
│  │                  │  │ - Interface      │                             │
│  │                  │  │   validation     │                             │
│  └──────────────────┘  └──────────────────┘                             │
│                                                                         │
│  Profiling (Protocol-based):                                            │
│  ┌──────────────────┐                                                   │
│  │ ProfilingBackend │  ◄─── Protocol (structural subtyping)             │
│  │ (Protocol)       │                                                   │
│  │ - register_view  │                                                   │
│  │ - profile_column │                                                   │
│  │ - profile_batch  │                                                   │
│  └──────────────────┘                                                   │
│           △                                                             │
│           │ implements                                                  │
│           │                                                             │
│  ┌──────────────────┐                                                   │
│  │ GizmoDuckDb      │                                                   │
│  │ Profiler         │                                                   │
│  │ - ADBC client    │                                                   │
│  │ - DuckDB queries │                                                   │
│  │ - Iceberg support│                                                   │
│  │ - TLS connection │                                                   │
│  └──────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Data Layer                                     │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │ PyArrow          │  │ ADBC Flight SQL  │  │ PyIceberg        │       │
│  │ - ParquetFile    │  │ - Connection     │  │ - Catalog API    │       │
│  │ - Schema         │  │ - Cursor         │  │ - Table API      │       │
│  │ - Metadata       │  │ - Query exec     │  │ - Snapshot API   │       │
│  │ - Statistics     │  │ - TLS support    │  │ - REST catalog   │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐                             │
│  │ boto3 (S3)       │  │ fsspec           │                             │
│  │ - S3 file access │  │ - Filesystem abs │                             │
│  │ - Credentials    │  │ - S3 integration │                             │
│  └──────────────────┘  └──────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       External Systems                                  │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │ Local GizmoSQL   │  │ AWS S3           │  │ AWS Glue Catalog │       │
│  │ Server           │  │ - Parquet files  │  │ - Table metadata │       │
│  │ - DuckDB engine  │  │ - Iceberg data   │  │ - Databases      │       │
│  │ - Port 31337     │  │ - Metadata       │  │ - Tables         │       │
│  │ - TLS optional   │  │                  │  │                  │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐                             │
│  │ AWS S3 Tables    │  │ Local Filesystem │                             │
│  │ - Managed Iceberg│  │ - Parquet files  │                             │
│  │ - REST API       │  │ - SQLite catalog │                             │
│  │ - SigV4 auth     │  │                  │                             │
│  └──────────────────┘  └──────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────┘
```

## CLI Commands

Table Sleuth provides a **modular CLI architecture** (v0.5.3+) with auto-loading command discovery. Each command is in its own focused module, following a format-oriented design pattern.

### CLI Architecture (v0.5.3+)

**Structure**:
```
src/tablesleuth/cli/
├── __init__.py          # Entry point with auto-loader
├── helpers.py           # Shared utilities
├── init.py              # Init command
├── config_check.py      # Config validation
├── parquet.py           # Parquet inspection
├── iceberg.py           # Iceberg analysis
└── delta.py             # Delta Lake inspection
```

**Auto-Loading Pattern**:
Commands are automatically discovered and registered by convention (module name = function name). Adding a new command is as simple as dropping a file in the `cli/` directory.

**Benefits**:
- Single Responsibility: Each command in its own module
- Zero-friction extensibility: New commands auto-register
- Easy to test: Commands can be tested in isolation
- Clear boundaries: Shared logic in helpers module

### 1. `parquet` Command

**Purpose**: Analyze Parquet files, directories, or Iceberg table data files

**Usage**:
```bash
# Analyze local Parquet file
tablesleuth parquet data/file.parquet

# Analyze S3 Parquet file
tablesleuth parquet s3://bucket/path/file.parquet

# Analyze directory (recursive)
tablesleuth parquet data/warehouse/

# Analyze Iceberg table data files (discovers Parquet files from table)
tablesleuth parquet --catalog ratebeer ratebeer.reviews

# Analyze S3 Tables Iceberg table (ARN - discovers Parquet files)
tablesleuth parquet "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/db.table"
```

**Features**:
- Multi-file support with file list navigation
- Schema inspection with filtering
- Row group analysis
- Column statistics from metadata
- Data sample preview
- Column profiling via GizmoSQL

### 2. `iceberg` Command

**Purpose**: Analyze Iceberg table snapshots and compare performance

**Usage**:
```bash
# View snapshots from Glue catalog
tablesleuth iceberg --catalog ratebeer --table ratebeer.reviews

# View snapshots from S3 Tables catalog
tablesleuth iceberg --catalog tpch --table tpch.lineitem

# View from metadata file
tablesleuth iceberg s3://bucket/warehouse/table/metadata/metadata.json

# With verbose logging
tablesleuth iceberg --catalog ratebeer --table ratebeer.reviews -v
```

**Features**:
- Snapshot browsing and navigation
- Snapshot detail view (files, schema, properties)
- Merge-on-read (MOR) overhead analysis
- Snapshot comparison (file/record changes)
- Query performance testing between snapshots
- Predefined query templates

### 3. `delta` Command

**Purpose**: Analyze Delta Lake tables with forensic analysis

**Usage**:
```bash
# Analyze local Delta table
tablesleuth delta path/to/delta/table

# Analyze S3 Delta table
tablesleuth delta s3://bucket/path/to/delta/table

# Time travel to specific version
tablesleuth delta path/to/table --version 5

# With storage options
tablesleuth delta s3://bucket/table/ --storage-option AWS_REGION=us-west-2
```

**Features**:
- Version history navigation and time travel
- File size analysis with small file detection
- Storage waste tracking (tombstoned files)
- DML operation forensics (MERGE, UPDATE, DELETE)
- Z-Order effectiveness monitoring
- Checkpoint health assessment
- Optimization recommendations with priorities

## Architectural Layers

### 1. Presentation Layer (TUI)

**Responsibility**: User interface and interaction handling

**Technology**: Textual framework (Python TUI library)

**Components**:

- **Views**: Full-screen or panel components
  - `FileListView`: Displays list of discovered files with selection
  - `FileDetailView`: Shows file-level metadata (size, rows, compression)
  - `SchemaView`: Displays column schema with type filtering
  - `RowGroupsView`: Shows row group breakdown and compression stats
  - `ColumnStatsView`: Displays column statistics from Parquet metadata
  - `DataSampleView`: Preview data with column selection and filtering
  - `ProfileView`: Shows profiling results from GizmoSQL
  - `IcebergView`: Iceberg table browser with snapshot navigation
  - `SnapshotDetailView`: Detailed snapshot information (files, schema, properties)
  - `SnapshotComparisonView`: Compare two snapshots with diff and performance testing
  - `PerformanceTestView`: Query execution and performance comparison

- **Widgets**: Reusable UI components
  - `Notification`: Toast-style notifications
  - `LoadingIndicator`: Async operation indicators
  - `Modal`: Dialog boxes for user input
  - `DataTable`: Rich table display with sorting

- **App**: Main application orchestrator
  - `TableSleuthApp`: Coordinates views, handles events, manages state

**Key Patterns**:
- **Observer Pattern**: Views observe model changes
- **Command Pattern**: User actions trigger commands
- **Async/Await**: All I/O operations are asynchronous
- **Reactive UI**: Views update automatically on data changes

### 2. Service Layer

**Responsibility**: Business logic and orchestration

**Components**:

#### ParquetService

**Purpose**: Extract metadata and statistics from Parquet files

**Key Methods**:
```python
def inspect_file(file_path: str | Path) -> ParquetFileInfo
def get_schema(file_path: str | Path) -> dict[str, Any]
def get_row_groups(file_path: str | Path) -> list[RowGroupInfo]
def get_column_stats(file_path: str | Path, column_name: str) -> ColumnStats
def get_data_sample(file_path: str | Path, columns: list[str] | None, limit: int) -> dict
```

**Design Decisions**:
- Uses PyArrow for metadata access (fast, native)
- Handles missing statistics gracefully (returns None)
- Supports nested column structures
- Caches metadata to avoid repeated reads
- Supports both local and S3 files via fsspec

#### FileDiscoveryService

**Purpose**: Discover Parquet files from various sources

**Key Methods**:
```python
def discover_from_path(path: str | Path) -> list[FileRef]
def discover_from_table(table_identifier: str, catalog_name: str) -> list[FileRef]
```

**Supported Sources**:
- Local files and directories (recursive)
- S3 files and prefixes
- Iceberg tables (via catalog)
- S3 Tables (via ARN)

**Design Decisions**:
- Validates files before returning (checks magic bytes)
- Recursively scans directories
- Delegates to IcebergAdapter for table discovery
- Returns lightweight FileRef objects
- Handles S3 and local paths uniformly

#### FilesystemService

**Purpose**: Abstract filesystem operations for local and S3

**Key Methods**:
```python
def read_file(path: str) -> bytes
def list_files(path: str, pattern: str | None) -> list[str]
def file_exists(path: str) -> bool
def get_file_size(path: str) -> int
```

**Design Decisions**:
- Uses fsspec for unified filesystem interface
- Supports S3 via s3fs
- Handles AWS credentials automatically
- Provides consistent API for local and remote files

#### ProfilingBackend (Protocol)

**Purpose**: Abstract interface for data profiling

**Key Methods**:
```python
def register_file_view(file_paths: list[str], view_name: str | None) -> str
def profile_single_column(view_name: str, column: str, filters: str | None) -> ColumnProfile
def profile_columns(view_name: str, columns: Sequence[str], filters: str | None) -> dict[str, ColumnProfile]
```

**Design Decisions**:
- Uses Protocol (structural subtyping) for flexibility
- Enables multiple implementations (GizmoSQL, Spark, Trino)
- Supports multi-file views for partitioned datasets
- Allows optional SQL filters

#### GizmoDuckDbProfiler

**Purpose**: DuckDB-based profiling implementation via local GizmoSQL

**Connection**:
```python
uri = "grpc+tls://localhost:31337"  # Local GizmoSQL server
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = True  # For self-signed certificates
```

**Key Features**:
- Connects to local GizmoSQL server via ADBC Flight SQL
- Direct filesystem access (no path conversion needed)
- Uses DuckDB's `read_parquet()` for file access
- Supports Iceberg tables via DuckDB's Iceberg extension
- Executes SQL queries for statistics
- Handles connection pooling and retries
- TLS support with self-signed certificates

**Profiling Capabilities**:
- Single column profiling (min, max, avg, distinct count, nulls)
- Batch column profiling (multiple columns at once)
- Custom SQL filters
- Multi-file views (for partitioned datasets)
- Iceberg snapshot-specific queries

**Iceberg Support**:
- Registers Iceberg tables using `iceberg_scan()` function
- Supports snapshot-specific queries via metadata pointer
- Enables performance testing across snapshots
- Automatic S3 Tables attachment on server startup

**Design Decisions**:
- Lazy connection initialization
- Connection reuse across queries
- Graceful error handling with retries
- Local deployment (no Docker complexity)
- Optional TLS for security
- Configurable via `tablesleuth.toml`

#### IcebergAdapter

**Purpose**: Interface with Iceberg catalogs and tables

**Key Methods**:
```python
def open_table(table_identifier: str, catalog_name: str | None) -> TableHandle
def get_data_files(table_identifier: str, catalog_name: str | None) -> list[FileRef]
def load_catalog(catalog_name: str) -> Catalog
def parse_s3_tables_arn(arn: str) -> tuple[str, str] | None
```

**Supported Catalog Types**:
- **SQL Catalog**: Local SQLite-based catalogs
- **Glue Catalog**: AWS Glue Data Catalog
- **REST Catalog**: AWS S3 Tables (managed Iceberg)

**S3 Tables Support**:
- Parses S3 Tables ARNs: `arn:aws:s3tables:region:account:bucket/name/table/namespace.table`
- Configures REST catalog with SigV4 authentication
- Automatic region detection from ARN

**Design Decisions**:
- Uses PyIceberg for catalog access
- Supports multiple catalog types
- Handles data and delete files
- Returns FileRef objects for consistency
- Graceful fallback for missing catalogs

#### IcebergMetadataService

**Purpose**: Load and parse Iceberg table metadata

**Key Methods**:
```python
def load_table(catalog_name: str | None, table_identifier: str | None, metadata_path: str | None) -> TableInfo
def get_snapshots(table: Table) -> list[SnapshotInfo]
def get_snapshot_details(table: Table, snapshot_id: int) -> SnapshotDetail
```

**Features**:
- Loads tables from catalog or metadata file
- Parses snapshot information
- Extracts schema, properties, and statistics
- Handles both data and delete files

**Design Decisions**:
- Flexible loading (catalog or direct metadata)
- Rich snapshot information
- Supports S3 and local metadata files
- Caches table metadata

#### MORService (Merge-on-Read)

**Purpose**: Analyze merge-on-read overhead in Iceberg tables

**Key Methods**:
```python
def calculate_mor_metrics(snapshot: Snapshot) -> MORMetrics
def get_delete_file_stats(snapshot: Snapshot) -> DeleteFileStats
def calculate_compaction_benefit(snapshot: Snapshot) -> CompactionBenefit
```

**Metrics Calculated**:
- Delete file count and size
- Position delete vs equality delete breakdown
- MOR overhead percentage
- Compaction recommendations

**Design Decisions**:
- Analyzes delete files from snapshot
- Calculates overhead ratios
- Provides actionable insights
- Supports both delete file types

#### SnapshotTestManager

**Purpose**: Manage Iceberg snapshot registration for performance testing

**Key Features**:
- Registers snapshots in local PyIceberg catalog
- Creates dedicated `snapshot_tests` namespace
- Manages table lifecycle (create/cleanup)
- Supports multiple snapshot comparisons

**Key Methods**:
```python
def ensure_snapshot_namespace() -> None
def register_snapshots(table_name: str, snapshot_a: Snapshot, snapshot_b: Snapshot) -> tuple[str, str]
def cleanup_test_tables() -> None
```

**Design Decisions**:
- Uses configured local catalog (no temporary catalogs)
- Persists tables across sessions
- Namespace-based isolation
- Automatic cleanup of test tables

#### SnapshotPerformanceAnalyzer

**Purpose**: Execute and compare query performance across snapshots

**Key Features**:
- Runs queries against registered snapshot tables
- Collects execution metrics (time, files scanned, bytes read)
- Compares performance between snapshots
- Provides predefined query templates

**Key Methods**:
```python
def run_query_test(table_name: str, query: str) -> QueryPerformanceMetrics
def compare_query_performance(table_a: str, table_b: str, query: str) -> PerformanceComparison
def get_predefined_queries() -> dict[str, str]
```

**Design Decisions**:
- Delegates query execution to profiler
- Template-based queries for common scenarios
- Captures comprehensive metrics
- Supports custom SQL queries

### 3. Data Layer

**Responsibility**: Low-level data access

**Components**:

- **PyArrow**: Parquet file metadata extraction
- **ADBC**: Arrow Flight SQL client for GizmoSQL
- **PyIceberg**: Iceberg catalog and table access

## Design Patterns

### 1. Protocol-Based Abstraction

**Pattern**: Structural subtyping using Python Protocol

**Usage**: ProfilingBackend interface

**Benefits**:
- No inheritance required
- Duck typing support
- Easy to mock for testing
- Supports multiple implementations

**Example**:
```python
class ProfilingBackend(Protocol):
    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str: ...
    def profile_single_column(self, view_name: str, column: str) -> ColumnProfile: ...

class GizmoDuckDbProfiler:
    # Implements protocol without explicit inheritance
    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        ...
```

### 2. Async/Await Pattern

**Pattern**: Asynchronous I/O operations

**Usage**: All TUI operations

**Benefits**:
- Keeps UI responsive
- Enables concurrent operations
- Supports cancellation
- Natural integration with Textual

**Example**:
```python
async def on_file_selected(self, file_ref: FileRef) -> None:
    self.show_loading()
    try:
        file_info = await self.inspect_file_async(file_ref.path)
        self.display_file_info(file_info)
    finally:
        self.hide_loading()
```

### 3. Caching Strategy

**Pattern**: Multi-level caching with TTL

**Levels**:
1. **File Metadata Cache**: Keyed by file path
2. **Profiling Results Cache**: Keyed by (view_name, column, filters)
3. **Schema Cache**: Keyed by file path

**Implementation**:
```python
class CacheManager:
    def __init__(self, ttl: int = 300):
        self._file_cache: dict[str, tuple[ParquetFileInfo, float]] = {}
        self._profile_cache: dict[tuple, tuple[ColumnProfile, float]] = {}
        self._ttl = ttl

    def get_file_info(self, file_path: str) -> ParquetFileInfo | None:
        if file_path in self._file_cache:
            info, timestamp = self._file_cache[file_path]
            if time.time() - timestamp < self._ttl:
                return info
        return None

    def set_file_info(self, file_path: str, info: ParquetFileInfo) -> None:
        self._file_cache[file_path] = (info, time.time())
```

**Invalidation**:
- Manual: User presses 'r' to refresh
- Automatic: TTL expiration (5 minutes default)

### 4. Graceful Degradation

**Pattern**: Continue operation when optional features fail

**Usage**: Throughout the application

**Example**:
```python
try:
    profiler = create_profiling_backend(config)
    if profiler:
        profile = profiler.profile_single_column(view, column)
        self.display_profile(profile)
    else:
        self.show_notification("Profiling backend not available")
except ConnectionError:
    self.show_notification("Failed to connect to profiling backend")
    # Continue with other features
```

### 5. Dependency Injection

**Pattern**: Constructor injection for dependencies

**Usage**: Service layer components

**Example**:
```python
class TableSleuthApp:
    def __init__(
        self,
        inspector: ParquetInspector,
        discovery: FileDiscoveryService,
        profiler: ProfilingBackend | None = None,
    ):
        self._inspector = inspector
        self._discovery = discovery
        self._profiler = profiler
```

## Data Flow

### File Inspection Flow

```
User selects file
       │
       ▼
FileListView.on_file_selected()
       │
       ▼
TableSleuthApp.inspect_file_async()
       │
       ▼
Check cache
       │
       ├─ Hit ──────────────────┐
       │                        │
       ▼                        │
ParquetInspector.inspect_file() │
       │                        │
       ▼                        │
PyArrow.ParquetFile             │
       │                        │
       ▼                        │
Extract metadata                │
       │                        │
       ▼                        │
Cache result                    │
       │                        │
       └────────────────────────┤
                                │
                                ▼
                    Update views with file info
                                │
                                ▼
                    FileDetailView.update()
                    SchemaView.update()
                    RowGroupsView.update()
```

### Column Profiling Flow

```
User clicks column in Profile view
       │
       ▼
ProfileView.on_click()
       │
       ▼
TableSleuthApp.profile_column_async()
       │
       ▼
Check cache
       │
       ├─ Hit ──────────────────┐
       │                        │
       ▼                        │
GizmoDuckDbProfiler.register_file_view()
       │                        │
       ▼                        │
ADBC Connection to local GizmoSQL
       │                        │
       ▼                        │
Execute SQL query               │
       │                        │
       ▼                        │
Parse results                   │
       │                        │
       ▼                        │
Cache result                    │
       │                        │
       └────────────────────────┤
                                │
                                ▼
                    ProfileView.display_profile()
```

### Iceberg Snapshot Performance Testing Flow

```
User selects 2 snapshots in Compare mode
       │
       ▼
SnapshotComparisonView.on_compare_triggered()
       │
       ▼
SnapshotTestManager.register_snapshots()
       │
       ▼
Create tables in snapshot_tests namespace
       │
       ▼
GizmoDuckDbProfiler.register_iceberg_table_with_snapshot()
       │
       ▼
User runs performance test with query
       │
       ▼
SnapshotPerformanceAnalyzer.compare_query_performance()
       │
       ▼
Execute query on both snapshot tables
       │
       ▼
Collect metrics (time, files scanned, bytes read)
       │
       ▼
Calculate performance difference
       │
       ▼
Display comparison results
```

## Configuration Management

### Configuration Sources (Priority Order)

1. **Environment Variables** (highest priority)
2. **Configuration File** (`tablesleuth.toml` or `~/.config/tablesleuth.toml`)
3. **Built-in Defaults** (lowest priority)

### Table Sleuth Configuration

**File**: `tablesleuth.toml` (project root) or `~/.config/tablesleuth.toml`

```toml
[catalog]
default = "local"

[gizmosql]
# GizmoSQL connection settings for column profiling and Iceberg performance testing
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true  # For self-signed certificates
```

### PyIceberg Configuration

**File**: `~/.pyiceberg.yaml`

**Local SQL Catalog**:
```yaml
catalog:
  local:
    type: sql
    uri: sqlite:////absolute/path/to/warehouse/catalog.db
    warehouse: file:///absolute/path/to/warehouse
```

**AWS Glue Catalog**:
```yaml
catalog:
  ratebeer:
    type: glue
    region: us-east-2
    # Uses IAM role or AWS credentials from environment
```

**AWS S3 Tables (REST Catalog)**:
```yaml
catalog:
  tpch:
    type: rest
    warehouse: arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket
    uri: https://s3tables.us-east-2.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: us-east-2
```

**Mixed Environment**:
```yaml
catalog:
  # Local development
  local:
    type: sql
    uri: sqlite:///~/iceberg_catalog.db
    warehouse: file:///~/iceberg_warehouse

  # Glue production
  prod-glue:
    type: glue
    region: us-east-2

  # S3 Tables
  tpch:
    type: rest
    warehouse: arn:aws:s3tables:us-east-2:123456789012:bucket/tpch-data
    uri: https://s3tables.us-east-2.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: us-east-2
```

### AWS Configuration

**Credentials** (via AWS CLI or environment):
```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-2
export AWS_DEFAULT_REGION=us-east-2
```

**Region Detection** (priority order):
1. `AWS_REGION` environment variable
2. `AWS_DEFAULT_REGION` environment variable
3. Default: `us-east-2`

### Configuration Loading

```python
class Config:
    @classmethod
    def load(cls) -> "Config":
        # 1. Load defaults
        config = cls._defaults()

        # 2. Load from file (project root or ~/.config)
        config_paths = [
            Path("tablesleuth.toml"),
            Path.home() / ".config" / "tablesleuth.toml",
        ]
        for path in config_paths:
            if path.exists():
                config.update(cls._load_toml(path))
                break

        # 3. Override with environment variables
        config.update(cls._load_env())

        return config
```

## GizmoSQL Deployment

### Local GizmoSQL Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Table Sleuth TUI                           │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  GizmoDuckDbProfiler                             │   │
│  │  - ADBC Flight SQL Client                        │   │
│  │  - TLS connection (optional)                     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                        │
                        │ gRPC+TLS (localhost:31337)
                        ▼
┌─────────────────────────────────────────────────────────┐
│         Local GizmoSQL Server (v1.12.13)                │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  DuckDB Engine                                   │   │
│  │  - AWS extension (S3 access)                     │   │
│  │  - HTTPFS extension (HTTP/HTTPS)                 │   │
│  │  - Iceberg extension (Iceberg tables)            │   │
│  │  - Credential chain (IAM roles)                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  Initialization SQL:                                    │
│  - install aws; install httpfs; install iceberg;        │
│  - load aws; load httpfs; load iceberg;                 │
│  - CREATE SECRET (TYPE s3, PROVIDER credential_chain);  │
│  - ATTACH S3 Tables bucket (if configured)              │
└─────────────────────────────────────────────────────────┘
                        │
                        │ Direct file access
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Data Sources                               │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Local Files  │  │ S3 Buckets   │  │ S3 Tables    │   │
│  │ - Parquet    │  │ - Parquet    │  │ - Iceberg    │   │
│  │ - Iceberg    │  │ - Iceberg    │  │ - Managed    │   │
│  │ - Catalog DB │  │ - Metadata   │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Key Benefits

- **No Docker complexity**: Runs as a local process
- **Direct filesystem access**: No path conversion needed
- **Fast startup**: Instant availability
- **Easy debugging**: Direct process access
- **Low overhead**: No container layer
- **S3 support**: Native S3 access via AWS extension
- **Iceberg support**: Full Iceberg table support including S3 Tables
- **TLS security**: Optional TLS for encrypted connections

### Installation

**macOS (ARM64)**:
```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_macos_arm64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

**macOS (Intel)**:
```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_macos_amd64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

**Linux**:
```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_linux_amd64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

### TLS Certificate Generation

```bash
# Create certificates directory
mkdir -p ~/.certs

# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout ~/.certs/cert0.key \
  -out ~/.certs/cert0.pem -days 365 -nodes -subj "/CN=localhost"

# Set permissions
chmod 600 ~/.certs/cert0.key
chmod 644 ~/.certs/cert0.pem
```

### Server Startup

**Basic (no TLS)**:
```bash
# Not recommended for production - use TLS
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);"
```

**With TLS (recommended)**:
```bash
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**With S3 Tables Initialization**:
```bash
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; \
      load aws; load httpfs; load iceberg; \
      CREATE SECRET (TYPE s3, PROVIDER credential_chain); \
      ATTACH 'arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket' AS tpch (TYPE iceberg, ENDPOINT_TYPE s3_tables);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**Server Options**:
- `-P`: Password for authentication
- `-Q`: Enable query printing (verbose mode)
- `-I`: Initialization SQL commands
- `-T`: TLS certificate and key files
- Default port: `31337`

### Client Testing

```bash
# Test connection
gizmosql_client --command Execute --use-tls --tls-skip-verify \
  --username gizmosql_username --password gizmosql_password \
  "SELECT 1"

# Query S3 Tables
gizmosql_client --command Execute --use-tls --tls-skip-verify \
  --username gizmosql_username --password gizmosql_password \
  "SELECT * FROM tpch.lineitem LIMIT 10"
```

## Error Handling Strategy

### Error Categories

1. **User Errors**: Invalid input, file not found
2. **System Errors**: Connection failures, timeouts
3. **Data Errors**: Corrupted files, missing metadata

### Error Handling Approach

```python
try:
    # Operation
    result = operation()
except FileNotFoundError as e:
    # User error - show friendly message
    logger.warning(f"File not found: {e}")
    self.show_notification(f"File not found: {path}")
except ConnectionError as e:
    # System error - show error and log details
    logger.error(f"Connection failed: {e}", exc_info=True)
    self.show_notification("Failed to connect to profiling backend")
except Exception as e:
    # Unexpected error - log and show generic message
    logger.exception(f"Unexpected error: {e}")
    self.show_notification("An unexpected error occurred")
```

### Error Presentation

- **Notifications**: Toast-style messages at top of screen
- **Logging**: Detailed errors logged for debugging
- **Graceful Degradation**: Continue operation when possible

## Performance Considerations

### Optimization Strategies

1. **Lazy Loading**
   - Load file list immediately
   - Load file details on selection
   - Defer row group inspection until viewed

2. **Async Operations**
   - All I/O operations are asynchronous
   - UI remains responsive during operations
   - Multiple operations can run concurrently

3. **Caching**
   - File metadata cached per path
   - Profiling results cached per query
   - TTL-based invalidation

4. **Batch Operations**
   - Batch file discovery for directories
   - Use PyArrow's batch APIs
   - Minimize round trips to GizmoSQL

### Performance Targets

- File metadata extraction: < 1 second per file
- Directory scanning: < 2 seconds for 100 files
- Column profiling: 2-10 seconds depending on data size
- Snapshot performance test: 5-30 seconds per query
- UI responsiveness: < 100ms for user interactions

## Security Considerations

### Credential Management

- Load from environment variables or config file
- Never log passwords or sensitive credentials
- Support TLS for GizmoSQL connections (optional)
- Local deployment reduces attack surface

### Input Validation

- Validate file paths before accessing
- Sanitize SQL filters before passing to backend
- Validate column names before profiling
- Limit query complexity to prevent DoS

### Read-Only Operations

- No write operations to files
- No modification of metadata
- No data deletion or updates
- Safe for production file inspection

### Iceberg Catalog Access

- Snapshot registration uses dedicated namespace
- Cleanup only affects `snapshot_tests` namespace
- No modification of production tables
- Read-only access to table metadata

## Testing Architecture

### Test Pyramid

```
        ┌─────────────┐
        │   E2E Tests │  (Few, slow, comprehensive)
        │   ~10 tests │
        └─────────────┘
      ┌───────────────────┐
      │ Integration Tests │  (Some, medium speed)
      │    ~40 tests      │
      └───────────────────┘
    ┌───────────────────────────┐
    │      Unit Tests           │  (Many, fast, focused)
    │      ~120 tests           │
    └───────────────────────────┘
```

### Test Organization

```
tests/
├── conftest.py                          # Shared fixtures
├── test_parquet_inspector.py
├── test_file_discovery.py
├── test_profiling_backend.py
├── test_gizmo_profiler_config.py        # Configuration tests
├── test_snapshot_test_manager.py        # Iceberg snapshot tests
├── test_snapshot_performance_analyzer.py
├── test_parquet_profiling_integration.py
├── test_end_to_end.py                   # E2E tests
└── fixtures/
    ├── test_data.parquet
    └── test_iceberg_table/
```

## Extension Points

### Adding New Profiling Backends

1. Implement `ProfilingBackend` protocol
2. Register in backend factory
3. Add configuration support
4. Add tests

### Adding New Table Formats

1. Create adapter class (similar to `IcebergAdapter`)
2. Implement file discovery method
3. Integrate with `FileDiscoveryService`
4. Add tests

### Adding New Export Formats

1. Create exporter class
2. Implement export method
3. Add CLI option
4. Add tests

## Current Features (v0.4.2)

### Parquet Inspection
- **File Discovery**:
  - Local files and directories (recursive)
  - S3 files and prefixes
  - Iceberg table data files
  - Multi-file support with navigation

- **Metadata Analysis**:
  - File-level metadata (size, rows, compression)
  - Schema inspection with type filtering
  - Row group breakdown and statistics
  - Column statistics from Parquet metadata
  - Nested column support

- **Data Preview**:
  - Data sample view with column selection
  - Filtering support
  - Pagination for large datasets

- **Column Profiling** (via GizmoSQL):
  - Min/max values
  - Average, sum, count
  - Distinct count
  - Null count and percentage
  - Custom SQL filters
  - Batch profiling (multiple columns)

### Iceberg Support

- **Catalog Types**:
  - Local SQL catalogs (SQLite)
  - AWS Glue Data Catalog
  - AWS S3 Tables (managed Iceberg)
  - Direct ARN support for S3 Tables

- **Snapshot Analysis**:
  - Snapshot browsing and navigation
  - Snapshot detail view (files, schema, properties)
  - Data file and delete file inspection
  - Schema evolution tracking
  - Snapshot metadata (operation, timestamp, summary)

- **Snapshot Comparison**:
  - Side-by-side snapshot comparison
  - File-level diff (added, removed, modified)
  - Record-level changes
  - Schema changes
  - Property changes

- **Merge-on-Read (MOR) Analysis**:
  - Delete file metrics
  - Position delete vs equality delete breakdown
  - MOR overhead calculation
  - Compaction recommendations

- **Performance Testing**:
  - Query execution across snapshots
  - Performance comparison (time, files scanned, bytes read)
  - Predefined query templates
  - Custom SQL query support
  - Metrics collection and visualization

### Deployment Options

- **Local Development**:
  - Direct Python installation
  - Local GizmoSQL server
  - Local or S3-based data

- **AWS EC2 Production**:
  - Automated EC2 setup script
  - Python 3.13.9 pre-installed
  - GizmoSQL with TLS certificates
  - S3 and S3 Tables access
  - IAM role-based authentication
  - Spot or On-Demand instances

## Project Structure

```
tablesleuth/
├── src/tablesleuth/
│   ├── __init__.py
│   ├── config.py                       # Configuration management
│   ├── exceptions.py                   # Custom exceptions
│   │
│   ├── cli/                            # CLI commands (v0.5.3+)
│   │   ├── __init__.py                 # Entry point with auto-loader
│   │   ├── helpers.py                  # Shared utilities
│   │   ├── init.py                     # Init command
│   │   ├── config_check.py             # Config validation
│   │   ├── parquet.py                  # Parquet inspection
│   │   ├── iceberg.py                  # Iceberg analysis
│   │   └── delta.py                    # Delta Lake inspection
│   │
│   ├── models/                         # Data models
│   │   ├── __init__.py
│   │   ├── file_ref.py                 # File reference model
│   │   ├── iceberg.py                  # Iceberg-specific models
│   │   ├── parquet.py                  # Parquet metadata models
│   │   ├── performance.py              # Performance metrics models
│   │   ├── profiling.py                # Profiling result models
│   │   ├── snapshot.py                 # Snapshot models
│   │   └── table.py                    # Table handle models
│   │
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   ├── delta_forensics.py          # Delta Lake forensics (v0.5.0+)
│   │   ├── file_discovery.py           # File discovery service
│   │   ├── filesystem.py               # Filesystem abstraction (S3/local)
│   │   ├── iceberg_metadata_service.py # Iceberg metadata loading
│   │   ├── mor_service.py              # Merge-on-read analysis
│   │   ├── parquet_service.py          # Parquet inspection
│   │   ├── snapshot_performance_analyzer.py  # Performance testing
│   │   ├── snapshot_test_manager.py    # Snapshot registration
│   │   │
│   │   ├── formats/                    # Format adapters
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # Base adapter protocol
│   │   │   ├── delta.py                # Delta adapter (v0.5.0+)
│   │   │   ├── delta_filesystem.py     # Delta filesystem abstraction (v0.5.3+)
│   │   │   ├── delta_log_parser.py     # Delta log parser (v0.5.0+)
│   │   │   ├── delta_utils.py          # Delta utilities (v0.5.0+)
│   │   │   └── iceberg.py              # Iceberg adapter
│   │   │
│   │   └── profiling/                  # Profiling backends
│   │       ├── __init__.py
│   │       ├── backend_base.py         # Protocol definition
│   │       ├── fake_backend.py         # Testing backend
│   │       └── gizmo_duckdb.py         # GizmoSQL implementation
│   │
│   ├── tui/                            # Terminal UI layer
│   │   ├── __init__.py
│   │   ├── app.py                      # Main TUI application
│   │   │
│   │   ├── views/                      # Full-screen views
│   │   │   ├── __init__.py
│   │   │   ├── delta_view.py           # Delta table view (v0.5.0+)
│   │   │   ├── file_list_view.py       # File list navigation
│   │   │   ├── file_detail_view.py     # File metadata view
│   │   │   ├── schema_view.py          # Schema inspection
│   │   │   ├── row_groups_view.py      # Row group analysis
│   │   │   ├── column_stats_view.py    # Column statistics
│   │   │   ├── data_sample_view.py     # Data preview
│   │   │   ├── profile_view.py         # Profiling results
│   │   │   ├── iceberg_view.py         # Iceberg snapshot browser
│   │   │   ├── snapshot_detail_view.py # Snapshot details
│   │   │   ├── snapshot_comparison_view.py  # Snapshot comparison
│   │   │   └── performance_test_view.py     # Performance testing
│   │   │
│   │   └── widgets/                    # Reusable UI components
│   │       ├── __init__.py
│   │       ├── notification.py         # Toast notifications
│   │       ├── loading_indicator.py    # Loading spinners
│   │       ├── modal.py                # Dialog boxes
│   │       └── data_table.py           # Rich table display
│   │
│   └── utils/                          # Utility functions
│       └── __init__.py
│
├── tests/                              # Test suite
│   ├── conftest.py                     # Shared fixtures
│   ├── test_parquet_service.py
│   ├── test_file_discovery.py
│   ├── test_profiling_backend.py
│   ├── test_gizmo_profiler_config.py
│   ├── test_snapshot_test_manager.py
│   ├── test_snapshot_performance_analyzer.py
│   ├── test_parquet_profiling_integration.py
│   ├── test_end_to_end.py
│   └── fixtures/
│       ├── test_data.parquet
│       └── test_iceberg_table/
│
├── resources/                          # Infrastructure as Code & Examples
│   ├── aws-cdk/                        # AWS CDK deployment
│   │   ├── app.py                      # CDK app entry point
│   │   ├── cdk.json                    # CDK configuration
│   │   ├── requirements.txt            # CDK dependencies
│   │   ├── tablesleuth_cdk/            # CDK stack
│   │   └── *.md                        # CDK documentation
│   ├── examples/                       # Example scripts
│   │   ├── README.md                   # Examples documentation
│   │   └── *.py                        # Example scripts
│   └── README.md                       # IaC overview
│
├── docs/                               # Documentation
│   ├── ARCHITECTURE.md                 # This file
│   ├── USER_GUIDE.md                   # User documentation
│   ├── DEVELOPER_GUIDE.md              # Developer documentation
│   ├── EC2_DEPLOYMENT_GUIDE.md         # EC2 deployment guide
│   ├── gizmosql-deployment.md          # GizmoSQL setup
│   ├── s3_tables_guide.md              # S3 Tables configuration
│   └── images/                         # Screenshots
│
├── pyproject.toml                      # Project metadata and dependencies
├── uv.lock                             # Dependency lock file
├── tablesleuth.toml                    # Application configuration
├── README.md                           # Project overview
├── QUICKSTART.md                       # Quick start guide
├── TABLESLEUTH_SETUP.md                # User setup guide
├── DEVELOPMENT_SETUP.md                # Developer setup guide
├── CONTRIBUTING.md                     # Contribution guidelines
├── CHANGELOG.md                        # Version history
└── Makefile                            # Development commands
```

## Technology Stack

### Core Dependencies

- **Python 3.13+**: Latest Python features and performance
- **Textual**: Terminal UI framework
- **PyArrow**: Parquet file access and Arrow data structures
- **PyIceberg**: Iceberg catalog and table API
- **ADBC**: Arrow Database Connectivity for GizmoSQL
- **boto3**: AWS SDK for S3 and Glue access
- **fsspec/s3fs**: Unified filesystem interface
- **click**: CLI framework
- **tomli**: TOML configuration parsing

### Development Dependencies

- **pytest**: Testing framework
- **pytest-cov**: Code coverage
- **mypy**: Static type checking
- **ruff**: Linting and formatting
- **pre-commit**: Git hooks for code quality
- **uv**: Fast dependency management

### External Systems

- **GizmoSQL**: Local DuckDB server for profiling
- **AWS S3**: Object storage for Parquet files
- **AWS Glue**: Managed Iceberg catalog
- **AWS S3 Tables**: Managed Iceberg service

## Future Architecture

### Planned Enhancements

1. **Advanced Snapshot Analysis**
   - Schema evolution visualization
   - Partition evolution tracking
   - Automated compaction recommendations
   - Historical performance trends

2. **Performance Optimization**
   - Query result caching
   - Batch performance testing
   - Historical performance tracking
   - Benchmark suite

3. **Export Capabilities**
   - JSON export for metadata
   - Markdown reports
   - HTML reports with charts
   - Performance dashboards
   - CSV export for statistics

4. **Advanced Filtering**
   - Partition-aware filtering
   - Time-travel queries
   - Custom query builder UI
   - Saved query templates

5. **Additional Table Formats**
   - Delta Lake support
   - Apache Hudi support
   - Unified table format interface

6. **Enhanced Profiling**
   - PySpark profiling backend
   - Trino profiling backend
   - Custom profiling queries
   - Profile comparison across snapshots

## References

### External Documentation

- [Textual Documentation](https://textual.textualize.io/)
- [PyArrow Documentation](https://arrow.apache.org/docs/python/)
- [PyIceberg Documentation](https://py.iceberg.apache.org/)
- [ADBC Documentation](https://arrow.apache.org/docs/format/ADBC.html)
- [GizmoSQL Documentation](https://docs.gizmodata.com/)

### Internal Documentation

- [Developer Guide](DEVELOPER_GUIDE.md)
- [User Guide](USER_GUIDE.md)
- [GizmoSQL Deployment Guide](gizmosql-deployment.md)
- [Iceberg Viewer Guide](iceberg-viewer-guide.md)
