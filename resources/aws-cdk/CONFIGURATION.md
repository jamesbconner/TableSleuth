# CDK Configuration Best Practices

This document explains the configuration approach used in this CDK application, following AWS CDK best practices.

## Configuration Strategy

The application uses a **layered configuration approach**:

1. **CDK Context** (`cdk.json`) - Environment-specific settings (instance type, region, spot usage)
2. **Environment Variables** - Secrets and user-specific values (IP address, passwords)
3. **Defaults** - Sensible defaults in code

This follows CDK best practices by:
- ✓ Keeping secrets out of version control
- ✓ Using CDK's built-in context system
- ✓ Separating environment-specific from secret configuration
- ✓ Making configuration explicit and type-safe

## Configuration Layers

### Layer 1: CDK Context (cdk.json)

Environment-specific settings that can be version controlled:

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

**What goes here:**
- Instance types
- Region selection
- Spot vs On-Demand
- Feature flags
- Non-sensitive environment settings

**What doesn't go here:**
- Passwords
- API keys
- IP addresses
- Any PII or sensitive data

### Layer 2: Environment Variables

Secrets and user-specific values:

```bash
export SSH_ALLOWED_CIDR="1.2.3.4/32"
export GIZMOSQL_USERNAME="admin"
export GIZMOSQL_PASSWORD="your-secure-password"

# Optional S3 Tables configuration
export S3TABLES_BUCKET_ARN="arn:aws:s3tables:..."
export S3TABLES_TABLE_ARN="arn:aws:s3tables:..."
```

**What goes here:**
- Passwords and secrets
- User-specific values (IP addresses)
- Optional configuration
- Values that change per developer

**What doesn't go here:**
- Environment-specific settings (use context)
- Defaults (use code)

### Layer 3: Code Defaults

Sensible defaults in the code:

```python
@dataclass
class TablesleuthConfig:
    region: str = "us-east-2"
    instance_type: str = "m4.xlarge"
    use_spot: bool = False
```

## Usage Examples

### Deploy to Development

```bash
# Set secrets
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
export GIZMOSQL_PASSWORD="dev-password"

# Deploy to dev environment
cdk deploy -c environment=dev
```

### Deploy to Production

```bash
# Set secrets
export SSH_ALLOWED_CIDR="10.0.0.0/8"
export GIZMOSQL_PASSWORD="$(aws secretsmanager get-secret-value --secret-id prod/gizmosql --query SecretString --output text)"

# Deploy to prod environment
cdk deploy -c environment=prod
```

### Override Instance Type

```bash
# Use context override
cdk deploy -c environment=prod

# Then edit cdk.json to change prod instanceType
```

### Multiple Environments

```bash
# Deploy dev
cdk deploy -c environment=dev

# Deploy staging
cdk deploy -c environment=staging

# Deploy prod
cdk deploy -c environment=prod
```

Each creates a separate stack: `TablesleuthStack-dev`, `TablesleuthStack-staging`, `TablesleuthStack-prod`

## Environment Variable Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SSH_ALLOWED_CIDR` | CIDR block allowed to SSH | `1.2.3.4/32` |
| `GIZMOSQL_PASSWORD` | Password for GizmoSQL | `secure-password-123` |

### Optional

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `GIZMOSQL_USERNAME` | Username for GizmoSQL | `admin` | `myuser` |
| `S3TABLES_BUCKET_ARN` | S3 Tables bucket ARN | None | `arn:aws:s3tables:...` |
| `S3TABLES_TABLE_ARN` | S3 Tables table ARN | None | `arn:aws:s3tables:...` |

## CDK Context Reference

### Environment Configuration

Each environment in `cdk.json` supports:

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `region` | string | AWS region | `us-east-2` |
| `instanceType` | string | EC2 instance type | `m4.xlarge` |
| `useSpot` | boolean | Use Spot instances | `false` |

## Best Practices Comparison

### ❌ Anti-Pattern: config.json File

```json
// config.json (DON'T DO THIS)
{
  "ssh_allowed_cidr": "1.2.3.4/32",
  "gizmosql_password": "password123",  // Secret in version control!
  "instance_type": "m4.xlarge"
}
```

**Problems:**
- Secrets in version control
- Not environment-specific
- Requires .gitignore management
- Easy to accidentally commit secrets

### ✅ Best Practice: Layered Configuration

```bash
# Environment variables for secrets
export SSH_ALLOWED_CIDR="1.2.3.4/32"
export GIZMOSQL_PASSWORD="password123"

# CDK context for environment settings
cdk deploy -c environment=prod
```

**Benefits:**
- Secrets never in version control
- Environment-specific configuration
- Type-safe configuration object
- Clear separation of concerns

## Advanced Configuration

### Using AWS Secrets Manager

For production, store secrets in AWS Secrets Manager:

```bash
# Store secret
aws secretsmanager create-secret \
  --name tablesleuth/gizmosql-password \
  --secret-string "your-secure-password"

# Retrieve and use
export GIZMOSQL_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id tablesleuth/gizmosql-password \
  --query SecretString \
  --output text)

cdk deploy -c environment=prod
```

### Using AWS Systems Manager Parameter Store

For shared configuration:

```bash
# Store parameter
aws ssm put-parameter \
  --name /tablesleuth/ssh-allowed-cidr \
  --value "10.0.0.0/8" \
  --type String

# Retrieve and use
export SSH_ALLOWED_CIDR=$(aws ssm get-parameter \
  --name /tablesleuth/ssh-allowed-cidr \
  --query Parameter.Value \
  --output text)

cdk deploy -c environment=prod
```

### Using .env Files (Development Only)

For local development, you can use a `.env` file:

```bash
# .env (add to .gitignore!)
SSH_ALLOWED_CIDR=1.2.3.4/32
GIZMOSQL_PASSWORD=dev-password
```

Load with:
```bash
export $(cat .env | xargs)
cdk deploy -c environment=dev
```

**Warning:** Never commit `.env` files to version control!

## Migration from config.json

If you're migrating from the old `config.json` approach:

### Old Way (config.json)
```json
{
  "ssh_allowed_cidr": "1.2.3.4/32",
  "gizmosql_password": "password",
  "instance_type": "m4.xlarge",
  "region": "us-east-2"
}
```

### New Way (Environment Variables + Context)

1. **Move secrets to environment variables:**
```bash
export SSH_ALLOWED_CIDR="1.2.3.4/32"
export GIZMOSQL_PASSWORD="password"
```

2. **Move environment settings to cdk.json:**
```json
{
  "context": {
    "prod": {
      "instanceType": "m4.xlarge",
      "region": "us-east-2"
    }
  }
}
```

3. **Deploy:**
```bash
cdk deploy -c environment=prod
```

## Troubleshooting

### Error: "SSH_ALLOWED_CIDR environment variable is required"

**Solution:** Set the environment variable:
```bash
export SSH_ALLOWED_CIDR="$(curl -s ifconfig.me)/32"
```

### Error: "Environment 'xyz' not found in cdk.json context"

**Solution:** Add the environment to `cdk.json`:
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

### Error: "GIZMOSQL_PASSWORD environment variable is required"

**Solution:** Set the password:
```bash
export GIZMOSQL_PASSWORD="your-secure-password"
```

## Security Checklist

- [ ] No secrets in `cdk.json`
- [ ] No secrets in version control
- [ ] `.env` files in `.gitignore`
- [ ] Production secrets in AWS Secrets Manager
- [ ] Environment variables set before deployment
- [ ] SSH CIDR restricted to specific IPs
- [ ] Strong GizmoSQL password

## References

- [CDK Best Practices - Configuration](https://docs.aws.amazon.com/cdk/v2/guide/best-practices.html#best-practices-apps)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
