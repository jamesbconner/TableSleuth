# Table Sleuth User Guide

## Overview

Table Sleuth is a comprehensive tool for analyzing Parquet files, Apache Iceberg tables, and Delta Lake tables with a powerful terminal user interface (TUI). It provides:

- **Parquet Inspection**: Deep metadata analysis, schema viewing, row group inspection
- **Column Profiling**: Statistical analysis via local GizmoSQL
- **Iceberg Support**: Table browsing, snapshot navigation, and comparison
- **Delta Lake Support**: Version history, forensic analysis, and optimization recommendations
- **Performance Testing**: Measure merge-on-read overhead across snapshots

## Installation

### Prerequisites

- Python 3.12 or higher
- uv for dependency management (recommended)

### Install from Source

```bash
# Clone the repository
git clone <repository-url>
cd TableSleuth

# Install dependencies with uv
uv sync

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
.venv\Scripts\activate     # On Windows
```

### Verify Installation

```bash
tablesleuth --version
```

## Configuration

### Configuration File

Create a `tablesleuth.toml` file in your project directory or `~/.config/tablesleuth.toml`:

```toml
[catalog]
default = "local"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = false
```

### Environment Variables

You can override configuration with environment variables:

```bash
export TABLESLEUTH_CATALOG_NAME="local"
export TABLESLEUTH_GIZMO_URI="grpc+tls://localhost:31337"
export TABLESLEUTH_GIZMO_USERNAME="gizmosql_username"
export TABLESLEUTH_GIZMO_PASSWORD="gizmosql_password"
```

### PyIceberg Configuration (Required for Iceberg Features)

For Iceberg table support, configure PyIceberg in `~/.pyiceberg.yaml`:

```yaml
catalog:
  local:
    type: sql
    uri: sqlite:////absolute/path/to/warehouse/catalog.db
    warehouse: file:///absolute/path/to/warehouse
```

**Note**: Use absolute paths for both `uri` and `warehouse`. The SQL catalog type is required for snapshot management and performance testing.

## CLI Usage

### Basic Commands

```bash
# Show help
tablesleuth --help
tablesleuth parquet --help

# Show version
tablesleuth --version
```

### Inspect a Single File

```bash
tablesleuth parquet data/file.parquet
```

### Inspect a Directory

Recursively scans for all `.parquet` files:

```bash
tablesleuth parquet data/warehouse/
```

### Inspect an Iceberg Table

```bash
tablesleuth iceberg --catalog local --table ratebeer.reviews
```

**Note**: The `iceberg` command has two modes:
- **Catalog mode**: `tablesleuth iceberg --catalog NAME --table TABLE` (requires both options)
- **Metadata file mode**: `tablesleuth iceberg /path/to/metadata.json` (direct path to metadata file)

### Verbose Mode

Enable debug logging:

```bash
tablesleuth parquet data/file.parquet --verbose
```

## TUI Navigation

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Table Sleuth - Parquet File Inspector                       │
├──────────────────┬──────────────────────────────────────────┤
│ Files            │ [File Detail] [Schema] [Row Groups]      │
│ ┌──────────────┐ │ [Column Stats] [Profile]                 │
│ │ file1.parquet│ │                                          │
│ │ file2.parquet│ │ File details, schema, and statistics     │
│ │ file3.parquet│ │ displayed here based on selection        │
│ └──────────────┘ │                                          │
├──────────────────┴──────────────────────────────────────────┤
│ q: Quit | r: Refresh | p: Profile | f: Filter | Tab: Next  │
└─────────────────────────────────────────────────────────────┘
```

### Keybindings

| Key | Action | Description |
|-----|--------|-------------|
| `q` | Quit | Exit the application |
| `r` | Refresh | Reload current file and clear caches |
| `p` | Profile | Profile the selected column (requires GizmoSQL) |
| `f` | Filter | Focus the schema filter input |
| `Tab` | Next Tab | Navigate to next tab or widget |
| `Shift+Tab` | Previous Tab | Navigate to previous tab or widget |
| `Escape` | Dismiss | Dismiss notification |
| `↑/↓` | Navigate | Navigate through lists |
| `Enter` | Select | Select file or row |

### Tabs

1. **File Detail**: Shows file metadata (size, rows, row groups, compression)
2. **Schema**: Lists all columns with types and filtering
3. **Row Groups**: Shows row group breakdown with expandable details
4. **Column Stats**: Displays statistics for selected column
5. **Profile**: Shows profiling results from GizmoSQL

## Common Workflows

### Workflow 1: Inspect a Single File

1. Launch Table Sleuth:
   ```bash
   tablesleuth parquet data/file.parquet
   ```

2. The file will be automatically selected and inspected

3. Navigate tabs to view:
   - File details (size, rows, compression)
   - Schema (column names and types)
   - Row groups (data distribution)

4. Select a column in the Schema tab (use arrow keys)

5. View column statistics in the Column Stats tab

### Workflow 2: Explore a Directory

1. Launch with directory:
   ```bash
   tablesleuth parquet data/warehouse/
   ```

2. Use arrow keys to navigate the file list

3. Press `Enter` to select a file

4. Explore the file using tabs

5. Select another file to compare

### Workflow 3: Profile Column Data

1. Select a file from the list

2. Navigate to the Schema tab

3. Select a column with arrow keys

4. Press `p` to profile the column

5. View results in the Profile tab:
   - Row count
   - Null count and percentage
   - Distinct count and cardinality
   - Min/max values

### Workflow 4: Filter Columns

1. Navigate to the Schema tab

2. Press `f` to focus the filter input

3. Type part of a column name or type

4. Results update in real-time

5. Press `Escape` to clear focus

### Workflow 5: Inspect Iceberg Table

1. Configure PyIceberg (see Configuration section)

2. Launch with table identifier:
   ```bash
   tablesleuth iceberg ratebeer.reviews --catalog local
   ```

3. Navigate to the **Iceberg** tab to see:
   - Table metadata
   - Current snapshot information
   - Snapshot history

4. Browse snapshots and view details

5. All data files from the current snapshot are available in the File List

### Workflow 6: Compare Iceberg Snapshots

1. Open an Iceberg table

2. Navigate to the **Iceberg** tab

3. Press `c` to enter Compare mode

4. Select two snapshots to compare:
   - Use arrow keys to navigate
   - Press `Enter` to select first snapshot
   - Press `Enter` again to select second snapshot

5. View comparison metrics:
   - File count changes
   - Data size changes
   - Merge-on-read metrics (data files, delete files, positional deletes)

6. Press `Escape` to exit Compare mode

### Workflow 7: Test Snapshot Performance

1. In Compare mode with two snapshots selected

2. Press `t` to run a performance test

3. Choose a query template or enter custom SQL

4. View performance comparison:
   - Execution time for each snapshot
   - Files scanned
   - Bytes read
   - Performance difference percentage

5. Analyze merge-on-read overhead

## GizmoSQL Setup for Profiling

GizmoSQL is a DuckDB instance exposed via Arrow Flight SQL that enables fast column profiling and Iceberg performance testing. It runs as a local process with direct filesystem access.

### Installation

**macOS (ARM64):**
```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_arm64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

**macOS (Intel):**
```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_amd64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

**Linux:**
```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_linux_amd64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

### Start GizmoSQL Server

Run in a terminal window:

```bash
GIZMOSQL_PASSWORD="gizmosql_password" gizmosql_server --port 31337 --print-queries
```

### Configure Connection

Create or update `tablesleuth.toml`:

```toml
[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = false
```

Or use environment variables:

```bash
export TABLESLEUTH_GIZMO_URI="grpc+tls://localhost:31337"
export TABLESLEUTH_GIZMO_USERNAME="gizmosql_username"
export TABLESLEUTH_GIZMO_PASSWORD="gizmosql_password"
```

### Test Connection

1. Launch Table Sleuth with a file:
   ```bash
   tablesleuth parquet data/sample.parquet
   ```

2. Navigate to Schema tab and select a column

3. Press `p` to profile

4. Check results:
   - **Success**: Results appear in Profile tab
   - **Failure**: Error notification appears at top of screen

### Troubleshooting GizmoSQL

**Server Not Running:**
```bash
# Check if GizmoSQL is running
curl http://localhost:31337/health

# If not running, start it:
GIZMOSQL_PASSWORD="gizmosql_password" gizmosql_server --port 31337 --print-queries
```

**Connection Refused:**
```bash
# Check port is accessible
nc -zv localhost 31337

# Check firewall settings
# Ensure port 31337 is not blocked
```

**Authentication Failed:**
```bash
# Verify credentials in configuration
cat tablesleuth.toml

# Check environment variables
env | grep TABLESLEUTH_GIZMO

# Verify password matches in both places
echo $GIZMOSQL_PASSWORD
```

### Advanced GizmoSQL Configuration

**Custom Port:**
```bash
GIZMOSQL_PASSWORD="gizmosql_password" gizmosql_server --port 10502 --print-queries
```

Update configuration:
```toml
[gizmosql]
uri = "grpc://localhost:10502"
```

**Remote GizmoSQL:**
```toml
[gizmosql]
uri = "grpc://gizmosql.example.com:31337"
username = "your_username"
password = "your_password"
tls_skip_verify = false
```

## Iceberg Features

### Snapshot Navigation

**View Snapshot History:**
1. Open an Iceberg table
2. Navigate to the **Iceberg** tab
3. View list of all snapshots with:
   - Snapshot ID
   - Timestamp
   - Operation (append, delete, replace, overwrite)
   - Summary statistics

**View Snapshot Details:**
1. Select a snapshot from the list
2. Press `Enter` to view details:
   - Manifest files
   - Data files count
   - Delete files count
   - Total data size
   - Schema information

### Snapshot Comparison

**Compare Two Snapshots:**
1. Press `c` in the Iceberg tab to enter Compare mode
2. Select two snapshots to compare
3. View metrics:
   - **File Changes**: Added/removed data files
   - **Size Changes**: Data size difference
   - **MOR Metrics**: Merge-on-read overhead
     - Data files vs delete files ratio
     - Positional delete count
     - Equality delete count

**Merge-on-Read Analysis:**
- **Low MOR**: Few delete files, good query performance
- **High MOR**: Many delete files, consider compaction
- **Metrics Tracked**:
  - Delete files percentage
  - Positional deletes per data file
  - Total delete file size

### Performance Testing

**Run Query Tests:**
1. In Compare mode with two snapshots selected
2. Press `t` to open performance test dialog
3. Choose from predefined queries:
   - `full_scan`: Full table scan
   - `filtered_scan`: Filtered query
   - `aggregation`: Aggregation query
   - `sample_rows`: Sample data retrieval
   - `table_stats`: Basic statistics
4. Or enter custom SQL query
5. View results:
   - Execution time for each snapshot
   - Files scanned
   - Bytes read
   - Rows returned
   - Performance difference (%)

**Query Templates:**
- Templates use `{table}` placeholder
- Automatically substituted with snapshot-specific table reference
- Custom queries supported with same placeholder syntax

**Use Cases:**
- Measure compaction impact
- Quantify merge-on-read overhead
- Compare query performance before/after operations
- Identify when compaction is needed

### Iceberg Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `c` | Enter/exit Compare mode |
| `t` | Run performance test (in Compare mode) |
| `Enter` | Select snapshot or view details |
| `Escape` | Exit Compare mode or close dialogs |
| `↑/↓` | Navigate snapshot list |
| `Tab` | Switch between panels |

## Delta Lake Features

### Version History and Time Travel

Navigate through Delta table versions to understand table evolution:

```bash
# Inspect latest version
tablesleuth delta path/to/delta/table

# Time travel to specific version
tablesleuth delta path/to/delta/table --version 5

# Inspect S3-based Delta table
tablesleuth delta s3://bucket/path/to/delta/table
```

### Delta Lake TUI Interface

The Delta Lake viewer provides a comprehensive interface with multiple panels and tabs:

**Left Panel: Version History**
- Lists all table versions (most recent first)
- Shows timestamp, operation type, file count, and record count
- Select any version to view details
- Compare mode checkbox for version comparison

**Right Panel: Tabbed Views**

1. **Overview Tab**
   - Version number and timestamp
   - Operation type (WRITE, MERGE, UPDATE, DELETE, OPTIMIZE, VACUUM)
   - Data file count and total size
   - Total record count
   - Operation-specific metrics (rows affected, bytes written, etc.)

2. **Files Tab**
   - List of all data files in the selected version
   - File path, size, record count, and partition values
   - Sortable columns for analysis
   - Identify large files or partition skew

3. **Schema Tab**
   - Complete table schema at the selected version
   - Column names and data types
   - Track schema evolution across versions
   - Identify schema changes

4. **Data Sample Tab**
   - Preview data from the first file in the version
   - View actual column values
   - Inspect data quality
   - Verify schema interpretation

5. **Forensics Tab**
   - **File Size Distribution**: Histogram showing file size buckets
   - **Small File Analysis**: Count and percentage of files <10MB
   - **Storage Waste**: Active vs tombstoned files, reclaimable storage
   - **Checkpoint Health**: Status, log tail length, issues and recommendations

6. **Recommendations Tab**
   - Prioritized optimization recommendations (High/Medium/Low)
   - OPTIMIZE recommendations for small files
   - VACUUM recommendations for storage waste
   - ZORDER recommendations for degraded clustering
   - CHECKPOINT recommendations for log tail issues
   - Each recommendation includes reason, impact, and command

7. **Compare Tab** (enabled in Compare Mode)
   - Side-by-side comparison of two selected versions
   - File count changes
   - Record count changes
   - Size changes (bytes added/removed)
   - Delta calculations

### Version Comparison

Compare any two versions to understand changes:

1. Press `c` to enable Compare Mode
2. Select first version with Enter
3. Select second version with Enter
4. View comparison in the Compare tab:
   - File changes (added/removed)
   - Record changes (net delta)
   - Size changes (storage impact)

### Forensic Analysis Capabilities

Delta Lake forensics provides deep insights into table health:

**File Size Analysis**
- Identify small file problems (<10MB)
- Calculate file size distribution histogram
- Estimate benefits of OPTIMIZE operations
- Get recommendations for file consolidation

**Storage Waste Analysis**
- Track tombstoned (deleted) files
- Calculate reclaimable storage beyond retention period
- Monitor storage waste percentage
- Get VACUUM recommendations with retention periods

**Checkpoint Health**
- Monitor transaction log health
- Track log tail length (JSON files since last checkpoint)
- Identify checkpoint issues (missing, corrupted, or stale)
- Get proactive maintenance recommendations

**Optimization Recommendations**
- Automatically generated based on forensic analysis
- Prioritized by impact (High/Medium/Low)
- Includes estimated benefits and specific commands
- Covers OPTIMIZE, VACUUM, ZORDER, and CHECKPOINT operations

### Delta Lake Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Select version to view details |
| `c` | Toggle Compare Mode |
| `Escape` | Dismiss notifications |
| `↑/↓` | Navigate version list |
| `Tab` | Switch between tabs |
| `r` | Refresh table metadata and analysis |
| `q` | Quit the viewer |

## Troubleshooting

### "File not found" Error

- Verify the file path is correct
- Check file permissions
- Ensure file has `.parquet` or `.pq` extension

### "Invalid Parquet file" Error

- File may be corrupted
- File may not be a valid Parquet file
- Try opening with another tool to verify

### "Profiling backend not available" Error

- GizmoSQL server is not running
- Check connection settings in configuration
- Verify network connectivity to GizmoSQL
- Ensure password matches in both server and config

### No Files Found in Directory

- Directory may not contain Parquet files
- Check file extensions (`.parquet` or `.pq`)
- Verify directory path is correct

### Slow Performance

- Large files may take time to inspect
- Use caching (automatic) for repeated access
- Press `r` to refresh and clear caches if needed

## Tips and Best Practices

1. **Use Filtering**: Press `f` in Schema tab to quickly find columns
2. **Cache Awareness**: File metadata is cached automatically
3. **Refresh When Needed**: Press `r` if file has changed on disk
4. **Profile Selectively**: Profiling queries can be slow for large files
5. **Check Notifications**: Watch top of screen for status messages

## Current Limitations

- **Read-only**: No write operations (safe for production)
- **No data preview**: Metadata analysis only (no actual data displayed)
- **Profiling requires GizmoSQL**: Column profiling needs local GizmoSQL server
- **Iceberg features**:
  - ✅ Snapshot navigation and comparison
  - ✅ Performance testing across snapshots
  - ✅ Merge-on-read analysis
  - ❌ Schema evolution tracking (planned)
  - ❌ Partition evolution analysis (planned)

## Real-World Examples

### Example 1: Investigating File Size Issues

**Scenario**: Your Parquet files are larger than expected.

```bash
# Inspect the file
tablesleuth parquet data/large_file.parquet
```

**What to check:**
1. **File Detail Tab**: Check compression codec
   - SNAPPY: Fast but larger files
   - GZIP: Slower but better compression
   - ZSTD: Good balance

2. **Row Groups Tab**: Check row group sizes
   - Too many small row groups = overhead
   - Optimal: 100MB-1GB per row group

3. **Column Stats Tab**: Check encoding types
   - PLAIN: No compression
   - DICTIONARY: Good for low cardinality
   - RLE: Good for repeated values

**Action**: If using PLAIN encoding with high cardinality, consider re-encoding with dictionary compression.

### Example 2: Analyzing Partitioned Datasets

**Scenario**: You have a partitioned dataset and want to understand data distribution.

```bash
# Inspect the partition directory
tablesleuth parquet data/warehouse/orders/
```

**What to check:**
1. **File List**: Review file sizes and row counts
   - Look for imbalanced partitions
   - Identify small files (< 10MB)
   - Identify large files (> 1GB)

2. **Aggregate Statistics**: Check total rows and size
   - Verify expected data volume
   - Calculate average file size

3. **Individual Files**: Inspect outliers
   - Select small files to understand why
   - Select large files to check row groups

**Action**: Consider repartitioning if you have many small files or very large files.

### Example 3: Validating Data Quality

**Scenario**: You want to check for null values and data ranges.

```bash
# Inspect with profiling
tablesleuth parquet data/customer_data.parquet
```

**What to check:**
1. **Column Stats Tab**: Check null counts from metadata
   - Quick overview without profiling
   - May not be available for all types

2. **Profile Tab**: Profile critical columns
   - Press `p` on each column
   - Check null percentage
   - Verify min/max ranges
   - Check distinct counts

**Example checks:**
- `customer_id`: Should have 0 nulls, high distinct count
- `email`: Should have low null percentage
- `age`: Should be in reasonable range (e.g., 18-120)
- `country_code`: Should have low distinct count

**Action**: Document any data quality issues found.

### Example 4: Comparing Schema Evolution

**Scenario**: You have multiple versions of a file and want to compare schemas.

```bash
# Inspect old version
tablesleuth parquet data/v1/customers.parquet
# Note columns in Schema tab

# Quit and inspect new version
tablesleuth parquet data/v2/customers.parquet
# Compare columns in Schema tab
```

**What to check:**
1. **Schema Tab**: Compare column lists
   - New columns added?
   - Columns removed?
   - Type changes?

2. **Column Stats**: Compare statistics
   - Data range changes?
   - Null count changes?

**Action**: Document schema changes for migration planning.

### Example 5: Investigating Query Performance

**Scenario**: Queries on your Parquet files are slow.

```bash
# Inspect the file
tablesleuth parquet data/slow_query_table.parquet
```

**What to check:**
1. **Row Groups Tab**: Check row group count
   - Too many row groups = more metadata overhead
   - Too few row groups = less parallelism

2. **Column Stats Tab**: Check encoding and compression
   - Inefficient encoding = slower reads
   - No compression = more I/O

3. **Profile Tab**: Check cardinality of filter columns
   - Low cardinality = good for filtering
   - High cardinality = consider indexing

**Action**: Optimize file layout based on query patterns.

### Example 6: Iceberg Table Investigation

**Scenario**: You want to understand the physical files behind an Iceberg table.

```bash
# Configure PyIceberg first
cat > ~/.pyiceberg.yaml << EOF
catalog:
  local:
    type: file
    warehouse: "file:///path/to/warehouse"
EOF

# Inspect table
tablesleuth iceberg ratebeer.reviews --catalog local
```

**What to check:**
1. **File List**: See all data files in current snapshot
   - Number of files
   - File size distribution
   - Total data size

2. **Individual Files**: Inspect file structure
   - Row group organization
   - Compression settings
   - Schema consistency

**Action**: Identify opportunities for compaction or optimization.

## Performance Tips

### Optimizing Inspection Speed

1. **Use Caching**: Metadata is cached automatically
   - First inspection: Slower (reads metadata)
   - Subsequent inspections: Faster (uses cache)
   - Press `r` to refresh and clear cache

2. **Lazy Loading**: Only inspect what you need
   - File list loads immediately
   - File details load on selection
   - Row groups load on tab view

3. **Async Operations**: UI stays responsive
   - Loading indicators show progress
   - Can navigate while loading
   - Cancel operations with `Escape`

### Optimizing Profiling Speed

1. **Profile Selectively**: Don't profile all columns
   - Focus on key columns
   - Skip large text columns
   - Profile numeric columns first

2. **Use Filters**: Reduce data volume
   - Profile subsets of data
   - Use WHERE clauses (future feature)

3. **Check Metadata First**: Use Column Stats before profiling
   - Metadata is instant
   - Profiling requires query execution
   - Only profile when metadata insufficient

## Integration with Other Tools

### Integration with Data Pipelines

```python
# Python integration (future API)
from tablesleuth import ParquetInspector

inspector = ParquetInspector()
info = inspector.inspect_file("data/file.parquet")

if info.num_rows == 0:
    raise ValueError("Empty file detected")

if info.file_size_bytes > 1_000_000_000:
    print("Warning: Large file detected")
```

## Keyboard Shortcuts Reference

### Global Shortcuts

| Key | Action | Context |
|-----|--------|---------|
| `q` | Quit | Anywhere |
| `Ctrl+C` | Force quit | Anywhere |
| `Escape` | Dismiss notification | When notification shown |
| `Tab` | Next tab/widget | Anywhere |
| `Shift+Tab` | Previous tab/widget | Anywhere |

### File List Shortcuts

| Key | Action |
|-----|--------|
| `↑` | Previous file |
| `↓` | Next file |
| `Enter` | Select file |
| `Home` | First file |
| `End` | Last file |
| `Page Up` | Scroll up |
| `Page Down` | Scroll down |

### Schema Tab Shortcuts

| Key | Action |
|-----|--------|
| `f` | Focus filter input |
| `↑/↓` | Navigate columns |
| `Enter` | Select column |
| `p` | Profile selected column |

### Row Groups Tab Shortcuts

| Key | Action |
|-----|--------|
| `↑/↓` | Navigate row groups |
| `Enter` | Expand/collapse details |

### Application Shortcuts

| Key | Action |
|-----|--------|
| `r` | Refresh current file |
| `?` | Show help (future) |
| `/` | Search (future) |

## Next Steps

- See [QUICKSTART.md](../QUICKSTART.md) for quick examples
- See [PERFORMANCE_PROFILING.md](PERFORMANCE_PROFILING.md) for performance analysis
- See [CHANGELOG.md](../CHANGELOG.md) for version history
- See [ARCHITECTURE.md](ARCHITECTURE.md) for system architecture and design
- See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for developer documentation
- See `.kiro/specs/` for detailed feature specifications
