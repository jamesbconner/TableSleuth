# Table Sleuth Quick Start Guide

Get up and running with Table Sleuth for Parquet forensics and Iceberg snapshot analysis.

## Table of Contents
- [Local Installation](#local-installation)
- [AWS EC2 Deployment](#aws-ec2-deployment)
- [Basic Usage](#basic-usage)
- [Iceberg Snapshot Analysis](#iceberg-snapshot-analysis)
- [Troubleshooting](#troubleshooting)

---

## Local Installation

### Prerequisites
- Python 3.13+
- `uv` package manager
- AWS credentials (if accessing S3 data)

### Install

```bash
# Clone repository
git clone https://github.com/jamesbconner/TableSleuth.git
cd TableSleuth

# Install dependencies
uv sync --all-extras

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux

# Initialize configuration files
tablesleuth init

# Verify configuration
tablesleuth config-check
```

### Configure AWS Credentials (if using S3)

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-2  # Or your preferred region
```

Or use AWS CLI:
```bash
aws configure
```

### Configure Iceberg Catalogs

The `tablesleuth init` command creates `.pyiceberg.yaml` with example catalogs.
Edit this file (`.pyiceberg.yaml` or `~/.pyiceberg.yaml`) to configure your Iceberg catalogs:

```yaml
catalog:
  # Glue catalog for regular S3 + Iceberg
  dataset1-glue:
    type: glue
    region: us-east-2

  # S3 Tables catalog (managed Iceberg)
  dataset2-s3tables:
    type: rest
    warehouse: arn:aws:s3tables:us-east-2:ACCOUNT:bucket/BUCKET_NAME
    uri: https://s3tables.us-east-2.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: us-east-2
```

**Tip:** Run `tablesleuth config-check` to verify your configuration.

---

## AWS EC2 Deployment

For production use with large datasets in S3, deploy to EC2 with pre-configured environment.

### Prerequisites

1. **AWS Account** with permissions to create:
   - EC2 instances
   - VPC, Subnets, Internet Gateway
   - Security Groups
   - IAM Roles and Instance Profiles
   - Key Pairs

2. **AWS Credentials** configured locally:
   ```bash
   aws sts get-caller-identity  # Verify your account
   ```

3. **Your Public IP** for SSH access:
   ```bash
   curl -4 ifconfig.me
   ```

### Configuration

1. **Clone repository locally**:
   ```bash
   git clone https://github.com/jamesbconner/TableSleuth.git
   cd TableSleuth/resources
   ```

2. **Create deployment config**:
   ```bash
   cp config.json.template config.json
   ```

3. **Edit `config.json`**:
   ```json
   {
     "ssh_allowed_cidr": "YOUR_IP/32", // Limits access to the EC2 Instance
     "gizmosql_username": "gizmosql_username", // Used for creating aliases
     "gizmosql_password": "gizmosql_password", // Used for creating aliases
     "s3tables_bucket_arn": null,  // Optional: only for S3 Tables
     "s3tables_table_arn": null    // Optional: only for S3 Tables
   }
   ```

4. **Update `tablesleuth.toml`** (project root):
   ```toml
   [gizmosql]
   # This config us used by the Table Sleuth service when tasked with performing
   #   a performance test or comparison between snapshots.
   uri = "grpc+tls://localhost:31337"
   username = "gizmosql_username"  # Must match config.json
   password = "gizmosql_password"  # Must match config.json
   tls_skip_verify = true
   ```

### Deploy to EC2

```bash
# Dry run to preview
python tablesleuth_create_env.py --dry-run

# Create environment with default instance (m4.large, On-Demand)
python tablesleuth_create_env.py --region us-east-2

# Create with larger instance for big datasets
python tablesleuth_create_env.py --region us-east-2 --instance-type m4.xlarge

# Use Spot instance (cheaper, may be interrupted)
python tablesleuth_create_env.py --region us-east-2 --use-spot

# Spot instance with specific type
python tablesleuth_create_env.py --region us-east-2 --instance-type m4.2xlarge --use-spot
```

**Instance Type Recommendations:**
- **m4.large** (2 vCPU, 8 GB RAM) - Default, good for small-medium datasets
- **m4.xlarge** (4 vCPU, 16 GB RAM) - Better for larger datasets and complex queries
- **m4.2xlarge** (8 vCPU, 32 GB RAM) - Large datasets with heavy profiling
- **m4.4xlarge** (16 vCPU, 64 GB RAM) - Very large datasets or multiple concurrent analyses

The script will:
- Create VPC, subnet, security group
- Create IAM role with S3 and Glue permissions
- Launch EC2 instance with Python 3.13, GizmoSQL, and TableSleuth
- Generate TLS certificates for GizmoSQL
- Clone and configure TableSleuth

### Connect to EC2

```bash
# SSH into instance (IP shown in script output)
ssh -i ~/.ssh/tablesleuth-key.pem ec2-user@<INSTANCE_IP>
```

### Configure Iceberg Catalogs on EC2

Edit `~/.pyiceberg.yaml` on the EC2 instance:

```yaml
catalog:
  # Glue catalog for regular S3 + Iceberg tables
  dataset1-glue:
    type: glue
    region: us-east-2

  dataset2-glue:
    type: glue
    region: us-east-2

  # S3 Tables catalog (managed Iceberg) - if using S3 Tables
  dataset3-s3tables:
    type: rest
    warehouse: arn:aws:s3tables:us-east-2:835323357340:bucket/dataset3
    uri: https://s3tables.us-east-2.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: us-east-2
```

**Note:** If you configured S3 Tables ARNs in `resources/config.json`, the deployment script automatically creates this configuration for you.

### Start GizmoSQL Server

```bash
# Option 1: Use alias (runs in foreground)
gizmosvr

# Option 2: Background process
nohup gizmosql_server -P gizmosql_password -Q -T ~/.certs/cert0.pem ~/.certs/cert0.key &

# Option 3: In separate tmux window
tmux new-session -d -s gizmo 'gizmosvr'
```

### Configure tmux for Better Colors

Create `~/.tmux.conf`:

```bash
set -g default-terminal "tmux-256color"
set -ga terminal-overrides ",xterm-256color:RGB"
set -ga terminal-overrides ",*:Tc"
```

Then reload: `tmux source-file ~/.tmux.conf`

### Run TableSleuth

```bash
# Start tmux session
tmux

# Activate virtual environment
cd ~/Code/TableSleuth
source .venv/bin/activate

# Ensure dependencies are current
uv sync --all-extras

# Run TableSleuth
table-sleuth iceberg --catalog dataset1 --table dataset1.table1
```

---

## Basic Usage

### Inspect Parquet Files

```bash
# Single file (local)
table-sleuth inspect data/file.parquet

# Single file (S3)
table-sleuth inspect s3://bucket/path/file.parquet

# Directory (recursive)
table-sleuth inspect data/warehouse/

# Iceberg table files
table-sleuth inspect --catalog ratebeer ratebeer.reviews
```

### Navigate the TUI

```
↑/↓     - Navigate lists
Tab     - Switch tabs
Enter   - Select item
q       - Quit
```

### View File Information

**Tabs available:**
- **File Details** - Size, rows, compression, format version
- **Schema** - Column names, types, nullability
- **Row Groups** - Data distribution across row groups
- **Structure** - Column statistics (min/max, null count, encoding)
- **Data Sample** - Preview actual data (select columns, adjust row count)
- **Profile** - Column profiling with GizmoSQL (requires GizmoSQL server)

---

## Iceberg Snapshot Analysis

### View Snapshots

```bash
# Using Glue catalog as defined in the ~/.pyiceberg.yaml
table-sleuth iceberg --catalog dataset1 --table dataset1.table1

# Using S3 Tables catalog as defined in the ~/.pyiceberg.yaml
table-sleuth iceberg --catalog dataset2 --table dataset2.table1
```

### Snapshot Tabs

- **Overview** - Snapshot metadata, operation type, timestamp
- **Files** - Data files in the snapshot
- **Schema** - Table schema at this snapshot
- **Deletes** - Delete files (merge-on-read analysis)
- **Properties** - Snapshot properties
- **Data Sample** - Preview data from snapshot

### Compare Snapshots

1. Press **c** to enable Compare mode
2. Select 2 snapshots using arrow keys (or mouse) + Enter
3. View **Compare** tab to see:
   - File changes (added/removed)
   - Record changes
   - Delete ratio changes
   - Read amplification
   - Compaction recommendations

### Performance Testing

1. Enable Compare mode and select 2 snapshots
2. Switch to **Performance Test** tab
3. Enter a SQL query (use `{table}` placeholder)
4. Press **t** or click "Run Performance Test"
5. View execution time, files scanned, scan efficiency

**Example queries:**
```sql
SELECT COUNT(*) FROM {table}
SELECT * FROM {table} LIMIT 1000
SELECT AVG(price) FROM {table} WHERE year = 2024
```

### Cleanup Test Tables

After performance testing, cleanup temporary tables:

- Press **x** in the TUI
- Or manually via AWS Glue:
  ```bash
  aws glue delete-database --name snapshot_tests --region us-east-2
  ```

---

## Troubleshooting

### TUI Colors Not Working

Ensure tmux is configured:
```bash
echo 'set -g default-terminal "tmux-256color"' >> ~/.tmux.conf
tmux source-file ~/.tmux.conf
```

### GizmoSQL Connection Failed

1. Check server is running:
   ```bash
   ps aux | grep gizmosql_server
   ```

2. Verify credentials match in both files:
   - `tablesleuth.toml`
   - `resources/config.json`

3. Test connection:
   ```bash
   gizmo "SELECT 1"
   ```

### S3 Access Denied

1. Verify AWS credentials:
   ```bash
   aws sts get-caller-identity
   ```

2. Check region matches:
   ```bash
   echo $AWS_REGION
   ```

3. Verify IAM permissions for S3 and Glue

### Snapshot Comparison Shows "UNKNOWN" Operation

This is normal for older snapshots that don't record operation type. TableSleuth infers the operation from file changes.

### Files Scanned Shows 0

This can happen if DuckDB's EXPLAIN ANALYZE doesn't expose file counts. The fallback reads from Iceberg metadata, but may not always be available.

---

## Next Steps

- Read [USER_GUIDE.md](docs/USER_GUIDE.md) for detailed features
- See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- Check [gizmosql-deployment.md](docs/gizmosql-deployment.md) for GizmoSQL setup
- Review [s3_tables_guide.md](docs/s3_tables_guide.md) for S3 Tables configuration

---

## Quick Reference

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| ↑/↓ | Navigate |
| Tab | Switch tabs |
| Enter | Select |
| q | Quit |
| r | Refresh (Iceberg view) |
| c | Toggle Compare mode |
| t | Run performance test |
| x | Cleanup test tables |

### Command Examples

```bash
# Local Parquet file
table-sleuth inspect data/file.parquet

# S3 Parquet file
table-sleuth inspect s3://bucket/path/file.parquet

# Iceberg table (Glue catalog)
table-sleuth iceberg --catalog ratebeer --table ratebeer.reviews

# Iceberg table (S3 Tables)
table-sleuth iceberg --catalog tpch --table tpch.lineitem

# Verbose logging
table-sleuth iceberg --catalog ratebeer --table ratebeer.reviews -v
```
