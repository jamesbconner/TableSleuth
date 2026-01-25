"""TableSleuth CDK Stack.

Creates EC2 infrastructure for running TableSleuth on AWS.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Stack,
    Tags,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_iam as iam,
)
from constructs import Construct


def escape_for_toml(value: str) -> str:
    """Escape a string for use in TOML.

    Args:
        value: String to escape

    Returns:
        Escaped string safe for TOML
    """
    # Escape backslashes first, then quotes
    return value.replace("\\", "\\\\").replace('"', '\\"')


def escape_for_systemd(value: str) -> str:
    """Escape a string for use in systemd Environment directives.

    Systemd interprets $ as variable references in double-quoted values.
    We need to escape backslashes, double quotes, and dollar signs.

    Args:
        value: String to escape

    Returns:
        Escaped string safe for systemd Environment directives
    """
    # Escape backslashes first, then quotes, then dollar signs
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")


def escape_for_bash_single_quote(value: str) -> str:
    """Escape a string for use in bash single quotes.

    In bash single quotes, you cannot escape anything except the single quote itself.
    To include a single quote, you must end the quoted string, add an escaped quote, and start a new quoted string.

    Args:
        value: String to escape

    Returns:
        Escaped string safe for bash single quotes
    """
    # Replace ' with '\''
    return value.replace("'", "'\\''")


@dataclass
class TablesleuthConfig:
    """Configuration for TableSleuth stack.

    Attributes:
        ssh_allowed_cidr: CIDR block allowed to SSH (e.g., "1.2.3.4/32")
        gizmosql_username: Username for GizmoSQL authentication
        gizmosql_password: Password for GizmoSQL authentication
        s3tables_bucket_arn: Optional S3 Tables bucket ARN
        s3tables_table_arn: Optional S3 Tables table ARN pattern
        region: AWS region for deployment
        instance_type: EC2 instance type (e.g., "m4.xlarge")
        use_spot: Whether to use Spot instances
    """

    ssh_allowed_cidr: str
    gizmosql_username: str
    gizmosql_password: str
    s3tables_bucket_arn: str | None = None
    s3tables_table_arn: str | None = None
    region: str = "us-east-2"
    instance_type: str = "m4.xlarge"
    use_spot: bool = False


class TablesleuthStack(Stack):
    """Stack for TableSleuth EC2 infrastructure."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: TablesleuthConfig,
        **kwargs,
    ) -> None:
        """Initialize the TableSleuth stack.

        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            config: Configuration object with deployment settings
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        self.config = config

        # Add tags to all resources
        Tags.of(self).add("Project", "tablesleuth")
        Tags.of(self).add("ManagedBy", "CDK")

        # Create VPC
        self.vpc = self._create_vpc()

        # Create security group
        self.security_group = self._create_security_group()

        # Create IAM role
        self.instance_role = self._create_iam_role()

        # Create key pair (note: CDK doesn't create the private key file)
        self.key_pair = self._create_key_pair()

        # Create EC2 instance
        self.instance = self._create_instance()

        # Outputs
        self._create_outputs()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with public subnet and internet gateway.

        Returns:
            VPC construct
        """
        vpc = ec2.Vpc(
            self,
            "TablesleuthVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.10.0.0/16"),
            max_azs=1,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
            # Enable VPC Flow Logs for security monitoring
            flow_logs={
                "FlowLog": ec2.FlowLogOptions(
                    traffic_type=ec2.FlowLogTrafficType.ALL,
                )
            },
        )

        return vpc

    def _create_security_group(self) -> ec2.SecurityGroup:
        """Create security group allowing SSH from configured CIDR.

        Returns:
            Security group construct
        """
        sg = ec2.SecurityGroup(
            self,
            "TablesleuthSecurityGroup",
            vpc=self.vpc,
            description="SSH only security group for tablesleuth instance",
            allow_all_outbound=True,
        )

        # Add ingress rule
        sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.config.ssh_allowed_cidr),
            connection=ec2.Port.tcp(22),
            description="SSH access from allowed CIDR",
        )

        return sg

    def _create_iam_role(self) -> iam.Role:
        """Create IAM role with least-privilege S3, S3 Tables, and Glue permissions.

        Returns:
            IAM role construct
        """
        role = iam.Role(
            self,
            "TablesleuthEC2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="EC2 role with S3 and S3Tables access for tablesleuth instance",
        )

        # Add least-privilege S3 permissions
        # Allow listing all buckets (needed for discovery)
        role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowS3ListBuckets",
                effect=iam.Effect.ALLOW,
                actions=["s3:ListAllMyBuckets", "s3:GetBucketLocation"],
                resources=["*"],
            )
        )

        # Allow read/write to all buckets (can be restricted per environment)
        role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowS3BucketAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketVersioning",
                    "s3:GetBucketLocation",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )

        role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowS3ObjectAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                    "s3:PutObject",
                    "s3:DeleteObject",
                ],
                resources=["arn:aws:s3:::*/*"],
            )
        )

        # Add Glue read-only access for Iceberg catalog
        role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowGlueCatalogAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "glue:GetDatabase",
                    "glue:GetDatabases",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetPartition",
                    "glue:GetPartitions",
                ],
                resources=["*"],
            )
        )

        # Add inline policy for S3 Tables if configured
        if self.config.s3tables_bucket_arn and self.config.s3tables_table_arn:
            role.add_to_policy(
                iam.PolicyStatement(
                    sid="AllowUseOfS3TablesBucketAndTables",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3tables:GetTableBucket",
                        "s3tables:ListNamespaces",
                        "s3tables:GetNamespace",
                        "s3tables:ListTables",
                        "s3tables:GetTable",
                        "s3tables:GetTableMetadataLocation",
                        "s3tables:GetTableData",
                        "s3tables:PutTableData",
                    ],
                    resources=[
                        self.config.s3tables_bucket_arn,
                        self.config.s3tables_table_arn,
                    ],
                )
            )

        return role

    def _create_key_pair(self) -> ec2.CfnKeyPair:
        """Create EC2 key pair.

        Note: CDK creates the key pair but doesn't save the private key.
        You must retrieve it from AWS Systems Manager Parameter Store.

        Returns:
            Key pair construct
        """
        # Use environment-specific key pair name to allow multiple deployments
        key_name = f"tablesleuth-{self.stack_name}-key"

        key_pair = ec2.CfnKeyPair(
            self,
            "TablesleuthKeyPair",
            key_name=key_name,
        )

        return key_pair

    def _get_user_data(self) -> str:
        """Generate user data script for EC2 instance.

        Returns:
            User data script as string
        """
        region = self.config.region

        # Build PyIceberg config conditionally
        pyiceberg_config = ""
        if self.config.s3tables_bucket_arn and self.config.s3tables_table_arn:
            pyiceberg_config = f"""
echo "Configuring PyIceberg for S3 Tables..."
cat > /home/ec2-user/.pyiceberg.yaml <<PYICEEOF
catalog:
  tpch:
    type: rest
    warehouse: {self.config.s3tables_bucket_arn}
    uri: https://s3tables.{region}.amazonaws.com/iceberg
    rest.sigv4-enabled: "true"
    rest.signing-name: s3tables
    rest.signing-region: {region}
PYICEEOF

chown ec2-user:ec2-user /home/ec2-user/.pyiceberg.yaml
"""
        else:
            pyiceberg_config = """
echo "Skipping PyIceberg S3 Tables config (not configured)"
"""

        # Build S3 Tables environment variables conditionally
        s3tables_env = ""
        if self.config.s3tables_bucket_arn and self.config.s3tables_table_arn:
            s3tables_env = f"""
# S3 Tables configuration
export S3TABLES_BUCKET_ARN="{self.config.s3tables_bucket_arn}"
export S3TABLES_TABLE_ARN="{self.config.s3tables_table_arn}"
"""

        # Build GizmoSQL S3 Tables attachment conditionally
        gizmosql_attach = ""
        if self.config.s3tables_bucket_arn and self.config.s3tables_table_arn:
            gizmosql_attach = f"ATTACH '{self.config.s3tables_bucket_arn}' AS tpch (TYPE iceberg, ENDPOINT_TYPE s3_tables);"

        user_data = f"""#!/bin/bash
set -euxo pipefail

echo "alias lf='ls -AFlh'" >> /home/ec2-user/.bashrc

cat << 'EOF' >/usr/local/bin/install_python_3_13_9.sh
#!/usr/bin/env bash
set -euo pipefail

PY_VERSION="3.13.9"
PY_SHORT="3.13"
PY_TARBALL="Python-${{PY_VERSION}}.tgz"
PY_SRC_DIR="Python-${{PY_VERSION}}"
PY_DOWNLOAD_URL="https://www.python.org/ftp/python/${{PY_VERSION}}/${{PY_TARBALL}}"

echo "Installing build dependencies and libraries..."
dnf groupinstall -y "Development Tools"
dnf install -y \\
  openssl-devel \\
  libffi-devel \\
  bzip2-devel \\
  zlib-devel \\
  xz-devel \\
  sqlite-devel \\
  readline-devel \\
  tk-devel \\
  gdbm-devel \\
  ncurses-devel \\
  uuid-devel \\
  expat-devel \\
  wget \\
  git \\
  awscli \\
  unzip \\
  tmux

cd /tmp

if [ ! -f "${{PY_TARBALL}}" ]; then
  echo "Downloading Python ${{PY_VERSION}} source..."
  wget "${{PY_DOWNLOAD_URL}}"
else
  echo "Python tarball ${{PY_TARBALL}} already present, reusing."
fi

if [ -d "${{PY_SRC_DIR}}" ]; then
  echo "Removing existing source directory ${{PY_SRC_DIR}}..."
  rm -rf "${{PY_SRC_DIR}}"
fi

echo "Extracting Python ${{PY_VERSION}} source..."
tar -xzf "${{PY_TARBALL}}"

cd "${{PY_SRC_DIR}}"

echo "Configuring Python ${{PY_VERSION}} build..."
./configure --enable-optimizations --with-ensurepip=install

echo "Building Python ${{PY_VERSION}}..."
make -j "$(nproc)"

echo "Installing Python ${{PY_VERSION}} with altinstall..."
make altinstall

PY_BIN="/usr/local/bin/python${{PY_SHORT}}"
PIP_BIN="/usr/local/bin/pip${{PY_SHORT}}"

if [ ! -x "${{PY_BIN}}" ]; then
  echo "Error: ${{PY_BIN}} not found after install."
  exit 1
fi

echo "Python installed at ${{PY_BIN}}"
"${{PY_BIN}}" --version

echo "Ensuring pip is available and up to date..."
"${{PY_BIN}}" -m ensurepip --upgrade || true
"${{PY_BIN}}" -m pip install --upgrade pip

if [ ! -x "${{PIP_BIN}}" ]; then
  echo "pip for Python ${{PY_SHORT}} not found as ${{PIP_BIN}}, using python -m pip directly."
  PIP_BIN="${{PY_BIN}} -m pip"
fi

echo "Registering python3 with alternatives..."
alternatives --install /usr/bin/python3 python3 "${{PY_BIN}}" 1 || true
alternatives --set python3 "${{PY_BIN}}" || true

echo "Linking python -> python3.13 ..."
ln -sf "${{PY_BIN}}" /usr/bin/python

echo "Linking pip and pip3 to pip3.13 ..."
rm -f /usr/bin/pip /usr/bin/pip3 || true
if [ -x "/usr/local/bin/pip${{PY_SHORT}}" ]; then
  ln -s "/usr/local/bin/pip${{PY_SHORT}}" /usr/bin/pip
  ln -s "/usr/local/bin/pip${{PY_SHORT}}" /usr/bin/pip3
else
  echo "pip3.13 binary not found, leaving pip links untouched."
fi

echo "Installing virtualenv..."
eval "${{PIP_BIN}} install --upgrade virtualenv"

echo "Creating venv at /home/ec2-user/py313-venv..."
"${{PY_BIN}}" -m venv /home/ec2-user/py313-venv
chown -R ec2-user:ec2-user /home/ec2-user/py313-venv

echo "Installing AWS CLI v2..."
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -o awscliv2.zip
./aws/install
rm -rf aws awscliv2.zip

echo "Installing GizmoSQL CLI..."
cd /tmp
wget https://github.com/gizmodata/gizmosql/releases/download/v1.12.13/gizmosql_cli_linux_amd64.zip
unzip -o gizmosql_cli_linux_amd64.zip -d /usr/local/bin/
chmod +x /usr/local/bin/gizmosql*

echo "Cloning TableSleuth repo for ec2-user..."
su - ec2-user -c 'mkdir -p ~/Code && git clone https://github.com/jamesbconner/TableSleuth.git ~/Code/TableSleuth || true'

echo "Creating .venv in ~/Code/TableSleuth and installing uv + project dependencies..."
su - ec2-user -c 'cd ~/Code/TableSleuth && python -m venv .venv && . .venv/bin/activate && pip install uv && uv sync --all-extras'

echo "Installing tablesleuth package globally for ec2-user..."
su - ec2-user -c 'pip install --upgrade pip'
su - ec2-user -c 'pip install --user --upgrade --no-cache-dir tablesleuth'

echo "Creating tablesleuth.toml configuration..."
cat > /home/ec2-user/tablesleuth.toml <<'TOMLEOF'
[catalog]
# Set your default Iceberg catalog name here
# Example: default = "my_glue_catalog"
# default = "my_catalog"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "{escape_for_toml(self.config.gizmosql_username)}"
password = "{escape_for_toml(self.config.gizmosql_password)}"
tls_skip_verify = true
TOMLEOF

chown ec2-user:ec2-user /home/ec2-user/tablesleuth.toml

{pyiceberg_config}

echo "Python ${{PY_VERSION}}, pip, venv, virtualenv, git, awscli, GizmoSQL, and TableSleuth are installed and bootstrapped."
EOF

chmod +x /usr/local/bin/install_python_3_13_9.sh
/usr/local/bin/install_python_3_13_9.sh > /var/log/install_python_3_13_9.log 2>&1

# Generate TLS certificates for DuckDB server
cat << 'CERTEOF' >/usr/local/bin/gen-certs.sh
#!/bin/bash
set -eux

if ! command -v openssl &> /dev/null; then
    echo "Error: OpenSSL is not installed."
    exit 1
fi

CERT_DIR="${{1:-$HOME/.certs}}"
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

SUBJECT_ALT_NAME="DNS:$(hostname),DNS:host.docker.internal,DNS:localhost,DNS:example.com,DNS:another.example.com,IP:127.0.0.1"

openssl genrsa -out root-ca.key 4096
chmod 600 root-ca.key

openssl req -x509 -new -nodes \\
        -subj "/C=US/ST=CA/O=MyOrg, Inc./CN=Test CA" \\
        -key root-ca.key -sha256 -days 10000 \\
        -out root-ca.pem -extensions v3_ca

for i in 0 1; do
    openssl genrsa -out cert${{i}}.key 4096
    chmod 600 cert${{i}}.key

    openssl req -new -sha256 -key cert${{i}}.key \\
        -subj "/C=US/ST=CA/O=MyOrg, Inc./CN=localhost" \\
        -config <(echo "[req]
distinguished_name=req_distinguished_name
[req_distinguished_name]
[SAN]
subjectAltName=${{SUBJECT_ALT_NAME}}") \\
        -out cert${{i}}.csr

    cat > v3_usr.cnf <<EOFCERT
[ v3_usr_extensions ]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = ${{SUBJECT_ALT_NAME}}
EOFCERT

    openssl x509 -req -in cert${{i}}.csr -CA root-ca.pem -CAkey root-ca.key -CAcreateserial \\
        -out cert${{i}}.pem -days 10000 -sha256 -extfile v3_usr.cnf -extensions v3_usr_extensions

    openssl pkcs8 -in cert${{i}}.key -topk8 -nocrypt > cert${{i}}.pkcs1
done

rm -f *.csr v3_usr.cnf

echo "Certificates generated successfully in $CERT_DIR!"
ls -lh "$CERT_DIR"
CERTEOF

chmod +x /usr/local/bin/gen-certs.sh

echo "Generating TLS certificates for DuckDB server..."
su - ec2-user -c '/usr/local/bin/gen-certs.sh /home/ec2-user/.certs' > /var/log/gen-certs.log 2>&1

echo "Configuring environment variables and aliases..."
cat >> /home/ec2-user/.bashrc <<'ENVEOF'
{s3tables_env}
export AWS_REGION="{region}"
export AWS_DEFAULT_REGION="{region}"

# PyIceberg Glue catalog configuration
# Add your catalog-specific environment variables here
# Example: export PYICEBERG_CATALOG__MY_CATALOG__REGION="{region}"

# GizmoSQL configuration
export GIZMOSQL_USERNAME='{escape_for_bash_single_quote(self.config.gizmosql_username)}'
export GIZMOSQL_PASSWORD='{escape_for_bash_single_quote(self.config.gizmosql_password)}'

# GizmoSQL aliases
alias gizmosvr='gizmosql_server -U "${{GIZMOSQL_USERNAME}}" -P "${{GIZMOSQL_PASSWORD}}" -Q -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain); {gizmosql_attach}" -T ~/.certs/cert0.pem ~/.certs/cert0.key'
alias gizmo='gizmosql_client --command Execute --use-tls --tls-skip-verify --username "${{GIZMOSQL_USERNAME}}" --password "${{GIZMOSQL_PASSWORD}}"'
ENVEOF

chown ec2-user:ec2-user /home/ec2-user/.bashrc

echo "Creating GizmoSQL systemd service..."
cat > /etc/systemd/system/gizmosql.service <<'SERVICEEOF'
[Unit]
Description=GizmoSQL Server
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user
Environment="GIZMOSQL_USERNAME={escape_for_systemd(self.config.gizmosql_username)}"
Environment="GIZMOSQL_PASSWORD={escape_for_systemd(self.config.gizmosql_password)}"
ExecStart=/usr/local/bin/gizmosql_server -U "${{GIZMOSQL_USERNAME}}" -P "${{GIZMOSQL_PASSWORD}}" -Q -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain); {gizmosql_attach}" -T /home/ec2-user/.certs/cert0.pem /home/ec2-user/.certs/cert0.key
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
SERVICEEOF

echo "Enabling and starting GizmoSQL service..."
systemctl daemon-reload
systemctl enable gizmosql.service
systemctl start gizmosql.service

echo "Setup complete: Python, GizmoSQL, TableSleuth, TLS certificates, and environment variables are ready."
echo "GizmoSQL server is running as a systemd service."
"""
        return user_data

    def _create_instance(self) -> ec2.Instance:
        """Create EC2 instance with user data.

        Returns:
            EC2 instance construct
        """
        # Get latest Amazon Linux 2023 AMI
        machine_image = ec2.MachineImage.latest_amazon_linux2023(
            cpu_type=ec2.AmazonLinuxCpuType.X86_64,
        )

        # Create instance
        instance_type = ec2.InstanceType(self.config.instance_type)

        # Note: ec2.Instance construct does not support spot instances directly
        # For spot instances, you would need to use Launch Templates or Auto Scaling Groups
        # For now, we'll use on-demand instances
        if self.config.use_spot:
            print(
                "Warning: ec2.Instance construct does not support spot instances. "
                "Using on-demand instance instead. "
                "To use spot instances, consider using Launch Templates or Auto Scaling Groups."
            )

        instance = ec2.Instance(
            self,
            "TablesleuthInstance",
            instance_type=instance_type,
            machine_image=machine_image,
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=self.security_group,
            role=self.instance_role,
            key_pair=ec2.KeyPair.from_key_pair_name(
                self,
                "ImportedKeyPair",
                self.key_pair.ref,  # Use .ref for CloudFormation reference
            ),
            user_data=ec2.UserData.custom(self._get_user_data()),
            # Enable EBS encryption for security
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

        # Apply removal policy based on environment
        # For dev/test, allow destruction; for prod, retain
        instance.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

        return instance

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            "InstanceId",
            value=self.instance.instance_id,
            description="EC2 Instance ID",
        )

        CfnOutput(
            self,
            "PublicIP",
            value=self.instance.instance_public_ip,
            description="Public IP address",
        )

        CfnOutput(
            self,
            "PublicDNS",
            value=self.instance.instance_public_dns_name,
            description="Public DNS name",
        )

        CfnOutput(
            self,
            "KeyPairName",
            value=self.key_pair.key_name,
            description="EC2 Key Pair name (retrieve private key from Parameter Store)",
        )

        CfnOutput(
            self,
            "SSHCommand",
            value=f"ssh -i {self.key_pair.key_name}.pem ec2-user@{self.instance.instance_public_dns_name}",
            description="SSH command to connect to instance",
        )

        CfnOutput(
            self,
            "Region",
            value=self.config.region,
            description="AWS region",
        )

        # Note: Since ec2.Instance construct doesn't support spot instances,
        # we always use on-demand regardless of the use_spot configuration
        instance_type_str = "On-Demand"
        CfnOutput(
            self,
            "InstanceType",
            value=f"{instance_type_str} ({self.config.instance_type})",
            description="Instance type and pricing model",
        )
