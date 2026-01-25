# TableSleuth Examples

This directory contains example scripts demonstrating programmatic usage of TableSleuth components for automation and analysis tasks.

## Available Examples

### 1. **inspect_s3_tables.py** - AWS S3 Tables Inspection

Demonstrates inspecting Iceberg tables stored in AWS S3 Tables service using ARN-based references.

```bash
# Test ARN parsing
python resources/examples/inspect_s3_tables.py

# Inspect actual S3 Tables (uncomment function calls in script)
# Requires AWS credentials and S3 Tables permissions
```

**Features:**
- ARN parsing and validation
- Table metadata extraction
- Snapshot analysis
- Data file discovery
- Size and record statistics

---

### 2. **delta_forensics.py** - Delta Lake Forensics

Comprehensive Delta table health analysis and optimization recommendations.

```bash
# Analyze local Delta table
python resources/examples/delta_forensics.py ./data/events/

# Analyze S3 Delta table
python resources/examples/delta_forensics.py s3://bucket/warehouse/events/
```

**Features:**
- File size analysis (small file detection)
- Storage waste analysis (tombstones)
- DML operation patterns
- Rewrite amplification tracking
- Prioritized optimization recommendations

**Prerequisites:** `pip install deltalake`

---

### 3. **iceberg_snapshot_diff.py** - Iceberg Snapshot Comparison

Compare two Iceberg snapshots to understand changes between versions.

```bash
python resources/examples/iceberg_snapshot_diff.py \
  --catalog local \
  --table db.table \
  --from 123 \
  --to 456
```

**Features:**
- File additions/deletions
- Storage size changes
- Record count changes
- Summary metadata comparison
- MOR overhead analysis

**Prerequisites:** Configured `.pyiceberg.yaml` for catalog access

---

### 4. **discover_parquet_files.py** - Parquet File Discovery

Discover and analyze Parquet files from various sources.

```bash
# Discover from local directory
python resources/examples/discover_parquet_files.py --path /data/warehouse

# Discover from S3
python resources/examples/discover_parquet_files.py --path s3://bucket/warehouse/

# Discover from Iceberg table
python resources/examples/discover_parquet_files.py --catalog local --table db.table
```

**Features:**
- Multi-source discovery (local, S3, Iceberg)
- File size distribution analysis
- Partition analysis
- Statistics aggregation

**Prerequisites:** `pip install boto3` (for S3), `pip install pyiceberg` (for Iceberg)

---

### 5. **extract_parquet_metadata.py** - Parquet Metadata Extraction

Extract comprehensive Parquet metadata programmatically without TUI.

```bash
# Extract and display summary
python resources/examples/extract_parquet_metadata.py file.parquet

# Extract as JSON
python resources/examples/extract_parquet_metadata.py file.parquet --output json

# Extract from S3
python resources/examples/extract_parquet_metadata.py s3://bucket/path/file.parquet
```

**Features:**
- Schema extraction
- Row group statistics
- Column statistics (min/max/nulls)
- Compression analysis
- JSON export for automation

**Prerequisites:** `pip install pyarrow`

---

### 6. **batch_table_analysis.py** - Batch Table Analysis

Analyze multiple Iceberg tables and generate a health report.

```bash
python resources/examples/batch_table_analysis.py \
  --catalog local \
  --tables db.table1,db.table2,db.table3
```

**Features:**
- Multi-table analysis
- Health assessment
- MOR overhead tracking
- Small file detection
- Summary statistics
- Prioritized recommendations

**Prerequisites:** Configured `.pyiceberg.yaml` for catalog access

---

## Common Prerequisites

### AWS Credentials (for S3 and Glue)
```bash
# Configure AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-2
```

### PyIceberg Configuration
Create `.pyiceberg.yaml` in your home directory or project root:

```yaml
catalog:
  local:
    type: sql
    uri: sqlite:////path/to/catalog.db
    warehouse: file:///path/to/warehouse

  glue:
    type: glue

  s3tables:
    type: glue
```

See [TABLESLEUTH_SETUP.md](../TABLESLEUTH_SETUP.md) for detailed configuration.

---

## Usage Patterns

### Automation and CI/CD

These scripts can be integrated into data pipelines and CI/CD workflows:

```bash
# Check Delta table health before deployment
python resources/examples/delta_forensics.py s3://bucket/table/ || exit 1

# Validate Parquet file metadata
python resources/examples/extract_parquet_metadata.py file.parquet --output json > metadata.json

# Monitor table health across environments
python resources/examples/batch_table_analysis.py --catalog prod --tables $(cat tables.txt)
```

### Monitoring and Alerting

Use scripts to generate metrics for monitoring systems:

```python
# Example: Extract metrics for Prometheus/Datadog
import json
import subprocess

result = subprocess.run(
    ["python", "resources/examples/delta_forensics.py", "s3://bucket/table/"],
    capture_output=True,
    text=True
)

# Parse output and send to monitoring system
# ...
```

### Data Quality Checks

Integrate into data quality frameworks:

```bash
# Check for small files before processing
python resources/examples/discover_parquet_files.py --path s3://bucket/data/ | grep "Small (<10MB)"

# Verify snapshot consistency
python resources/examples/iceberg_snapshot_diff.py --catalog prod --table db.table --from 100 --to 101
```

---

## Development

### Adding New Examples

When creating new examples:

1. Follow the existing pattern:
   - Clear docstring with usage examples
   - Proper error handling
   - Informative output
   - Command-line argument support

2. Include prerequisites in docstring

3. Add entry to this README

4. Test with various input types (local, S3, etc.)

### Testing Examples

```bash
# Test all examples (requires test data)
for script in resources/examples/*.py; do
    echo "Testing $script..."
    python "$script" --help
done
```

---

## Troubleshooting

### Import Errors

If you get import errors, ensure TableSleuth is installed:

```bash
# Install from source
pip install -e .

# Or install from PyPI
pip install tablesleuth
```

### AWS Credential Errors

Verify AWS credentials are configured:

```bash
aws sts get-caller-identity
```

### Catalog Not Found

Ensure `.pyiceberg.yaml` is configured and in the correct location:

```bash
# Check for config file
ls -la ~/.pyiceberg.yaml
ls -la ./.pyiceberg.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('.pyiceberg.yaml'))"
```

---

## Additional Resources

- [TableSleuth Documentation](../docs/)
- [User Guide](../docs/USER_GUIDE.md)
- [Setup Guide](../TABLESLEUTH_SETUP.md)
- [PyIceberg Documentation](https://py.iceberg.apache.org/)
- [Delta Lake Documentation](https://docs.delta.io/)
