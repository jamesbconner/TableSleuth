# Iceberg Metadata Viewer - Examples

This document provides practical examples for using the Iceberg Metadata Viewer.

## Example 1: Basic Snapshot Exploration

### Scenario
You want to explore the snapshot history of an Iceberg table to understand its evolution.

### Steps

```bash
# Launch the viewer
table-sleuth iceberg data/warehouse/orders/metadata/metadata.json
```

**In the viewer:**

1. Browse the snapshot list in the left panel
2. Notice snapshots are sorted by timestamp (newest first)
3. Look for visual indicators:
   - ⚠️ High: Snapshots with >15% delete ratio
   - ⚠️ Med: Snapshots with 5-15% delete ratio
   - ⚠️ Low: Snapshots with <5% delete ratio

4. Select a snapshot to view details
5. Check the Overview tab for:
   - Total records and files
   - Delete ratio and read amplification
   - Compaction recommendations

### Expected Output

```
Snapshot Information
  Snapshot ID: 7914469585847343616
  Parent ID: 3731279082546187264
  Timestamp: 2024-11-15 14:23:45
  Operation: DELETE
  Schema ID: 0

File Statistics
  Data Files: 142
  Delete Files: 23
  Total Size: 2.3 GB

Record Statistics
  Total Records: 2,945,097
  Position Deletes: 441,765
  Equality Deletes: 0

Merge-on-Read Metrics
  Delete Ratio: 15.00%
  Read Amplification: 1.16x
  ⚠️  High MOR overhead - compaction recommended
```

## Example 2: Comparing Snapshots Before and After Compaction

### Scenario
You've run compaction on your table and want to verify the improvement.

### Steps

```bash
# Launch the viewer
table-sleuth iceberg orders --catalog production
```

**In the viewer:**

1. Enable Compare Mode (checkbox in left panel)
2. Select the snapshot before compaction (older, with deletes)
3. Select the snapshot after compaction (newer, without deletes)
4. Click the "Compare" tab

### Expected Output

```
Comparing Snapshots
  Snapshot A: 3731279082546187264 (before compaction)
  Snapshot B: 8821469585847343617 (after compaction)

File Changes
  Data Files Added: 0
  Data Files Removed: 0
  Delete Files Added: 0
  Delete Files Removed: 23

Record Changes
  Records Added: 0
  Records Deleted: 0
  Net Change: 0

Size Changes
  Size Added: 0 B
  Size Removed: 156.8 MB
  Net Change: -156.8 MB

Merge-on-Read Metrics
  Snapshot A Delete Ratio: 15.00%
  Snapshot B Delete Ratio: 0.00%
  Change: -15.00%

  Snapshot A Read Amplification: 1.16x
  Snapshot B Read Amplification: 1.00x
  Change: -0.16x

✓ No compaction needed
```

### Interpretation

- All 23 delete files were removed
- 156.8 MB of delete file overhead eliminated
- Delete ratio dropped from 15% to 0%
- Read amplification improved from 1.16x to 1.00x (optimal)
- Compaction was successful!

## Example 3: Measuring Query Performance Impact

### Scenario
You want to quantify how much delete files are slowing down your queries.

### Prerequisites
- GizmoSQL running and configured
- Two snapshots selected (one with deletes, one without)

### Steps

```bash
# Launch the viewer
table-sleuth iceberg data/warehouse/events/metadata/metadata.json
```

**In the viewer:**

1. Enable Compare Mode
2. Select snapshot without deletes (Snapshot A)
3. Select snapshot with deletes (Snapshot B)
4. Click "Performance Test" tab
5. Select "Full Scan" from the query template dropdown
6. Click "Run Performance Test"

### Expected Output

```
Registered Tables:
  Snapshot A: snapshot_tests.events_snap_3731279082546187264
  Snapshot B: snapshot_tests.events_snap_7914469585847343616

Query
  SELECT * FROM {table}

Execution Time
  events_snap_3731279082546187264: 245.3 ms
  events_snap_7914469585847343616: 367.9 ms
  Delta: +50.0% (red)

Files Scanned
  events_snap_3731279082546187264: 142
  events_snap_7914469585847343616: 165
  Delta: +16.2% (red)

Scan Efficiency
  events_snap_3731279082546187264: 100.0%
  events_snap_7914469585847343616: 85.0%

Analysis
• Query is 50.0% slower on events_snap_7914469585847343616 due to MOR overhead
• 23 additional files must be processed
• Scan efficiency dropped from 100.0% to 85.0%
```

### Interpretation

- Query is 50% slower with delete files
- 23 additional delete files must be read
- 15% of scanned rows are deleted (wasted work)
- **Recommendation**: Run compaction to improve performance

## Example 4: Testing Different Query Patterns

### Scenario
You want to understand how MOR overhead affects different types of queries.

### Predefined Query Templates

#### Full Scan
```sql
SELECT * FROM {table}
```
**Use case**: Measures worst-case MOR overhead (all files must be read)

#### Filtered Scan
```sql
SELECT * FROM {table} WHERE date >= '2024-01-01'
```
**Use case**: Measures overhead with partition pruning

#### Aggregation
```sql
SELECT COUNT(*), AVG(amount), SUM(total) FROM {table}
```
**Use case**: Measures overhead for analytical queries

#### Point Lookup
```sql
SELECT * FROM {table} WHERE id = 12345
```
**Use case**: Measures overhead for selective queries

#### Column Stats
```sql
SELECT MIN(created_at), MAX(created_at) FROM {table}
```
**Use case**: Measures overhead for metadata queries

#### Distinct Count
```sql
SELECT COUNT(DISTINCT user_id) FROM {table}
```
**Use case**: Measures overhead for cardinality queries

### Example Results

| Query Type | Without Deletes | With Deletes | Delta |
|------------|----------------|--------------|-------|
| Full Scan | 245 ms | 368 ms | +50% |
| Filtered Scan | 89 ms | 112 ms | +26% |
| Aggregation | 156 ms | 198 ms | +27% |
| Point Lookup | 12 ms | 15 ms | +25% |
| Column Stats | 45 ms | 52 ms | +16% |
| Distinct Count | 234 ms | 301 ms | +29% |

### Interpretation

- Full scans are most affected by MOR overhead
- Even selective queries show 25% overhead
- Compaction would improve all query types
- Prioritize compaction for workloads with many full scans

## Example 5: Monitoring Table Health Over Time

### Scenario
You want to establish a monitoring routine to catch MOR overhead before it becomes a problem.

### Monitoring Script

```python
#!/usr/bin/env python3
"""Monitor Iceberg table health and alert on high MOR overhead."""

from table_sleuth.services.iceberg_metadata_service import IcebergMetadataService

def check_table_health(metadata_path: str) -> dict:
    """Check table health and return metrics."""
    service = IcebergMetadataService()

    # Load table
    table = service.load_table(metadata_path=metadata_path)

    # Get current snapshot
    snapshots = service.list_snapshots(table)
    current = snapshots[0]

    return {
        "snapshot_id": current.snapshot_id,
        "delete_ratio": current.delete_ratio,
        "read_amplification": current.read_amplification,
        "needs_compaction": current.delete_ratio > 10.0 or current.read_amplification > 1.2,
    }

# Check table
metrics = check_table_health("data/warehouse/orders/metadata/metadata.json")

# Alert if needed
if metrics["needs_compaction"]:
    print(f"⚠️  ALERT: Table needs compaction!")
    print(f"  Delete Ratio: {metrics['delete_ratio']:.1f}%")
    print(f"  Read Amplification: {metrics['read_amplification']:.2f}x")
else:
    print(f"✓ Table health OK")
    print(f"  Delete Ratio: {metrics['delete_ratio']:.1f}%")
    print(f"  Read Amplification: {metrics['read_amplification']:.2f}x")
```

### Monitoring Thresholds

| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| Delete Ratio | <5% | 5-15% | >15% |
| Read Amplification | <1.1x | 1.1-1.3x | >1.3x |
| Action | None | Monitor | Compact |

## Example 6: Validating Compaction Effectiveness

### Scenario
You want to verify that compaction actually improved performance.

### Steps

1. **Before Compaction**: Run performance test
   ```bash
   table-sleuth iceberg orders --catalog production
   # Select current snapshot
   # Note delete ratio and query time
   ```

2. **Run Compaction** (outside Table Sleuth)
   ```sql
   -- Using Spark or other Iceberg engine
   CALL system.rewrite_data_files('orders');
   ```

3. **After Compaction**: Run performance test again
   ```bash
   table-sleuth iceberg orders --catalog production
   # Enable Compare Mode
   # Select before and after snapshots
   # Run same query in Performance Test tab
   ```

### Expected Results

**Before Compaction:**
- Delete Ratio: 15.0%
- Read Amplification: 1.16x
- Query Time: 368 ms
- Files Scanned: 165

**After Compaction:**
- Delete Ratio: 0.0%
- Read Amplification: 1.00x
- Query Time: 245 ms
- Files Scanned: 142

**Improvement:**
- Query Time: -33% (123 ms faster)
- Files Scanned: -14% (23 fewer files)
- Delete Ratio: -15% (eliminated)
- Read Amplification: -0.16x (optimal)

## Example 7: Custom Query Testing

### Scenario
You have a specific query that's running slowly and want to test if MOR overhead is the cause.

### Custom Query Example

```sql
SELECT
    date_trunc('day', order_date) as day,
    COUNT(*) as order_count,
    SUM(total_amount) as total_revenue
FROM {table}
WHERE
    order_date >= '2024-01-01'
    AND status = 'completed'
GROUP BY 1
ORDER BY 1
```

### Steps

1. Launch viewer with two snapshots selected
2. Go to Performance Test tab
3. Paste your custom query in the query input field
4. Ensure `{table}` placeholder is used
5. Click "Run Performance Test"

### Interpreting Results

If the query is significantly slower on the snapshot with deletes:
- MOR overhead is affecting your query
- Consider compaction
- Consider rewriting query to be more selective

If the query shows similar performance:
- MOR overhead is not the bottleneck
- Look for other optimization opportunities
- Partition pruning may be helping

## Example 8: Analyzing Delete File Distribution

### Scenario
You want to understand how delete files are distributed across your data files.

### Steps

1. Select a snapshot with delete files
2. Go to "Deletes" tab
3. Review the summary:

```
Delete Files Summary
  Total Delete Files: 23
  Total Delete Records: 441,765
  Total Delete Size: 156.8 MB

Merge-on-Read Impact
  Delete Ratio: 15.00%
  Read Amplification: 1.16x

⚠️  High delete ratio detected
   Compaction is strongly recommended
```

4. Go to "Files" tab to see individual files
5. Look for patterns:
   - Are deletes concentrated in specific files?
   - Are some partitions more affected?
   - Is the distribution even?

### Interpretation

**Even Distribution:**
- Deletes spread across many files
- Compaction will help all queries
- Schedule full table compaction

**Concentrated Distribution:**
- Deletes in specific partitions/files
- Targeted compaction may be sufficient
- Consider partition-level compaction

## Best Practices Summary

### When to Use Each Feature

| Feature | Use Case | Frequency |
|---------|----------|-----------|
| Snapshot List | Browse history | Daily |
| Overview Tab | Check current health | Daily |
| Compare Tab | Validate compaction | After compaction |
| Performance Test | Quantify overhead | Weekly |
| Deletes Tab | Analyze distribution | Before compaction |

### Recommended Workflow

1. **Daily**: Check current snapshot health
2. **Weekly**: Run performance tests if delete ratio >5%
3. **Before Compaction**: Compare snapshots to identify worst case
4. **After Compaction**: Validate improvement with performance tests
5. **Monthly**: Review snapshot history for trends

### Automation Opportunities

- Script health checks with alerting
- Integrate with compaction scheduling
- Track metrics over time in monitoring system
- Generate reports for capacity planning

## Additional Resources

- [User Guide](./iceberg-viewer-guide.md)
- [Developer Documentation](./iceberg-viewer-dev.md)
- [Apache Iceberg Maintenance](https://iceberg.apache.org/docs/latest/maintenance/)
