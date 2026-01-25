#!/usr/bin/env python3
"""TableSleuth CDK Application.

This CDK app creates EC2 infrastructure for running TableSleuth on AWS.

Configuration follows CDK best practices:
- Use CDK context for environment-specific settings
- Use environment variables for secrets
- Use SSM Parameter Store for shared configuration (optional)
"""

import os

import aws_cdk as cdk
from tablesleuth_cdk.tablesleuth_stack import TablesleuthConfig, TablesleuthStack


def get_config(app: cdk.App, environment: str) -> TablesleuthConfig:
    """Get configuration from CDK context and environment variables.

    Args:
        app: CDK application
        environment: Environment name (dev, prod, etc.)

    Returns:
        Configuration object

    Raises:
        ValueError: If required configuration is missing
    """
    # Get environment-specific context
    env_context = app.node.try_get_context(environment)
    if not env_context:
        raise ValueError(
            f"Environment '{environment}' not found in cdk.json context. "
            f"Add configuration for this environment."
        )

    # Get secrets from environment variables
    ssh_allowed_cidr = os.getenv("SSH_ALLOWED_CIDR")
    gizmosql_username = os.getenv("GIZMOSQL_USERNAME", "admin")
    gizmosql_password = os.getenv("GIZMOSQL_PASSWORD")

    if not ssh_allowed_cidr:
        raise ValueError(
            "SSH_ALLOWED_CIDR environment variable is required. "
            "Set it to your IP address with /32 suffix."
        )

    if not gizmosql_password:
        raise ValueError(
            "GIZMOSQL_PASSWORD environment variable is required. "
            "Set it to a secure password for GizmoSQL."
        )

    # Optional S3 Tables configuration
    s3tables_bucket_arn = os.getenv("S3TABLES_BUCKET_ARN")
    s3tables_table_arn = os.getenv("S3TABLES_TABLE_ARN")

    return TablesleuthConfig(
        ssh_allowed_cidr=ssh_allowed_cidr,
        gizmosql_username=gizmosql_username,
        gizmosql_password=gizmosql_password,
        s3tables_bucket_arn=s3tables_bucket_arn,
        s3tables_table_arn=s3tables_table_arn,
        region=env_context.get("region", "us-east-2"),
        instance_type=env_context.get("instanceType", "m4.xlarge"),
        use_spot=env_context.get("useSpot", False),
    )


app = cdk.App()

# Get environment from context (defaults to 'dev')
environment = app.node.try_get_context("environment") or "dev"

# Load configuration
config = get_config(app, environment)

# Create stack
TablesleuthStack(
    app,
    f"TablesleuthStack-{environment}",
    config=config,
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=config.region,
    ),
    description=f"TableSleuth EC2 infrastructure for data analysis ({environment})",
)

app.synth()
