# Performance Profiling for Merge-on-Read

## Overview

Performance profiling allows Table Sleuth to measure the actual query performance impact of merge-on-read operations in Apache Iceberg tables. This helps data platform engineers make informed decisions about when to trigger table compaction.

## Why Performance Profiling?

While file-level metrics (number of delete files, delete row counts) provide useful indicators, they don't directly tell you how much merge-on-read operations are slowing down your queries. Performance profiling measures the actual overhead by:

1. Running a query **without** applying delete files (base data only)
2. Running the same query **with** delete file application (full merge-on-read)
3. Comparing the execution times to calculate overhead

## Models

### QueryPerformanceProfile

Captures metrics for a single query execution:

```python
@dataclass
class QueryPerformanceProfile:
    query: str                    # The SQL query executed
    execution_time_ms: float      # Total execution time in milliseconds
    rows_scanned: int             # Total rows scanned from data files
    rows_returned: int            # Rows returned after filtering
    delete_files_applied: int     # Number of delete files processed
    data_files_scanned: int       # Number of data files scanned
```

### MergeOnReadPerformance

Compares performance with and without delete application:

```python
@dataclass
class MergeOnReadPerformance:
    with_deletes: QueryPerformanceProfile      # Query with delete application
    without_deletes: QueryPerformanceProfile   # Query without deletes

    @property
    def overhead_ms(self) -> float:
        """Time overhead in milliseconds"""

    @property
    def overhead_percentage(self) -> float:
        """Percentage overhead (0-100+)"""

    @property
    def rows_deleted(self) -> int:
        """Number of rows filtered by delete files"""
```

## Usage Example

```python
from table_sleuth.services.profiling import GizmoDuckDbProfiler
from table_sleuth.models import SnapshotInfo

# Initialize profiler
profiler = GizmoDuckDbProfiler(
    uri="grpc://localhost:31337",
    username="admin",
    password="password"
)

# Profile query performance
performance = profiler.profile_query_performance(
    snapshot=snapshot_info,
    query="SELECT COUNT(*)",
    filters="date > '2024-01-01'"
)

# Analyze results
print(f"Base query time: {performance.without_deletes.execution_time_ms}ms")
print(f"With deletes: {performance.with_deletes.execution_time_ms}ms")
print(f"Overhead: {performance.overhead_ms}ms ({performance.overhead_percentage:.1f}%)")
print(f"Rows deleted: {performance.rows_deleted}")
```

## Interpreting Results

### Low Overhead (< 10%)
- Merge-on-read is not significantly impacting query performance
- Compaction may not be urgent

### Moderate Overhead (10-50%)
- Noticeable performance impact
- Consider compaction if query latency is critical
- Monitor trend over time

### High Overhead (> 50%)
- Significant performance degradation
- Strong candidate for compaction
- May indicate too many small delete files

### Very High Overhead (> 200%)
- Severe performance impact
- Immediate compaction recommended
- May indicate pathological delete patterns

## Implementation Notes

### Backend Support

The `profile_query_performance()` method is optional in the `ProfilingBackend` abstract base class. The default implementation raises `NotImplementedError`. Backends that support performance profiling should override this method.

```python
class ProfilingBackend(ABC):
    def profile_query_performance(
        self,
        snapshot: SnapshotInfo,
        query: str,
        filters: Optional[str] = None,
    ) -> MergeOnReadPerformance:
        """
        Optional method for performance profiling.
        Default implementation raises NotImplementedError.
        Override to add support.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support performance profiling."
        )
```

**Checking for support:**
```python
# Check if backend supports performance profiling
try:
    performance = profiler.profile_query_performance(snapshot, "SELECT COUNT(*)")
    print(f"Overhead: {performance.overhead_percentage:.1f}%")
except NotImplementedError:
    print("Performance profiling not supported by this backend")
```

### Measurement Accuracy

Performance measurements are approximate and may vary based on:
- Cache state (warm vs. cold cache)
- System load
- Network latency (for remote storage)
- Concurrent queries

**Best practices:**
- Run multiple iterations and average results
- Ensure consistent system state between measurements
- Clear caches if measuring cold query performance
- Document measurement conditions

### Edge Case Handling

The performance models include safeguards for edge cases:

**Negative rows deleted:**
If `with_deletes.rows_returned > without_deletes.rows_returned` (which shouldn't happen but could due to timing differences or data changes between measurements), the `rows_deleted` property returns 0 instead of a negative value.

**Zero base time with overhead:**
If the base query time is 0ms but there's overhead (e.g., 0ms → 10ms), `overhead_percentage` returns `float('inf')` to correctly represent infinite percentage overhead, rather than misleadingly returning 0%.

**Both times zero:**
If both query times are 0ms, `overhead_percentage` returns 0.0 (no overhead).

These safeguards ensure that performance metrics are always semantically correct and interpretable.

### Query Selection

Choose representative queries for profiling:
- **Full table scans**: `SELECT COUNT(*)`
- **Filtered queries**: `SELECT COUNT(*) WHERE date > '2024-01-01'`
- **Aggregations**: `SELECT SUM(amount) GROUP BY category`
- **Point lookups**: `SELECT * WHERE id = 12345`

Different query patterns may show different overhead characteristics.

## Future Enhancements

Potential improvements for future versions:

1. **Automatic query generation**: Generate representative queries based on table schema
2. **Historical tracking**: Store performance profiles over time to track trends
3. **Compaction recommendations**: Automatically suggest compaction based on overhead thresholds
4. **Query plan analysis**: Break down overhead by operation (scan, filter, merge)
5. **Multi-query benchmarks**: Run a suite of queries to get comprehensive performance picture
6. **Cost estimation**: Estimate query cost in terms of I/O and compute resources

## Related Documentation

- [Product Specification - Story 6](product_specification.md#story-6---performance-profiling-for-merge-on-read-queries)
- [Profiling Backend Interface](../src/table_sleuth/services/profiling/backend_base.py)
- [Performance Models](../src/table_sleuth/models/performance.py)
- [Performance Tests](../tests/test_performance_models.py)
