# Iceberg Metadata Viewer - User Guide

## Overview

The Iceberg Metadata Viewer is a powerful feature in Table Sleuth that enables you to explore Apache Iceberg table metadata, compare snapshots, and measure merge-on-read (MOR) performance degradation. This guide will help you understand when compaction is needed and quantify the performance impact of delete files.

## Getting Started

### Prerequisites

- Table Sleuth installed with PyIceberg support
- Access to an Iceberg table (via metadata file or catalog)
- Optional: GizmoSQL running for performance testing

### Launching the Viewer

There are two ways to launch the Iceberg viewer:

#### 1. From Metadata File

```bash
table-sleuth iceberg /path/to/metadata/metadata.json
```

#### 2. From Catalog

```bash
table-sleuth iceberg database.table --catalog local
```

## Understanding the Interface

The Iceberg viewer has a two-panel layout:

### Left Panel: Snapshot List

- **Snapshot ID**: Unique identifier for each snapshot
- **Timestamp**: When the snapshot was created
- **Operation**: Type of operation (APPEND, DELETE, OVERWRITE, etc.)
- **Records**: Total number of records
- **Files**: Number of data files (and delete files if present)
- **Deletes**: Visual indicator showing MOR overhead level
  - ⚠️ High: >15% delete ratio (compaction strongly recommended)
  - ⚠️ Med: 5-15% delete ratio (consider compaction)
  - ⚠️ Low: <5% delete ratio (acceptable overhead)

### Right Panel: Detail Tabs

#### Overview Tab
Shows summary statistics for the selected snapshot:
- Snapshot metadata (ID, timestamp, operation, parent)
- File statistics (data files, delete files, total size)
- Record statistics (total records, position deletes, equality deletes)
- MOR metrics (delete ratio, read amplification)
- Compaction recommendations

#### Files Tab
Lists all data and delete files in the snapshot:
- File path
- File size
- Record count
- File type (Data or Delete)

#### Schema Tab
Displays the table schema:
- Field ID
- Field name
- Data type
- Required flag
- Documentation

#### Deletes Tab
Analyzes delete files (if present):
- Total delete files and records
- Total delete file size
- MOR impact assessment
- Compaction recommendations

#### Properties Tab
Shows snapshot properties from the summary:
- All key-value pairs from snapshot metadata
- Operation-specific properties

## Comparing Snapshots

### Enabling Compare Mode

1. Click the "Compare Mode" checkbox in the left panel
2. Select exactly 2 snapshots from the list
3. The "Compare" tab will become available

### Compare Tab

The Compare tab shows:

**File Changes:**
- Data files added/removed
- Delete files added/removed

**Record Changes:**
- Records added
- Records deleted
- Net change

**Size Changes:**
- Size added
- Size removed
- Net change

**MOR Metrics:**
- Delete ratio for both snapshots and change
- Read amplification for both snapshots and change
- Compaction recommendation

### Interpreting Results

- **Delete Ratio**: Percentage of records that are deleted
  - <5%: Low overhead, no action needed
  - 5-15%: Medium overhead, consider compaction
  - >15%: High overhead, compaction recommended

- **Read Amplification**: Ratio of total files to data files
  - 1.0x: No delete files, optimal
  - 1.1-1.2x: Low overhead
  - >1.2x: Compaction recommended

## Performance Testing

### Prerequisites

- GizmoSQL must be running and configured
- Two snapshots selected in Compare Mode

### Running a Performance Test

1. Enable Compare Mode and select 2 snapshots
2. Click the "Performance Test" tab
3. Choose a predefined query template or write a custom query
4. Click "Run Performance Test"

### Predefined Query Templates

- **Full Scan**: `SELECT * FROM {table}`
- **Filtered Scan**: `SELECT * FROM {table} WHERE <condition>`
- **Aggregation**: `SELECT COUNT(*), AVG(column) FROM {table}`
- **Point Lookup**: `SELECT * FROM {table} WHERE id = <value>`
- **Column Stats**: `SELECT MIN(col), MAX(col) FROM {table}`
- **Distinct Count**: `SELECT COUNT(DISTINCT col) FROM {table}`

### Understanding Performance Results

The Performance Test tab displays:

**Execution Time:**
- Time for each snapshot
- Delta percentage
- Color-coded (red = slower, green = faster)

**Files Scanned:**
- Number of files read for each snapshot
- Delta percentage
- More files = more MOR overhead

**Scan Efficiency:**
- Percentage of scanned rows that were returned
- Lower efficiency indicates more deleted rows

**Analysis:**
- Automated analysis explaining performance differences
- Recommendations based on results

### Example Interpretation

```
Execution Time:
  Snapshot A: 100.0 ms
  Snapshot B: 150.0 ms
  Delta: +50.0% (red)

Files Scanned:
  Snapshot A: 10
  Snapshot B: 15
  Delta: +50.0% (red)

Analysis:
• Query is 50.0% slower on snap_2 due to MOR overhead
• 5 additional files must be processed
• Scan efficiency dropped from 95.0% to 85.0%
```

This indicates that Snapshot B has significant MOR overhead and would benefit from compaction.

## Key Bindings

- **q**: Quit the viewer
- **r**: Refresh snapshot list
- **c**: Toggle compare mode
- **t**: Run performance test (when available)
- **x**: Cleanup test tables
- **f**: Focus filter input
- **tab**: Next tab
- **shift+tab**: Previous tab
- **escape**: Dismiss notification

## Cleanup

### Manual Cleanup

Click the "Cleanup Test Tables" button to remove registered snapshot tables from the test catalog.

### Automatic Cleanup

- Test tables are automatically cleaned up when exiting Compare Mode
- The test catalog is automatically cleaned up when closing the viewer

## Best Practices

### When to Compare Snapshots

- After delete operations to assess MOR overhead
- Before and after compaction to measure improvement
- When query performance degrades
- Periodically to monitor table health

### When to Run Performance Tests

- When delete ratio exceeds 5%
- When read amplification exceeds 1.2x
- Before scheduling compaction
- To validate compaction effectiveness

### Compaction Guidelines

**Compact when:**
- Delete ratio > 15% (high priority)
- Delete ratio > 10% and query performance is critical
- Read amplification > 1.3x
- Performance tests show >20% degradation

**Consider compacting when:**
- Delete ratio 5-15%
- Read amplification 1.2-1.3x
- Performance tests show 10-20% degradation

**No action needed when:**
- Delete ratio < 5%
- Read amplification < 1.2x
- Performance tests show <10% degradation

## Troubleshooting

### "Metadata file not found"

- Verify the path to the metadata.json file
- Ensure you have read permissions
- Check that the file exists and is not corrupted

### "Failed to load catalog"

- Verify catalog configuration in `.pyiceberg.yaml`
- Check catalog name spelling
- Ensure catalog is accessible

### "Performance testing requires 2 selected snapshots"

- Enable Compare Mode
- Select exactly 2 snapshots
- Ensure both snapshots are successfully registered

### "GizmoSQL not available"

- Verify GizmoSQL is running
- Check connection settings in `table_sleuth.toml`
- Test connection with `table-sleuth inspect` command

### "Snapshot registration failed"

- Check that metadata file is accessible
- Verify snapshot ID exists in the table
- Ensure test catalog has write permissions

## Examples

### Example 1: Assessing MOR Overhead

```bash
# Launch viewer
table-sleuth iceberg data/warehouse/orders/metadata/metadata.json

# In the viewer:
# 1. Browse snapshots in the left panel
# 2. Look for snapshots with delete indicators (⚠️)
# 3. Select a snapshot with deletes
# 4. Check the Overview tab for MOR metrics
# 5. Review the Deletes tab for detailed analysis
```

### Example 2: Comparing Before/After Compaction

```bash
# Launch viewer
table-sleuth iceberg orders --catalog production

# In the viewer:
# 1. Enable Compare Mode
# 2. Select snapshot before compaction
# 3. Select snapshot after compaction
# 4. View Compare tab to see improvements:
#    - Delete files removed
#    - Delete ratio decreased
#    - Read amplification decreased
```

### Example 3: Performance Testing

```bash
# Launch viewer
table-sleuth iceberg data/warehouse/events/metadata/metadata.json

# In the viewer:
# 1. Enable Compare Mode
# 2. Select two snapshots (one with deletes, one without)
# 3. Go to Performance Test tab
# 4. Select "Full Scan" template
# 5. Click "Run Performance Test"
# 6. Review results to quantify MOR overhead
```

## Additional Resources

- [Iceberg Metadata Viewer Design Document](../design.md)
- [Developer Documentation](./iceberg-viewer-dev.md)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [Table Sleuth README](../../README.md)
