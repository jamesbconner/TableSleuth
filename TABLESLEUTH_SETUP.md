# Table Sleuth Setup Guide

Complete setup guide for Table Sleuth with different catalog configurations and deployment options.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Catalog Configuration](#catalog-configuration)
- [GizmoSQL Setup](#gizmosql-setup)
- [AWS EC2 Production Setup](#aws-ec2-production-setup)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **Python 3.13+** (required for latest features)
- **uv** package manager (`pip install uv`)
- **Git** for repository cloning
- **tmux** for proper TUI color support
- **AWS CLI** (if using AWS services)

### AWS Requirements (if using AWS)
- AWS account with appropriate permissions
- AWS credentials configured
- Access to S3 buckets containing Iceberg data
- Glue catalog access (for Glue-based catalogs)
- S3 Tables access (if using managed Iceberg)

---

## Local Development Setup

### 1. Clone and Install

```bash
# Clone repository
git clone https://github.com/jamesbconner/TableSleuth.git
cd TableSleuth

# Install dependencies
uv sync --all-extras

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows
```

### 2. Configure tmux (Recommended)

For proper TUI colors, configure tmux:

```bash
# Create tmux config
cat > ~/.tmux.conf << 'EOF'
set -g default-terminal "tmux-256color"
set -ga terminal-overrides ",xterm-256color:RGB"
set -ga terminal-overrides ",*:Tc"
EOF

# Reload tmux config (if tmux is running)
tmux source-file ~/.tmux.conf
```

### 3. Configure AWS Credentials (if needed)

```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-2  # or your preferred region

# Option 3: AWS credentials file
# Edit ~/.aws/credentials
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key
region = us-east-2
```

---

## Catalog Configuration

Table Sleuth supports multiple catalog types. Configure `~/.pyiceberg.yaml` based on your setup:

### Local Catalog (for testing)

```yaml
catalog:
  local:
    type: sql
    uri: sqlite:///path/to/catalog.db
    warehouse: file:///path/to/warehouse
```

### AWS Glue Catalog

```yaml
catalog:
  # Production Glue catalog
  production:
    type: glue
    region: us-east-2

  # Development Glue catalog
  development:
    type: glue
    region: us-west-2

  # Specific catalog with custom settings
  ratebeer:
    type: glue
    region: us-east-2
    s3.access-key-id: ""      # Use IAM role instead
    s3.secret-access-key: ""  # Use IAM role instead
    s3.session-token: ""      # Use IAM role instead
```

### AWS S3 Tables (Managed Iceberg)

```yaml
catalog:
  # S3 Tables catalog
  tpch-s3tables:
    type: rest
    warehouse: arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket
    uri: https://s3tables.us-east-2.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: us-east-2
```

### Mixed Environment Example

```yaml
catalog:
  # Local development
  local:
    type: sql
    uri: sqlite:///~/iceberg_catalog.db
    warehouse: file:///~/iceberg_warehouse

  # Glue production
  prod-glue:
    type: glue
    region: us-east-2

  # S3 Tables for specific datasets
  tpch:
    type: rest
    warehouse: arn:aws:s3tables:us-east-2:123456789012:bucket/tpch-data
    uri: https://s3tables.us-east-2.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: us-east-2

  # Development Glue
  dev-glue:
    type: glue
    region: us-west-2
```

---

## GizmoSQL Setup

GizmoSQL provides column profiling and performance testing capabilities.

### 1. Install GizmoSQL

```bash
# Install GizmoSQL CLI
pip install gizmosql

# Verify installation
gizmosql_server --help
gizmosql_client --help
```

### 2. Generate TLS Certificates

```bash
# Create certificates directory
mkdir -p ~/.certs

# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout ~/.certs/cert0.key -out ~/.certs/cert0.pem -days 365 -nodes -subj "/CN=localhost"

# Set permissions
chmod 600 ~/.certs/cert0.key
chmod 644 ~/.certs/cert0.pem
```

### 3. Configure Table Sleuth

Edit `tablesleuth.toml` in the project root:

```toml
[gizmosql]
# GizmoSQL connection settings for column profiling and Iceberg performance testing
# GizmoSQL runs as a local process with direct filesystem access
#
# IMPORTANT: These credentials should match those in resources/config.json
# used for EC2 deployment. Update both files if you change the username or password.

uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = true
```

### 4. Start GizmoSQL Server

```bash
# Start server with TLS and AWS/S3 support
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key

# Or run in background
nohup gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key &

# Or in separate tmux session
tmux new-session -d -s gizmo 'gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key'

# With S3 Tables attachment (optional)
gizmosql_server -U gizmosql_username -P gizmosql_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain); ATTACH 'arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket' AS tpch (TYPE iceberg, ENDPOINT_TYPE s3_tables);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**Initialization Commands Explained:**
- `install aws; load aws;` - AWS extension for S3 access
- `install httpfs; load httpfs;` - HTTPFS extension for HTTP/HTTPS access
- `install iceberg; load iceberg;` - Iceberg extension for Iceberg table support
- `CREATE SECRET (TYPE s3, PROVIDER credential_chain);` - Use AWS credential chain for S3 authentication
- `ATTACH '...' AS tpch (...)` - (Optional) Attach S3 Tables bucket as Iceberg catalog

**Alternative S3 Authentication Methods:**

GizmoSQL uses DuckDB under the hood. The examples above use `credential_chain` which reads AWS credentials from `~/.aws/credentials`, environment variables, or IAM roles. For alternative S3 authentication options, see:
- [DuckDB S3 API Documentation](https://duckdb.org/docs/stable/core_extensions/httpfs/s3api)

Options include:
- Static credentials in the SECRET
- Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- Config file
- IAM role (automatic on EC2)
- And more

### 5. Test GizmoSQL Connection

```bash
# Test client connection
gizmosql_client --command Execute --use-tls --tls-skip-verify --username gizmosql_username --password gizmosql_password "SELECT 1"

# Should return: 1
```

---

## AWS EC2 Production Setup

For production deployments with large datasets, use the automated EC2 setup.

**For complete details, see [docs/EC2_DEPLOYMENT_GUIDE.md](docs/EC2_DEPLOYMENT_GUIDE.md)**

### Quick Start

```bash
# Navigate to AWS CDK directory
cd resources/aws-cdk

# Set required environment variables
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
export GIZMOSQL_PASSWORD="secure-password"

# Optional: Set additional configuration
export GIZMOSQL_USERNAME="admin"
export S3TABLES_BUCKET_ARN="arn:aws:s3tables:..."
export S3TABLES_TABLE_ARN="arn:aws:s3tables:..."

# Bootstrap CDK (first time only)
cdk bootstrap

# Preview deployment (recommended)
cdk diff -c environment=dev

# Deploy
cdk deploy -c environment=dev

# Retrieve SSH key from Parameter Store
KEY_NAME=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KeyPairName`].OutputValue' \
  --output text)

aws ssm get-parameter \
  --name /ec2/keypair/${KEY_NAME} \
  --with-decryption \
  --query Parameter.Value \
  --output text > ${KEY_NAME}.pem

chmod 600 ${KEY_NAME}.pem

# Get public DNS
PUBLIC_DNS=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicDNS`].OutputValue' \
  --output text)

# Connect
ssh -i ${KEY_NAME}.pem ec2-user@${PUBLIC_DNS}
```

### What Gets Created

The CDK stack creates:
- VPC with public subnet and internet gateway
- Security group (SSH access from your IP only)
- IAM role with least-privilege S3, Glue, and S3 Tables permissions
- EC2 instance with encrypted EBS volume
- VPC Flow Logs for network monitoring
- Python 3.13.9, GizmoSQL, and TableSleuth pre-installed
- TLS certificates for GizmoSQL
- Complete environment configuration

### Environment Options

```bash
# Development environment (smaller instance, spot pricing)
cdk deploy -c environment=dev

# Production environment (larger instance, on-demand)
cdk deploy -c environment=prod

# Custom environment (edit cdk.json first)
cdk deploy -c environment=staging
```

### After Deployment

```bash
# Start GizmoSQL server
gizmosvr

# Run TableSleuth
cd ~/Code/TableSleuth
source .venv/bin/activate
tablesleuth iceberg --catalog your-catalog --table your.table
```

For detailed deployment steps, troubleshooting, and teardown instructions, see [docs/EC2_DEPLOYMENT_GUIDE.md](docs/EC2_DEPLOYMENT_GUIDE.md).

---

## Verification

### Test Local Files

```bash
# Test with sample Parquet file
tablesleuth parquet tests/data/sample.parquet

# Test directory scanning
tablesleuth parquet tests/data/
```

### Test S3 Files

```bash
# Test S3 Parquet file
tablesleuth parquet s3://your-bucket/path/to/file.parquet
```

### Test Iceberg Tables

```bash
# Test Glue catalog
tablesleuth iceberg --catalog your-glue-catalog --table database.table

# Test S3 Tables catalog
tablesleuth iceberg --catalog your-s3tables-catalog --table namespace.table

# Test local catalog
tablesleuth iceberg --catalog local --table test.table
```

### Test GizmoSQL Integration

1. Start GizmoSQL server
2. Run Table Sleuth with Iceberg table
3. Navigate to **Profile** tab
4. Select columns and run profiling
5. Test snapshot comparison and performance testing

---

## Troubleshooting

### Common Issues

#### TUI Colors Not Working
```bash
# Ensure tmux is configured
echo $TERM  # Should show tmux-256color

# Check tmux config
cat ~/.tmux.conf

# Restart tmux
tmux kill-server
tmux
```

#### AWS Credentials Issues
```bash
# Verify credentials
aws sts get-caller-identity

# Check region
echo $AWS_REGION

# Test S3 access
aws s3 ls s3://your-bucket/
```

#### GizmoSQL Connection Failed
```bash
# Check if server is running
ps aux | grep gizmosql_server

# Test direct connection
gizmosql_client --command Execute --use-tls --tls-skip-verify --username gizmosql_username --password gizmosql_password "SELECT 1"

# Check certificates
ls -la ~/.certs/
```

#### Iceberg Catalog Issues
```bash
# Test PyIceberg directly
python -c "from pyiceberg.catalog import load_catalog; cat = load_catalog('your-catalog'); print(cat.list_tables())"

# Check catalog config
cat ~/.pyiceberg.yaml

# Verify permissions (for Glue)
aws glue get-databases
aws glue get-tables --database-name your-database
```

#### S3 Tables Access Issues
```bash
# Test S3 Tables access
aws s3tables list-namespaces --table-bucket-arn arn:aws:s3tables:region:account:bucket/name

# Check IAM permissions
aws iam get-user
aws sts get-caller-identity
```

### Performance Issues

#### Large Dataset Handling
- Use larger EC2 instances (m4.xlarge or higher)
- Increase GizmoSQL memory limits
- Use Spot instances for cost optimization
- Consider data sampling for initial analysis

#### Network Latency
- Deploy EC2 in same region as data
- Use VPC endpoints for S3 access
- Consider data locality for Glue catalogs

---

## Next Steps

After setup:

1. **Read the [QUICKSTART.md](QUICKSTART.md)** for usage examples
2. **Review [USER_GUIDE.md](docs/USER_GUIDE.md)** for detailed features
3. **Check [ARCHITECTURE.md](docs/ARCHITECTURE.md)** for system design
4. **See [gizmosql-deployment.md](docs/gizmosql-deployment.md)** for advanced GizmoSQL setup

---

## Support

For issues:
1. Check this troubleshooting section
2. Review logs with verbose mode (`-v` flag)
3. Check GitHub issues
4. Consult the documentation in `docs/`
