# Table Sleuth Developer Guide

**Version**: 0.5.3

## Overview

This guide provides comprehensive information for developers contributing to Table Sleuth, including architecture details, design decisions, testing strategies, and guidelines for extending the system.

**For detailed architecture information, see [ARCHITECTURE.md](ARCHITECTURE.md)**

**For development setup, see [../DEVELOPMENT_SETUP.md](../DEVELOPMENT_SETUP.md)**

## Quick Start for Developers

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/jamesbconner/TableSleuth.git
cd TableSleuth

# Install dependencies with dev tools
uv sync --all-extras

# Activate virtual environment
source .venv/bin/activate

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run quality checks
make check
```

See [DEVELOPMENT_SETUP.md](../DEVELOPMENT_SETUP.md) for complete setup instructions.

## Architecture Overview

Table Sleuth follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Layer                                │
│  - Modular structure with auto-loading (v0.5.3+)           │
│  - parquet: Parquet file analysis                           │
│  - iceberg: Snapshot analysis and comparison                │
│  - delta: Delta Lake forensics and optimization             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer (TUI)                 │
│  - Views: File list, schema, row groups, snapshots          │
│  - Widgets: Notifications, loading indicators, modals       │
│  - Event handling and user interactions                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                           │
│  - ParquetService: Metadata extraction                      │
│  - FileDiscoveryService: File and table discovery           │
│  - FilesystemService: S3/local abstraction                  │
│  - DeltaAdapter: Delta table management (v0.5.0+)           │
│  - DeltaForensics: Delta analysis (v0.5.0+)                 │
│  - DeltaLogFileSystem: Unified FS API (v0.5.3+)             │
│  - IcebergAdapter: Catalog and table management             │
│  - IcebergMetadataService: Snapshot loading                 │
│  - MORService: Merge-on-read analysis                       │
│  - ProfilingBackend: Abstract profiling interface           │
│  - SnapshotTestManager: Performance test setup              │
│  - SnapshotPerformanceAnalyzer: Query performance           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                             │
│  - PyArrow: Parquet file access                             │
│  - ADBC: Arrow Flight SQL client                            │
│  - PyIceberg: Iceberg catalog access (SQL, Glue, REST)      │
│  - boto3: AWS S3 and Glue access                            │
│  - fsspec: Unified filesystem interface                     │
└─────────────────────────────────────────────────────────────┘
```

**For detailed architecture documentation, see [ARCHITECTURE.md](ARCHITECTURE.md)**

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
tablesleuth/
├── src/tablesleuth/
│   ├── __init__.py
│   ├── config.py                       # Configuration loading and validation
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
│   ├── models/                         # Data models and types
│   │   ├── __init__.py
│   │   ├── file_ref.py                 # File reference model
│   │   ├── parquet.py                  # Parquet metadata models
│   │   ├── profiling.py                # Profiling result models
│   │   ├── performance.py              # Performance tracking models
│   │   ├── iceberg.py                  # Iceberg-specific models
│   │   ├── snapshot.py                 # Snapshot models
│   │   └── table.py                    # Table handle models
│   │
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   ├── parquet_service.py          # Parquet inspection service
│   │   ├── file_discovery.py           # File discovery service
│   │   ├── filesystem.py               # S3/local filesystem abstraction
│   │   ├── delta_forensics.py          # Delta Lake forensics (v0.5.0+)
│   │   ├── iceberg_metadata_service.py # Iceberg metadata loading
│   │   ├── mor_service.py              # Merge-on-read analysis
│   │   ├── snapshot_test_manager.py    # Snapshot registration for testing
│   │   ├── snapshot_performance_analyzer.py  # Query performance analysis
│   │   │
│   │   ├── profiling/                  # Profiling backends
│   │   │   ├── __init__.py
│   │   │   ├── backend_base.py         # ProfilingBackend protocol
│   │   │   ├── fake_backend.py         # Testing backend
│   │   │   └── gizmo_duckdb.py         # GizmoSQL/DuckDB implementation
│   │   │
│   │   └── formats/                    # Table format adapters
│   │       ├── __init__.py
│   │       ├── base.py                 # Base adapter protocol
│   │       ├── delta.py                # Delta adapter (v0.5.0+)
│   │       ├── delta_filesystem.py     # Delta filesystem abstraction (v0.5.3+)
│   │       ├── delta_log_parser.py     # Delta log parser (v0.5.0+)
│   │       ├── delta_utils.py          # Delta utilities (v0.5.0+)
│   │       └── iceberg.py              # Iceberg adapter (SQL, Glue, S3 Tables)
│   │
│   ├── tui/                            # Terminal UI layer
│   │   ├── __init__.py
│   │   ├── app.py                      # Main TUI application
│   │   │
│   │   ├── views/                      # TUI views (screens/panels)
│   │   │   ├── __init__.py
│   │   │   ├── file_list_view.py       # File list navigation
│   │   │   ├── file_detail_view.py     # File metadata view
│   │   │   ├── schema_view.py          # Schema inspection
│   │   │   ├── row_groups_view.py      # Row group analysis
│   │   │   ├── column_stats_view.py    # Column statistics
│   │   │   ├── data_sample_view.py     # Data preview
│   │   │   ├── profile_view.py         # Profiling results
│   │   │   ├── delta_view.py           # Delta table view (v0.5.0+)
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
│       ├── __init__.py
│       └── formatting.py               # Display formatting helpers
│
├── tests/                              # Test suite
│   ├── __init__.py
│   ├── conftest.py                     # Pytest fixtures
│   ├── test_parquet_service.py
│   ├── test_file_discovery.py
│   ├── test_profiling_backend.py
│   ├── test_gizmo_profiler_config.py
│   ├── test_snapshot_test_manager.py
│   ├── test_snapshot_performance_analyzer.py
│   ├── test_parquet_profiling_integration.py
│   ├── test_end_to_end.py              # E2E tests
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
│   │   ├── inspect_s3_tables.py        # S3 Tables inspection
│   │   ├── delta_forensics.py          # Delta health analysis
│   │   ├── iceberg_snapshot_diff.py    # Snapshot comparison
│   │   ├── discover_parquet_files.py   # File discovery
│   │   ├── extract_parquet_metadata.py # Metadata extraction
│   │   └── batch_table_analysis.py     # Batch analysis
│   └── README.md                       # IaC overview
│
├── docs/                               # Documentation
│   ├── ARCHITECTURE.md                 # System architecture
│   ├── USER_GUIDE.md                   # User documentation
│   ├── DEVELOPER_GUIDE.md              # This file
│   ├── EC2_DEPLOYMENT_GUIDE.md         # EC2 deployment
│   ├── PERFORMANCE_PROFILING.md        # Performance guide
│   ├── gizmosql-deployment.md          # GizmoSQL setup
│   ├── s3_tables_guide.md              # S3 Tables configuration
│   └── images/                         # Screenshots
│
├── .kiro/specs/                        # Feature specifications
│   ├── tablesleuth-mvp-0/
│   │   ├── requirements.md
│   │   ├── design.md
│   │   └── tasks.md
│   └── tablesleuth-mvp-v1/
│
├── pyproject.toml                      # Project configuration
├── uv.lock                             # Dependency lock file
├── tablesleuth.toml                    # Application configuration
├── Makefile                            # Development commands
├── README.md
├── QUICKSTART.md
├── TABLESLEUTH_SETUP.md                # User setup guide
├── DEVELOPMENT_SETUP.md                # Developer setup guide
├── CONTRIBUTING.md
├── CHANGELOG.md
└── .pre-commit-config.yaml
```

## Component Interfaces

### ParquetService

**Purpose**: Extract metadata and data from Parquet files using PyArrow

**Interface**:
```python
class ParquetService:
    def inspect_file(self, file_path: str | Path) -> ParquetFileInfo:
        """Extract complete metadata from a Parquet file."""

    def get_schema(self, file_path: str | Path) -> dict[str, Any]:
        """Extract schema information."""

    def get_row_groups(self, file_path: str | Path) -> list[RowGroupInfo]:
        """Extract row group information."""

    def get_column_stats(self, file_path: str | Path, column_name: str) -> ColumnStats:
        """Extract statistics for a specific column."""

    def get_data_sample(
        self,
        file_path: str | Path,
        columns: list[str] | None = None,
        limit: int = 100
    ) -> dict[str, Any]:
        """Extract data sample from Parquet file."""
```

**Key Implementation Details**:
- Uses `pyarrow.parquet.ParquetFile` for metadata access
- Handles missing statistics gracefully (returns None)
- Supports nested column structures
- Extracts physical and logical types
- Collects encoding and compression information
- Supports both local and S3 files via fsspec

### FileDiscoveryService

**Purpose**: Discover Parquet files from various sources

**Interface**:
```python
class FileDiscoveryService:
    def discover_from_path(self, path: str | Path) -> list[FileRef]:
        """Discover files from a file or directory path (local or S3)."""

    def discover_from_table(self, table_identifier: str, catalog_name: str) -> list[FileRef]:
        """Discover files from an Iceberg table."""

    def _is_parquet_file(self, path: Path) -> bool:
        """Check if a file is a valid Parquet file."""

    def _scan_directory(self, directory: Path) -> list[Path]:
        """Recursively scan directory for Parquet files."""
```

**Supported Sources**:
- Local files and directories (recursive)
- S3 files and prefixes (s3://bucket/path/)
- Iceberg tables (via catalog)
- S3 Tables (via ARN)

**Key Implementation Details**:
- Validates file extensions (.parquet, .pq)
- Uses PyArrow to verify file validity
- Recursively scans directories
- Delegates to IcebergAdapter for table discovery
- Returns FileRef objects with basic metadata
- Handles S3 and local paths uniformly via fsspec

### FilesystemService

**Purpose**: Abstract filesystem operations for local and S3

**Interface**:
```python
class FilesystemService:
    def read_file(self, path: str) -> bytes:
        """Read file contents."""

    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """List files in directory."""

    def file_exists(self, path: str) -> bool:
        """Check if file exists."""

    def get_file_size(self, path: str) -> int:
        """Get file size in bytes."""
```

**Key Implementation Details**:
- Uses fsspec for unified filesystem interface
- Supports S3 via s3fs
- Handles AWS credentials automatically
- Provides consistent API for local and remote files

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

    def register_iceberg_table_with_snapshot(
        self,
        table_name: str,
        metadata_location: str,
        view_name: str | None = None
    ) -> str:
        """Register Iceberg table with specific snapshot for querying."""
```

**GizmoSQL/DuckDB Implementation**:
```python
class GizmoDuckDbProfiler:
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        tls_skip_verify: bool = False
    ):
        self._uri = uri
        self._username = username
        self._password = password
        self._tls_skip_verify = tls_skip_verify
        self._connection: dbapi.Connection | None = None

    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        # Uses DuckDB's read_parquet() function
        # Supports multiple files for partitioned datasets
        # Direct filesystem access (no path conversion)

    def profile_single_column(self, view_name: str, column: str, filters: str | None = None) -> ColumnProfile:
        # Executes SQL query for statistics
        # Returns ColumnProfile with min, max, avg, distinct count, nulls

    def register_iceberg_table_with_snapshot(
        self,
        table_name: str,
        metadata_location: str,
        view_name: str | None = None
    ) -> str:
        # Uses DuckDB's iceberg_scan() function
        # Supports snapshot-specific queries
        # Enables performance testing across snapshots
```

**Connection Details**:
- Protocol: gRPC with optional TLS
- Default port: 31337
- Authentication: Username/password
- TLS: Self-signed certificates supported

### IcebergAdapter

**Purpose**: Interface with Iceberg catalogs and tables

**Interface**:
```python
class IcebergAdapter:
    def open_table(self, table_identifier: str, catalog_name: str | None = None) -> TableHandle:
        """Open Iceberg table from catalog."""

    def get_data_files(self, table_identifier: str, catalog_name: str | None = None) -> list[FileRef]:
        """Get data files from Iceberg table."""

    def load_catalog(self, catalog_name: str) -> Catalog:
        """Load PyIceberg catalog by name."""

    def _parse_s3_tables_arn(self, arn: str) -> tuple[str, str] | None:
        """Parse S3 Tables ARN into catalog and table identifier."""
```

**Supported Catalog Types**:
- **SQL Catalog**: Local SQLite-based catalogs
- **Glue Catalog**: AWS Glue Data Catalog
- **REST Catalog**: AWS S3 Tables (managed Iceberg)

**S3 Tables ARN Format**:
```
arn:aws:s3tables:region:account:bucket/bucket-name/table/namespace.table
```

**Key Implementation Details**:
- Uses PyIceberg for catalog access
- Automatic catalog type detection
- S3 Tables ARN parsing and REST catalog configuration
- SigV4 authentication for S3 Tables
- Graceful fallback for missing catalogs

### IcebergMetadataService

**Purpose**: Load and parse Iceberg table metadata

**Interface**:
```python
class IcebergMetadataService:
    def load_table(
        self,
        catalog_name: str | None = None,
        table_identifier: str | None = None,
        metadata_path: str | None = None
    ) -> TableInfo:
        """Load table from catalog or metadata file."""

    def get_snapshots(self, table: Table) -> list[SnapshotInfo]:
        """Get all snapshots from table."""

    def get_snapshot_details(self, table: Table, snapshot_id: int) -> SnapshotDetail:
        """Get detailed information about a snapshot."""
```

**Key Implementation Details**:
- Flexible loading (catalog or direct metadata file)
- Rich snapshot information extraction
- Supports both data and delete files
- Handles S3 and local metadata files

### MORService (Merge-on-Read)

**Purpose**: Analyze merge-on-read overhead in Iceberg tables

**Interface**:
```python
class MORService:
    def calculate_mor_metrics(self, snapshot: Snapshot) -> MORMetrics:
        """Calculate MOR overhead metrics."""

    def get_delete_file_stats(self, snapshot: Snapshot) -> DeleteFileStats:
        """Get statistics about delete files."""

    def calculate_compaction_benefit(self, snapshot: Snapshot) -> CompactionBenefit:
        """Estimate benefit of compaction."""
```

**Metrics Calculated**:
- Delete file count and total size
- Position delete vs equality delete breakdown
- MOR overhead percentage
- Compaction recommendations

### SnapshotTestManager

**Purpose**: Manage Iceberg snapshot registration for performance testing

**Interface**:
```python
class SnapshotTestManager:
    def ensure_snapshot_namespace(self) -> None:
        """Ensure snapshot_tests namespace exists."""

    def register_snapshots(
        self,
        table_name: str,
        snapshot_a: Snapshot,
        snapshot_b: Snapshot
    ) -> tuple[str, str]:
        """Register two snapshots as separate tables for comparison."""

    def cleanup_test_tables(self) -> None:
        """Clean up all test tables in snapshot_tests namespace."""
```

**Key Implementation Details**:
- Uses configured local catalog
- Creates dedicated `snapshot_tests` namespace
- Persists tables across sessions
- Automatic cleanup of test tables

### SnapshotPerformanceAnalyzer

**Purpose**: Execute and compare query performance across snapshots

**Interface**:
```python
class SnapshotPerformanceAnalyzer:
    def run_query_test(self, table_name: str, query: str) -> QueryPerformanceMetrics:
        """Run query against snapshot table and collect metrics."""

    def compare_query_performance(
        self,
        table_a: str,
        table_b: str,
        query: str
    ) -> PerformanceComparison:
        """Compare query performance between two snapshots."""

    def get_predefined_queries(self) -> dict[str, str]:
        """Get predefined query templates."""
```

**Metrics Collected**:
- Execution time
- Files scanned
- Bytes read
- Row count

**Predefined Queries**:
- Full table scan
- Filtered scan
- Aggregation queries
- Join queries (if applicable)

## Adding New Profiling Backends

### Step 1: Implement the Protocol

Create a new file in `src/tablesleuth/services/profiling/`:

```python
# src/tablesleuth/services/profiling/spark_backend.py
from typing import Sequence
from tablesleuth.models.profiling import ColumnProfile
from tablesleuth.services.profiling.base import ProfilingBackend

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
# tablesleuth.toml
[profiling]
backend = "spark"  # or "gizmosql"

[spark]
master = "local[*]"
app_name = "tablesleuth"
```

### Step 3: Update Backend Factory

```python
# src/tablesleuth/services/profiling/__init__.py
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
from tablesleuth.services.profiling.spark_backend import SparkProfiler

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

**Requirements**: Local GizmoSQL server for profiling tests

**Example**:
```python
# tests/test_parquet_profiling_integration.py
@pytest.mark.skipif(not GIZMOSQL_AVAILABLE, reason="TEST_GIZMOSQL_URI not set")
def test_gizmosql_profiling_workflow(test_parquet_file):
    profiler = GizmoDuckDbProfiler(
        uri="grpc+tls://localhost:31337",
        username="gizmosql_username",
        password="gizmosql_password",
        tls_skip_verify=False,
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
import os

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
def gizmosql_config():
    """Get GizmoSQL configuration from environment."""
    uri = os.getenv("TEST_GIZMOSQL_URI", "grpc+tls://localhost:31337")
    username = os.getenv("TEST_GIZMOSQL_USERNAME", "gizmosql_username")
    password = os.getenv("TEST_GIZMOSQL_PASSWORD", "gizmosql_password")

    return {
        "uri": uri,
        "username": username,
        "password": password,
        "tls_skip_verify": True,
    }

@pytest.fixture
def gizmosql_available(gizmosql_config):
    """Check if GizmoSQL server is available."""
    try:
        from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler
        profiler = GizmoDuckDbProfiler(**gizmosql_config)
        # Try a simple query
        profiler._get_connection()
        return True
    except Exception:
        return False

# Skip marker for tests requiring GizmoSQL
requires_gizmosql = pytest.mark.skipif(
    not os.getenv("TEST_GIZMOSQL_URI"),
    reason="TEST_GIZMOSQL_URI not set"
)
```

### Running Tests

**All Tests**:
```bash
pytest
```

**With Coverage**:
```bash
pytest --cov=src/tablesleuth --cov-report=html --cov-report=term-missing
```

**Specific Test Categories**:
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Tests requiring GizmoSQL
pytest -m requires_gizmosql
```

**Specific Test Files**:
```bash
pytest tests/test_parquet_service.py -v
pytest tests/test_snapshot_test_manager.py -v
```

**With GizmoSQL**:
```bash
# Set environment variables
export TEST_GIZMOSQL_URI="grpc+tls://localhost:31337"
export TEST_GIZMOSQL_USERNAME="gizmosql_username"
export TEST_GIZMOSQL_PASSWORD="gizmosql_password"

# Run integration tests
pytest tests/test_parquet_profiling_integration.py -v
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
   cd TableSleuth
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
   pytest --cov=src/tablesleuth --cov-report=html
   ```

6. **Check Code Quality**:
   ```bash
   ruff format .
   ruff check .
   mypy src/tablesleuth
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

## Current Status (v0.4.2)

### Completed Features

1. **Parquet Inspection** ✅
   - File metadata extraction
   - Schema viewing with filtering
   - Row group analysis
   - Column statistics
   - Data sample preview
   - Column profiling via GizmoSQL

2. **Iceberg Support** ✅
   - Snapshot history navigation
   - Delete file inspection
   - Merge-on-read analysis
   - Snapshot comparison
   - Multiple catalog types (SQL, Glue, S3 Tables)
   - S3 Tables ARN support

3. **Performance Testing** ✅
   - Query performance analysis across snapshots
   - Predefined query templates
   - Custom SQL query support
   - Metrics collection (time, files, bytes)

4. **Deployment** ✅
   - Local development setup
   - Automated EC2 deployment
   - GizmoSQL integration
   - S3 and S3 Tables access

### Planned Enhancements

1. **Advanced Snapshot Analysis**
   - Schema evolution visualization
   - Partition evolution tracking
   - Automated compaction recommendations
   - Historical performance trends

2. **Export Capabilities**
   - JSON export for metadata
   - Markdown reports
   - HTML reports with charts
   - CSV export for statistics
   - Performance dashboards

3. **Advanced Filtering**
   - Partition-aware filtering
   - Time-travel queries
   - Custom query builder UI
   - Saved query templates

4. **Query History**
   - Save profiling queries
   - Bookmark files and tables
   - Recent files list
   - Query performance history

5. **Additional Table Formats**
   - Delta Lake support
   - Apache Hudi support
   - Unified table format interface

### Extension Points

**New Table Formats**:
1. Create adapter class (similar to `IcebergAdapter`)
2. Implement file discovery method
3. Integrate with `FileDiscoveryService`
4. Add tests and documentation

**New Profiling Backends**:
1. Implement `ProfilingBackend` protocol
2. Add configuration support
3. Register in backend factory
4. Add integration tests

**New Catalog Types**:
1. Add catalog configuration to PyIceberg
2. Update `IcebergAdapter` to support new type
3. Add authentication handling
4. Test with real catalog

**New Export Formats**:
1. Create exporter class
2. Implement export method
3. Add CLI option
4. Add tests

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
- [Architecture](ARCHITECTURE.md) - System architecture and design patterns
- [User Guide](USER_GUIDE.md) - Complete user documentation
- [Performance Profiling](PERFORMANCE_PROFILING.md) - Performance testing guide
- [EC2 Deployment](EC2_DEPLOYMENT_GUIDE.md) - AWS deployment guide
- [Kiro Specs](.kiro/specs/) - Feature specifications and requirements
