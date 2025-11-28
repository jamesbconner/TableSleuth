# Table Sleuth Quick Start Guide

Get up and running with Table Sleuth in 5 minutes.

## Installation

```bash
# Clone and install
git clone <repository-url>
cd table-sleuth
uv sync
source .venv/bin/activate
```

## Basic Usage

### 1. Inspect Your First File

```bash
# Inspect a single Parquet file
table-sleuth inspect data/sample.parquet
```

The TUI will launch and automatically display:
- File metadata (size, rows, compression)
- Schema with column types
- Row group information
- Column statistics

### 2. Navigate the Interface

Use these keys to explore:

```
↑/↓     - Navigate through files or lists
Tab     - Switch between tabs
Enter   - Select a file
q       - Quit
```

### 3. Explore File Metadata

**File Detail Tab**: Shows file-level information
```
Path: /data/sample.parquet
Size: 1.2 MB
Rows: 10,000
Row Groups: 2
Compression: SNAPPY
```

**Schema Tab**: Lists all columns
```
Column Name    | Physical Type | Logical Type
---------------|---------------|-------------
id             | INT64         | -
name           | BYTE_ARRAY    | UTF8
created_at     | INT64         | TIMESTAMP_MILLIS
```

**Row Groups Tab**: Shows data distribution
```
Group 0: 5,000 rows | 600 KB
Group 1: 5,000 rows | 600 KB
```

### 4. View Column Statistics

1. Navigate to the **Schema** tab
2. Use arrow keys to select a column
3. Switch to **Column Stats** tab to see:
   - Null count
   - Min/max values
   - Encoding type
   - Compression codec

## Advanced Usage

### Inspect a Directory

Recursively scan all Parquet files:

```bash
table-sleuth inspect data/warehouse/
```

Navigate through the file list with arrow keys and press Enter to inspect each file.

### Profile Column Data (Requires GizmoSQL)

#### Install GizmoSQL

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

#### Start GizmoSQL Server

```bash
gizmosql_server -P gizmosql_password -Q -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

(Default port is 31337, -Q enables query printing, -T enables TLS)

#### Configure Connection

Create `table_sleuth.toml`:

```toml
[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true
```

#### Profile a Column

1. Launch Table Sleuth with a file
2. Navigate to **Profile** tab
3. Click on a column name in the list (or use arrow keys and Enter)
4. View profiling results with statistics:

```
Column: customer_id
Rows: 10,000
Nulls: 0 (0.0%)
Distinct: 5,234 (52.3% cardinality)
Min: 1
Max: 10000
```

### Inspect Iceberg Tables

#### Configure PyIceberg

Create `~/.pyiceberg.yaml`:

```yaml
catalog:
  local:
    type: sql  # Use SQL catalog for local file-based catalogs
    uri: sqlite:////absolute/path/to/warehouse/catalog.db
    warehouse: file:///absolute/path/to/warehouse
```

**Example** for a warehouse at `/Users/you/data/warehouse`:

```yaml
catalog:
  local:
    type: sql
    uri: sqlite:////Users/you/data/warehouse/catalog.db
    warehouse: file:///Users/you/data/warehouse
```

#### Inspect Table Files

```bash
table-sleuth inspect ratebeer.reviews --catalog local
```

All data files from the current snapshot will be loaded for inspection.

**Note**: PyIceberg supports several catalog types:
- `sql` - Local file-based catalog with SQLite
- `rest` - REST catalog server
- `hive` - Hive Metastore
- `glue` - AWS Glue
- See [PyIceberg documentation](https://py.iceberg.apache.org/) for more options

## Common Workflows

### Workflow 1: Quick File Check

```bash
# Launch with file
table-sleuth inspect data/file.parquet

# Check File Detail tab for:
# - File size
# - Row count
# - Compression type

# Press q to quit
```

### Workflow 2: Find Columns by Name

```bash
# Launch with file
table-sleuth inspect data/file.parquet

# Navigate to Schema tab
# Press 'f' to filter
# Type part of column name (e.g., "customer")
# Results update in real-time
# Press Escape to clear filter
```

### Workflow 3: Compare Row Group Sizes

```bash
# Launch with file
table-sleuth inspect data/file.parquet

# Navigate to Row Groups tab
# Review row counts and sizes
# Identify imbalanced row groups
```

### Workflow 4: Analyze Column Distribution

```bash
# Launch with file (GizmoSQL required)
table-sleuth inspect data/file.parquet

# Navigate to Profile tab
# Click on a column name (or use arrow keys and Enter)
# View profiling results:
#   - Null percentage
#   - Distinct count
#   - Cardinality ratio
#   - Min/max values
#   - Quartiles (for numeric columns)
#   - Mode (most frequent value)
```

### Workflow 5: Inspect Partitioned Dataset

```bash
# Launch with directory
table-sleuth inspect data/warehouse/orders/

# File list shows all partitions
# Use arrow keys to navigate
# Press Enter to inspect each partition
# Compare row counts and sizes
# Press 'r' to refresh if files change
```

## Configuration Options

### Minimal Configuration

No configuration needed for basic file inspection.

### Full Configuration

Create `table_sleuth.toml`:

```toml
[catalog]
default = "local"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true
```

### Environment Variables

Override configuration with environment variables:

```bash
export TABLE_SLEUTH_CATALOG_NAME="local"
export TABLE_SLEUTH_GIZMO_URI="grpc+tls://localhost:31337"
export TABLE_SLEUTH_GIZMO_USERNAME="gizmosql_username"
export TABLE_SLEUTH_GIZMO_PASSWORD="gizmosql_password"
```

## Troubleshooting

### File Not Found

```bash
# Verify file exists
ls -lh data/file.parquet

# Check file extension
# Must be .parquet or .pq
```

### No Files in Directory

```bash
# Check for Parquet files
find data/warehouse -name "*.parquet"

# Verify directory path
ls -la data/warehouse/
```

### GizmoSQL Connection Failed

```bash
# Check server is running
curl http://localhost:31337/health

# Check port is accessible
nc -zv localhost 31337

# Restart server if needed
gizmosql_server -P gizmosql_password -Q -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

### Slow Performance

```bash
# Enable verbose logging to diagnose
table-sleuth inspect data/file.parquet --verbose

# Large files may take time to inspect
# Caching is automatic for repeated access
# Press 'r' to refresh and clear caches
```

## Tips and Tricks

1. **Use Filtering**: Press `f` in Schema tab to quickly find columns
2. **Keyboard Navigation**: Learn the keybindings for faster navigation
3. **Cache Awareness**: Metadata is cached automatically for performance
4. **Refresh When Needed**: Press `r` if files change on disk
5. **Profile Selectively**: Profiling can be slow for large files
6. **Check Notifications**: Watch the top of screen for status messages

## Next Steps

- Read the [User Guide](docs/USER_GUIDE.md) for comprehensive documentation
- Explore the [Performance Profiling Guide](docs/PERFORMANCE_PROFILING.md)
- Check the [Technical Specification](docs/technical_specification.md) for architecture details
- Review the [Product Specification](docs/product_specification.md) for feature roadmap

## Example Session

```bash
# Start with a sample file
table-sleuth inspect data/sample.parquet

# TUI launches showing file list
# File is auto-selected and inspected

# Press Tab to navigate tabs:
# - File Detail: See metadata
# - Schema: View columns
# - Row Groups: Check distribution
# - Column Stats: See statistics

# In Schema tab:
# - Use ↑/↓ to select column
# - Press 'f' to filter columns

# In Profile tab:
# - Click column name to profile (if GizmoSQL configured)
# - Or use ↑/↓ and Enter to select column

# Press 'q' to quit
```

## Getting Help

```bash
# Show CLI help
table-sleuth --help

# Show inspect command help
table-sleuth inspect --help

# Show version
table-sleuth --version
```

For more detailed information, see the [User Guide](docs/USER_GUIDE.md).
