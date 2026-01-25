"""Configuration file templates for TableSleuth initialization."""

from __future__ import annotations

TABLESLEUTH_TOML_TEMPLATE = """# TableSleuth Configuration
#
# This file configures TableSleuth behavior including default Iceberg catalog
# and GizmoSQL connection settings for profiling and performance testing.
#
# Configuration Priority (highest to lowest):
# 1. Environment variables (TABLESLEUTH_*)
# 2. Local config (./tablesleuth.toml)
# 3. Home config (~/tablesleuth.toml)
# 4. Built-in defaults

[catalog]
# Default Iceberg catalog to use when --catalog flag is not specified
# Must match a catalog name defined in .pyiceberg.yaml
# Comment out or leave empty to require explicit --catalog flag
# default = ""

# Examples:
# default = "local"      # Use local SQLite catalog
# default = "glue"       # Use AWS Glue catalog
# default = "s3tables"   # Use AWS S3 Tables catalog

[gizmosql]
# GizmoSQL connection settings for column profiling and Iceberg performance testing
# GizmoSQL is a DuckDB-based query engine accessible over Arrow Flight SQL
#
# IMPORTANT: These credentials should match those in resources/config.json
# if you're using the EC2 deployment scripts. Update both files if changed.

# Connection URI - supports grpc:// (insecure) or grpc+tls:// (TLS)
uri = "grpc+tls://localhost:31337"

# Authentication credentials
username = "gizmosql_username"
password = "gizmosql_password"

# TLS verification - set to false in production with valid certificates
tls_skip_verify = true

# ============================================================================
# GizmoSQL Setup Instructions
# ============================================================================
#
# Installation (use latest version from https://github.com/gizmodata/gizmosql):
#
# macOS (ARM64):
#   curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_arm64.zip | sudo unzip -o -d /usr/local/bin -
#
# macOS (Intel):
#   curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_amd64.zip | sudo unzip -o -d /usr/local/bin -
#
# Linux:
#   curl -L https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_linux_amd64.zip | sudo unzip -o -d /usr/local/bin -
#
# Starting the server:
#   gizmosql_server -U username -P password -Q -T ~/.certs/cert0.pem ~/.certs/cert0.key
#
# Options:
#   -P: Set password (must match config above)
#   -Q: Enable query logging
#   -T: Enable TLS with certificate and key files
#   --port: Change port (default: 31337)
#
# For detailed setup instructions, see:
#   docs/GIZMOSQL_DEPLOYMENT_GUIDE.md

# ============================================================================
# Environment Variable Overrides
# ============================================================================
#
# You can override any setting using environment variables:
#
# TABLESLEUTH_CONFIG=/path/to/config.toml  # Use custom config file location
# TABLESLEUTH_CATALOG_NAME=glue             # Override default catalog
# TABLESLEUTH_GIZMO_URI=grpc://host:port    # Override GizmoSQL URI
# TABLESLEUTH_GIZMO_USERNAME=user           # Override GizmoSQL username
# TABLESLEUTH_GIZMO_PASSWORD=pass           # Override GizmoSQL password
"""

PYICEBERG_YAML_TEMPLATE = """# PyIceberg Configuration
#
# This file configures Iceberg catalog connections used by TableSleuth.
# PyIceberg supports multiple catalog types: SQL, Hive, Glue, REST, and more.
#
# Configuration Priority (highest to lowest):
# 1. Environment variables (PYICEBERG_*)
# 2. Local config (./.pyiceberg.yaml)
# 3. Home config (~/.pyiceberg.yaml)
#
# For more information, see: https://py.iceberg.apache.org/configuration/

# ============================================================================
# Catalog Definitions
# ============================================================================

catalog:
  # ---------------------------------------------------------------------------
  # Local SQLite Catalog (for development and testing)
  # ---------------------------------------------------------------------------
  local-name:
    type: sql
    uri: sqlite:////tmp/iceberg_catalog.db
    warehouse: file:///tmp/iceberg_warehouse

    # Optional: S3 configuration for data files
    # s3.endpoint: http://localhost:9000
    # s3.access-key-id: minioadmin
    # s3.secret-access-key: minioadmin

  # ---------------------------------------------------------------------------
  # AWS Glue Catalog (production AWS environment)
  # ---------------------------------------------------------------------------
  # Note: This is different from S3 Tables. Use this for regular Glue Data Catalog.
  # For S3 Tables, see the "s3tables" catalog configuration below.
  glue-name:
    type: glue

    # AWS region where Glue catalog is located
    # Can also be set via AWS_REGION or AWS_DEFAULT_REGION environment variables
    # region: us-east-1

    # Optional: Glue catalog ID (defaults to AWS account ID)
    # catalog-id: "123456789012"

    # Optional: S3 configuration
    # s3.region: us-east-1
    # s3.endpoint: https://s3.us-east-1.amazonaws.com

    # AWS credentials are typically loaded from:
    # - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    # - AWS credentials file (~/.aws/credentials)
    # - IAM role (when running on EC2/ECS/Lambda)

  # ---------------------------------------------------------------------------
  # AWS S3 Tables Catalog (managed Iceberg service)
  # ---------------------------------------------------------------------------
  # You can have multiple S3 Tables catalogs for different buckets/regions
  # The catalog name "s3tables" is used as the default when using ARNs without --catalog flag
  s3tables:
    type: rest
    warehouse: arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket
    uri: https://s3tables.us-east-2.amazonaws.com/iceberg

    # S3 Tables REST API authentication (uses AWS SigV4)
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: us-east-2

    # AWS credentials are loaded from:
    # - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    # - AWS credentials file (~/.aws/credentials)
    # - IAM role (when running on EC2/ECS/Lambda)

  # Example: Additional S3 Tables catalog for a different bucket
  # my-dataset-s3tables:
  #   type: rest
  #   warehouse: arn:aws:s3tables:us-west-2:123456789012:bucket/my-dataset
  #   uri: https://s3tables.us-west-2.amazonaws.com/iceberg
  #   rest.sigv4-enabled: "true"
  #   rest.signing-name: s3tables
  #   rest.signing-region: us-west-2

    # Usage examples:
    # Using ARN without --catalog (uses "s3tables" catalog name by default):
    #   tablesleuth parquet "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/db.table"
    # Using ARN with --catalog to specify which S3 Tables catalog:
    #   tablesleuth parquet "arn:aws:s3tables:..." --catalog my-dataset-s3tables
    # Using catalog name explicitly:
    #   tablesleuth parquet db.table --catalog s3tables

  # ---------------------------------------------------------------------------
  # REST Catalog (for custom catalog servers)
  # ---------------------------------------------------------------------------
  # rest:
  #   type: rest
  #   uri: https://catalog-server.example.com
  #
  #   # Optional: Authentication
  #   # credential: user:password
  #   # token: your-auth-token
  #
  #   # Optional: S3 configuration
  #   # s3.region: us-east-1
  #   # s3.endpoint: https://s3.amazonaws.com

  # ---------------------------------------------------------------------------
  # Hive Metastore Catalog (for Hadoop environments)
  # ---------------------------------------------------------------------------
  # hive:
  #   type: hive
  #   uri: thrift://metastore-host:9083
  #
  #   # Optional: S3 configuration
  #   # s3.region: us-east-1
  #   # s3.access-key-id: your-key
  #   # s3.secret-access-key: your-secret

# ============================================================================
# Environment Variable Overrides
# ============================================================================
#
# PYICEBERG_HOME=/path/to/config/dir  # Directory containing .pyiceberg.yaml
# PYICEBERG_CATALOG__<NAME>__<KEY>=value  # Override specific catalog settings
#
# Examples:
# PYICEBERG_CATALOG__GLUE__REGION=us-west-2
# PYICEBERG_CATALOG__LOCAL__WAREHOUSE=file:///custom/path

# ============================================================================
# AWS Configuration
# ============================================================================
#
# For AWS catalogs (Glue, S3 Tables), credentials can be provided via:
#
# 1. Environment variables:
#    AWS_ACCESS_KEY_ID=your-key
#    AWS_SECRET_ACCESS_KEY=your-secret
#    AWS_SESSION_TOKEN=your-token (for temporary credentials)
#    AWS_REGION=us-east-1
#
# 2. AWS credentials file (~/.aws/credentials):
#    [default]
#    aws_access_key_id = your-key
#    aws_secret_access_key = your-secret
#
# 3. IAM role (when running on AWS infrastructure)
#
# For more details, see:
# - AWS credentials: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html
# - PyIceberg AWS: https://py.iceberg.apache.org/configuration/#aws
"""


def get_tablesleuth_template() -> str:
    """Get the tablesleuth.toml template content.

    Returns:
        Template content as string
    """
    return TABLESLEUTH_TOML_TEMPLATE


def get_pyiceberg_template() -> str:
    """Get the .pyiceberg.yaml template content.

    Returns:
        Template content as string
    """
    return PYICEBERG_YAML_TEMPLATE
