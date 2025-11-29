# Table Sleuth

A powerful Parquet file forensics tool with a terminal user interface (TUI) for inspecting file metadata, analyzing data structure, and profiling column statistics.

## Features

- **File Inspection**: Extract and display comprehensive Parquet file metadata using PyArrow
- **Directory Scanning**: Recursively discover and inspect all Parquet files in a directory
- **Iceberg Support**: Discover data files from Iceberg tables via local catalog or AWS S3 Tables
- **AWS S3 Tables**: Direct ARN-based access to Iceberg tables in AWS S3 Tables service
- **Interactive TUI**: Navigate files, schemas, row groups, and column statistics with keyboard shortcuts
- **Column Profiling**: Profile column data using GizmoSQL (DuckDB over Arrow Flight SQL)
- **Performance Optimized**: Async operations, caching, and lazy loading for responsive UI

## Screenshots

### Iceberg Table Overview
![Iceberg Overview](docs/images/iceberg_overview.png)
*Navigate Iceberg table snapshots, view metadata, and explore table structure*

### Iceberg Performance Testing
![Iceberg Performance](docs/images/iceberg_table_perf_with_menu.png)
*Compare snapshot performance and analyze table evolution*

### Parquet File Schema
![Parquet Schema](docs/images/parquet_table_schema.png)
*Inspect column schemas with detailed type information and statistics*

### Data Sample View
![Data Sample](docs/images/parquet_table_data_sample.png)
*Preview data with column selection and filtering capabilities*

### Row Group Analysis
![Row Groups](docs/images/parquet_table_groups.png)
*Analyze row group distribution and compression statistics*

## Quick Start

```bash
# Install dependencies
uv sync

# Inspect a single file
table-sleuth inspect data/file.parquet

# Inspect a directory
table-sleuth inspect data/warehouse/

# Inspect an Iceberg table (local catalog)
table-sleuth inspect ratebeer.reviews --catalog local

# Inspect an AWS S3 Tables Iceberg table (using ARN)
table-sleuth inspect "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/db.table"

# Or use catalog name
table-sleuth inspect db.table --catalog s3tables
```

See [QUICKSTART.md](QUICKSTART.md) for detailed examples, [TABLESLEUTH_SETUP.md](TABLESLEUTH_SETUP.md) for complete setup instructions, and [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for comprehensive documentation.

## Installation

### Prerequisites

- Python 3.12 or higher
- `uv` for dependency management

### Install from Source

```bash
# Clone the repository
git clone https://github.com/jamesbconner/TableSleuth>
cd table-sleuth

# Install with uv (recommended)
uv sync --all-extras

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### Verify Installation

```bash
table-sleuth --version
```

## Configuration

Create `table_sleuth.toml` in your project directory or `~/.config/table_sleuth.toml`:

```toml
[catalog]
default = "local"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
```

### AWS S3 Configuration

For S3 file access and AWS S3 Tables support, configure AWS credentials and region:

```bash
# Using AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-2  # Or your preferred region
export AWS_DEFAULT_REGION=us-east-2  # Fallback if AWS_REGION not set
```

**Note**: TableSleuth automatically detects the AWS region from:
1. `AWS_REGION` environment variable (highest priority)
2. `AWS_DEFAULT_REGION` environment variable
3. Defaults to `us-east-2` if neither is set

Install PyIceberg with AWS extras:

```bash
pip install "pyiceberg[glue,s3fs]"
```

See [docs/s3_tables_guide.md](docs/s3_tables_guide.md) for detailed AWS S3 Tables configuration
tls_skip_verify = false
```

For Iceberg support, configure PyIceberg in `~/.pyiceberg.yaml`:

```yaml
catalog:
  local:
    type: sql  # Use SQL catalog for local file-based catalogs
    uri: sqlite:////absolute/path/to/warehouse/catalog.db
    warehouse: file:///absolute/path/to/warehouse
```

## Usage

### CLI Commands

```bash
# Show help
table-sleuth --help

# Inspect a file
table-sleuth inspect data/file.parquet

# Inspect with verbose logging
table-sleuth inspect data/file.parquet --verbose

# Inspect Iceberg table
table-sleuth inspect db.table --catalog local
```

### TUI Navigation

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `r` | Refresh and clear caches |
| `f` | Filter columns by name/type |
| `Tab` | Navigate between tabs |
| `↑/↓` | Navigate lists |
| `Enter` | Select file or item |
| `Click` | Click column in Profile view to profile |

### Tabs

1. **File Detail**: File metadata (size, rows, compression)
2. **Schema**: Column names, types, and filtering
3. **Row Groups**: Row group breakdown and statistics
4. **Column Stats**: Column-level statistics from metadata
5. **Profile**: Profiling results from GizmoSQL

## GizmoSQL Setup (Optional)

For column profiling and Iceberg performance testing:

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

### Start Server

```bash
gizmosql_server -P gizmosql_password -Q -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

(Default port is 31337, -Q enables query printing, -T enables TLS with self-signed certs)

### Configure

Update `table_sleuth.toml`:
```toml
[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true
```

See [docs/gizmosql-deployment.md](docs/gizmosql-deployment.md) for detailed setup instructions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Textual TUI Layer                      │
│  File List | File Detail | Schema | Row Groups | Profile    │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                           │
│  Parquet Inspector | Profiling Backend | File Discovery     │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                   External Systems                          │
│  PyArrow | GizmoSQL (DuckDB/ADBC) | PyIceberg               │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
table-sleuth/
├── src/table_sleuth/
│   ├── cli.py                 # CLI entry point
│   ├── config.py              # Configuration management
│   ├── models/                # Data models
│   ├── services/              # Business logic
│   │   ├── parquet_service.py
│   │   ├── file_discovery.py
│   │   └── profiling/
│   └── tui/                   # Terminal UI
│       ├── app.py
│       ├── views/
│       └── widgets/
├── tests/                     # Test suite
├── docs/                      # Documentation
└── .kiro/specs/              # Feature specifications
```

## Development

See [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md) for complete development setup instructions.

### Quick Development Commands

```bash
# Install with dev dependencies
make install-dev

# Run all quality checks
make check

# Run tests with coverage
make test-cov

# Format and lint
make format
make lint
```

## Documentation

### User Documentation
- [Table Sleuth Setup](TABLESLEUTH_SETUP.md) - Complete setup guide for all catalog types
- [Quick Start](QUICKSTART.md) - Get started quickly with examples
- [User Guide](docs/USER_GUIDE.md) - Comprehensive usage guide
- [Performance Profiling](docs/PERFORMANCE_PROFILING.md) - Performance analysis guide

### Developer Documentation
- [Development Setup](DEVELOPMENT_SETUP.md) - Development environment setup
- [EC2 Deployment Guide](docs/EC2_DEPLOYMENT_GUIDE.md) - Automated AWS EC2 deployment
- [Architecture](docs/ARCHITECTURE.md) - System architecture and technical details
- [Developer Guide](docs/DEVELOPER_GUIDE.md) - API reference and contribution guide

## Roadmap

### Current Release (v0.2.x) ✅
- Parquet file inspection (local and S3)
- Directory scanning with recursive discovery
- Iceberg snapshot navigation and analysis
- Delete file inspection and MOR forensics
- Snapshot comparison and diff analysis
- Query performance testing between snapshots
- Column profiling with GizmoSQL
- AWS Glue catalog support
- AWS S3 Tables support
- Interactive TUI with rich visualizations

### Future Enhancements
- Delta Lake and Hudi support
- Schema evolution visualization
- Export capabilities (JSON, CSV reports)
- PySpark profiling backend option
- REST catalog support
- Automated compaction recommendations

## Contributing

Contributions are welcome! Please see the developer documentation in `.kiro/specs/` for architecture details and contribution guidelines.

## License

[Add license information]

## Support

For issues, questions, or feature requests, please open an issue on the repository.
