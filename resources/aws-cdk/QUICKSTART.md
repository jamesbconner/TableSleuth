# TableSleuth CDK Quick Start

Get TableSleuth running on AWS EC2 in under 10 minutes.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Mac/Linux Deployment](#maclinux-deployment)
- [Windows Deployment](#windows-deployment)
- [Post-Deployment](#post-deployment)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### All Platforms
- AWS account with appropriate permissions
- AWS CLI configured with credentials (`aws sts get-caller-identity` should work)
- Node.js and npm (for CDK CLI)

### Mac/Linux
- Python 3.13+
- Bash shell

### Windows
- Python 3.13+
- PowerShell 5.1+ or PowerShell Core 7+

---

## Mac/Linux Deployment

### 1. Install CDK CLI

```bash
npm install -g aws-cdk
cdk --version
```

### 2. Setup Project

```bash
cd resources/aws-cdk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Get your IP address
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"

# Set GizmoSQL credentials
export GIZMOSQL_USERNAME="admin"
export GIZMOSQL_PASSWORD="your-secure-password"

# Optional: S3 Tables configuration
# export S3TABLES_BUCKET_ARN="arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket"
# export S3TABLES_TABLE_ARN="arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/*"

# Verify environment variables
echo "SSH CIDR: $SSH_ALLOWED_CIDR"
echo "Username: $GIZMOSQL_USERNAME"
echo "Password is set: $([ -n "$GIZMOSQL_PASSWORD" ] && echo 'Yes' || echo 'No')"
```

### 4. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap
```

### 5. Deploy

```bash
# Preview changes (recommended)
cdk diff -c environment=dev

# Deploy to dev environment
cdk deploy -c environment=dev

# Or deploy to prod
cdk deploy -c environment=prod
```

Deployment takes ~5-10 minutes.

### 6. Retrieve SSH Key

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

# Set permissions
chmod 600 $KEY_NAME.pem

echo "Key saved to: $KEY_NAME.pem"
```

### 7. Connect to Instance

```bash
# Get public DNS from stack outputs
PUBLIC_DNS=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicDNS`].OutputValue' \
  --output text)

# SSH to instance
ssh -i $KEY_NAME.pem ec2-user@$PUBLIC_DNS
```

---

## Windows Deployment

### 1. Install CDK CLI

Open PowerShell as Administrator:

```powershell
npm install -g aws-cdk
cdk --version
```

### 2. Setup Project

```powershell
cd resources\aws-cdk

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# If you get execution policy error, run:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```powershell
# Get your IP address
$MY_IP = Invoke-RestMethod -Uri "https://ifconfig.me/ip"
$env:SSH_ALLOWED_CIDR = "$MY_IP/32"

# Set GizmoSQL credentials
$env:GIZMOSQL_USERNAME = "admin"
$env:GIZMOSQL_PASSWORD = "your-secure-password"

# Optional: S3 Tables configuration
# $env:S3TABLES_BUCKET_ARN = "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket"
# $env:S3TABLES_TABLE_ARN = "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/*"

# Verify environment variables
Write-Host "SSH CIDR: $env:SSH_ALLOWED_CIDR"
Write-Host "Username: $env:GIZMOSQL_USERNAME"
Write-Host "Password is set: $(if($env:GIZMOSQL_PASSWORD){'Yes'}else{'No'})"
```

### 4. Bootstrap CDK (First Time Only)

```powershell
cdk bootstrap
```

### 5. Deploy

```powershell
# Preview changes (recommended)
cdk diff -c environment=dev

# Deploy to dev environment
cdk deploy -c environment=dev

# Or deploy to prod
cdk deploy -c environment=prod
```

Deployment takes ~5-10 minutes.

### 6. Retrieve SSH Key

```powershell
# Get key pair name from stack outputs
$KEY_NAME = aws cloudformation describe-stacks `
  --stack-name TablesleuthStack-dev `
  --query 'Stacks[0].Outputs[?OutputKey==`KeyPairName`].OutputValue' `
  --output text

# Get key pair ID
$KEY_ID = aws ec2 describe-key-pairs `
  --key-names $KEY_NAME `
  --query 'KeyPairs[0].KeyPairId' `
  --output text

# Retrieve private key
aws ssm get-parameter `
  --name /ec2/keypair/$KEY_ID `
  --with-decryption `
  --query Parameter.Value `
  --output text | Out-File -FilePath "$KEY_NAME.pem" -Encoding ASCII

Write-Host "Key saved to: $KEY_NAME.pem"
```

### 7. Connect to Instance

**Option A: Using PowerShell with OpenSSH**

```powershell
# Get public DNS from stack outputs
$PUBLIC_DNS = aws cloudformation describe-stacks `
  --stack-name TablesleuthStack-dev `
  --query 'Stacks[0].Outputs[?OutputKey==`PublicDNS`].OutputValue' `
  --output text

# SSH to instance (requires OpenSSH client)
ssh -i $KEY_NAME.pem ec2-user@$PUBLIC_DNS
```

**Option B: Using PuTTY**

1. Convert `.pem` to `.ppk` using PuTTYgen:
   - Open PuTTYgen
   - Click "Load" and select your `.pem` file
   - Click "Save private key" and save as `.ppk`

2. Connect using PuTTY:
   - Host Name: `ec2-user@<PUBLIC_DNS>`
   - Connection → SSH → Auth → Private key file: Select your `.ppk` file
   - Click "Open"

**Option C: Using Windows Subsystem for Linux (WSL)**

```bash
# In WSL terminal
ssh -i /mnt/c/path/to/key.pem ec2-user@<PUBLIC_DNS>
```

---

## Post-Deployment

### Configure AWS Credentials on EC2

After connecting to the EC2 instance, configure AWS credentials:

```bash
# Configure AWS credentials
aws configure

# You'll be prompted for:
# AWS Access Key ID: [your-access-key]
# AWS Secret Access Key: [your-secret-key]
# Default region name: [us-east-2]
# Default output format: [json]
```

### Restart GizmoSQL

After configuring AWS credentials, restart GizmoSQL:

```bash
# Restart GizmoSQL service
sudo systemctl restart gizmosql

# Verify it's running
sudo systemctl status gizmosql

# Check logs if needed
sudo journalctl -u gizmosql -f
```

### Configure Iceberg Catalogs

Edit `~/.pyiceberg.yaml` to add your Glue catalogs:

```bash
vi ~/.pyiceberg.yaml
```

Add your catalogs:

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

### Update TableSleuth Configuration

Edit `~/tablesleuth.toml` to set your default catalog:

```bash
vi ~/tablesleuth.toml
```

Update the catalog section:

```toml
[catalog]
default = "my_catalog"  # Change to your catalog name

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "admin"
password = "your-password"
tls_skip_verify = true
```

### Run TableSleuth

```bash
# Start tmux for better terminal experience
tmux

# Run TableSleuth with your catalog and table
tablesleuth iceberg --catalog my_catalog --table my_database.my_table
```

---

## Troubleshooting

### Common Issues

#### "SSH_ALLOWED_CIDR environment variable is required"

**Mac/Linux:**
```bash
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
```

**Windows:**
```powershell
$MY_IP = Invoke-RestMethod -Uri "https://ifconfig.me/ip"
$env:SSH_ALLOWED_CIDR = "$MY_IP/32"
```

#### "GIZMOSQL_PASSWORD environment variable is required"

**Mac/Linux:**
```bash
export GIZMOSQL_USERNAME="admin"
export GIZMOSQL_PASSWORD="your-secure-password"
```

**Windows:**
```powershell
$env:GIZMOSQL_USERNAME = "admin"
$env:GIZMOSQL_PASSWORD = "your-secure-password"
```

#### "Unable to resolve AWS account"

Verify AWS credentials are configured:

```bash
aws sts get-caller-identity
```

If this fails, run `aws configure` to set up credentials.

#### "Key pair already exists"

The CDK will reuse the existing key pair. Retrieve it from Parameter Store using the steps above.

#### "Cannot connect via SSH"

1. **Verify your IP hasn't changed:**
   ```bash
   curl -s ifconfig.me
   ```

2. **Update security group if needed:**
   ```bash
   # Get security group ID
   SG_ID=$(aws cloudformation describe-stacks \
     --stack-name TablesleuthStack-dev \
     --query 'Stacks[0].Outputs[?OutputKey==`SecurityGroupId`].OutputValue' \
     --output text)

   # Update ingress rule
   aws ec2 authorize-security-group-ingress \
     --group-id $SG_ID \
     --protocol tcp \
     --port 22 \
     --cidr $(curl -s ifconfig.me)/32
   ```

3. **Check key permissions:**
   ```bash
   chmod 600 key.pem
   ```

4. **Wait for user data script:**
   - Initial setup takes 2-3 minutes
   - Check logs: `sudo cat /var/log/cloud-init-output.log`

#### Windows: "Execution policy error"

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Windows: "OpenSSH not found"

Install OpenSSH client:

1. Settings → Apps → Optional Features
2. Click "Add a feature"
3. Search for "OpenSSH Client"
4. Install

Or use PuTTY or WSL as alternatives.

#### GizmoSQL not starting

```bash
# Check service status
sudo systemctl status gizmosql

# Check logs
sudo journalctl -u gizmosql -f

# Restart service
sudo systemctl restart gizmosql
```

### Getting Help

- **Documentation:** See [README.md](README.md) for full documentation index
- **Configuration:** See [CONFIGURATION.md](CONFIGURATION.md) for advanced configuration
- **Implementation:** See [IMPLEMENTATION.md](IMPLEMENTATION.md) for technical details
- **Issues:** GitHub Issues

---

## Quick Reference

### Mac/Linux Commands

```bash
# Deploy
cd resources/aws-cdk
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
export GIZMOSQL_USERNAME="admin"
export GIZMOSQL_PASSWORD="your-password"
cdk deploy -c environment=dev

# Get outputs
aws cloudformation describe-stacks --stack-name TablesleuthStack-dev --query 'Stacks[0].Outputs'

# Destroy
cdk destroy -c environment=dev
```

### Windows Commands

```powershell
# Deploy
cd resources\aws-cdk
$MY_IP = Invoke-RestMethod -Uri "https://ifconfig.me/ip"
$env:SSH_ALLOWED_CIDR = "$MY_IP/32"
$env:GIZMOSQL_USERNAME = "admin"
$env:GIZMOSQL_PASSWORD = "your-password"
cdk deploy -c environment=dev

# Get outputs
aws cloudformation describe-stacks --stack-name TablesleuthStack-dev --query 'Stacks[0].Outputs'

# Destroy
cdk destroy -c environment=dev
```

### Environment Options

- **dev** - t3.small instance (cost-effective for testing)
- **staging** - m4.large instance (medium workloads)
- **prod** - m4.xlarge instance (production workloads)

Edit `cdk.json` to customize or add environments.

---

## Next Steps

- Configure your Iceberg catalogs in `~/.pyiceberg.yaml`
- Set default catalog in `~/tablesleuth.toml`
- Run TableSleuth: `tablesleuth iceberg --catalog my_catalog --table my_database.my_table`
- See [User Guide](../../docs/USER_GUIDE.md) for features and usage
- See [GizmoSQL Deployment Guide](../../docs/GIZMOSQL_DEPLOYMENT_GUIDE.md) for advanced GizmoSQL configuration
