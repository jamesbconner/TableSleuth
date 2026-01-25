# CDK Implementation Details

Technical documentation for the TableSleuth CDK infrastructure implementation.

## Architecture Overview

The CDK implementation creates production-ready AWS infrastructure following CDK best practices:

- **VPC**: 10.10.0.0/16 with public subnet and internet gateway
- **Security Group**: SSH access from configured CIDR
- **IAM Role**: Least-privilege S3, Glue, and S3 Tables permissions
- **EC2 Instance**: Amazon Linux 2023 with encrypted EBS volume
- **VPC Flow Logs**: Network traffic monitoring
- **User Data**: Python 3.13.9, GizmoSQL, TableSleuth setup

## CDK Best Practices Applied

### 1. Configuration Management

**Type-Safe Configuration Object:**
```python
@dataclass
class TablesleuthConfig:
    ssh_allowed_cidr: str
    gizmosql_username: str
    gizmosql_password: str
    region: str = "us-east-2"
    instance_type: str = "m4.xlarge"
    use_spot: bool = False
```

**Benefits:**
- Compile-time type checking
- IDE autocomplete
- Self-documenting code
- Validation at construction time

**CDK Context for Environment Settings:**
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

**Environment Variables for Secrets:**
```bash
export SSH_ALLOWED_CIDR="1.2.3.4/32"
export GIZMOSQL_PASSWORD="secure-password"
```

### 2. Least-Privilege IAM Permissions

**Specific S3 Permissions:**
```python
role.add_to_policy(
    iam.PolicyStatement(
        sid="AllowS3ObjectAccess",
        actions=["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
        resources=["arn:aws:s3:::*/*"],
    )
)
```

**Glue Catalog Read-Only:**
```python
role.add_to_policy(
    iam.PolicyStatement(
        sid="AllowGlueCatalogAccess",
        actions=[
            "glue:GetDatabase",
            "glue:GetTable",
            "glue:GetPartitions",
        ],
        resources=["*"],
    )
)
```

**Conditional S3 Tables Access:**
```python
if self.config.s3tables_bucket_arn:
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["s3tables:GetTable", "s3tables:GetTableData"],
            resources=[self.config.s3tables_bucket_arn],
        )
    )
```

### 3. Security Enhancements

**EBS Encryption:**
```python
instance = ec2.Instance(
    self,
    "TablesleuthInstance",
    block_devices=[
        ec2.BlockDevice(
            device_name="/dev/xvda",
            volume=ec2.BlockDeviceVolume.ebs(
                volume_size=30,
                encrypted=True,
                delete_on_termination=True,
            ),
        )
    ],
)
```

**VPC Flow Logs:**
```python
vpc = ec2.Vpc(
    self,
    "TablesleuthVPC",
    flow_logs={
        "FlowLog": ec2.FlowLogOptions(
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )
    },
)
```

### 4. Generated Resource Names

**VPC and Security Group:**
```python
vpc = ec2.Vpc(
    self,
    "TablesleuthVPC",
    # CDK generates unique name
)

sg = ec2.SecurityGroup(
    self,
    "TablesleuthSecurityGroup",
    vpc=self.vpc,
    # CDK generates unique name
)
```

**Environment-Specific Key Pairs:**
```python
key_name = f"tablesleuth-{self.stack_name}-key"
key_pair = ec2.CfnKeyPair(
    self,
    "TablesleuthKeyPair",
    key_name=key_name,
)
```

### 5. Explicit Resource Lifecycle

**Removal Policies:**
```python
instance.apply_removal_policy(cdk.RemovalPolicy.DESTROY)
```

**Benefits:**
- Explicit cleanup behavior
- Environment-specific policies possible
- Prevents accidental retention

### 6. L2 Constructs

**Using High-Level Constructs:**
```python
# L2 constructs with sensible defaults
vpc = ec2.Vpc(...)
security_group = ec2.SecurityGroup(...)
role = iam.Role(...)
instance = ec2.Instance(...)

# L1 only when no L2 available
key_pair = ec2.CfnKeyPair(...)
```

### 7. Multi-Environment Support

**Stack Naming:**
```python
TablesleuthStack(
    app,
    f"TablesleuthStack-{environment}",
    config=config,
)
```

**Deployment:**
```bash
cdk deploy -c environment=dev
cdk deploy -c environment=prod
```

## Code Organization

```
resources/aws-cdk/
├── app.py                          # CDK app entry point
├── tablesleuth_cdk/
│   ├── __init__.py
│   └── tablesleuth_stack.py       # Stack definition
├── cdk.json                        # CDK configuration
└── requirements.txt                # Dependencies
```

## Deployment Workflow

### 1. Configure Environment

```bash
# Set secrets
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
export GIZMOSQL_PASSWORD="secure-password"

# Optional S3 Tables
export S3TABLES_BUCKET_ARN="arn:aws:s3tables:..."
```

### 2. Preview Changes

```bash
cdk diff -c environment=dev
```

### 3. Deploy

```bash
cdk deploy -c environment=dev
```

### 4. Retrieve Key Pair

```bash
# Get key pair name from outputs
KEY_NAME=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KeyPairName`].OutputValue' \
  --output text)

# Retrieve private key from Parameter Store
aws ssm get-parameter \
  --name /ec2/keypair/${KEY_NAME} \
  --with-decryption \
  --query Parameter.Value \
  --output text > ${KEY_NAME}.pem

chmod 600 ${KEY_NAME}.pem
```

### 5. Connect

```bash
ssh -i ${KEY_NAME}.pem ec2-user@<public-dns>
```

## Testing Strategy

### Synthesis Testing

```bash
# Verify stack synthesizes without errors
cdk synth -c environment=dev
```

### Validation

```bash
# Check for security issues
cdk diff -c environment=dev

# Review generated CloudFormation
cat cdk.out/TablesleuthStack-dev.template.json
```

### Unit Tests (Future)

```python
from aws_cdk import assertions

def test_vpc_created():
    app = cdk.App()
    stack = TablesleuthStack(app, "TestStack", config=test_config)
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::EC2::VPC", 1)
```

## Troubleshooting

### Common Issues

**Issue: "SSH_ALLOWED_CIDR environment variable is required"**

Solution:
```bash
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
```

**Issue: "Environment 'xyz' not found in cdk.json context"**

Solution: Add environment to `cdk.json`:
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

**Issue: "Key pair already exists"**

Solution: The CDK will use the existing key pair. Retrieve the private key from Parameter Store using the key pair ID.

**Issue: "Instance not accessible"**

Solutions:
- Verify security group allows your IP
- Check key pair permissions: `chmod 600 key.pem`
- Wait 2-3 minutes for user data script to complete
- Check cloud-init logs: `sudo cat /var/log/cloud-init-output.log`

## Migration from boto3

To migrate from boto3 scripts to CDK:

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

3. **Retrieve key pair** (see Deployment Workflow above)

## Security Considerations

### Secrets Management

- Passwords in environment variables (not version control)
- Key pairs in AWS Parameter Store
- IAM roles instead of access keys

### Network Security

- Security group restricts SSH to specific CIDR
- VPC Flow Logs for monitoring
- Public subnet for accessibility

### Data Security

- EBS volumes encrypted at rest
- S3 access via IAM role
- Least-privilege permissions

## Performance Considerations

### Deployment Time

- VPC creation: ~1 minute
- Instance launch: ~2 minutes
- User data execution: ~5 minutes
- **Total: ~8-10 minutes**

### Instance Startup

User data installs:
- Python 3.13.9 from source (~3 minutes)
- AWS CLI v2 (~1 minute)
- GizmoSQL CLI (~30 seconds)
- TableSleuth with dependencies (~1 minute)

## References

- [AWS CDK Best Practices](https://docs.aws.amazon.com/cdk/v2/guide/best-practices.html)
- [CDK Python Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)
- [EC2 Instance Types](https://aws.amazon.com/ec2/instance-types/)
- [VPC Flow Logs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html)
