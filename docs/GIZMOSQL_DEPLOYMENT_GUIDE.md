# GizmoSQL Deployment Guide

Complete guide to deploying and configuring GizmoSQL for Table Sleuth column profiling and Iceberg performance testing.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Performance Considerations](#performance-considerations)
- [Security Considerations](#security-considerations)
- [Running as a Service](#running-as-a-background-service)
- [Quick Reference](#quick-reference)

---

## Overview

Table Sleuth uses **local GizmoSQL** (DuckDB over Arrow Flight SQL) for column profiling and performance testing. GizmoSQL runs directly on your machine with direct filesystem access, providing:

- **Fast Performance**: Direct filesystem access, no Docker overhead
- **Simple Configuration**: Single binary, no containers
- **Full Feature Set**: DuckDB with AWS, HTTPFS, and Iceberg extensions
- **S3 Support**: Native S3 access via AWS extension
- **Iceberg Support**: Full Iceberg table support including S3 Tables

**Current Version**: v1.12.13

## Installation

### Prerequisites

- **Operating System**: macOS or Linux
- **Python 3.13+**: For Table Sleuth
- **OpenSSL**: For TLS certificate generation (usually pre-installed)

### Install GizmoSQL

#### macOS (ARM64)

```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_macos_arm64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

#### macOS (Intel)

```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_macos_amd64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

#### Linux

```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_linux_amd64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

### Verify Installation

```bash
# Check version
gizmosql_server --version

# Check help
gizmosql_server --help
```

Expected output: `GizmoSQL Server v1.12.13` or similar

## Configuration

### 1. Generate TLS Certificates

GizmoSQL requires TLS certificates for secure connections:

```bash
# Create certificates directory
mkdir -p ~/.certs

# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout ~/.certs/cert0.key \
  -out ~/.certs/cert0.pem -days 365 -nodes -subj "/CN=localhost"

# Set permissions
chmod 600 ~/.certs/cert0.key
chmod 644 ~/.certs/cert0.pem
```

### 2. Configure Table Sleuth

Create or edit `tablesleuth.toml` in your project root:

```toml
[gizmosql]
# GizmoSQL connection settings for column profiling and Iceberg performance testing
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true  # For self-signed certificates
```

**Configuration Options**:
- `uri`: GizmoSQL server address (default: `grpc+tls://localhost:31337`)
- `username`: Authentication username
- `password`: Authentication password (must match server password)
- `tls_skip_verify`: Skip TLS certificate verification for self-signed certs

### 3. Start GizmoSQL Server

#### Basic Startup

```bash
# Basic startup with AWS/S3/Iceberg support (recommended)
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**Note:** The `-I` initialization commands install and load DuckDB extensions needed for AWS/S3/Glue access. For alternative S3 authentication methods (static credentials, environment variables, etc.), see the [DuckDB S3 API documentation](https://duckdb.org/docs/stable/core_extensions/httpfs/s3api).

#### With S3 Tables Support

```bash
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; \
      load aws; load httpfs; load iceberg; \
      CREATE SECRET (TYPE s3, PROVIDER credential_chain); \
      ATTACH 'arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket' AS tpch (TYPE iceberg, ENDPOINT_TYPE s3_tables);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**Server Options**:
- `-U <username>`: Username for authentication (required)
- `-P <password>`: Password for authentication (required)
- `-Q`: Print queries for debugging (optional)
- `-I <sql>`: Initialization SQL commands (required for S3/Glue access)
- `-T <cert> <key>`: TLS certificate and key files (required)
- Default port: `31337`

**Initialization Commands Explained**:
- `install aws; load aws;` - AWS extension for S3 access and credential management
- `install httpfs; load httpfs;` - HTTPFS extension for HTTP/HTTPS access
- `install iceberg; load iceberg;` - Iceberg extension for Iceberg table support
- `CREATE SECRET (TYPE s3, PROVIDER credential_chain);` - Use AWS credential chain for S3 authentication (reads from ~/.aws/credentials, environment variables, or IAM role)
- `ATTACH '...' AS tpch (...)` - (Optional) Attach S3 Tables bucket as Iceberg catalog

**Alternative S3 Authentication Methods**:

GizmoSQL uses DuckDB under the hood. For alternative S3 authentication options beyond credential_chain, see:
- [DuckDB S3 API Documentation](https://duckdb.org/docs/stable/core_extensions/httpfs/s3api)

Options include:
- Static credentials
- Environment variables
- Config file
- IAM role
- And more

### 4. Verify Connection

#### Test Server Health

```bash
# Check if server is running
ps aux | grep gizmosql_server

# Test with client
gizmosql_client --command Execute --use-tls --tls-skip-verify \
  --username gizmosql_username --password gizmosql_password "SELECT 1"
```

Expected output: `1`

#### Test with Table Sleuth

```bash
# Open a Parquet file
tablesleuth parquet data/your-file.parquet

# Navigate to Profile tab and click on a column
# If profiling works, GizmoSQL is configured correctly
```

## Usage

### Parquet Column Profiling

**Step 1**: Start GizmoSQL server (see Configuration section)

**Step 2**: Open a Parquet file in Table Sleuth
```bash
tablesleuth parquet data/your-file.parquet
```

**Step 3**: Navigate to the "Profile" tab

**Step 4**: Click on any column name to profile it

**Step 5**: View statistics including:
- Row counts and null percentages
- Distinct values and cardinality
- Min/max values
- Data type information
- Value distributions

### Iceberg Performance Testing

**Step 1**: Start GizmoSQL server with Iceberg support

**Step 2**: Open an Iceberg table
```bash
# From Glue catalog
tablesleuth iceberg --catalog ratebeer --table ratebeer.reviews

# From S3 Tables
tablesleuth iceberg --catalog tpch --table tpch.lineitem
```

**Step 3**: Navigate to snapshot comparison view

**Step 4**: Select two snapshots to compare

**Step 5**: Run performance tests
- Choose predefined queries or enter custom SQL
- View execution metrics:
  - Execution time (seconds)
  - Files scanned
  - Bytes read
  - Rows returned

**Step 6**: Analyze results
- Compare performance between snapshots
- Identify performance regressions
- Make compaction decisions

### Advanced Usage

#### Custom Initialization SQL

```bash
# Load additional extensions
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install spatial; load spatial; \
      install json; load json;" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

#### Multiple S3 Tables Attachments

```bash
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; \
      load aws; load httpfs; load iceberg; \
      CREATE SECRET (TYPE s3, PROVIDER credential_chain); \
      ATTACH 'arn:aws:s3tables:us-east-2:123456789012:bucket/bucket1' AS catalog1 (TYPE iceberg, ENDPOINT_TYPE s3_tables); \
      ATTACH 'arn:aws:s3tables:us-east-2:123456789012:bucket/bucket2' AS catalog2 (TYPE iceberg, ENDPOINT_TYPE s3_tables);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

#### Custom Port

```bash
# Use different port
gizmosql_server -U gizmosql_username -P gizmosql_password -Q --port 10502 \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

Update `tablesleuth.toml`:
```toml
[gizmosql]
uri = "grpc+tls://localhost:10502"
```

## Troubleshooting

### Installation Issues

#### Command Not Found

**Problem**: `gizmosql_server: command not found`

**Solutions**:
```bash
# Check if installed
which gizmosql_server

# Check PATH
echo $PATH

# If not found, reinstall
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_macos_arm64.zip \
  | sudo unzip -o -d /usr/local/bin -

# Verify installation
ls -la /usr/local/bin/gizmosql*
```

#### Permission Denied

**Problem**: Permission denied when installing

**Solutions**:
```bash
# Use sudo for installation
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_macos_arm64.zip \
  | sudo unzip -o -d /usr/local/bin -

# Or install to user directory
mkdir -p ~/bin
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_macos_arm64.zip \
  | unzip -o -d ~/bin -

# Add to PATH
export PATH="$HOME/bin:$PATH"
```

### Server Startup Issues

#### Port Already in Use

**Problem**: `Address already in use` error

**Solutions**:
```bash
# Find process using port 31337
lsof -i :31337

# Kill existing process
kill <PID>

# Or use different port
gizmosql_server -U gizmosql_username -P gizmosql_password -Q --port 10502 \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

Update `tablesleuth.toml`:
```toml
[gizmosql]
uri = "grpc+tls://localhost:10502"
```

#### Certificate Issues

**Problem**: TLS certificate errors

**Solutions**:
```bash
# Regenerate certificates
rm -rf ~/.certs
mkdir -p ~/.certs
openssl req -x509 -newkey rsa:4096 -keyout ~/.certs/cert0.key \
  -out ~/.certs/cert0.pem -days 365 -nodes -subj "/CN=localhost"

# Check permissions
chmod 600 ~/.certs/cert0.key
chmod 644 ~/.certs/cert0.pem

# Verify files exist
ls -la ~/.certs/
```

### Connection Issues

#### Connection Failed

**Problem**: "GizmoSQL connection failed" in Table Sleuth

**Solutions**:

1. **Verify server is running**:
   ```bash
   ps aux | grep gizmosql_server
   ```

2. **Test connection**:
   ```bash
   gizmosql_client --command Execute --use-tls --tls-skip-verify \
     --username gizmosql_username --password gizmosql_password "SELECT 1"
   ```

3. **Check password matches**:
   - Server: `-P gizmosql_password`
   - Config: `password = "gizmosql_password"`

4. **Verify port matches**:
   - Server: default `31337` or `--port <number>`
   - Config: `uri = "grpc+tls://localhost:31337"`

5. **Check firewall**:
   ```bash
   # macOS
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

   # Linux
   sudo ufw status
   ```

#### Profiling Backend Not Available

**Problem**: "Profiling backend not available" message

**Solutions**:

1. **Verify GizmoSQL is running**:
   ```bash
   ps aux | grep gizmosql_server
   ```

2. **Check configuration**:
   ```bash
   cat tablesleuth.toml
   ```

3. **Test connection manually**:
   ```bash
   gizmosql_client --command Execute --use-tls --tls-skip-verify \
     --username gizmosql_username --password gizmosql_password "SELECT 1"
   ```

4. **Check logs**:
   - Look at GizmoSQL server output for errors
   - Run with `-Q` flag to see queries

### Profiling Issues

#### Slow Performance

**Problem**: Profiling takes a long time

**Solutions**:
- **Large files**: GizmoSQL loads data into memory
- **Sample data**: Profile a subset first
- **Check query**: Use `-Q` flag to see actual SQL
- **Monitor resources**: Check memory and CPU usage

```bash
# Monitor GizmoSQL process
top -pid $(pgrep gizmosql_server)
```

#### Column Not Found

**Problem**: "Column not found" error

**Solutions**:
- **Check column name**: Case-sensitive, verify in Schema tab
- **Complex types**: Nested columns may not be profilable
- **Special characters**: Columns with spaces or special chars may need quoting

#### Query Timeout

**Problem**: Query times out or hangs

**Solutions**:
```bash
# Restart GizmoSQL server
pkill gizmosql_server
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key

# Check for large files
ls -lh data/*.parquet

# Try simpler query first
# Use Table Sleuth to profile a small column (e.g., ID column)
```

### S3 Access Issues

#### AWS Credentials

**Problem**: Cannot access S3 files

**Solutions**:
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check credentials are available
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY

# Test S3 access
aws s3 ls s3://your-bucket/

# Ensure GizmoSQL has access to credentials
# Credentials are inherited from environment
```

#### S3 Tables Access

**Problem**: Cannot attach S3 Tables

**Solutions**:
```bash
# Verify S3 Tables permissions
aws s3tables list-namespaces --table-bucket-arn <bucket-arn>

# Check IAM permissions include:
# - s3tables:GetTableBucket
# - s3tables:ListNamespaces
# - s3tables:GetTable
# - s3tables:GetTableMetadataLocation

# Test attachment manually
gizmosql_client --command Execute --use-tls --tls-skip-verify \
  --username gizmosql_username --password gizmosql_password \
  "ATTACH 'arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket' AS test (TYPE iceberg, ENDPOINT_TYPE s3_tables);"
```

## Performance Considerations

### Resource Usage

- **Memory**: GizmoSQL loads data into memory for processing
- **CPU**: Query execution is CPU-intensive for large files
- **Disk**: Minimal disk usage (no persistent storage)

### Optimization Tips

1. **Profile smaller files first** to test configuration
2. **Use filters** in queries to reduce data scanned
3. **Close unused GizmoSQL instances** to free resources
4. **Monitor memory usage** with large Parquet files

## Security Considerations

### Authentication

- Always set a strong password via `GIZMOSQL_PASSWORD`
- Password is transmitted over gRPC (not encrypted by default)
- For production use, consider running behind a reverse proxy with TLS

### Network Access

- GizmoSQL listens on localhost by default (127.0.0.1)
- Not accessible from other machines unless explicitly configured
- No authentication required for localhost connections in development

### File Access

- GizmoSQL has full filesystem access (runs as your user)
- Can read any file your user can access
- Be cautious when profiling sensitive data

## Environment Variables

You can override configuration via environment variables:

```bash
# Connection settings
export TABLESLEUTH_GIZMO_URI="grpc+tls://localhost:31337"
export TABLESLEUTH_GIZMO_USERNAME="gizmosql_username"
export TABLESLEUTH_GIZMO_PASSWORD="gizmosql_password"

# Run Table Sleuth
tablesleuth parquet data/your-file.parquet
```

## Running as a Background Service

### Using systemd (Linux)

Create `/etc/systemd/system/gizmosql.service`:

```ini
[Unit]
Description=GizmoSQL Server
After=network.target

[Service]
Type=simple
User=your-username
Environment="GIZMOSQL_USERNAME=gizmosql_username"
Environment="GIZMOSQL_PASSWORD=gizmosql_password"
ExecStart=/usr/local/bin/gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T /home/your-username/.certs/cert0.pem /home/your-username/.certs/cert0.key
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable gizmosql
sudo systemctl start gizmosql
sudo systemctl status gizmosql
```

### Using launchd (macOS)

Create `~/Library/LaunchAgents/com.gizmodata.gizmosql.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gizmodata.gizmosql</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/gizmosql_server</string>
        <string>-U</string>
        <string>gizmosql_username</string>
        <string>-P</string>
        <string>gizmosql_password</string>
        <string>-Q</string>
        <string>-T</string>
        <string>/Users/YOUR_USERNAME/.certs/cert0.pem</string>
        <string>/Users/YOUR_USERNAME/.certs/cert0.key</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>GIZMOSQL_USERNAME</key>
        <string>gizmosql_username</string>
        <key>GIZMOSQL_PASSWORD</key>
        <string>gizmosql_password</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load and start:
```bash
launchctl load ~/Library/LaunchAgents/com.gizmodata.gizmosql.plist
launchctl start com.gizmodata.gizmosql
```

---

## Quick Reference

### Common Commands

**Start GizmoSQL (Basic)**:
```bash
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**Start with S3 Tables**:
```bash
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain); ATTACH 'arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket' AS tpch (TYPE iceberg, ENDPOINT_TYPE s3_tables);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**Check Status**:
```bash
ps aux | grep gizmosql_server
```

**Test Connection**:
```bash
gizmosql_client --command Execute --use-tls --tls-skip-verify \
  --username gizmosql_username --password gizmosql_password "SELECT 1"
```

**Stop GizmoSQL**:
```bash
# Press Ctrl+C in terminal, or:
pkill gizmosql_server
```

**View Logs**:
```bash
# Logs print to stdout with -Q flag
# Redirect to file:
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key > gizmosql.log 2>&1
```

### Configuration Template

**tablesleuth.toml**:
```toml
[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true
```

### Server Options

| Option | Description | Example |
|--------|-------------|---------|
| `-U` | Username (required) | `-U gizmosql_username` |
| `-P` | Password (required) | `-P gizmosql_password` |
| `-Q` | Print queries | `-Q` |
| `-I` | Initialization SQL | `-I "load aws;"` |
| `-T` | TLS cert and key | `-T cert.pem cert.key` |
| `--port` | Port number | `--port 31337` |

### Environment Variables

```bash
# Override configuration
export TABLESLEUTH_GIZMO_URI="grpc+tls://localhost:31337"
export TABLESLEUTH_GIZMO_USERNAME="gizmosql_username"
export TABLESLEUTH_GIZMO_PASSWORD="gizmosql_password"

# AWS credentials (for S3 access)
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_REGION="us-east-2"
```

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [PERFORMANCE_PROFILING.md](PERFORMANCE_PROFILING.md) - Performance testing guide
- [TABLESLEUTH_SETUP.md](../TABLESLEUTH_SETUP.md) - Complete setup guide
- [AWS CDK Deployment](../resources/aws-cdk/README.md) - AWS EC2 deployment with CDK

## External Resources

- [GizmoSQL Documentation](https://docs.gizmodata.com/)
- [GizmoSQL GitHub Releases](https://github.com/gizmodata/gizmosql/releases)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Arrow Flight SQL](https://arrow.apache.org/docs/format/FlightSql.html)
