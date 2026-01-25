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

For production use with large datasets in S3, deploy to EC2 with pre-configured environment using AWS CDK.

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

3. **Node.js and CDK CLI**:
   ```bash
   npm install -g aws-cdk
   cdk --version
   ```

4. **Your Public IP** for SSH access:
   ```bash
   # Linux/macOS
   curl -s ifconfig.me

   # Windows PowerShell
   Invoke-RestMethod -Uri "https://ifconfig.me/ip"
   ```

### Deploy to AWS EC2

```bash
cd resources/aws-cdk

# Set required environment variables
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
export GIZMOSQL_USERNAME="database-username"
export GIZMOSQL_PASSWORD="secure-password"

# Windows PowerShell:
# $MY_IP = Invoke-RestMethod -Uri "https://ifconfig.me/ip"
# $env:SSH_ALLOWED_CIDR = "$MY_IP/32"
# $env:GIZMOSQL_USERNAME="database-username"
# $env:GIZMOSQL_PASSWORD = "secure-password"

# Bootstrap CDK (first time only)
cdk bootstrap

# Preview deployment
cdk diff -c environment=dev

# Deploy
cdk deploy -c environment=dev
```

**Environment Options:**
- **dev** - t3.small instance (cost-effective for testing)
- **prod** - m4.xlarge instance (stable for production)
- **Custom** - Edit `cdk.json` to add your own environment

The CDK stack will:
- Create VPC, subnet, security group, internet gateway
- Create IAM role with S3 and Glue permissions
- Launch EC2 instance with Python 3.13, GizmoSQL, and TableSleuth
- Generate TLS certificates for GizmoSQL
- Clone TableSleuth repository to `~/Code/TableSleuth`
- Install `tablesleuth` package with `pip install tablesleuth`
- Create `~/tablesleuth.toml` with GizmoSQL configuration
- Start GizmoSQL server as a systemd service

### Retrieve SSH Key

After deployment, retrieve the private key from AWS Parameter Store:

```bash
# Get key pair name from stack outputs
KEY_NAME=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KeyPairName`].OutputValue' \
  --output text)

# Get key pair ID
KEY_ID=$(aws ec2 describe-key-pairs \
  --key-names $KEY_NAME \
  --query 'KeyPairs[0].KeyPairId' \
  --output text)

# Retrieve private key
aws ssm get-parameter \
  --name /ec2/keypair/$KEY_ID \
  --with-decryption \
  --query Parameter.Value \
  --output text > $KEY_NAME.pem

chmod 600 $KEY_NAME.pem
```

### Connect to EC2

```bash
# Get public DNS from stack outputs
PUBLIC_DNS=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicDNS`].OutputValue' \
  --output text)

# SSH into instance
ssh -i $KEY_NAME.pem ec2-user@$PUBLIC_DNS
```

### Configure AWS Credentials on EC2

**Important:** After connecting to the EC2 instance, you must configure AWS credentials so you can access your S3 data and Glue catalogs.

```bash
# Configure AWS credentials
aws configure

# You'll be prompted for:
# AWS Access Key ID: [your-access-key]
# AWS Secret Access Key: [your-secret-key]
# Default region name: [us-east-2]
# Default output format: [json]
```

**Restart GizmoSQL after configuring credentials:**

The GizmoSQL server starts automatically on boot, but it needs AWS credentials to access S3. After running `aws configure`, restart the service:

```bash
# Restart GizmoSQL service
sudo systemctl restart gizmosql

# Verify it's running
sudo systemctl status gizmosql

# Check logs if needed
sudo journalctl -u gizmosql -f
```

### Configure Iceberg Catalogs on EC2

Edit `~/.pyiceberg.yaml` on the EC2 instance to add your Glue catalogs:

```yaml
catalog:
  # Example Glue catalog
  my_catalog:
    type: glue
    region: us-east-2

  # Another Glue catalog
  another_catalog:
    type: glue
    region: us-west-2

  # S3 Tables catalog (if using S3 Tables)
  my_s3tables:
    type: rest
    warehouse: arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket
    uri: https://s3tables.us-east-2.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: us-east-2
```

**Update tablesleuth.toml with your default catalog:**

Edit `~/tablesleuth.toml` and set your default catalog:

```toml
[catalog]
default = "my_catalog"  # Change to your catalog name

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "admin"
password = "your-password"
tls_skip_verify = true
```

**Note:** The `~/tablesleuth.toml` file is automatically created with GizmoSQL configuration during deployment.

### GizmoSQL Server

GizmoSQL server is automatically started as a systemd service during deployment.

**Check status:**
```bash
sudo systemctl status gizmosql
```

**View logs:**
```bash
sudo journalctl -u gizmosql -f
```

**Restart if needed:**
```bash
sudo systemctl restart gizmosql
```

**Manual start (if needed):**
```bash
# Use the pre-configured alias
gizmosvr

# Or run directly
gizmosql_server -U $GIZMOSQL_USERNAME -P $GIZMOSQL_PASSWORD -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**Note on S3 Authentication:** The initialization commands use `credential_chain` which reads AWS credentials from `~/.aws/credentials`, environment variables, or IAM roles. GizmoSQL uses DuckDB under the hood - for alternative S3 authentication methods (static credentials, environment variables, etc.), see the [DuckDB S3 API documentation](https://duckdb.org/docs/stable/core_extensions/httpfs/s3api).

**Initialization Commands Explained:**
- `install aws; load aws;` - AWS extension for S3 access
- `install httpfs; load httpfs;` - HTTPFS extension for HTTP/HTTPS access
- `install iceberg; load iceberg;` - Iceberg extension for Iceberg tables
- `CREATE SECRET (TYPE s3, PROVIDER credential_chain);` - Use AWS credential chain for authentication

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

# Activate virtual environment (if using repository version)
cd ~/Code/TableSleuth
source .venv/bin/activate

# Or just use the installed package directly
# (no venv activation needed)

# Run TableSleuth with your catalog and table
tablesleuth iceberg --catalog my_catalog --table my_database.my_table
```

---

## Basic Usage

### Inspect Parquet Files

```bash
# Single file (local)
tablesleuth parquet data/file.parquet

# Single file (S3)
tablesleuth parquet s3://bucket/path/file.parquet

# Directory (recursive)
tablesleuth parquet data/warehouse/

# Iceberg table from catalog
tablesleuth iceberg --catalog my_catalog --table my_database.my_table

# Iceberg table from metadata file
tablesleuth iceberg /path/to/metadata.json
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
# Using Glue catalog as defined in ~/.pyiceberg.yaml
tablesleuth iceberg --catalog my_catalog --table my_database.my_table

# Using S3 Tables catalog as defined in ~/.pyiceberg.yaml
tablesleuth iceberg --catalog my_s3tables --table my_database.my_table
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
tablesleuth parquet data/file.parquet

# S3 Parquet file
tablesleuth parquet s3://bucket/path/file.parquet

# Iceberg table (Glue catalog)
tablesleuth iceberg --catalog my_catalog --table my_database.my_table

# Iceberg table (S3 Tables)
tablesleuth iceberg --catalog my_s3tables --table my_database.my_table

# Verbose logging
tablesleuth iceberg --catalog my_catalog --table my_database.my_table -v
```
