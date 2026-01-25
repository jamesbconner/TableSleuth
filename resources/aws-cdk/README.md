# TableSleuth CDK Infrastructure

AWS CDK application for deploying TableSleuth EC2 infrastructure following AWS best practices.

## Overview

This CDK app creates production-ready infrastructure for running TableSleuth on AWS:

- **VPC** with public subnet and internet gateway
- **Security Group** restricting SSH to your IP
- **IAM Role** with least-privilege S3, Glue, and S3 Tables permissions
- **EC2 Instance** with encrypted EBS volume
- **VPC Flow Logs** for network monitoring
- **User Data** that installs Python 3.13.9, GizmoSQL, and TableSleuth

## Quick Start

Get started in 10 minutes - see **[QUICKSTART.md](QUICKSTART.md)** for detailed instructions.

```bash
# 1. Setup
cd resources/aws-cdk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
export GIZMOSQL_PASSWORD="secure-password"

# 3. Bootstrap (first time only)
cdk bootstrap

# 4. Deploy
cdk deploy -c environment=dev
```

## Documentation

| Document | Description |
|----------|-------------|
| **[QUICKSTART.md](QUICKSTART.md)** | Deploy in 10 minutes (Mac/Linux and Windows) |
| **[CONFIGURATION.md](CONFIGURATION.md)** | Configuration best practices |
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)** | Technical details and architecture |
| **[KEY_PAIR_NOTES.md](KEY_PAIR_NOTES.md)** | EC2 key pair management |
| **[FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md)** | Planned enhancements and limitations |

## Prerequisites

- Python 3.13+
- AWS CLI configured with credentials
- Node.js and npm (for CDK CLI)
- AWS CDK CLI: `npm install -g aws-cdk`

## Configuration

Configuration uses CDK best practices with two layers:

### Environment Variables (Secrets)

```bash
# Required
export SSH_ALLOWED_CIDR="YOUR_IP/32"
export GIZMOSQL_PASSWORD="secure-password"

# Optional
export GIZMOSQL_USERNAME="admin"
export S3TABLES_BUCKET_ARN="arn:aws:s3tables:..."
export S3TABLES_TABLE_ARN="arn:aws:s3tables:..."
```

### CDK Context (Environment Settings)

Edit `cdk.json` to customize environments:

```json
{
  "context": {
    "dev": {
      "region": "us-east-2",
      "instanceType": "t3.small",
      "useSpot": true
    },
    "prod": {
      "region": "us-east-2",
      "instanceType": "m4.xlarge",
      "useSpot": false
    }
  }
}
```

See **[CONFIGURATION.md](CONFIGURATION.md)** for detailed configuration guide.

## Usage

### Deploy

```bash
# Preview changes
cdk diff -c environment=dev

# Deploy to development
cdk deploy -c environment=dev

# Deploy to production
cdk deploy -c environment=prod
```

### Retrieve SSH Key

After deployment, retrieve the private key from AWS Parameter Store:

```bash
# Get key pair name from stack outputs
KEY_NAME=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KeyPairName`].OutputValue' \
  --output text)

# Retrieve private key
aws ssm get-parameter \
  --name /ec2/keypair/${KEY_NAME} \
  --with-decryption \
  --query Parameter.Value \
  --output text > ${KEY_NAME}.pem

chmod 600 ${KEY_NAME}.pem
```

See **[KEY_PAIR_NOTES.md](KEY_PAIR_NOTES.md)** for more details.

### Connect

```bash
# Get public DNS from outputs
PUBLIC_DNS=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicDNS`].OutputValue' \
  --output text)

# SSH to instance
ssh -i ${KEY_NAME}.pem ec2-user@${PUBLIC_DNS}
```

### Destroy

```bash
cdk destroy -c environment=dev
```

## What Gets Created

- **VPC**: 10.10.0.0/16 with public subnet
- **Internet Gateway**: For outbound connectivity
- **Security Group**: SSH access from your IP only
- **IAM Role**: Least-privilege S3, Glue, and S3 Tables permissions
- **VPC Flow Logs**: Network traffic monitoring
- **EC2 Instance**: Amazon Linux 2023 with:
  - Encrypted EBS volume (30 GB)
  - Python 3.13.9
  - Git, AWS CLI v2
  - GizmoSQL CLI
  - TableSleuth repository
  - TLS certificates
  - Environment variables

## CDK Best Practices

This implementation follows AWS CDK best practices:

- ✓ **Least-privilege IAM** - Specific S3 actions, not wildcard permissions
- ✓ **EBS encryption** - Data encrypted at rest
- ✓ **VPC Flow Logs** - Network monitoring enabled
- ✓ **Generated names** - Enables multiple deployments
- ✓ **Type-safe config** - Dataclass with type hints
- ✓ **Multi-environment** - Dev, staging, prod support
- ✓ **Explicit lifecycle** - Removal policies defined

See **[IMPLEMENTATION.md](IMPLEMENTATION.md)** for technical details.

## Migration from Python Scripts

To migrate from the boto3 scripts:

1. **Teardown existing infrastructure:**
   ```bash
   cd resources/aws-cdk
   cdk destroy
   ```

2. **Deploy with CDK:**
   ```bash
   cd resources/aws-cdk
   export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
   export GIZMOSQL_PASSWORD="your-password"
   cdk deploy -c environment=prod
   ```

3. **Retrieve key pair** (see [KEY_PAIR_NOTES.md](KEY_PAIR_NOTES.md))

## Troubleshooting

### Common Issues

**"SSH_ALLOWED_CIDR environment variable is required"**
```bash
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
```

**"Environment 'xyz' not found in cdk.json context"**

Add the environment to `cdk.json`:
```json
{
  "context": {
    "xyz": {
      "region": "us-east-2",
      "instanceType": "m4.xlarge",
      "useSpot": false
    }
  }
}
```

**"Key pair already exists"**

The CDK will use the existing key pair. Retrieve the private key from Parameter Store.

**"Instance not accessible"**
- Verify security group allows your IP
- Check key pair permissions: `chmod 600 key.pem`
- Wait 2-3 minutes for user data script
- Check logs: `sudo cat /var/log/cloud-init-output.log`

## Cost Estimate

- **On-Demand m4.xlarge**: ~$0.20/hour (~$144/month if running 24/7)
- **Spot m4.xlarge**: ~$0.06/hour (~$43/month if running 24/7)
- **VPC, Internet Gateway**: Free
- **Data transfer**: Varies by usage

**Remember to stop or terminate the instance when not in use!**

```bash
# Stop instance (can restart later)
aws ec2 stop-instances --instance-ids <INSTANCE_ID>

# Or destroy everything
cdk destroy -c environment=dev
```

## Support

- **Issues**: GitHub Issues
- **Questions**: GitHub Discussions
- **Documentation**: This directory
