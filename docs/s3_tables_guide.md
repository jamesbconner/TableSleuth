# AWS S3 Tables Integration Guide

TableSleuth supports inspecting Iceberg tables stored in AWS S3 Tables service using ARN-based references.

## Overview

AWS S3 Tables is a managed service for Apache Iceberg tables. TableSleuth can connect to these tables using their ARNs and inspect their structure, metadata, and data files.

## Prerequisites

1. **AWS Credentials**: Configure AWS credentials using one of these methods:
   - AWS CLI: `aws configure`
   - Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
   - IAM role (when running on EC2)

2. **Required Permissions**: Your AWS credentials need these S3 Tables permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3tables:GetTableBucket",
           "s3tables:ListNamespaces",
           "s3tables:GetNamespace",
           "s3tables:ListTables",
           "s3tables:GetTable",
           "s3tables:GetTableMetadataLocation",
           "s3tables:GetTableData"
         ],
         "Resource": [
           "arn:aws:s3tables:*:*:bucket/*"
         ]
       }
     ]
   }
   ```

3. **PyIceberg with AWS Support**: Install with AWS extras:
   ```bash
   pip install "pyiceberg[glue,s3fs]"
   ```

## Configuration

The S3 Tables catalog is pre-configured in `.pyiceberg.yaml`:

```yaml
catalog:
  s3tables:
    type: glue
    # AWS credentials picked up from environment
```

## Usage

### Using S3 Tables ARN

You can reference tables directly using their ARN:

```bash
# Inspect a table using its ARN
table-sleuth inspect "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/tpch.customer"

# Or use the catalog name explicitly
table-sleuth inspect "tpch.customer" --catalog s3tables
```

### ARN Format

S3 Tables ARNs follow this pattern:
```
arn:aws:s3tables:{region}:{account-id}:bucket/{bucket-name}/table/{namespace}.{table-name}
```

Example:
```
arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.lineitem
```

### Python API

```python
from table_sleuth.services.formats.iceberg import IcebergAdapter

# Initialize adapter
adapter = IcebergAdapter()

# Open table using ARN
table_handle = adapter.open_table(
    "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/db.table"
)

# Or use catalog name
table_handle = adapter.open_table("db.table", catalog_name="s3tables")

# Get data files
data_files = adapter.get_data_files(
    "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/db.table"
)
```

## EC2 Deployment

When running on EC2 (using the provided deployment scripts), the instance automatically has:
- AWS credentials via IAM role
- S3 and S3 Tables permissions
- TableSleuth installed and configured

Example on EC2:
```bash
# SSH to instance
ssh -i tablesleuth-ssh-key.pem ec2-user@<instance-ip>

# Activate environment
cd ~/Code/TableSleuth
source .venv/bin/activate

# Inspect S3 Tables
table-sleuth inspect "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.lineitem"
```

## Troubleshooting

### Authentication Errors

If you see authentication errors:
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check S3 Tables access
aws s3tables list-table-buckets
```

### Region Mismatch

Ensure your AWS region matches the S3 Tables bucket region:
```bash
export AWS_REGION=us-east-2
```

### Missing Dependencies

Install AWS extras if not already installed:
```bash
pip install "pyiceberg[glue,s3fs]"
```

## Examples

### Inspect TPC-H Tables

```bash
# Customer table
table-sleuth inspect "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.customer"

# Lineitem table (large)
table-sleuth inspect "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.lineitem"

# Orders table
table-sleuth inspect "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.orders"
```

### List Data Files

```python
from table_sleuth.services.formats.iceberg import IcebergAdapter

adapter = IcebergAdapter()
files = adapter.get_data_files(
    "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.customer"
)

for f in files:
    print(f"File: {f.path}")
    print(f"  Size: {f.file_size_bytes:,} bytes")
    print(f"  Records: {f.record_count:,}")
    print(f"  Partition: {f.partition}")
```

## See Also

- [AWS S3 Tables Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables.html)
- [PyIceberg Catalogs](https://py.iceberg.apache.org/configuration/)
- [EC2 Deployment Guide](../resources/README.md)
