# Iceberg Metadata Viewer - Developer Documentation

## Architecture Overview

The Iceberg Metadata Viewer follows a layered architecture:

```
┌─────────────────────────────────────────┐
│           TUI Layer (Textual)           │
│  - IcebergView (main screen)            │
│  - SnapshotListView                     │
│  - Detail views (Overview, Files, etc.) │
│  - Comparison views                     │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│          Service Layer                  │
│  - IcebergMetadataService               │
│  - SnapshotTestManager                  │
│  - SnapshotPerformanceAnalyzer          │
│  - GizmoDuckDbProfiler (enhanced)       │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│          Data Models                    │
│  - IcebergTableInfo                     │
│  - IcebergSnapshotInfo                  │
│  - SnapshotComparison                   │
│  - PerformanceComparison                │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│       External Dependencies             │
│  - PyIceberg (table access)             │
│  - DuckDB (query execution)             │
│  - SQLite (test catalog)                │
└─────────────────────────────────────────┘
```

## Core Components

### 1. IcebergMetadataService

**Purpose**: High-level interface for loading and querying Iceberg table metadata.

**Location**: `src/table_sleuth/services/iceberg_metadata_service.py`

**Key Methods**:

```python
def load_table(
    metadata_path: str | None = None,
    catalog_name: str | None = None,
    table_identifier: str | None = None,
) -> IcebergTableInfo:
    """Load an Iceberg table from metadata file or catalog."""

def list_snapshots(table: IcebergTableInfo) -> list[IcebergSnapshotInfo]:
    """Get all snapshots for a table, sorted by timestamp descending."""

def get_snapshot_details(
    table: IcebergTableInfo,
    snapshot_id: int,
) -> IcebergSnapshotDetails:
    """Get detailed information about a specific snapshot."""

def compare_snapshots(
    table: IcebergTableInfo,
    snapshot_a_id: int,
    snapshot_b_id: int,
) -> SnapshotComparison:
    """Compare two snapshots and calculate differences."""
```

**Usage Example**:

```python
from table_sleuth.services.iceberg_metadata_service import IcebergMetadataService

service = IcebergMetadataService()

# Load table
table = service.load_table(metadata_path="/path/to/metadata.json")

# List snapshots
snapshots = service.list_snapshots(table)

# Get details
details = service.get_snapshot_details(table, snapshots[0].snapshot_id)

# Compare
comparison = service.compare_snapshots(table, snap_a_id, snap_b_id)
```

### 2. SnapshotTestManager

**Purpose**: Manages local catalog snapshot table registration in a dedicated namespace.

**Location**: `src/table_sleuth/services/snapshot_test_manager.py`

**Key Methods**:

```python
def ensure_snapshot_namespace() -> str:
    """Ensure snapshot_tests namespace exists in local catalog. Returns namespace name."""

def register_snapshot(
    source_metadata_path: str,
    snapshot_id: int,
    alias: str | None = None,
) -> str:
    """Register a snapshot as a table in snapshot_tests namespace. Returns full table identifier."""

def get_registered_tables() -> list[str]:
    """Get list of all registered snapshot tables in snapshot_tests namespace."""

def cleanup_tables(table_names: list[str] | None = None):
    """Drop specified tables from snapshot_tests namespace or all tables if None."""

def get_catalog_path() -> str:
    """Get the path to the local catalog database file."""
```

**Implementation Details**:

- Uses local catalog from `.pyiceberg.yaml` configuration (typically SQLite-based)
- Catalog location: Defined in `.pyiceberg.yaml` (e.g., `sqlite:////path/to/data/warehouse/catalog.db`)
- Namespace: `snapshot_tests` (dedicated namespace for snapshot table registrations)
- Table naming: `snapshot_tests.{source}_snap_{snapshot_id}`
- No data file copying (metadata-only registration)
- Catalog persists across sessions; only tables in `snapshot_tests` namespace are cleaned up

**Usage Example**:

```python
from table_sleuth.services.snapshot_test_manager import SnapshotTestManager

# Initialize with catalog name from .pyiceberg.yaml (default: 'local')
manager = SnapshotTestManager(catalog_name="local")

# Ensure namespace exists
namespace = manager.ensure_snapshot_namespace()

# Register snapshots
table_a = manager.register_snapshot(metadata_path, snapshot_id=1)
table_b = manager.register_snapshot(metadata_path, snapshot_id=2)

# Query registered tables
tables = manager.get_registered_tables()

# Get catalog path for GizmoSQL
catalog_path = manager.get_catalog_path()

# Cleanup only snapshot tables (preserves catalog and other namespaces)
manager.cleanup_tables()
```

### 3. SnapshotPerformanceAnalyzer

**Purpose**: Executes queries against snapshot tables and collects performance metrics.

**Location**: `src/table_sleuth/services/snapshot_performance_analyzer.py`

**Key Methods**:

```python
def run_query_test(table_name: str, query: str) -> QueryPerformanceMetrics:
    """Run a query against a snapshot table and collect metrics."""

def compare_query_performance(
    table_a: str,
    table_b: str,
    query_template: str,
) -> PerformanceComparison:
    """Run the same query against two tables and compare results."""

def get_predefined_queries() -> dict[str, str]:
    """Get predefined query templates for common test scenarios."""
```

**Usage Example**:

```python
from table_sleuth.services.snapshot_performance_analyzer import (
    SnapshotPerformanceAnalyzer
)

analyzer = SnapshotPerformanceAnalyzer(profiler)

# Run single test
metrics = analyzer.run_query_test("snap_1", "SELECT COUNT(*) FROM {table}")

# Compare performance
comparison = analyzer.compare_query_performance(
    "snap_1",
    "snap_2",
    "SELECT * FROM {table} WHERE date > '2024-01-01'"
)

# Get predefined queries
queries = analyzer.get_predefined_queries()
```

### 4. GizmoDuckDbProfiler (Enhanced)

**Purpose**: Extended profiler with Iceberg catalog support and detailed metrics collection.

**Location**: `src/table_sleuth/services/profiling/gizmo_duckdb.py`

**New Methods**:

```python
def register_catalog(catalog_path: str, catalog_name: str = "test_catalog"):
    """Register an Iceberg catalog with DuckDB."""

def execute_query_with_metrics(query: str) -> tuple[Any, QueryPerformanceMetrics]:
    """Execute query and return results plus detailed metrics."""

def explain_analyze(query: str) -> str:
    """Get query execution plan with timing information."""
```

## Data Models

### IcebergSnapshotInfo

**Location**: `src/table_sleuth/models/iceberg.py`

**Key Properties**:

```python
@property
def has_deletes(self) -> bool:
    """Check if snapshot has delete files."""
    return self.total_delete_files > 0

@property
def delete_ratio(self) -> float:
    """Calculate percentage of deleted records."""
    if self.total_records == 0:
        return 0.0
    deleted = self.position_deletes + self.equality_deletes
    return (deleted / self.total_records) * 100

@property
def read_amplification(self) -> float:
    """Calculate read amplification factor."""
    if self.total_data_files == 0:
        return 1.0
    total_files = self.total_data_files + self.total_delete_files
    return total_files / self.total_data_files
```

### SnapshotComparison

**Key Properties**:

```python
@property
def needs_compaction(self) -> bool:
    """Determine if compaction is recommended."""
    return (
        self.snapshot_b.delete_ratio > 10.0 or
        self.snapshot_b.read_amplification > 1.2
    )

@property
def compaction_recommendation(self) -> str:
    """Get compaction recommendation message."""
    # Returns human-readable recommendation
```

### PerformanceComparison

**Key Properties**:

```python
@property
def execution_time_delta_pct(self) -> float:
    """Calculate execution time change percentage."""

@property
def files_scanned_delta_pct(self) -> float:
    """Calculate files scanned change percentage."""

@property
def analysis(self) -> str:
    """Generate analysis text."""
    # Returns human-readable analysis
```

## TUI Components

### IcebergView

**Location**: `src/table_sleuth/tui/views/iceberg_view.py`

**Main Screen**: Horizontal layout with snapshot list (left) and detail tabs (right).

**Key Methods**:

```python
def _load_snapshots():
    """Load snapshots from the table."""

def _load_snapshot_details(snapshot: IcebergSnapshotInfo):
    """Load detailed information for a snapshot."""

def _register_snapshots_for_comparison():
    """Register selected snapshots as tables for comparison."""

def _run_performance_test():
    """Run performance test with current query."""

def _cleanup_test_tables():
    """Cleanup registered test tables."""
```

### Detail Views

**Locations**:
- `src/table_sleuth/tui/views/snapshot_detail_view.py`
- `src/table_sleuth/tui/views/snapshot_comparison_view.py`

**Components**:
- `SnapshotOverviewView`: Summary stats and MOR metrics
- `SnapshotFilesView`: Data and delete file listings
- `SnapshotSchemaView`: Schema field display
- `SnapshotDeletesView`: Delete file analysis
- `SnapshotPropertiesView`: Snapshot properties
- `SnapshotComparisonView`: Side-by-side comparison
- `PerformanceTestView`: Query testing interface

## Error Handling

### Custom Exceptions

**Location**: `src/table_sleuth/exceptions.py`

```python
class IcebergError(TableSleuthError):
    """Base exception for Iceberg-related errors."""

class TableLoadError(IcebergError):
    """Error loading Iceberg table."""

class CatalogError(IcebergError):
    """Error with test catalog operations."""

class SnapshotRegistrationError(IcebergError):
    """Error registering snapshot as table."""

class QueryExecutionError(IcebergError):
    """Error executing query."""

class SnapshotNotFoundError(IcebergError):
    """Error when snapshot cannot be found."""

class MetadataError(IcebergError):
    """Error reading or parsing Iceberg metadata."""
```

### Error Handling Pattern

```python
try:
    # Operation
    result = service.load_table(metadata_path)
except TableLoadError as e:
    logger.error(f"Failed to load table: {e}")
    # Show user-friendly error
    notification.error(str(e))
except Exception as e:
    logger.exception("Unexpected error")
    # Show generic error
    notification.error(f"Unexpected error: {e}")
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_iceberg_models.py

# Run with coverage
pytest --cov=table_sleuth tests/

# Run only unit tests (skip integration)
pytest -m "not integration" tests/

# Run only integration tests
pytest -m integration tests/
```

### Test Structure

- `test_iceberg_models.py`: Data model tests
- `test_iceberg_metadata_service.py`: Service tests
- `test_snapshot_test_manager.py`: Catalog manager tests
- `test_snapshot_performance_analyzer.py`: Performance analyzer tests

### Integration Test Setup

Integration tests require:

1. Set environment variable:
   ```bash
   export TEST_ICEBERG_METADATA_PATH=/path/to/test/metadata.json
   ```

2. Ensure GizmoSQL is running for performance tests

3. Run with integration marker:
   ```bash
   pytest -m integration tests/
   ```

## Extending the Feature

### Adding New Query Templates

Edit `SnapshotPerformanceAnalyzer.get_predefined_queries()`:

```python
def get_predefined_queries(self) -> dict[str, str]:
    return {
        "full_scan": "SELECT * FROM {table}",
        "my_custom_query": "SELECT custom_col FROM {table} WHERE condition",
        # Add more templates
    }
```

### Adding New Detail Views

1. Create view class in `snapshot_detail_view.py`:

```python
class MyCustomView(Container):
    def compose(self) -> ComposeResult:
        yield Static("", id="custom-content")

    def update_data(self, data):
        content = self.query_one("#custom-content", Static)
        content.update(str(data))
```

2. Add tab to `IcebergView.compose()`:

```python
with TabPane("My Custom", id="custom-tab"):
    yield MyCustomView(id="custom-view")
```

3. Update in `_update_detail_views()`:

```python
custom = self.query_one("#custom-view", MyCustomView)
custom.update_data(self._selected_snapshot)
```

### Adding New MOR Metrics

1. Add property to `IcebergSnapshotInfo`:

```python
@property
def my_custom_metric(self) -> float:
    """Calculate custom metric."""
    return self.some_calculation()
```

2. Display in `SnapshotOverviewView.update_snapshot()`:

```python
lines.append(f"  Custom Metric: {snapshot.my_custom_metric:.2f}")
```

## Performance Considerations

### Caching

The implementation uses several caching strategies:

1. **Snapshot Details Cache**: `_details_cache` in `IcebergView`
   - Key: `snapshot_id`
   - Invalidation: Manual refresh

2. **Performance Test Cache**: Planned but not yet implemented
   - Key: `(snapshot_id, query_hash)`
   - Invalidation: Manual or on cleanup

### Virtual Scrolling

For tables with >100 snapshots, Textual's DataTable provides virtual scrolling automatically.

### Async Operations

Loading indicators are shown during:
- Table loading
- Snapshot details loading
- Snapshot registration
- Query execution
- Cleanup operations

## Debugging

### Enable Verbose Logging

```bash
table-sleuth iceberg metadata.json -v
```

### Check Logs

Logs include:
- Service method calls
- Error stack traces
- PyIceberg operations
- DuckDB query execution

### Common Issues

1. **"Snapshot not found"**: Check snapshot ID exists in table
2. **"Catalog error"**: Check write permissions for temp directory
3. **"Query execution failed"**: Check GizmoSQL connection and query syntax

## Contributing

### Code Style

- Follow PEP 8
- Use type hints (Python 3.12+ syntax)
- Write Google-style docstrings
- Run `ruff` for formatting

### Adding Features

1. Update data models if needed
2. Implement service layer logic
3. Add TUI components
4. Write tests
5. Update documentation

### Pull Request Checklist

- [ ] Code passes `ruff` checks
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] No diagnostics errors
- [ ] Changelog updated

## API Reference

See inline documentation in source files for detailed API reference. All public methods include comprehensive docstrings with:
- Purpose
- Parameters
- Return values
- Exceptions
- Usage examples

## Additional Resources

- [User Guide](./iceberg-viewer-guide.md)
- [Design Document](../.kiro/specs/iceberg-metadata-viewer/design.md)
- [Requirements](../.kiro/specs/iceberg-metadata-viewer/requirements.md)
- [PyIceberg Documentation](https://py.iceberg.apache.org/)
- [Textual Documentation](https://textual.textualize.io/)
