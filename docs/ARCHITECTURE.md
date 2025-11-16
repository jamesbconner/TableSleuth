# Table Sleuth Architecture

## Overview

Table Sleuth is a Python-based Parquet file forensics tool built with a layered architecture that separates concerns between presentation, business logic, and data access. This document provides a comprehensive overview of the system architecture, design patterns, and key technical decisions.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Presentation Layer                          │
│                     (Textual TUI)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ File List    │  │ File Detail  │  │ Schema View  │          │
│  │ View         │  │ View         │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Row Groups   │  │ Column Stats │  │ Profile View │          │
│  │ View         │  │ View         │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────────────────────────────────────────┐          │
│  │ Widgets: Notifications, Loading Indicators       │          │
│  └──────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                              │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ Parquet          │  │ File Discovery   │                    │
│  │ Inspector        │  │ Service          │                    │
│  │                  │  │                  │                    │
│  │ - inspect_file() │  │ - discover_from  │                    │
│  │ - get_schema()   │  │   _path()        │                    │
│  │ - get_row_groups │  │ - discover_from  │                    │
│  │ - get_column_    │  │   _table()       │                    │
│  │   stats()        │  │                  │                    │
│  └──────────────────┘  └──────────────────┘                    │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ Profiling        │  │ Iceberg Adapter  │                    │
│  │ Backend          │  │                  │                    │
│  │ (Protocol)       │  │ - get_data_files │                    │
│  │                  │  │ - load_catalog() │                    │
│  │ - register_file  │  │ - load_table()   │                    │
│  │   _view()        │  │                  │                    │
│  │ - profile_single │  │                  │                    │
│  │   _column()      │  │                  │                    │
│  │ - profile_       │  │                  │                    │
│  │   columns()      │  │                  │                    │
│  └──────────────────┘  └──────────────────┘                    │
│           │                                                     │
│           ▼                                                     │
│  ┌──────────────────┐                                          │
│  │ GizmoDuckDb      │                                          │
│  │ Profiler         │                                          │
│  │ (Implementation) │                                          │
│  └──────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Data Layer                                │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ PyArrow          │  │ ADBC Flight SQL  │                    │
│  │                  │  │ Client           │                    │
│  │ - ParquetFile    │  │                  │                    │
│  │ - Schema         │  │ - Connection     │                    │
│  │ - Metadata       │  │ - Cursor         │                    │
│  └──────────────────┘  └──────────────────┘                    │
│  ┌──────────────────┐                                          │
│  │ PyIceberg        │                                          │
│  │                  │                                          │
│  │ - Catalog        │                                          │
│  │ - Table          │                                          │
│  │ - Snapshot       │                                          │
│  └──────────────────┘                                          │
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

**Purpose**: DuckDB-based profiling implementation

**Key Features**:
- Connects via ADBC Flight SQL
- Uses DuckDB's `read_parquet()` for file access
- Executes SQL queries for statistics
- Handles connection pooling and retries

**Design Decisions**:
- Lazy connection initialization
- Connection reuse across queries
- Graceful error handling
- TLS support with optional skip-verify

#### IcebergAdapter

**Purpose**: Discover files from Iceberg tables

**Key Methods**:
```python
def get_data_files(table_identifier: str, catalog_name: str | None) -> list[FileRef]
```

**Design Decisions**:
- Uses PyIceberg for catalog access
- Loads current snapshot only (MVP 0)
- Ignores delete files (MVP 0)
- Returns FileRef objects for consistency

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
User presses 'p' on column
       │
       ▼
SchemaView.on_profile_triggered()
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
ADBC Connection                 │
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
username = "gizmo"
password = "gizmo"
tls_skip_verify = true

[cache]
ttl = 300  # seconds
max_size = 1000  # entries

[logging]
level = "INFO"
format = "json"
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
- UI responsiveness: < 100ms for user interactions

## Security Considerations

### Credential Management

- Load from environment variables or config file
- Never log passwords or sensitive credentials
- Support TLS for GizmoSQL connections
- Optional TLS verification skip for development

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

## Testing Architecture

### Test Pyramid

```
        ┌─────────────┐
        │   E2E Tests │  (Few, slow, comprehensive)
        │   ~10 tests │
        └─────────────┘
      ┌───────────────────┐
      │ Integration Tests │  (Some, medium speed)
      │    ~30 tests      │
      └───────────────────┘
    ┌───────────────────────────┐
    │      Unit Tests           │  (Many, fast, focused)
    │      ~100 tests           │
    └───────────────────────────┘
```

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── test_parquet_inspector.py
├── test_file_discovery.py
├── test_profiling_backend.py
├── test_gizmosql_integration.py  # Integration tests
├── test_end_to_end.py            # E2E tests
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

## Future Architecture (MVP 1)

### Planned Changes

1. **Snapshot Navigation**
   - Add snapshot history service
   - Implement time-travel queries
   - Add snapshot comparison views

2. **Delete File Support**
   - Extend IcebergAdapter for delete files
   - Add merge-on-read analysis
   - Show delete file statistics

3. **Performance Profiling**
   - Add performance tracking service
   - Collect query metrics
   - Generate optimization suggestions

4. **Export Capabilities**
   - Add export service
   - Support multiple formats (JSON, Markdown, HTML)
   - Generate reports

## References

### External Documentation

- [Textual Documentation](https://textual.textualize.io/)
- [PyArrow Documentation](https://arrow.apache.org/docs/python/)
- [PyIceberg Documentation](https://py.iceberg.apache.org/)
- [ADBC Documentation](https://arrow.apache.org/docs/format/ADBC.html)

### Internal Documentation

- [Developer Guide](DEVELOPER_GUIDE.md)
- [User Guide](USER_GUIDE.md)
- [Requirements](.kiro/specs/table-sleuth-mvp-0/requirements.md)
- [Design](.kiro/specs/table-sleuth-mvp-0/design.md)
