# GizmoSQL Deployment Guide

This guide explains how to deploy GizmoSQL for use with Table Sleuth's column profiling and Iceberg performance testing features.

## Overview

Table Sleuth uses **local GizmoSQL** which runs directly on your machine with direct filesystem access. This provides the best performance and simplest configuration.

## Installation

### macOS (ARM64)

```bash
# Install GizmoSQL to /usr/local/bin
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_arm64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

### macOS (Intel)

```bash
# Install GizmoSQL to /usr/local/bin
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_amd64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

### Linux

```bash
# Install GizmoSQL to /usr/local/bin
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_linux_amd64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

### Verify Installation

```bash
gizmosql_server --version
```

## Configuration

### 1. Configure Table Sleuth

Edit `table_sleuth.toml`:

```toml
[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true
```

**Important**: Do not configure `local_data_path` or `docker_data_path`. These are legacy settings for Docker deployments which are no longer recommended.

### 2. Start GizmoSQL Server

Run GizmoSQL in a terminal window:

```bash
gizmosql_server -P gizmosql_password -Q -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**Options**:
- Default port is 31337
- `-P`: Password for authentication (must match config)
- `-Q`: Print queries for debugging
- `-T`: Enable TLS with certificate and key files

### 3. Verify Connection

```bash
# Check if GizmoSQL is running
curl http://localhost:31337/health

# Or use Table Sleuth to test profiling
table-sleuth inspect data/your-file.parquet
# Navigate to Profile tab and click on a column
```

## Usage

### Parquet Column Profiling

1. Start GizmoSQL server (see above)
2. Open a Parquet file in Table Sleuth
3. Navigate to the "Profile" tab
4. Click on any column name to profile it
5. View statistics including:
   - Row counts and null percentages
   - Distinct values and cardinality
   - Min/max values
   - Numeric statistics (mean, median, quartiles)
   - Mode (most frequent value)

### Iceberg Performance Testing

1. Start GizmoSQL server (see above)
2. Open an Iceberg table in Table Sleuth
3. Navigate to the Iceberg view
4. Select two snapshots to compare
5. Run performance tests with predefined or custom queries
6. View execution time, files scanned, and other metrics

## Troubleshooting

### GizmoSQL Won't Start

**Problem**: `gizmosql_server: command not found`

**Solution**: Ensure GizmoSQL is installed and in your PATH:
```bash
# Check if installed
which gizmosql_server

# If not found, reinstall using the installation commands above
```

**Problem**: Port already in use

**Solution**: Use a different port:
```bash
GIZMOSQL_PASSWORD="gizmosql_password" gizmosql_server --port 10502 --print-queries
```

Then update `table_sleuth.toml`:
```toml
uri = "grpc://localhost:10502"
```

**Problem**: Permission denied when installing

**Solution**: Use sudo for installation:
```bash
curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_arm64.zip \
  | sudo unzip -o -d /usr/local/bin -
```

### Connection Issues

**Problem**: "GizmoSQL connection failed" in Table Sleuth

**Solution**:
1. Verify GizmoSQL is running:
   ```bash
   curl http://localhost:31337/health
   ```

2. Check the password matches in both places:
   - Environment variable: `GIZMOSQL_PASSWORD="gizmosql_password"`
   - Config file: `password = "gizmosql_password"`

3. Verify the port matches:
   - GizmoSQL: `--port 31337`
   - Config: `uri = "grpc+tls://localhost:31337"`

**Problem**: "Profiling backend not available"

**Solution**: This means GizmoSQL isn't running or isn't reachable. Check:
1. GizmoSQL server is running (check terminal window)
2. No firewall blocking port 31337
3. Configuration in `table_sleuth.toml` is correct

### Profiling Issues

**Problem**: Profiling is slow

**Solution**:
- GizmoSQL processes queries in-memory, so large files may take time
- Consider profiling a sample of the data first
- Check GizmoSQL logs (`--print-queries`) to see query execution

**Problem**: "Column not found" error

**Solution**:
- Verify the column name is correct (case-sensitive)
- Check the Parquet file schema in the "Schema" tab
- Some columns may not be profilable (e.g., complex nested types)

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
export TABLE_SLEUTH_GIZMO_URI="grpc+tls://localhost:31337"
export TABLE_SLEUTH_GIZMO_USERNAME="gizmosql_username"
export TABLE_SLEUTH_GIZMO_PASSWORD="gizmosql_password"

# Run Table Sleuth
table-sleuth inspect data/your-file.parquet
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
Environment="GIZMOSQL_PASSWORD=gizmosql_password"
ExecStart=/usr/local/bin/gizmosql_server --port 31337 --print-queries
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
        <string>--port</string>
        <string>31337</string>
        <string>--print-queries</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
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

## Additional Resources

- [GizmoSQL Documentation](https://docs.gizmodata.com/)
- [GizmoSQL GitHub Releases](https://github.com/gizmodata/gizmosql/releases)
- [Table Sleuth Configuration Guide](./configuration.md)

## Quick Reference

### Start GizmoSQL
```bash
GIZMOSQL_PASSWORD="gizmosql_password" gizmosql_server --port 31337 --print-queries
```

### Check Status
```bash
curl http://localhost:31337/health
```

### Stop GizmoSQL
```bash
# Press Ctrl+C in the terminal where it's running
# Or kill the process:
pkill gizmosql_server
```

### View Logs
```bash
# Logs are printed to stdout when using --print-queries
# Redirect to file if needed:
GIZMOSQL_PASSWORD="gizmosql_password" gizmosql_server --port 31337 --print-queries > gizmosql.log 2>&1
```
