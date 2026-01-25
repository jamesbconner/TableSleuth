# Performance Profiling and Snapshot Comparison

**Version**: 0.4.2

## Overview

Table Sleuth provides comprehensive performance profiling capabilities for Apache Iceberg tables, allowing you to:

1. **Measure query performance** across different snapshots
2. **Compare snapshot performance** to understand the impact of table operations
3. **Analyze merge-on-read overhead** from delete files
4. **Make informed compaction decisions** based on actual query metrics

This helps data platform engineers optimize table performance and make data-driven decisions about when to trigger compaction.

## Why Performance Profiling?

While file-level metrics (number of delete files, delete row counts) provide useful indicators, they don't directly tell you how table operations are affecting query performance. Performance profiling measures actual impact by:

1. **Snapshot Comparison**: Running queries against different snapshots to measure performance changes
2. **Metrics Collection**: Capturing execution time, files scanned, bytes read, and row counts
3. **Overhead Analysis**: Calculating the performance impact of merge-on-read operations
4. **Trend Analysis**: Understanding how table evolution affects query performance over time

## Architecture

### Snapshot Registration

Before performance testing, snapshots must be registered as queryable tables:

```
┌─────────────────────────────────────────────────────────────┐
│           SnapshotTestManager                               │
│  - Creates snapshot_tests namespace                         │
│  - Registers snapshots as separate tables                   │
│  - Manages table lifecycle                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           Local PyIceberg Catalog                           │
│  snapshot_tests/                                            │
│    ├── table_name_snapshot_a                                │
│    └── table_name_snapshot_b                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           GizmoDuckDbProfiler                               │
│  - Registers Iceberg tables with DuckDB                     │
│  - Executes queries via iceberg_scan()                      │
│  - Collects performance metrics                             │
└─────────────────────────────────────────────────────────────┘
```

### Performance Models

#### QueryPerformanceMetrics

Captures metrics for a single query execution:

```python
@dataclass
class QueryPerformanceMetrics:
    query: str                      # The SQL query executed
    execution_time_seconds: float   # Total execution time in seconds
    files_scanned: int              # Number of data files scanned
    bytes_read: int                 # Total bytes read from storage
    rows_returned: int              # Rows returned by query
    snapshot_id: int | None         # Snapshot ID queried
```

#### PerformanceComparison

Compares performance between two snapshots:

```python
@dataclass
class PerformanceComparison:
    snapshot_a_metrics: QueryPerformanceMetrics  # Metrics for snapshot A
    snapshot_b_metrics: QueryPerformanceMetrics  # Metrics for snapshot B

    @property
    def time_difference_seconds(self) -> float:
        """Time difference (B - A) in seconds"""

    @property
    def time_difference_percentage(self) -> float:
        """Percentage change in execution time"""

    @property
    def files_difference(self) -> int:
        """Difference in files scanned"""

    @property
    def bytes_difference(self) -> int:
        """Difference in bytes read"""

    @property
    def faster_snapshot(self) -> str:
        """Which snapshot was faster ('A', 'B', or 'Equal')"""
```

## Usage via TUI

### Step 1: Open Iceberg Table

```bash
# Open table from Glue catalog
tablesleuth iceberg --catalog ratebeer --table ratebeer.reviews

# Open table from S3 Tables
tablesleuth iceberg --catalog tpch --table tpch.lineitem

# Open from metadata file
tablesleuth iceberg s3://bucket/warehouse/table/metadata/metadata.json
```

### Step 2: Navigate to Snapshot Comparison

1. Browse snapshots in the main Iceberg view
2. Select two snapshots to compare
3. Press `c` to enter comparison mode
4. View snapshot differences (files, records, schema)

### Step 3: Run Performance Test

1. In comparison view, press `p` to open performance testing
2. Choose a predefined query or enter custom SQL
3. View execution metrics for both snapshots
4. Analyze performance differences

### Predefined Queries

Table Sleuth provides common query templates:

- **Full Table Scan**: `SELECT COUNT(*) FROM {table}`
- **Filtered Scan**: `SELECT COUNT(*) FROM {table} WHERE {condition}`
- **Aggregation**: `SELECT {column}, COUNT(*) FROM {table} GROUP BY {column}`
- **Sample**: `SELECT * FROM {table} LIMIT 1000`

## Usage via API

### Programmatic Performance Testing

```python
from tablesleuth.services.snapshot_test_manager import SnapshotTestManager
from tablesleuth.services.snapshot_performance_analyzer import SnapshotPerformanceAnalyzer
from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler
from pyiceberg.catalog import load_catalog

# Load table and snapshots
catalog = load_catalog("ratebeer")
table = catalog.load_table("ratebeer.reviews")
snapshots = table.snapshots()

snapshot_a = snapshots[-2]  # Previous snapshot
snapshot_b = snapshots[-1]  # Current snapshot

# Initialize services
test_manager = SnapshotTestManager(catalog_name="local")
profiler = GizmoDuckDbProfiler(
    uri="grpc+tls://localhost:31337",
    username="gizmosql_username",
    password="gizmosql_password",
    tls_skip_verify=True
)
analyzer = SnapshotPerformanceAnalyzer(profiler=profiler)

# Register snapshots for testing
table_a, table_b = test_manager.register_snapshots(
    table_name="reviews",
    snapshot_a=snapshot_a,
    snapshot_b=snapshot_b
)

# Run performance comparison
query = "SELECT COUNT(*) FROM {table}"
comparison = analyzer.compare_query_performance(
    table_a=table_a,
    table_b=table_b,
    query=query
)

# Analyze results
print(f"Snapshot A: {comparison.snapshot_a_metrics.execution_time_seconds:.3f}s")
print(f"Snapshot B: {comparison.snapshot_b_metrics.execution_time_seconds:.3f}s")
print(f"Time difference: {comparison.time_difference_seconds:.3f}s ({comparison.time_difference_percentage:.1f}%)")
print(f"Files scanned: {comparison.snapshot_a_metrics.files_scanned} → {comparison.snapshot_b_metrics.files_scanned}")
print(f"Bytes read: {comparison.snapshot_a_metrics.bytes_read} → {comparison.snapshot_b_metrics.bytes_read}")
print(f"Faster snapshot: {comparison.faster_snapshot}")

# Cleanup
test_manager.cleanup_test_tables()
```

## Interpreting Results

### Performance Improvement (Negative Time Difference)

**Snapshot B is faster than Snapshot A**

Possible causes:
- **Compaction**: Table was compacted, reducing file count
- **Partition pruning**: Better partition layout
- **File size optimization**: Larger, more efficient files
- **Delete file cleanup**: Fewer delete files to process

**Action**: Document the improvement and the operation that caused it

### Performance Degradation (Positive Time Difference)

#### Minor Degradation (< 10%)
- Normal variation or minor overhead
- May be due to additional data or delete files
- Monitor trend over time

**Action**: Continue monitoring, no immediate action needed

#### Moderate Degradation (10-50%)
- Noticeable performance impact
- Likely due to accumulating delete files or small files
- Consider compaction if query latency is critical

**Action**:
- Review MOR metrics (delete file count, overhead)
- Plan compaction if trend continues
- Consider query optimization

#### Significant Degradation (50-100%)
- Substantial performance impact
- Strong indicator of table maintenance needed
- May affect user experience

**Action**:
- Review snapshot comparison details
- Check delete file accumulation
- Schedule compaction
- Investigate query patterns

#### Severe Degradation (> 100%)
- Critical performance impact
- Immediate attention required
- May indicate pathological patterns

**Action**:
- Immediate compaction recommended
- Review table write patterns
- Consider partition strategy changes
- Investigate for data quality issues

### Files and Bytes Analysis

**More files scanned but similar time**:
- Files may be cached
- Files may be smaller (better compression)
- Efficient file layout

**Fewer files but slower**:
- Larger files requiring more processing
- Less efficient compression
- Poor partition pruning

**More bytes read**:
- Additional data in snapshot
- Less efficient compression
- Reading unnecessary columns (check query)

**Fewer bytes read but slower**:
- Overhead from delete file processing
- Inefficient file layout
- Small file problem

## Implementation Details

### Snapshot Registration Process

1. **Namespace Creation**: `SnapshotTestManager` ensures `snapshot_tests` namespace exists in local catalog
2. **Table Registration**: Each snapshot is registered as a separate table with metadata pointer
3. **DuckDB Integration**: `GizmoDuckDbProfiler` uses `iceberg_scan()` to query registered tables
4. **Cleanup**: Test tables can be cleaned up after testing

### Query Execution

The profiler executes queries using DuckDB's Iceberg extension:

```sql
-- Register Iceberg table with specific snapshot
CREATE OR REPLACE TABLE snapshot_tests.table_name_snapshot_a AS
SELECT * FROM iceberg_scan('s3://bucket/warehouse/table/metadata/v123.metadata.json');

-- Execute performance test query
SELECT COUNT(*) FROM snapshot_tests.table_name_snapshot_a;
```

### Metrics Collection

Metrics are collected from DuckDB's query execution:

- **Execution Time**: Measured using Python's `time.perf_counter()`
- **Files Scanned**: Extracted from DuckDB query plan or metadata
- **Bytes Read**: Calculated from file sizes in snapshot manifest
- **Rows Returned**: Result of query execution

### Catalog Requirements

Performance testing requires:
- **Local PyIceberg catalog** configured (SQL or REST)
- **Write access** to create tables in `snapshot_tests` namespace
- **GizmoSQL server** running with Iceberg extension loaded

### Measurement Accuracy

Performance measurements are approximate and may vary based on:

**System Factors**:
- Cache state (warm vs. cold cache)
- System load and available resources
- Network latency (for S3 or remote storage)
- Concurrent queries on GizmoSQL server

**Data Factors**:
- File sizes and count
- Compression ratios
- Data distribution
- Partition layout

**Best Practices**:
1. **Run multiple iterations**: Execute queries 3-5 times and average results
2. **Consistent environment**: Use same system state for both snapshots
3. **Cold cache testing**: Restart GizmoSQL server between tests if measuring cold performance
4. **Document conditions**: Record system state, cache status, and concurrent load
5. **Use representative queries**: Test queries that match production workload

### Edge Cases and Safeguards

#### Zero Execution Time

If execution time is 0 seconds (very fast query):
- `time_difference_percentage` may show large variations
- Consider using absolute time difference instead
- May indicate query is too simple for meaningful comparison

#### Equal Performance

If both snapshots have identical execution time:
- `faster_snapshot` returns "Equal"
- `time_difference_percentage` returns 0.0
- Focus on other metrics (files scanned, bytes read)

#### Very Large Percentage Changes

If one snapshot is much slower (e.g., 500% slower):
- Indicates significant performance regression
- Review snapshot comparison for root cause
- Check for data quality issues or schema changes

#### Missing Metrics

If some metrics are unavailable:
- Files scanned may be 0 if not tracked
- Bytes read may be estimated from file sizes
- Rows returned is always available from query result

### Query Selection

Choose representative queries for profiling based on your workload:

#### Full Table Scans
```sql
SELECT COUNT(*) FROM {table}
```
- Tests overall table scan performance
- Sensitive to file count and size
- Good baseline metric

#### Filtered Scans
```sql
SELECT COUNT(*) FROM {table} WHERE date >= '2024-01-01'
```
- Tests partition pruning effectiveness
- Shows impact of data layout
- Reflects common analytical queries

#### Aggregations
```sql
SELECT category, COUNT(*), SUM(amount)
FROM {table}
GROUP BY category
```
- Tests aggregation performance
- Sensitive to data distribution
- Common in reporting queries

#### Point Lookups
```sql
SELECT * FROM {table} WHERE id = 12345
```
- Tests single-row retrieval
- Sensitive to delete file overhead
- Common in operational queries

#### Complex Queries
```sql
SELECT
    date_trunc('day', timestamp) as day,
    category,
    COUNT(*) as count,
    AVG(amount) as avg_amount
FROM {table}
WHERE date >= '2024-01-01'
GROUP BY day, category
ORDER BY day, category
```
- Tests realistic workload
- Combines filtering, aggregation, sorting
- Best for production-like testing

**Tip**: Use queries from your actual workload for most accurate results

## Use Cases

### 1. Compaction Decision Making

**Scenario**: Deciding when to compact a table with accumulating delete files

**Process**:
1. Compare current snapshot with pre-delete snapshot
2. Run representative queries on both
3. Measure performance degradation
4. If degradation > 50%, schedule compaction

**Example**:
```
Snapshot A (before deletes): 2.3s, 150 files, 2.1 GB
Snapshot B (after deletes):  4.1s, 150 files + 45 delete files, 2.1 GB + 50 MB
Degradation: 78% slower
Action: Schedule compaction
```

### 2. Schema Evolution Impact

**Scenario**: Understanding performance impact of schema changes

**Process**:
1. Compare snapshot before and after schema evolution
2. Run queries using both old and new columns
3. Measure any performance changes
4. Validate schema migration success

### 3. Partition Strategy Validation

**Scenario**: Validating a partition strategy change

**Process**:
1. Compare snapshot before and after repartitioning
2. Run filtered queries that benefit from partitioning
3. Measure improvement in file pruning
4. Validate partition strategy effectiveness

### 4. Write Pattern Analysis

**Scenario**: Understanding impact of different write patterns

**Process**:
1. Compare snapshots from different write operations
2. Measure query performance after each write
3. Identify problematic write patterns
4. Optimize write strategy

### 5. Continuous Monitoring

**Scenario**: Tracking table performance over time

**Process**:
1. Regularly test performance on latest snapshot
2. Compare with baseline snapshot
3. Track trends in execution time and resource usage
4. Proactively identify performance degradation

## Troubleshooting

### GizmoSQL Connection Issues

**Problem**: Cannot connect to GizmoSQL server

**Solutions**:
```bash
# Check if server is running
ps aux | grep gizmosql_server

# Test connection
gizmosql_client --command Execute --use-tls --tls-skip-verify \
  --username gizmosql_username --password gizmosql_password "SELECT 1"

# Restart server
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

### Snapshot Registration Fails

**Problem**: Cannot register snapshots for testing

**Solutions**:
- Verify local catalog is configured in `~/.pyiceberg.yaml`
- Check write permissions to catalog database
- Ensure `snapshot_tests` namespace can be created
- Verify metadata files are accessible

### Query Execution Fails

**Problem**: Query fails during performance test

**Solutions**:
- Verify query syntax is valid SQL
- Check that columns exist in table schema
- Ensure GizmoSQL has Iceberg extension loaded
- Verify S3 credentials if using S3 data

### Inconsistent Results

**Problem**: Performance varies significantly between runs

**Solutions**:
- Run multiple iterations and average
- Clear caches between runs
- Ensure no concurrent queries
- Check system load and resources
- Use consistent query patterns

## Future Enhancements

Potential improvements for future versions:

1. **Automatic Query Generation**
   - Generate representative queries based on table schema
   - Detect common query patterns from metadata
   - Create benchmark suites automatically

2. **Historical Tracking**
   - Store performance profiles over time
   - Track trends and identify regressions
   - Visualize performance evolution
   - Alert on significant degradation

3. **Automated Recommendations**
   - Suggest compaction based on overhead thresholds
   - Recommend partition strategy changes
   - Identify problematic write patterns
   - Estimate compaction benefits

4. **Query Plan Analysis**
   - Break down overhead by operation (scan, filter, merge)
   - Identify bottlenecks in query execution
   - Visualize query execution plans
   - Compare plans across snapshots

5. **Multi-Query Benchmarks**
   - Run comprehensive query suites
   - Test different query patterns
   - Generate performance reports
   - Compare against baselines

6. **Cost Estimation**
   - Estimate query cost in terms of I/O
   - Calculate compute resource usage
   - Project costs for different strategies
   - Optimize for cost vs performance

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design
- [USER_GUIDE.md](USER_GUIDE.md) - Complete user documentation
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) - Developer guide and API reference
- [EC2_DEPLOYMENT_GUIDE.md](EC2_DEPLOYMENT_GUIDE.md) - AWS EC2 deployment
- [Snapshot Performance Analyzer](../src/tablesleuth/services/snapshot_performance_analyzer.py) - Source code
- [Snapshot Test Manager](../src/tablesleuth/services/snapshot_test_manager.py) - Source code
- [Performance Models](../src/tablesleuth/models/performance.py) - Data models
