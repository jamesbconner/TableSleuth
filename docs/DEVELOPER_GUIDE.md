# Table Sleuth Developer Guide

## Overview

This guide provides comprehensive information for developers contributing to Table Sleuth, including architecture details, design decisions, testing strategies, and guidelines for extending the system.

## Architecture

### High-Level Architecture

Table Sleuth follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│                    (Textual TUI)                            │
│  - Views: File list, detail, schema, row groups, profile   │
│  - Widgets: Notifications, loading indicators              │
│  - Event handling and user interactions                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                           │
│  - ParquetInspector: Metadata extraction                   │
│  - FileDiscoveryService: File and table discovery          │
│  - ProfilingBackend: Abstract profiling interface          │
│  - IcebergAdapter: Iceberg table integration               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                             │
│  - PyArrow: Parquet file access                            │
│  - ADBC: Arrow Flight SQL client                           │
│  - PyIceberg: Iceberg catalog access                       │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Separation of Concerns**: Each layer has distinct responsibilities
2. **Dependency Inversion**: High-level modules don't depend on low-level details
3. **Interface Segregation**: Small, focused interfaces (e.g., ProfilingBackend)
4. **Single Responsibility**: Each class/module has one reason to change
5. **Open/Closed**: Open for extension, closed for modification

### Key Design Decisions

#### 1. Protocol-Based Profiling Backend

**Decision**: Use Python Protocol for profiling backend abstraction

**Rationale**:
- Allows multiple implementations without inheritance
- Enables duck typing for flexibility
- Simplifies testing with fake implementations
- Supports future backends (Spark, Trino, Athena)

**Implementation**:
```python
class ProfilingBackend(Protocol):
    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str: ...
    def profile_single_column(self, view_name: str, column: str) -> ColumnProfile: ...
    def profile_columns(self, view_name: str, columns: Sequence[str]) -> dict[str, ColumnProfile]: ...
```

#### 2. Async-First TUI Design

**Decision**: Use async/await for all I/O operations in TUI

**Rationale**:
- Keeps UI responsive during file operations
- Enables concurrent operations (e.g., loading multiple files)
- Integrates naturally with Textual framework
- Supports cancellation and timeout handling

**Implementation**:
```python
async def on_file_selected(self, file_ref: FileRef) -> None:
    self.show_loading()
    try:
        file_info = await self.inspect_file_async(file_ref.path)
        self.display_file_info(file_info)
    finally:
        self.hide_loading()
```

#### 3. Caching Strategy

**Decision**: Implement multi-level caching with TTL

**Rationale**:
- File metadata rarely changes
- Profiling queries are expensive
- Reduces latency for repeated access
- Improves user experience

**Cache Levels**:
1. **File Metadata Cache**: Keyed by file path
2. **Profiling Results Cache**: Keyed by (view_name, column, filters)
3. **Schema Cache**: Keyed by file path

**Invalidation**: Manual refresh (press `r`) or TTL expiration

#### 4. Graceful Degradation

**Decision**: Continue operation when optional features fail

**Rationale**:
- GizmoSQL may not be available
- Iceberg catalog may not be configured
- Some Parquet files may lack statistics
- User should still access core functionality

**Implementation**:
- Try/except blocks with user-friendly error messages
- Feature availability checks before operations
- Fallback behaviors (e.g., skip profiling if backend unavailable)

## Project Structure

```
table-sleuth/
├── src/table_sleuth/
│   ├── __init__.py
│   ├── cli.py                      # CLI entry point and argument parsing
│   ├── config.py                   # Configuration loading and validation
│   │
│   ├── models/                     # Data models and types
│   │   ├── __init__.py
│   │   ├── file_ref.py            # File reference model
│   │   ├── parquet.py             # Parquet metadata models
│   │   ├── profiling.py           # Profiling result models
│   │   └── performance.py         # Performance tracking models
│   │
│   ├── services/                   # Business logic layer
│   │   ├── __init__.py
│   │   ├── parquet_service.py     # Parquet inspection service
│   │   ├── file_discovery.py      # File discovery service
│   │   │
│   │   ├── profiling/             # Profiling backends
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # ProfilingBackend protocol
│   │   │   └── gizmo_duckdb.py    # GizmoSQL implementation
│   │   │
│   │   └── formats/               # Table format adapters
│   │       ├── __init__.py
│   │       └── iceberg.py         # Iceberg adapter
│   │
│   ├── tui/                        # Terminal UI layer
│   │   ├── __init__.py
│   │   ├── app.py                 # Main TUI application
│   │   │
│   │   ├── views/                 # TUI views (screens/panels)
│   │   │   ├── __init__.py
│   │   │   ├── file_list_view.py
│   │   │   ├── file_detail_view.py
│   │   │   ├── schema_view.py
│   │   │   ├── row_groups_view.py
│   │   │   ├── column_stats_view.py
│   │   │   └── profile_view.py
│   │   │
│   │   └── widgets/               # Reusable UI components
│   │       ├── __init__.py
│   │       ├── notification.py
│   │       └── loading.py
│   │
│   └── utils/                      # Utility functions
│       ├── __init__.py
│       └── formatting.py          # Display formatting helpers
│
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_parquet_inspector.py
│   ├── test_file_discovery.py
│   ├── test_profiling_backend.py
│   ├── test_gizmosql_integration.py
│   ├── test_*.py                  # Component tests
│   └── test_end_to_end.py         # E2E tests
│
├── docs/                           # Documentation
│   ├── USER_GUIDE.md
│   ├── DEVELOPER_GUIDE.md
│   ├── PERFORMANCE_PROFILING.md
│   ├── product_specification.md
│   └── technical_specification.md
│
├── .kiro/specs/                    # Feature specifications
│   ├── table-sleuth-mvp-0/
│   │   ├── requirements.md
│   │   ├── design.md
│   │   └── tasks.md
│   └── table-sleuth-mvp-v1/
│
├── scripts/                        # Utility scripts
│   ├── create_test_data.py
│   └── create_iceberg_tables.py
│
├── pyproject.toml                  # Project configuration
├── README.md
├── QUICKSTART.md
├── CHANGELOG.md
└── .pre-commit-config.yaml
```

## Component Interfaces

### ParquetInspector Service

**Purpose**: Extract metadata from Parquet files using PyArrow

**Interface**:
```python
class ParquetInspector:
    def inspect_file(self, file_path: str | Path) -> ParquetFileInfo:
        """Extract complete metadata from a Parquet file."""

    def get_schema(self, file_path: str | Path) -> dict[str, Any]:
        """Extract schema information."""

    def get_row_groups(self, file_path: str | Path) -> list[RowGroupInfo]:
        """Extract row group information."""

    def get_column_stats(self, file_path: str | Path, column_name: str) -> ColumnStats:
        """Extract statistics for a specific column."""
```

**Key Implementation Details**:
- Uses `pyarrow.parquet.ParquetFile` for metadata access
- Handles missing statistics gracefully (returns None)
- Supports nested column structures
- Extracts physical and logical types
- Collects encoding and compression information

### FileDiscoveryService

**Purpose**: Discover Parquet files from various sources

**Interface**:
```python
class FileDiscoveryService:
    def discover_from_path(self, path: str | Path) -> list[FileRef]:
        """Discover files from a file or directory path."""

    def discover_from_table(self, table_identifier: str, catalog_name: str) -> list[FileRef]:
        """Discover files from an Iceberg table."""

    def _is_parquet_file(self, path: Path) -> bool:
        """Check if a file is a valid Parquet file."""

    def _scan_directory(self, directory: Path) -> list[Path]:
        """Recursively scan directory for Parquet files."""
```

**Key Implementation Details**:
- Validates file extensions (.parquet, .pq)
- Uses PyArrow to verify file validity
- Recursively scans directories
- Delegates to IcebergAdapter for table discovery
- Returns FileRef objects with basic metadata

### ProfilingBackend Protocol

**Purpose**: Abstract interface for data profiling engines

**Interface**:
```python
class ProfilingBackend(Protocol):
    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        """Create a backend-specific view for Parquet files."""

    def profile_single_column(self, view_name: str, column: str, filters: str | None = None) -> ColumnProfile:
        """Profile a single column with optional filters."""

    def profile_columns(self, view_name: str, columns: Sequence[str], filters: str | None = None) -> dict[str, ColumnProfile]:
        """Profile multiple columns with optional filters."""
```

**GizmoSQL Implementation**:
```python
class GizmoDuckDbProfiler:
    def __init__(self, connection_uri: str, username: str, password: str):
        self._uri = connection_uri
        self._username = username
        self._password = password
        self._connection: dbapi.Connection | None = None

    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        # Uses DuckDB's read_parquet() function
        # Supports multiple files for partitioned datasets

    def profile_single_column(self, view_name: str, column: str, filters: str | None = None) -> ColumnProfile:
        # Executes SQL query for statistics
        # Returns ColumnProfile with results
```

## Adding New Profiling Backends

### Step 1: Implement the Protocol

Create a new file in `src/table_sleuth/services/profiling/`:

```python
# src/table_sleuth/services/profiling/spark_backend.py
from typing import Sequence
from table_sleuth.models.profiling import ColumnProfile
from table_sleuth.services.profiling.base import ProfilingBackend

class SparkProfiler:
    """PySpark-based profiling backend."""

    def __init__(self, spark_session):
        self._spark = spark_session

    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        """Register Parquet files as a Spark temporary view."""
        if view_name is None:
            view_name = f"view_{uuid.uuid4().hex[:8]}"

        df = self._spark.read.parquet(*file_paths)
        df.createOrReplaceTempView(view_name)
        return view_name

    def profile_single_column(self, view_name: str, column: str, filters: str | None = None) -> ColumnProfile:
        """Profile a column using Spark SQL."""
        query = f"""
            SELECT
                COUNT(*) as row_count,
                COUNT({column}) as non_null_count,
                COUNT(*) - COUNT({column}) as null_count,
                COUNT(DISTINCT {column}) as distinct_count,
                MIN({column}) as min_value,
                MAX({column}) as max_value
            FROM {view_name}
        """
        if filters:
            query += f" WHERE {filters}"

        result = self._spark.sql(query).collect()[0]

        return ColumnProfile(
            column=column,
            row_count=result.row_count,
            non_null_count=result.non_null_count,
            null_count=result.null_count,
            distinct_count=result.distinct_count,
            min_value=result.min_value,
            max_value=result.max_value,
        )

    def profile_columns(self, view_name: str, columns: Sequence[str], filters: str | None = None) -> dict[str, ColumnProfile]:
        """Profile multiple columns."""
        return {col: self.profile_single_column(view_name, col, filters) for col in columns}
```

### Step 2: Register the Backend

Update configuration to support the new backend:

```toml
# table_sleuth.toml
[profiling]
backend = "spark"  # or "gizmosql"

[spark]
master = "local[*]"
app_name = "table-sleuth"
```

### Step 3: Update Backend Factory

```python
# src/table_sleuth/services/profiling/__init__.py
def create_profiling_backend(config: Config) -> ProfilingBackend | None:
    backend_type = config.profiling.backend

    if backend_type == "gizmosql":
        return GizmoDuckDbProfiler(
            connection_uri=config.gizmosql.uri,
            username=config.gizmosql.username,
            password=config.gizmosql.password,
        )
    elif backend_type == "spark":
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.master(config.spark.master).appName(config.spark.app_name).getOrCreate()
        return SparkProfiler(spark)
    else:
        return None
```

### Step 4: Add Tests

```python
# tests/test_spark_profiling.py
import pytest
from table_sleuth.services.profiling.spark_backend import SparkProfiler

@pytest.fixture
def spark_session():
    from pyspark.sql import SparkSession
    return SparkSession.builder.master("local[1]").appName("test").getOrCreate()

def test_spark_profiler_register_view(spark_session, test_parquet_file):
    profiler = SparkProfiler(spark_session)
    view_name = profiler.register_file_view([str(test_parquet_file)])

    assert view_name is not None
    # Verify view exists
    df = spark_session.table(view_name)
    assert df.count() > 0

def test_spark_profiler_profile_column(spark_session, test_parquet_file):
    profiler = SparkProfiler(spark_session)
    view_name = profiler.register_file_view([str(test_parquet_file)])

    profile = profiler.profile_single_column(view_name, "id")

    assert profile.row_count > 0
    assert profile.non_null_count > 0
    assert profile.distinct_count > 0
```

## Testing Strategy

### Test Pyramid

```
        ┌─────────────┐
        │   E2E Tests │  (Few, slow, comprehensive)
        └─────────────┘
      ┌───────────────────┐
      │ Integration Tests │  (Some, medium speed)
      └───────────────────┘
    ┌───────────────────────────┐
    │      Unit Tests           │  (Many, fast, focused)
    └───────────────────────────┘
```

### Unit Tests

**Purpose**: Test individual components in isolation

**Coverage**: 90%+ for core services

**Example**:
```python
# tests/test_parquet_inspector.py
def test_inspect_file_basic_metadata(test_parquet_file):
    inspector = ParquetInspector()
    info = inspector.inspect_file(test_parquet_file)

    assert info.num_rows == 1000
    assert info.num_row_groups == 1
    assert info.num_columns == 5
    assert info.file_size_bytes > 0

def test_inspect_file_missing_statistics(parquet_file_no_stats):
    inspector = ParquetInspector()
    info = inspector.inspect_file(parquet_file_no_stats)

    # Should handle missing stats gracefully
    assert info.columns[0].null_count is None
    assert info.columns[0].min_value is None
```

### Integration Tests

**Purpose**: Test component interactions

**Requirements**: Docker for GizmoSQL tests

**Example**:
```python
# tests/test_gizmosql_integration.py
@pytest.mark.integration
def test_gizmosql_profiling_workflow(gizmosql_container, test_parquet_file):
    profiler = GizmoDuckDbProfiler(
        connection_uri="grpc+tls://localhost:31337",
        username="gizmo",
        password="gizmo",
    )

    # Register view
    view_name = profiler.register_file_view([str(test_parquet_file)])

    # Profile column
    profile = profiler.profile_single_column(view_name, "customer_id")

    assert profile.row_count == 1000
    assert profile.null_count == 0
    assert profile.distinct_count > 0
```

### End-to-End Tests

**Purpose**: Test complete user workflows

**Approach**: Use Textual testing utilities

**Example**:
```python
# tests/test_end_to_end.py
async def test_complete_inspection_workflow(test_parquet_file):
    app = TableSleuthApp(file_path=str(test_parquet_file))

    async with app.run_test() as pilot:
        # File should be loaded
        assert app.current_file is not None

        # Navigate to schema tab
        await pilot.press("tab")

        # Select first column
        await pilot.press("down")

        # Trigger profile
        await pilot.press("p")

        # Wait for profile to complete
        await pilot.pause(2.0)

        # Verify profile results displayed
        assert app.profile_view.has_results
```

### Test Fixtures

```python
# tests/conftest.py
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

@pytest.fixture
def test_parquet_file(tmp_path: Path) -> Path:
    """Create a test Parquet file with known data."""
    data = {
        "id": list(range(1000)),
        "name": [f"user_{i}" for i in range(1000)],
        "age": [20 + (i % 50) for i in range(1000)],
        "active": [i % 2 == 0 for i in range(1000)],
    }
    table = pa.table(data)

    file_path = tmp_path / "test.parquet"
    pq.write_table(table, file_path, compression="snappy")

    return file_path

@pytest.fixture
def test_parquet_directory(tmp_path: Path) -> Path:
    """Create a directory with multiple Parquet files."""
    dir_path = tmp_path / "data"
    dir_path.mkdir()

    for i in range(5):
        data = {"id": list(range(i * 100, (i + 1) * 100))}
        table = pa.table(data)
        pq.write_table(table, dir_path / f"file_{i}.parquet")

    return dir_path

@pytest.fixture
def gizmosql_container():
    """Start GizmoSQL container for integration tests."""
    import docker
    client = docker.from_env()

    container = client.containers.run(
        "gizmosql/gizmosql:latest",
        ports={"31337/tcp": 31337},
        detach=True,
        remove=True,
    )

    # Wait for container to be ready
    time.sleep(5)

    yield container

    container.stop()
```

## Code Quality Standards

### Type Annotations

All functions must have complete type annotations:

```python
# Good
def inspect_file(self, file_path: str | Path) -> ParquetFileInfo:
    """Extract metadata from a Parquet file."""
    ...

# Bad
def inspect_file(self, file_path):
    """Extract metadata from a Parquet file."""
    ...
```

### Docstrings

Use Google-style docstrings for all public functions:

```python
def profile_single_column(
    self,
    view_name: str,
    column: str,
    filters: str | None = None
) -> ColumnProfile:
    """Profile a single column with optional filters.

    Args:
        view_name: Name of the registered view
        column: Column name to profile
        filters: Optional SQL WHERE clause filters

    Returns:
        ColumnProfile with statistics including row count, null count,
        distinct count, and min/max values

    Raises:
        ConnectionError: If backend connection fails
        ValueError: If column doesn't exist in view

    Example:
        >>> profiler = GizmoDuckDbProfiler(uri, user, password)
        >>> view = profiler.register_file_view(["data.parquet"])
        >>> profile = profiler.profile_single_column(view, "customer_id")
        >>> print(f"Distinct: {profile.distinct_count}")
    """
    ...
```

### Error Handling

Use specific exceptions and provide context:

```python
# Good
try:
    file_info = inspector.inspect_file(file_path)
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    raise
except pa.ArrowInvalid as e:
    logger.error(f"Invalid Parquet file: {file_path}", exc_info=True)
    raise ValueError(f"Not a valid Parquet file: {file_path}") from e

# Bad
try:
    file_info = inspector.inspect_file(file_path)
except Exception as e:
    print(f"Error: {e}")
```

### Logging

Use structured logging with appropriate levels:

```python
import logging

logger = logging.getLogger(__name__)

# Info: Normal operations
logger.info("Inspecting file", extra={"file_path": file_path, "size_bytes": size})

# Warning: Recoverable issues
logger.warning("Missing column statistics", extra={"column": column_name})

# Error: Operation failures
logger.error("Failed to connect to GizmoSQL", extra={"uri": uri}, exc_info=True)

# Debug: Detailed information
logger.debug("Executing query", extra={"query": query, "view": view_name})
```

## Contribution Guidelines

### Development Workflow

1. **Fork and Clone**:
   ```bash
   git clone <your-fork-url>
   cd table-sleuth
   ```

2. **Create Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Install Dependencies**:
   ```bash
   uv sync
   source .venv/bin/activate
   ```

4. **Make Changes**:
   - Write code following style guidelines
   - Add tests for new functionality
   - Update documentation

5. **Run Tests**:
   ```bash
   pytest
   pytest --cov=src/table_sleuth --cov-report=html
   ```

6. **Check Code Quality**:
   ```bash
   ruff format .
   ruff check .
   mypy src/table_sleuth
   ```

7. **Commit Changes**:
   ```bash
   git add .
   git commit -m "feat: add new profiling backend"
   ```

8. **Push and Create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

Follow conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions or changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Build/tooling changes

**Examples**:
```
feat(profiling): add Spark profiling backend

Implement SparkProfiler class that uses PySpark for column profiling.
Supports single and multi-column profiling with optional filters.

Closes #123
```

```
fix(tui): handle missing column statistics gracefully

Display "N/A" instead of crashing when column statistics are not
available in Parquet metadata.

Fixes #456
```

### Code Review Checklist

- [ ] Code follows style guidelines (ruff, mypy pass)
- [ ] All tests pass
- [ ] New functionality has tests
- [ ] Documentation is updated
- [ ] Commit messages follow convention
- [ ] No breaking changes (or documented)
- [ ] Performance impact considered
- [ ] Security implications reviewed

## Path to MVP 1

### Planned Features

1. **Full Iceberg Support**
   - Snapshot history navigation
   - Delete file inspection
   - Merge-on-read analysis
   - Schema evolution tracking

2. **Performance Profiling**
   - Query performance analysis
   - File layout optimization suggestions
   - Compression ratio analysis

3. **Export Capabilities**
   - JSON export
   - Markdown reports
   - HTML reports
   - CSV statistics

4. **Advanced Filtering**
   - SQL WHERE clause support
   - Partition filtering
   - Time range filtering

5. **Query History**
   - Save profiling queries
   - Bookmark files
   - Recent files list

### Extension Points

**New Table Formats**:
- Delta Lake adapter
- Hudi adapter
- Custom format plugins

**New Profiling Backends**:
- Trino/Presto backend
- AWS Athena backend
- Databricks backend

**New Export Formats**:
- PDF reports
- Excel spreadsheets
- Grafana dashboards

## Resources

### Documentation
- [Textual Documentation](https://textual.textualize.io/)
- [PyArrow Documentation](https://arrow.apache.org/docs/python/)
- [PyIceberg Documentation](https://py.iceberg.apache.org/)
- [ADBC Documentation](https://arrow.apache.org/docs/format/ADBC.html)

### Specifications
- [Parquet Format Specification](https://parquet.apache.org/docs/)
- [Iceberg Table Format](https://iceberg.apache.org/spec/)
- [Arrow Flight SQL](https://arrow.apache.org/docs/format/FlightSql.html)

### Internal Documentation
- [Requirements](.kiro/specs/table-sleuth-mvp-0/requirements.md)
- [Design](.kiro/specs/table-sleuth-mvp-0/design.md)
- [Tasks](.kiro/specs/table-sleuth-mvp-0/tasks.md)
- [Product Specification](product_specification.md)
- [Technical Specification](technical_specification.md)
