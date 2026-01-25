# TableSleuth Infrastructure as Code

This directory contains Infrastructure as Code (IaC) and example scripts for deploying and using TableSleuth.

## Contents

### AWS CDK (`aws-cdk/`)

Production-ready AWS infrastructure using AWS CDK.

**Quick Start:**
```bash
cd resources/aws-cdk
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
export GIZMOSQL_PASSWORD="secure-password"
cdk deploy -c environment=dev
```

**Documentation:**
- [README.md](aws-cdk/README.md) - Complete deployment guide
- [QUICKSTART.md](aws-cdk/QUICKSTART.md) - 10-minute deployment
- [CONFIGURATION.md](aws-cdk/CONFIGURATION.md) - Configuration best practices
- [IMPLEMENTATION.md](aws-cdk/IMPLEMENTATION.md) - Technical details

---

### Example Scripts (`examples/`)

Programmatic usage examples for automation and analysis.

**Available Examples:**
- `inspect_s3_tables.py` - AWS S3 Tables inspection
- `delta_forensics.py` - Delta Lake health analysis
- `iceberg_snapshot_diff.py` - Iceberg snapshot comparison
- `discover_parquet_files.py` - Parquet file discovery
- `extract_parquet_metadata.py` - Metadata extraction
- `batch_table_analysis.py` - Batch table analysis

**Documentation:**
- [examples/README.md](examples/README.md) - Complete examples guide

---

## Available Platforms

### AWS (CDK)

Production-ready AWS infrastructure using AWS CDK.

**Location:** `resources/aws-cdk/`

**Quick Start:**
```bash
cd resources/aws-cdk
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
export GIZMOSQL_PASSWORD="secure-password"
cdk deploy -c environment=dev
```

**Documentation:**
- [README.md](aws-cdk/README.md) - Complete deployment guide
- [QUICKSTART.md](aws-cdk/QUICKSTART.md) - 10-minute deployment
- [CONFIGURATION.md](aws-cdk/CONFIGURATION.md) - Configuration best practices
- [IMPLEMENTATION.md](aws-cdk/IMPLEMENTATION.md) - Technical details

**Features:**
- Least-privilege IAM policies
- EBS encryption and VPC Flow Logs
- Multi-environment support (dev/staging/prod)
- Infrastructure as code with change preview
- Automatic rollback on failures

---

## Future Platforms

### Azure (Planned)

Azure Resource Manager (ARM) templates or Bicep for Azure deployment.

**Status:** Not yet implemented

---

### Google Cloud Platform (Planned)

Terraform or Deployment Manager for GCP deployment.

**Status:** Not yet implemented

---

## Contributing

When adding support for new cloud platforms:

1. Create a subdirectory: `resources/<platform>-<tool>/`
   - Example: `resources/azure-arm/`, `resources/gcp-terraform/`

2. Include comprehensive documentation:
   - README.md with quick start
   - Configuration guide
   - Troubleshooting guide

3. Follow platform best practices:
   - Least-privilege access
   - Encryption at rest and in transit
   - Network security
   - Cost optimization

4. Provide examples for multiple environments (dev/staging/prod)

5. Update this README with the new platform

---

## General Requirements

All IaC implementations should:

- ✅ Create VPC/network with proper security groups
- ✅ Deploy compute instance with TableSleuth pre-installed
- ✅ Configure Python 3.13+, Git, AWS CLI
- ✅ Install and configure GizmoSQL
- ✅ Set up TLS certificates
- ✅ Configure environment variables
- ✅ Enable encryption (storage and network)
- ✅ Implement least-privilege access
- ✅ Support multiple environments
- ✅ Provide cost estimates
- ✅ Include teardown/cleanup procedures

---

## Support

For platform-specific issues, see the documentation in each platform's directory.

For general TableSleuth questions, see the main [README.md](../README.md).
