# EC2 Deployment Guide

Complete guide to deploying Table Sleuth on AWS EC2 using the automated setup scripts.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Deployment Process](#deployment-process)
- [What Gets Created](#what-gets-created)
- [Instance Management](#instance-management)
- [Teardown Process](#teardown-process)
- [Cost Considerations](#cost-considerations)
- [Troubleshooting](#troubleshooting)

---

## Overview

The `tablesleuth_create_env.py` script automates the complete setup of a production-ready EC2 environment for Table Sleuth, including:

- VPC and networking infrastructure
- IAM roles and permissions
- EC2 instance with Python 3.13.9
- GizmoSQL server with TLS certificates
- Table Sleuth installation with dependencies
- S3 and S3 Tables access configuration

## Prerequisites

### Local Requirements
- Python 3.12+ with boto3 installed
- AWS CLI configured with credentials
- Appropriate AWS permissions (see below)

### AWS Permissions Required

Your AWS user/role needs the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PutRolePolicy",
        "iam:CreateInstanceProfile",
        "iam:AddRoleToInstanceProfile",
        "ssm:GetParameter"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Configuration

### 1. Create Configuration File

```bash
cd resources
cp config.json.template config.json
```

### 2. Edit Configuration

Edit `config.json` with your settings:

```json
{
  "ssh_allowed_cidr": "YOUR_PUBLIC_IP/32",
  "gizmosql_username": "gizmosql_username",
  "gizmosql_password": "gizmosql_password",
  "s3tables_bucket_arn": "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket",
  "s3tables_table_arn": "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/*"
}
```

**Configuration Fields:**

- `ssh_allowed_cidr`: Your public IP in CIDR notation (e.g., "203.0.113.42/32")
  - Find your IP: `curl ifconfig.me`
- `gizmosql_username`: Username for GizmoSQL server authentication
- `gizmosql_password`: Password for GizmoSQL server authentication
- `s3tables_bucket_arn`: (Optional) ARN of S3 Tables bucket for Iceberg access
- `s3tables_table_arn`: (Optional) ARN pattern for S3 Tables table access

**Note:** If S3 Tables ARNs are `null`, the script will skip S3 Tables configuration but still provide S3 and Glue catalog access.

---

## Deployment Process

### Dry Run (Recommended First)

Preview what will be created without making changes:

```bash
python tablesleuth_create_env.py --dry-run
```

### Deploy On-Demand Instance

```bash
# Default instance (m4.xlarge)
python tablesleuth_create_env.py --region us-east-2

# Specify instance type
python tablesleuth_create_env.py --region us-east-2 --instance-type m4.large

# Larger instance for heavy workloads
python tablesleuth_create_env.py --region us-east-2 --instance-type m4.2xlarge
```

### Deploy Spot Instance (Cost Savings)

```bash
# Spot instance (can be interrupted but cheaper)
python tablesleuth_create_env.py --region us-east-2 --use-spot

# Spot with specific instance type
python tablesleuth_create_env.py --region us-east-2 --instance-type m4.xlarge --use-spot
```

**Spot vs On-Demand:**
- **On-Demand**: Stable, guaranteed availability, higher cost
- **Spot**: 50-90% cheaper, can be interrupted with 2-minute warning

---

## What Gets Created

### 1. Network Infrastructure

#### VPC (Virtual Private Cloud)
- **Name**: `tablesleuth-vpc`
- **CIDR**: `10.10.0.0/16`
- **DNS Support**: Enabled
- **DNS Hostnames**: Enabled
- **Purpose**: Isolated network for Table Sleuth resources

#### Public Subnet
- **Name**: `tablesleuth-subnet-public`
- **CIDR**: `10.10.1.0/24`
- **Auto-assign Public IP**: Enabled
- **Purpose**: Hosts EC2 instance with internet access

#### Internet Gateway
- **Name**: `tablesleuth-igw`
- **Attached to**: `tablesleuth-vpc`
- **Purpose**: Provides internet connectivity

#### Route Table
- **Name**: `tablesleuth-public-rt`
- **Routes**:
  - `10.10.0.0/16` → local (VPC internal traffic)
  - `0.0.0.0/0` → Internet Gateway (internet traffic)
- **Associated with**: `tablesleuth-subnet-public`

#### Security Group
- **Name**: `tablesleuth-sg-ssh-only`
- **Inbound Rules**:
  - TCP port 22 (SSH) from your IP (configured in `ssh_allowed_cidr`)
- **Outbound Rules**:
  - All traffic allowed (default)
- **Purpose**: Restricts access to SSH from your IP only

### 2. IAM Resources

#### IAM Role
- **Name**: `tablesleuth-ec2-s3-role`
- **Trust Policy**: Allows EC2 service to assume role
- **Attached Policies**:
  - `AmazonS3FullAccess` (AWS managed)
  - `AWSGlueConsoleFullAccess` (AWS managed)
- **Inline Policy**: `tablesleuth-s3tables-access`

**S3 Tables Inline Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowUseOfS3TablesBucketAndTables",
      "Effect": "Allow",
      "Action": [
        "s3tables:GetTableBucket",
        "s3tables:ListNamespaces",
        "s3tables:GetNamespace",
        "s3tables:ListTables",
        "s3tables:GetTable",
        "s3tables:GetTableMetadataLocation",
        "s3tables:GetTableData",
        "s3tables:PutTableData"
      ],
      "Resource": [
        "<s3tables_bucket_arn>",
        "<s3tables_table_arn>"
      ]
    }
  ]
}
```

#### Instance Profile
- **Name**: `tablesleuth-ec2-s3-instance-profile`
- **Associated Role**: `tablesleuth-ec2-s3-role`
- **Purpose**: Attaches IAM role to EC2 instance

### 3. SSH Key Pair

- **Name**: `tablesleuth-ssh-key`
- **Private Key Path**: `./tablesleuth-ssh-key.pem`
- **Permissions**: `600` (read-only by owner)
- **Purpose**: SSH authentication to EC2 instance

**Note:** If key pair already exists, it will be reused. Private key is only saved on first creation.

### 4. EC2 Instance

#### Instance Configuration
- **AMI**: Latest Amazon Linux 2023 (x86_64)
- **Instance Type**: Configurable (default: `m4.xlarge`)
- **Network**: Public subnet with auto-assigned public IP
- **Security Group**: SSH-only access
- **IAM Role**: S3 and S3 Tables access
- **Tags**:
  - `Project: tablesleuth`
  - `Owner: tablesleuth-script`
  - `Name: tablesleuth-instance-<type>` or `tablesleuth-spot-instance-<type>`

#### User Data Script

The instance runs a comprehensive setup script on first boot:

**Phase 1: System Packages**
```bash
# Install build tools and dependencies
dnf groupinstall -y "Development Tools"
dnf install -y openssl-devel libffi-devel bzip2-devel zlib-devel \
               xz-devel sqlite-devel readline-devel tk-devel \
               gdbm-devel ncurses-devel uuid-devel expat-devel \
               wget git awscli unzip tmux
```

**Phase 2: Python 3.13.9 Installation**
```bash
# Download and compile Python 3.13.9 from source
wget https://www.python.org/ftp/python/3.13.9/Python-3.13.9.tgz
tar -xzf Python-3.13.9.tgz
cd Python-3.13.9
./configure --enable-optimizations --with-ensurepip=install
make -j $(nproc)
make altinstall

# Create symlinks for python, python3, pip, pip3
alternatives --install /usr/bin/python3 python3 /usr/local/bin/python3.13 1
ln -sf /usr/local/bin/python3.13 /usr/bin/python
ln -s /usr/local/bin/pip3.13 /usr/bin/pip
ln -s /usr/local/bin/pip3.13 /usr/bin/pip3

# Create virtual environment
python3.13 -m venv /home/ec2-user/py313-venv
```

**Phase 3: AWS CLI v2**
```bash
# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip
./aws/install
```

**Phase 4: GizmoSQL Installation**
```bash
# Download and install GizmoSQL CLI (v1.12.13)
wget https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_linux_amd64.zip
unzip gizmosql_cli_linux_amd64.zip -d /usr/local/bin/
chmod +x /usr/local/bin/gizmosql*
```

**Phase 5: TLS Certificate Generation**
```bash
# Generate self-signed certificates for GizmoSQL TLS
mkdir -p /home/ec2-user/.certs
cd /home/ec2-user/.certs

# Root CA
openssl genrsa -out root-ca.key 4096
openssl req -x509 -new -nodes -key root-ca.key -sha256 -days 10000 -out root-ca.pem

# Server certificates (cert0, cert1)
for i in 0 1; do
    openssl genrsa -out cert${i}.key 4096
    openssl req -new -sha256 -key cert${i}.key -out cert${i}.csr
    openssl x509 -req -in cert${i}.csr -CA root-ca.pem -CAkey root-ca.key \
                 -CAcreateserial -out cert${i}.pem -days 10000 -sha256
    openssl pkcs8 -in cert${i}.key -topk8 -nocrypt > cert${i}.pkcs1
done
```

**Phase 6: Table Sleuth Setup**
```bash
# Clone repository
git clone https://github.com/jamesbconner/TableSleuth.git /home/ec2-user/Code/TableSleuth

# Create virtual environment and install dependencies
cd /home/ec2-user/Code/TableSleuth
python -m venv .venv
source .venv/bin/activate
pip install uv
uv sync --all-extras
```

**Phase 7: PyIceberg Configuration**

If S3 Tables ARNs are configured:
```yaml
# /home/ec2-user/.pyiceberg.yaml
catalog:
  tpch:
    type: rest
    warehouse: <s3tables_bucket_arn>
    uri: https://s3tables.<region>.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: <region>
```

**Phase 8: Environment Configuration**

Added to `/home/ec2-user/.bashrc`:
```bash
# S3 Tables configuration (if configured)
export S3TABLES_BUCKET_ARN="<bucket_arn>"
export S3TABLES_TABLE_ARN="<table_arn>"

# AWS region
export AWS_REGION="<region>"
export AWS_DEFAULT_REGION="<region>"

# PyIceberg Glue catalog configuration
export PYICEBERG_CATALOG__TPCH__REGION="<region>"
export PYICEBERG_CATALOG__RATEBEER__REGION="<region>"

# GizmoSQL configuration
export GIZMOSQL_USERNAME="<username>"
export GIZMOSQL_PASSWORD="<password>"

# GizmoSQL aliases
alias gizmosvr='gizmosql_server -P "$GIZMOSQL_PASSWORD" -Q -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain); ATTACH '\''$S3TABLES_BUCKET_ARN'\'' AS tpch (TYPE iceberg, ENDPOINT_TYPE s3_tables);" -T ~/.certs/cert0.pem ~/.certs/cert0.key'
alias gizmo='gizmosql_client --command Execute --use-tls --tls-skip-verify --username "$GIZMOSQL_USERNAME" --password "$GIZMOSQL_PASSWORD"'

# Convenience alias
alias lf='ls -AFlh'
```

### Installation Logs

All installation logs are saved to:
- `/var/log/install_python_3_13_9.log` - Python installation
- `/var/log/gen-certs.log` - Certificate generation

---

## Instance Management

### Connect via SSH

```bash
ssh -i ./tablesleuth-ssh-key.pem ec2-user@<PUBLIC_DNS>
```

The public DNS is shown in the deployment output.

### Start GizmoSQL Server

```bash
# Using the pre-configured alias
gizmosvr

# Or manually
gizmosql_server -P "$GIZMOSQL_PASSWORD" -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain); ATTACH '$S3TABLES_BUCKET_ARN' AS tpch (TYPE iceberg, ENDPOINT_TYPE s3_tables);" \
  -T ~/.certs/cert0.pem ~/.certs/cert0.key
```

**GizmoSQL Server Options:**
- `-P`: Password for authentication
- `-Q`: Enable query printing (verbose mode)
- `-I`: Initialization SQL commands
- `-T`: TLS certificate and key files

### Use GizmoSQL Client

```bash
# Using the pre-configured alias
gizmo "SELECT 1"

# Or manually
gizmosql_client --command Execute --use-tls --tls-skip-verify \
  --username "$GIZMOSQL_USERNAME" --password "$GIZMOSQL_PASSWORD" \
  "SELECT 1"
```

### Run Table Sleuth Examples

```bash
cd ~/Code/TableSleuth
source .venv/bin/activate

# Inspect Iceberg table from S3 Tables
table-sleuth iceberg --catalog tpch --table tpch.lineitem

# Inspect Iceberg table from Glue
table-sleuth iceberg --catalog ratebeer --table ratebeer.reviews

# Inspect Parquet files in S3
table-sleuth inspect s3://your-bucket/path/to/file.parquet
```

### Instance Control Commands

```bash
# Stop instance (saves costs, preserves data)
aws ec2 stop-instances --instance-ids <INSTANCE_ID> --region <REGION>

# Start instance (after stopping)
aws ec2 start-instances --instance-ids <INSTANCE_ID> --region <REGION>

# Terminate instance (permanent deletion)
aws ec2 terminate-instances --instance-ids <INSTANCE_ID> --region <REGION>

# Check instance status
aws ec2 describe-instances --instance-ids <INSTANCE_ID> --region <REGION> \
  --query 'Reservations[0].Instances[0].State.Name' --output text

# Get public IP after restart
aws ec2 describe-instances --instance-ids <INSTANCE_ID> --region <REGION> \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

**Note:** Public IP changes when you stop/start an instance. Use Elastic IP if you need a static IP.

---

## Teardown Process

### Manual Teardown

To completely remove all resources:

```bash
# 1. Terminate EC2 instance
aws ec2 terminate-instances --instance-ids <INSTANCE_ID> --region <REGION>

# Wait for termination
aws ec2 wait instance-terminated --instance-ids <INSTANCE_ID> --region <REGION>

# 2. Delete security group
aws ec2 delete-security-group --group-id <SG_ID> --region <REGION>

# 3. Disassociate and delete route table
aws ec2 disassociate-route-table --association-id <ASSOC_ID> --region <REGION>
aws ec2 delete-route-table --route-table-id <RT_ID> --region <REGION>

# 4. Delete subnet
aws ec2 delete-subnet --subnet-id <SUBNET_ID> --region <REGION>

# 5. Detach and delete internet gateway
aws ec2 detach-internet-gateway --internet-gateway-id <IGW_ID> --vpc-id <VPC_ID> --region <REGION>
aws ec2 delete-internet-gateway --internet-gateway-id <IGW_ID> --region <REGION>

# 6. Delete VPC
aws ec2 delete-vpc --vpc-id <VPC_ID> --region <REGION>

# 7. Remove role from instance profile
aws iam remove-role-from-instance-profile \
  --instance-profile-name tablesleuth-ec2-s3-instance-profile \
  --role-name tablesleuth-ec2-s3-role

# 8. Delete instance profile
aws iam delete-instance-profile --instance-profile-name tablesleuth-ec2-s3-instance-profile

# 9. Detach policies from role
aws iam detach-role-policy --role-name tablesleuth-ec2-s3-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam detach-role-policy --role-name tablesleuth-ec2-s3-role \
  --policy-arn arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess

# 10. Delete inline policy
aws iam delete-role-policy --role-name tablesleuth-ec2-s3-role \
  --policy-name tablesleuth-s3tables-access

# 11. Delete IAM role
aws iam delete-role --role-name tablesleuth-ec2-s3-role

# 12. Delete key pair
aws ec2 delete-key-pair --key-name tablesleuth-ssh-key --region <REGION>
rm -f ./tablesleuth-ssh-key.pem
```

### Automated Teardown Script

Use the `tablesleuth_teardown.py` in the `resources/` directory for automated cleanup.  It leverages the tags placed on resources created by the `tablesleuth_create_env.py` script to identify infrastructure that needs to be removed.

---

## Cost Considerations

### On-Demand Instance Costs (us-east-2)

| Instance Type | vCPUs | Memory | Hourly Cost | Daily Cost | Monthly Cost |
|---------------|-------|--------|-------------|------------|--------------|
| m4.large      | 2     | 8 GB   | $0.10       | $2.40      | $73          |
| m4.xlarge     | 4     | 16 GB  | $0.20       | $4.80      | $146         |
| m4.2xlarge    | 8     | 32 GB  | $0.40       | $9.60      | $292         |

### Spot Instance Savings

Spot instances typically cost 50-90% less than On-Demand:

| Instance Type | Typical Spot Price | Savings |
|---------------|-------------------|---------|
| m4.large      | $0.03-0.05/hr     | 50-70%  |
| m4.xlarge     | $0.06-0.10/hr     | 50-70%  |
| m4.2xlarge    | $0.12-0.20/hr     | 50-70%  |

**Spot Instance Considerations:**
- Can be interrupted with 2-minute warning
- Best for non-critical workloads
- Use On-Demand for production/critical analysis

### Additional Costs

- **EBS Storage**: ~$0.10/GB-month (default 8GB root volume)
- **Data Transfer**:
  - Inbound: Free
  - Outbound: $0.09/GB (first 10TB)
- **S3 Requests**: Minimal for typical usage
- **S3 Tables**: Based on storage and requests

### Cost Optimization Tips

1. **Stop when not in use**: Stopped instances only incur EBS storage costs
2. **Use Spot instances**: 50-90% savings for interruptible workloads
3. **Right-size instance**: Start with m4.large, scale up if needed
4. **Set up billing alerts**: Monitor costs in AWS Billing Console
5. **Use AWS Budgets**: Set spending limits and alerts

---

## Troubleshooting

### SSH Connection Issues

**Problem**: Cannot connect via SSH

**Solutions**:
```bash
# 1. Verify security group allows your current IP
curl ifconfig.me  # Check your current IP

# 2. Update security group if IP changed
aws ec2 authorize-security-group-ingress \
  --group-id <SG_ID> \
  --protocol tcp --port 22 --cidr <NEW_IP>/32 \
  --region <REGION>

# 3. Verify instance is running
aws ec2 describe-instances --instance-ids <INSTANCE_ID> --region <REGION> \
  --query 'Reservations[0].Instances[0].State.Name'

# 4. Check key permissions
chmod 600 ./tablesleuth-ssh-key.pem
```

### User Data Script Failures

**Problem**: Instance launches but software not installed

**Solutions**:
```bash
# 1. SSH to instance and check logs
ssh -i ./tablesleuth-ssh-key.pem ec2-user@<PUBLIC_DNS>

# 2. View installation logs
sudo tail -f /var/log/cloud-init-output.log
sudo cat /var/log/install_python_3_13_9.log
sudo cat /var/log/gen-certs.log

# 3. Check user data execution
sudo cat /var/log/cloud-init.log

# 4. Manually run installation if needed
sudo /usr/local/bin/install_python_3_13_9.sh
```

### GizmoSQL Connection Issues

**Problem**: Cannot connect to GizmoSQL server

**Solutions**:
```bash
# 1. Verify server is running
ps aux | grep gizmosql_server

# 2. Check certificates exist
ls -la ~/.certs/

# 3. Test server startup manually
gizmosql_server -P "$GIZMOSQL_PASSWORD" -Q -T ~/.certs/cert0.pem ~/.certs/cert0.key

# 4. Test client connection
gizmo "SELECT 1"
```

### S3 Tables Access Issues

**Problem**: Cannot access S3 Tables

**Solutions**:
```bash
# 1. Verify IAM role has correct permissions
aws iam get-role-policy --role-name tablesleuth-ec2-s3-role \
  --policy-name tablesleuth-s3tables-access

# 2. Test S3 Tables access
aws s3tables list-namespaces --table-bucket-arn "$S3TABLES_BUCKET_ARN"

# 3. Verify environment variables
echo $S3TABLES_BUCKET_ARN
echo $S3TABLES_TABLE_ARN

# 4. Check PyIceberg configuration
cat ~/.pyiceberg.yaml
```

### Instance Profile Issues

**Problem**: IAM role not attached or permissions not working

**Solutions**:
```bash
# 1. Verify instance profile is attached
aws ec2 describe-instances --instance-ids <INSTANCE_ID> --region <REGION> \
  --query 'Reservations[0].Instances[0].IamInstanceProfile'

# 2. Check role association
aws iam get-instance-profile --instance-profile-name tablesleuth-ec2-s3-instance-profile

# 3. Test AWS credentials from instance
aws sts get-caller-identity

# 4. Wait for IAM propagation (can take up to 10 minutes)
```

### Python Version Issues

**Problem**: Wrong Python version or missing packages

**Solutions**:
```bash
# 1. Verify Python version
python --version  # Should show 3.13.9
python3 --version

# 2. Check symlinks
ls -la /usr/bin/python*
ls -la /usr/local/bin/python*

# 3. Activate virtual environment
cd ~/Code/TableSleuth
source .venv/bin/activate

# 4. Reinstall dependencies
pip install uv
uv sync --all-extras
```

---

## Advanced Configuration

### Custom VPC CIDR

Edit the script to change VPC/subnet ranges:

```python
VPC_CIDR = "10.20.0.0/16"
SUBNET_CIDR = "10.20.1.0/24"
```

### Multiple SSH Sources

Allow SSH from multiple IPs:

```bash
# Add additional CIDR blocks
aws ec2 authorize-security-group-ingress \
  --group-id <SG_ID> \
  --protocol tcp --port 22 --cidr <ADDITIONAL_IP>/32 \
  --region <REGION>
```

### Custom Instance Tags

Edit the script to add custom tags:

```python
TAGS = [
    {"Key": "Project", "Value": "tablesleuth"},
    {"Key": "Owner", "Value": "your-name"},
    {"Key": "Environment", "Value": "production"},
    {"Key": "CostCenter", "Value": "analytics"},
]
```

### Elastic IP (Static IP)

Allocate and associate an Elastic IP:

```bash
# Allocate Elastic IP
aws ec2 allocate-address --region <REGION>

# Associate with instance
aws ec2 associate-address --instance-id <INSTANCE_ID> \
  --allocation-id <EIP_ALLOCATION_ID> --region <REGION>
```

---

## Security Best Practices

1. **Restrict SSH Access**: Use specific IP, not 0.0.0.0/0
2. **Rotate Credentials**: Change GizmoSQL password regularly
3. **Use IAM Roles**: Never hardcode AWS credentials
4. **Enable CloudTrail**: Audit all API calls
5. **Regular Updates**: Keep system packages updated
6. **Monitor Logs**: Review CloudWatch and system logs
7. **Least Privilege**: Grant minimum required permissions
8. **Encrypt Data**: Use encrypted EBS volumes for sensitive data

---

## Next Steps

After deployment:

1. **Test connectivity**: SSH to instance and verify all services
2. **Configure catalogs**: Set up PyIceberg for your data sources
3. **Start GizmoSQL**: Launch server and test queries
4. **Run Table Sleuth**: Analyze your Iceberg tables
5. **Set up monitoring**: Configure CloudWatch alarms
6. **Document access**: Share connection details with team

For usage examples, see [QUICKSTART.md](../QUICKSTART.md) and [USER_GUIDE.md](USER_GUIDE.md).
