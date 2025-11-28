# Table Sleuth Architecture

## Overview

Table Sleuth is a Python-based Parquet file forensics and Iceberg table analysis tool built with a layered architecture that separates concerns between presentation, business logic, and data access. This document provides a comprehensive overview of the system architecture, design patterns, and key technical decisions.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Presentation Layer                          │
│                     (Textual TUI)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ File List    │  │ File Detail  │  │ Schema View  │           │
│  │ View         │  │ View         │  │              │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Row Groups   │  │ Column Stats │  │ Profile View │           │
│  │ View         │  │ View         │  │              │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Iceberg View │  │ Snapshot     │  │ Snapshot     │           │
│  │              │  │ Detail View  │  │ Comparison   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────────────────────────────────────────┐           │
│  │ Widgets: Notifications, Loading Indicators       │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                              │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Parquet          │  │ File Discovery   │                     │
│  │ Inspector        │  │ Service          │                     │
│  │                  │  │                  │                     │
│  │ - inspect_file() │  │ - discover_from  │                     │
│  │ - get_schema()   │  │   _path()        │                     │
│  │ - get_row_groups │  │ - discover_from  │                     │
│  │ - get_column_    │  │   _table()       │                     │
│  │   stats()        │  │                  │                     │
│  └──────────────────┘  └──────────────────┘                     │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Profiling        │  │ Iceberg Adapter  │                     │
│  │ Backend          │  │                  │                     │
│  │ (Protocol)       │  │ - get_data_files │                     │
│  │                  │  │ - load_catalog() │                     │
│  │ - register_file  │  │ - load_table()   │                     │
│  │   _view()        │  │                  │                     │
│  │ - profile_single │  │                  │                     │
│  │   _column()      │  │                  │                     │
│  └──────────────────┘  └──────────────────┘                     │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Snapshot Test    │  │ Snapshot         │                     │
│  │ Manager          │  │ Performance      │                     │
│  │                  │  │ Analyzer         │                     │
│  │ - register_      │  │ - run_query_test │                     │
│  │   snapshots()    │  │ - compare_query  │                     │
│  │ - cleanup()      │  │   _performance() │                     │
│  └──────────────────┘  └──────────────────┘                     │
│           │                                                     │
│           ▼                                                     │
│  ┌──────────────────┐                                           │
│  │ GizmoDuckDb      │                                           │
│  │ Profiler         │                                           │
│  │ (Implementation) │                                           │
│  │                  │                                           │
│  │ - Local GizmoSQL │                                           │
│  │ - Direct FS      │                                           │
│  │   access         │                                           │
│  │ - Iceberg        │                                           │
│  │   support        │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Data Layer                                │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ PyArrow          │  │ ADBC Flight SQL  │                     │
│  │                  │  │ Client           │                     │
│  │ - ParquetFile    │  │                  │                     │
│  │ - Schema         │  │ - Connection     │                     │
│  │ - Metadata       │  │ - Cursor         │                     │
│  └──────────────────┘  └──────────────────┘                     │
│  ┌──────────────────┐                                           │
│  │ PyIceberg        │                                           │
│  │                  │                                           │
│  │ - Catalog        │                                           │
│  │ - Table          │                                           │
│  │ - Snapshot       │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Architectural Layers

### 1. Presentation Layer (TUI)

**Responsibility**: User interface and interaction handling

**Technology**: Textual framework (Python TUI library)

**Components**:

- **Views**: Full-screen or panel components
  - `FileListView`: Displays list of discovered files
  - `FileDetailView`: Shows file-level metadata
  - `SchemaView`: Displays column schema with filtering
  - `RowGroupsView`: Shows row group breakdown
  - `ColumnStatsView`: Displays column statistics
  - `ProfileView`: Shows profiling results
  - `IcebergView`: Iceberg table browser with snapshot navigation
  - `SnapshotDetailView`: Detailed snapshot information
  - `SnapshotComparisonView`: Compare two snapshots with performance testing

- **Widgets**: Reusable UI components
  - `Notification`: Toast-style notifications
  - `LoadingIndicator`: Async operation indicators

- **App**: Main application orchestrator
  - `TableSleuthApp`: Coordinates views and handles events

**Key Patterns**:
- **Observer Pattern**: Views observe model changes
- **Command Pattern**: User actions trigger commands
- **Async/Await**: All I/O operations are asynchronous

### 2. Service Layer

**Responsibility**: Business logic and orchestration

**Components**:

#### ParquetInspector

**Purpose**: Extract metadata from Parquet files

**Key Methods**:
```python
def inspect_file(file_path: str | Path) -> ParquetFileInfo
def get_schema(file_path: str | Path) -> dict[str, Any]
def get_row_groups(file_path: str | Path) -> list[RowGroupInfo]
def get_column_stats(file_path: str | Path, column_name: str) -> ColumnStats
```

**Design Decisions**:
- Uses PyArrow for metadata access (fast, native)
- Handles missing statistics gracefully (returns None)
- Supports nested column structures
- Caches metadata to avoid repeated reads

#### FileDiscoveryService

**Purpose**: Discover Parquet files from various sources

**Key Methods**:
```python
def discover_from_path(path: str | Path) -> list[FileRef]
def discover_from_table(table_identifier: str, catalog_name: str) -> list[FileRef]
```

**Design Decisions**:
- Validates files before returning (checks magic bytes)
- Recursively scans directories
- Delegates to IcebergAdapter for table discovery
- Returns lightweight FileRef objects

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

**Key Features**:
- Connects to local GizmoSQL server via ADBC Flight SQL
- Direct filesystem access (no path conversion needed)
- Uses DuckDB's `read_parquet()` for file access
- Supports Iceberg tables via DuckDB's Iceberg extension
- Executes SQL queries for statistics
- Handles connection pooling and retries

**Iceberg Support**:
- Registers Iceberg tables using `iceberg_scan()` function
- Supports snapshot-specific queries
- Enables performance testing across snapshots

**Design Decisions**:
- Lazy connection initialization
- Connection reuse across queries
- Graceful error handling
- Local deployment (no Docker complexity)
- Optional path conversion for legacy Docker deployments

#### IcebergAdapter

**Purpose**: Discover files from Iceberg tables

**Key Methods**:
```python
def get_data_files(table_identifier: str, catalog_name: str | None) -> list[FileRef]
def load_table(table_identifier: str, catalog_name: str) -> Table
def get_snapshots(table: Table) -> list[Snapshot]
```

**Design Decisions**:
- Uses PyIceberg for catalog access
- Supports snapshot navigation
- Handles data and delete files
- Returns FileRef objects for consistency

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
2. **Configuration File** (`table_sleuth.toml`)
3. **Built-in Defaults** (lowest priority)

### Configuration Structure

```toml
[catalog]
default = "local"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = false

[cache]
ttl = 300  # seconds
max_size = 1000  # entries

[logging]
level = "INFO"
format = "json"
```

### PyIceberg Configuration

Separate configuration in `~/.pyiceberg.yaml`:

```yaml
catalog:
  local:
    type: sql
    uri: sqlite:////absolute/path/to/warehouse/catalog.db
    warehouse: file:///absolute/path/to/warehouse
```

### Configuration Loading

```python
class Config:
    @classmethod
    def load(cls) -> "Config":
        # 1. Load defaults
        config = cls._defaults()

        # 2. Load from file
        if Path("table_sleuth.toml").exists():
            config.update(cls._load_toml("table_sleuth.toml"))

        # 3. Override with environment variables
        config.update(cls._load_env())

        return config
```

## GizmoSQL Deployment

### Local GizmoSQL Architecture

```
┌─────────────────────────────────────┐
│      Table Sleuth TUI               │
│                                     │
│  ┌──────────────────────────────┐   │
│  │  GizmoDuckDbProfiler         │   │
│  │  - ADBC Flight SQL Client    │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
              │
              │ gRPC (localhost:31337)
              ▼
┌─────────────────────────────────────┐
│   Local GizmoSQL Server             │
│   - DuckDB Engine                   │
│   - Direct Filesystem Access        │
│   - Iceberg Extension               │
└─────────────────────────────────────┘
              │
              │ Direct file access
              ▼
┌─────────────────────────────────────┐
│   Local Filesystem                  │
│   - Parquet files                   │
│   - Iceberg metadata                │
│   - Catalog database                │
└─────────────────────────────────────┘
```

### Key Benefits

- **No Docker complexity**: Runs as a local process
- **Direct filesystem access**: No path conversion needed
- **Fast startup**: Instant availability
- **Easy debugging**: Direct process access
- **Low overhead**: No container layer

### Deployment

```bash
# Install GizmoSQL
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_arm64.zip \
  | sudo unzip -o -d /usr/local/bin -

# Start server
GIZMOSQL_PASSWORD="gizmosql_password" gizmosql_server --port 31337 --print-queries
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

## Current Features

### Parquet Inspection
- File metadata extraction
- Schema viewing with filtering
- Row group analysis
- Column statistics
- Column profiling via GizmoSQL

### Iceberg Support
- Table browsing
- Snapshot navigation
- Snapshot comparison
- Merge-on-read metrics
- Performance testing across snapshots
- Query template system

## Future Architecture

### Planned Enhancements

1. **Advanced Snapshot Analysis**
   - Schema evolution tracking
   - Partition evolution analysis
   - Compaction recommendations

2. **Performance Optimization**
   - Query result caching
   - Batch performance testing
   - Historical performance tracking

3. **Export Capabilities**
   - JSON export
   - Markdown reports
   - HTML reports
   - Performance dashboards

4. **Advanced Filtering**
   - Partition-aware filtering
   - Time-travel queries
   - Custom query builder

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
