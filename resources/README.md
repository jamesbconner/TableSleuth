# AWS Deployment Resources

This directory contains scripts for deploying TableSleuth to AWS EC2.

## Configuration

Before using the deployment scripts, create a configuration file:

1. Copy the template:
   ```bash
   cp config.json.template config.json
   ```

2. Edit `config.json` with your specific values:
   ```json
   {
     "ssh_allowed_cidr": "YOUR_IP_ADDRESS/32",
     "s3tables_bucket_arn": "arn:aws:s3tables:REGION:ACCOUNT_ID:bucket/BUCKET_NAME",
     "s3tables_table_arn": "arn:aws:s3tables:REGION:ACCOUNT_ID:bucket/BUCKET_NAME/table/*"
   }
   ```

   - `ssh_allowed_cidr`: Your public IP address with /32 suffix for SSH access
   - `s3tables_bucket_arn`: ARN of your S3 Tables bucket for Iceberg data
   - `s3tables_table_arn`: ARN pattern for tables in your S3 Tables bucket

## Usage

### Create Environment

```bash
# Dry run to see what would be created
python tablesleuth_create_env.py --dry-run

# Create the environment
python tablesleuth_create_env.py

# Use custom config file
python tablesleuth_create_env.py --config /path/to/config.json
```

### Teardown Environment

```bash
# Dry run to see what would be destroyed
python tablesleuth_teardown_env.py --dry-run

# Destroy the environment
python tablesleuth_teardown_env.py
```

## Security Notes

- The `config.json` file is git-ignored to prevent committing sensitive information
- SSH access is restricted to the IP address specified in `ssh_allowed_cidr`
- The EC2 instance has IAM permissions for S3 and S3 Tables access only
- Private SSH keys (*.pem) are also git-ignored

## What Gets Created

- VPC with public subnet and internet gateway
- Security group allowing SSH from your IP only
- IAM role with S3 and S3 Tables permissions
- EC2 Spot instance with Python 3.13.9, git, awscli, GizmoSQL CLI
- TableSleuth repository cloned and dependencies installed
- TLS certificates for DuckDB server in `~/.certs`

## Using S3 Tables on EC2

Once deployed, the EC2 instance can access AWS S3 Tables directly:

```bash
# SSH to instance
ssh -i tablesleuth-ssh-key.pem ec2-user@<instance-ip>

# Activate environment
cd ~/Code/TableSleuth
source .venv/bin/activate

# Inspect S3 Tables using ARN
table-sleuth inspect "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.customer"
```

See [../docs/s3_tables_guide.md](../docs/s3_tables_guide.md) for more details.
