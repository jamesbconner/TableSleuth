#!/usr/bin/env python
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError


# -----------------------------
# Configuration loading
# -----------------------------
def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config file. If None, looks for config.json in script directory.

    Returns:
        Dictionary containing configuration values.

    Raises:
        SystemExit: If config file not found or invalid.
    """
    if config_path is None:
        script_dir = Path(__file__).parent
        config_path = script_dir / "config.json"

    config_path = Path(config_path)

    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print(f"Please create {config_path} based on {config_path.parent / 'config.json.template'}")
        sys.exit(1)

    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file {config_path}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to load configuration file {config_path}: {e}")
        sys.exit(1)

    # Validate required fields
    required_fields = [
        "ssh_allowed_cidr",
        "gizmosql_username",
        "gizmosql_password",
    ]
    missing_fields = [field for field in required_fields if field not in config]

    if missing_fields:
        print(f"Error: Missing required fields in config: {', '.join(missing_fields)}")
        sys.exit(1)

    # Optional fields with defaults
    config.setdefault("s3tables_bucket_arn", None)
    config.setdefault("s3tables_table_arn", None)

    return config


# -----------------------------
# Configuration defaults
# -----------------------------

# Default region for all operations
DEFAULT_REGION = "us-east-2"

VPC_CIDR = "10.10.0.0/16"
SUBNET_CIDR = "10.10.1.0/24"

KEY_PAIR_NAME = "tablesleuth-ssh-key"
KEY_PAIR_PRIVATE_KEY_PATH = "./tablesleuth-ssh-key.pem"

INSTANCE_TYPE = "m4.xlarge"
SPOT_MAX_PRICE = None  # None lets AWS pick the current spot price

VPC_NAME = "tablesleuth-vpc"
SUBNET_NAME = "tablesleuth-subnet-public"
IGW_NAME = "tablesleuth-igw"
ROUTE_TABLE_NAME = "tablesleuth-public-rt"
SECURITY_GROUP_NAME = "tablesleuth-sg-ssh-only"
IAM_ROLE_NAME = "tablesleuth-ec2-s3-role"
INSTANCE_PROFILE_NAME = "tablesleuth-ec2-s3-instance-profile"

TAGS = [
    {"Key": "Project", "Value": "tablesleuth"},
    {"Key": "Owner", "Value": "tablesleuth-script"},
]

# These will be set inside main, after parsing args
ec2 = None
iam = None
ssm = None


# -----------------------------
# Helpers
# -----------------------------


def tag_resource(resource_id: str, extra_tags: dict[str, str] = None) -> None:
    tags = TAGS.copy()
    if extra_tags:
        for k, v in extra_tags.items():
            tags.append({"Key": k, "Value": v})
    ec2.create_tags(Resources=[resource_id], Tags=tags)


# -----------------------------
# Network setup (get or create)
# -----------------------------


def get_or_create_vpc() -> str:
    resp = ec2.describe_vpcs(
        Filters=[
            {"Name": "cidr-block", "Values": [VPC_CIDR]},
            {"Name": "tag:Name", "Values": [VPC_NAME]},
            {"Name": "tag:Project", "Values": ["tablesleuth"]},
        ]
    )
    vpcs = resp.get("Vpcs", [])
    if vpcs:
        vpc_id = vpcs[0]["VpcId"]
        print(f"Reusing VPC: {vpc_id}")
        tag_resource(vpc_id, {"Name": VPC_NAME})
        return vpc_id

    resp = ec2.create_vpc(CidrBlock=VPC_CIDR)
    vpc_id = resp["Vpc"]["VpcId"]
    print(f"Created VPC: {vpc_id}")
    tag_resource(vpc_id, {"Name": VPC_NAME})

    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={"Value": True})
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={"Value": True})
    return vpc_id


def get_or_create_internet_gateway(vpc_id: str) -> str:
    resp = ec2.describe_internet_gateways(
        Filters=[
            {"Name": "attachment.vpc-id", "Values": [vpc_id]},
            {"Name": "tag:Project", "Values": ["tablesleuth"]},
            {"Name": "tag:Name", "Values": [IGW_NAME]},
        ]
    )
    igws = resp.get("InternetGateways", [])
    if igws:
        igw_id = igws[0]["InternetGatewayId"]
        print(f"Reusing Internet Gateway: {igw_id}")
        tag_resource(igw_id, {"Name": IGW_NAME})
        return igw_id

    resp = ec2.describe_internet_gateways(
        Filters=[
            {"Name": "tag:Project", "Values": ["tablesleuth"]},
            {"Name": "tag:Name", "Values": [IGW_NAME]},
        ]
    )
    igws = resp.get("InternetGateways", [])
    if igws:
        igw_id = igws[0]["InternetGatewayId"]
        print(f"Found unattached IGW: {igw_id}, attaching to VPC {vpc_id}")
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        tag_resource(igw_id, {"Name": IGW_NAME})
        return igw_id

    resp = ec2.create_internet_gateway()
    igw_id = resp["InternetGateway"]["InternetGatewayId"]
    print(f"Created Internet Gateway: {igw_id}")
    tag_resource(igw_id, {"Name": IGW_NAME})

    ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
    print(f"Attached IGW {igw_id} to VPC {vpc_id}")
    return igw_id


def get_or_create_public_subnet(vpc_id: str) -> str:
    resp = ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "cidr-block", "Values": [SUBNET_CIDR]},
            {"Name": "tag:Name", "Values": [SUBNET_NAME]},
            {"Name": "tag:Project", "Values": ["tablesleuth"]},
        ]
    )
    subnets = resp.get("Subnets", [])
    if subnets:
        subnet_id = subnets[0]["SubnetId"]
        print(f"Reusing Subnet: {subnet_id}")
        tag_resource(subnet_id, {"Name": SUBNET_NAME})
        ec2.modify_subnet_attribute(
            SubnetId=subnet_id,
            MapPublicIpOnLaunch={"Value": True},
        )
        return subnet_id

    resp = ec2.create_subnet(VpcId=vpc_id, CidrBlock=SUBNET_CIDR)
    subnet_id = resp["Subnet"]["SubnetId"]
    print(f"Created Subnet: {subnet_id}")
    tag_resource(subnet_id, {"Name": SUBNET_NAME})

    ec2.modify_subnet_attribute(
        SubnetId=subnet_id,
        MapPublicIpOnLaunch={"Value": True},
    )
    return subnet_id


def get_or_create_public_route_table(vpc_id: str, igw_id: str, subnet_id: str) -> str:
    resp = ec2.describe_route_tables(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "tag:Name", "Values": [ROUTE_TABLE_NAME]},
            {"Name": "tag:Project", "Values": ["tablesleuth"]},
        ]
    )
    route_tables = resp.get("RouteTables", [])
    if route_tables:
        rt = route_tables[0]
        rt_id = rt["RouteTableId"]
        print(f"Reusing Route Table: {rt_id}")
        tag_resource(rt_id, {"Name": ROUTE_TABLE_NAME})

        has_default_route = any(
            r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("GatewayId") == igw_id
            for r in rt.get("Routes", [])
        )
        if not has_default_route:
            try:
                ec2.create_route(
                    RouteTableId=rt_id,
                    DestinationCidrBlock="0.0.0.0/0",
                    GatewayId=igw_id,
                )
                print(f"Added default route 0.0.0.0/0 to IGW {igw_id} on {rt_id}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "RouteAlreadyExists":
                    print("Default route already exists on route table")
                else:
                    raise

        associated_subnets = {
            assoc.get("SubnetId")
            for assoc in rt.get("Associations", [])
            if not assoc.get("Main", False)
        }
        if subnet_id not in associated_subnets:
            ec2.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_id)
            print(f"Associated route table {rt_id} with subnet {subnet_id}")

        return rt_id

    resp = ec2.create_route_table(VpcId=vpc_id)
    rt_id = resp["RouteTable"]["RouteTableId"]
    print(f"Created Route Table: {rt_id}")
    tag_resource(rt_id, {"Name": ROUTE_TABLE_NAME})

    ec2.create_route(
        RouteTableId=rt_id,
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=igw_id,
    )
    print(f"Created default route to IGW {igw_id}")

    ec2.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_id)
    print(f"Associated route table {rt_id} with subnet {subnet_id}")

    return rt_id


def get_or_create_security_group(vpc_id: str, config: dict[str, Any]) -> str:
    resp = ec2.describe_security_groups(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "group-name", "Values": [SECURITY_GROUP_NAME]},
        ]
    )
    sgs = resp.get("SecurityGroups", [])
    if sgs:
        sg_id = sgs[0]["GroupId"]
        print(f"Reusing Security Group: {sg_id}")
        tag_resource(sg_id, {"Name": SECURITY_GROUP_NAME})

        try:
            ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": config["ssh_allowed_cidr"]}],
                    }
                ],
            )
            print(f"Ensured SSH ingress from {config['ssh_allowed_cidr']} on SG {sg_id}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidPermission.Duplicate":
                print("SSH ingress rule already exists on security group")
            else:
                raise

        return sg_id

    resp = ec2.create_security_group(
        GroupName=SECURITY_GROUP_NAME,
        Description="SSH only security group for tablesleuth instance",
        VpcId=vpc_id,
    )
    sg_id = resp["GroupId"]
    print(f"Created Security Group: {sg_id}")
    tag_resource(sg_id, {"Name": SECURITY_GROUP_NAME})

    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": config["ssh_allowed_cidr"]}],
            }
        ],
    )

    return sg_id


# -----------------------------
# IAM setup
# -----------------------------


def create_iam_role_and_instance_profile(config: dict[str, Any]) -> str:
    assume_role_doc = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        resp = iam.create_role(
            RoleName=IAM_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(assume_role_doc),
            Description="EC2 role with S3 and S3Tables access for tablesleuth instance",
            Tags=[{"Key": t["Key"], "Value": t["Value"]} for t in TAGS],
        )
        role_arn = resp["Role"]["Arn"]
        print(f"Created IAM Role: {IAM_ROLE_NAME} ({role_arn})")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"IAM Role {IAM_ROLE_NAME} already exists, reusing")
        else:
            raise

    # Attach AWS managed policies
    iam.attach_role_policy(
        RoleName=IAM_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
    )
    print("Attached AmazonS3FullAccess to role")

    # Attach Glue read-only access for Iceberg catalog
    iam.attach_role_policy(
        RoleName=IAM_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess",
    )
    print("Attached AWSGlueConsoleFullAccess to role")

    # Inline policy for S3 Tables access
    s3tables_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowUseOfS3TablesBucketAndTables",
                "Effect": "Allow",
                "Action": [
                    "s3tables:GetTableBucket",
                    "s3tables:ListNamespaces",
                    "s3tables:GetNamespace",
                    "s3tables:ListTables",
                    "s3tables:GetTable",
                    "s3tables:GetTableMetadataLocation",
                    "s3tables:GetTableData",
                    "s3tables:PutTableData",
                ],
                "Resource": [
                    config["s3tables_bucket_arn"] or "*",
                    config["s3tables_table_arn"] or "*",
                ],
            }
        ],
    }

    # Only add S3 Tables policy if ARNs are configured
    if config["s3tables_bucket_arn"] and config["s3tables_table_arn"]:
        iam.put_role_policy(
            RoleName=IAM_ROLE_NAME,
            PolicyName="tablesleuth-s3tables-access",
            PolicyDocument=json.dumps(s3tables_policy),
        )
        print("Attached inline S3Tables policy to role")
    else:
        print("Skipping S3 Tables policy (ARNs not configured)")

    # Instance profile creation and role attachment
    try:
        iam.create_instance_profile(
            InstanceProfileName=INSTANCE_PROFILE_NAME,
            Tags=[{"Key": t["Key"], "Value": t["Value"]} for t in TAGS],
        )
        print(f"Created Instance Profile: {INSTANCE_PROFILE_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"Instance Profile {INSTANCE_PROFILE_NAME} already exists, reusing")
        else:
            raise

    try:
        iam.add_role_to_instance_profile(
            InstanceProfileName=INSTANCE_PROFILE_NAME,
            RoleName=IAM_ROLE_NAME,
        )
        print(f"Added role {IAM_ROLE_NAME} to instance profile {INSTANCE_PROFILE_NAME}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("LimitExceeded", "EntityAlreadyExists"):
            print("Role already associated with instance profile, continuing")
        else:
            raise

    # Give IAM a moment to propagate
    time.sleep(10)
    return INSTANCE_PROFILE_NAME


# -----------------------------
# Key pair
# -----------------------------


def ensure_key_pair(dry_run: bool) -> None:
    try:
        ec2.describe_key_pairs(KeyNames=[KEY_PAIR_NAME])
        print(f"Key pair {KEY_PAIR_NAME} already exists")
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidKeyPair.NotFound":
            if dry_run:
                print(
                    f"[dry-run] Would create key pair {KEY_PAIR_NAME} and save it to {KEY_PAIR_PRIVATE_KEY_PATH}"
                )
                return
            print(f"Key pair {KEY_PAIR_NAME} not found, creating")
            resp = ec2.create_key_pair(KeyName=KEY_PAIR_NAME)
            private_key = resp["KeyMaterial"]

            with open(KEY_PAIR_PRIVATE_KEY_PATH, "w") as f:
                f.write(private_key)

            os.chmod(KEY_PAIR_PRIVATE_KEY_PATH, 0o600)
            print(f"Saved private key to {KEY_PAIR_PRIVATE_KEY_PATH} and set permissions to 600")
        else:
            raise


# -----------------------------
# AMI lookup
# -----------------------------


def get_latest_amazon_linux_ami() -> str:
    param_name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    resp = ssm.get_parameter(Name=param_name)
    ami_id = resp["Parameter"]["Value"]
    print(f"Using AMI: {ami_id} from SSM parameter {param_name}")
    return ami_id


# -----------------------------
# EC2 Spot instance
# -----------------------------


def launch_instance(
    subnet_id: str,
    sg_id: str,
    instance_profile_name: str,
    ami_id: str,
    config: dict[str, Any],
    region: str,
    instance_type: str,
    use_spot: bool = False,
) -> dict[str, Any]:
    """Launch an EC2 instance (on-demand or spot).

    Args:
        subnet_id: Subnet ID for the instance
        sg_id: Security group ID
        instance_profile_name: IAM instance profile name
        ami_id: AMI ID to use
        config: Configuration dictionary with S3 Tables ARNs
        region: AWS region
        instance_type: EC2 instance type (e.g., m4.large, m4.xlarge)
        use_spot: If True, launch as spot instance; otherwise on-demand

    Returns:
        Instance information dictionary
    """
    # Build PyIceberg config conditionally
    pyiceberg_config = ""
    if config["s3tables_bucket_arn"] and config["s3tables_table_arn"]:
        pyiceberg_config = f"""
echo "Configuring PyIceberg for S3 Tables..."
cat > /home/ec2-user/.pyiceberg.yaml <<PYICEEOF
catalog:
  tpch:
    type: rest
    warehouse: {config["s3tables_bucket_arn"]}
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
    if config["s3tables_bucket_arn"] and config["s3tables_table_arn"]:
        s3tables_env = f"""
# S3 Tables configuration
export S3TABLES_BUCKET_ARN="{config["s3tables_bucket_arn"]}"
export S3TABLES_TABLE_ARN="{config["s3tables_table_arn"]}"
"""

    # Build GizmoSQL S3 Tables attachment conditionally
    gizmosql_attach = ""
    if config["s3tables_bucket_arn"]:
        gizmosql_attach = (
            "ATTACH '${S3TABLES_BUCKET_ARN}' AS tpch (TYPE iceberg, ENDPOINT_TYPE s3_tables);"
        )

    # User data writes and runs a Python 3.13.9 installer script plus git, awscli,
    # GizmoSQL CLI, and clones + bootstraps TableSleuth for ec2-user.
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

{pyiceberg_config}

echo "Python ${{PY_VERSION}}, pip, venv, virtualenv, git, awscli, GizmoSQL, and TableSleuth are installed and bootstrapped."
EOF

chmod +x /usr/local/bin/install_python_3_13_9.sh
/usr/local/bin/install_python_3_13_9.sh > /var/log/install_python_3_13_9.log 2>&1

# Generate TLS certificates for DuckDB server
cat << 'CERTEOF' >/usr/local/bin/gen-certs.sh
#!/bin/bash
set -eux

# Ensure OpenSSL is installed
if ! command -v openssl &> /dev/null; then
    echo "Error: OpenSSL is not installed."
    exit 1
fi

CERT_DIR="${{1:-$HOME/.certs}}"
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

SUBJECT_ALT_NAME="DNS:$(hostname),DNS:host.docker.internal,DNS:localhost,DNS:example.com,DNS:another.example.com,IP:127.0.0.1"

# Generate Root CA key and certificate
openssl genrsa -out root-ca.key 4096
chmod 600 root-ca.key

openssl req -x509 -new -nodes \
        -subj "/C=US/ST=CA/O=MyOrg, Inc./CN=Test CA" \
        -key root-ca.key -sha256 -days 10000 \
        -out root-ca.pem -extensions v3_ca

# Generate user certificates
for i in 0 1; do
    openssl genrsa -out cert${{i}}.key 4096
    chmod 600 cert${{i}}.key

    openssl req -new -sha256 -key cert${{i}}.key \
        -subj "/C=US/ST=CA/O=MyOrg, Inc./CN=localhost" \
        -config <(echo "[req]
distinguished_name=req_distinguished_name
[req_distinguished_name]
[SAN]
subjectAltName=${{SUBJECT_ALT_NAME}}") \
        -out cert${{i}}.csr

    cat > v3_usr.cnf <<EOF
[ v3_usr_extensions ]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = ${{SUBJECT_ALT_NAME}}
EOF

    openssl x509 -req -in cert${{i}}.csr -CA root-ca.pem -CAkey root-ca.key -CAcreateserial \
        -out cert${{i}}.pem -days 10000 -sha256 -extfile v3_usr.cnf -extensions v3_usr_extensions

    # Convert to PKCS#1 for Java
    openssl pkcs8 -in cert${{i}}.key -topk8 -nocrypt > cert${{i}}.pkcs1
done

# Clean up intermediate files
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
export PYICEBERG_CATALOG__TPCH__REGION="{region}"
export PYICEBERG_CATALOG__RATEBEER__REGION="{region}"

# GizmoSQL configuration
export GIZMOSQL_USERNAME="{config["gizmosql_username"]}"
export GIZMOSQL_PASSWORD="{config["gizmosql_password"]}"

# GizmoSQL aliases
alias gizmosvr='gizmosql_server -P "${{GIZMOSQL_PASSWORD}}" -Q -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain); {gizmosql_attach}" -T ~/.certs/cert0.pem ~/.certs/cert0.key'
alias gizmo='gizmosql_client --command Execute --use-tls --tls-skip-verify --username "${{GIZMOSQL_USERNAME}}" --password "${{GIZMOSQL_PASSWORD}}"'
ENVEOF

chown ec2-user:ec2-user /home/ec2-user/.bashrc

echo "Setup complete: Python, GizmoSQL, TableSleuth, TLS certificates, and environment variables are ready."
"""

    # Build run_instances parameters
    run_params = {
        "ImageId": ami_id,
        "InstanceType": instance_type,
        "MinCount": 1,
        "MaxCount": 1,
        "KeyName": KEY_PAIR_NAME,
        "NetworkInterfaces": [
            {
                "AssociatePublicIpAddress": True,
                "DeviceIndex": 0,
                "SubnetId": subnet_id,
                "Groups": [sg_id],
            }
        ],
        "IamInstanceProfile": {"Name": instance_profile_name},
        "UserData": user_data,
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": TAGS
                + [
                    {
                        "Key": "Name",
                        "Value": f"tablesleuth-{'spot-' if use_spot else ''}instance-{instance_type}",
                    }
                ],
            }
        ],
    }

    # Add spot market options if requested
    if use_spot:
        instance_market_options = {
            "MarketType": "spot",
            "SpotOptions": {
                "SpotInstanceType": "one-time",
                "InstanceInterruptionBehavior": "terminate",
            },
        }
        if SPOT_MAX_PRICE is not None:
            instance_market_options["SpotOptions"]["MaxPrice"] = str(SPOT_MAX_PRICE)
        run_params["InstanceMarketOptions"] = instance_market_options

    resp = ec2.run_instances(**run_params)

    instance = resp["Instances"][0]
    instance_id = instance["InstanceId"]
    instance_type = "Spot" if use_spot else "On-Demand"
    print(f"Launched {instance_type} instance: {instance_id}")
    return instance


def wait_for_instance_running(instance_id: str) -> dict[str, Any]:
    print(f"Waiting for instance {instance_id} to be running...")
    waiter = ec2.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])
    print(f"Instance {instance_id} is now running")

    desc = ec2.describe_instances(InstanceIds=[instance_id])
    return desc["Reservations"][0]["Instances"][0]


# -----------------------------
# Dry run planner
# -----------------------------


def print_plan(
    region: str, config: dict[str, Any], instance_type: str, use_spot: bool = False
) -> None:
    print("Dry run plan")
    print("============")
    print(f"Region: {region}")
    print(f"Instance Type: {'Spot (may be interrupted)' if use_spot else 'On-Demand (stable)'}")
    print(f"Instance Size: {instance_type}")
    print("")
    print("Resources that would be created or reused:")
    print(f"- VPC: {VPC_NAME} ({VPC_CIDR})")
    print(f"- Public Subnet: {SUBNET_NAME} ({SUBNET_CIDR})")
    print(f"- Internet Gateway: {IGW_NAME}")
    print(f"- Route table: {ROUTE_TABLE_NAME} with default route 0.0.0.0/0 to IGW")
    print(f"- Security group: {SECURITY_GROUP_NAME}")
    print(f"  - Inbound: TCP 22 from {config['ssh_allowed_cidr']}")
    print("  - Outbound: allow all (default)")
    print(f"- IAM role: {IAM_ROLE_NAME} with AmazonS3FullAccess")
    print(f"- Inline S3Tables policy for bucket: {config['s3tables_bucket_arn']}")
    print(f"- Instance profile: {INSTANCE_PROFILE_NAME}")
    instance_type_str = "Spot" if use_spot else "On-Demand"
    print(
        f"- EC2 {instance_type_str} instance: type {instance_type}, Amazon Linux 2023 AMI, public IP,"
    )
    print("  with user data that installs Python 3.13.9, git, awscli, GizmoSQL,")
    print("  and bootstraps TableSleuth including .venv and uv sync.")
    print(
        f"- Key pair: {KEY_PAIR_NAME} (private key path {KEY_PAIR_PRIVATE_KEY_PATH}) if it does not already exist"
    )
    print("")
    print("Instance capabilities:")
    print("- SSH access only, from your IP")
    print("- Outbound internet for package installs and external sites")
    print("- Read and write access to S3 buckets in this account (via AmazonS3FullAccess)")
    print("- S3 Tables Iceberg access through S3Tables inline policy")
    print("- Python 3.13.9, git, awscli, GizmoSQL CLI")
    print("- Global python, python3, pip, pip3 mapped to the 3.13 toolchain")
    print("- /home/ec2-user/py313-venv ready to go")
    print("- TableSleuth repo at ~/Code/TableSleuth with .venv and uv dependencies installed")
    print("- Environment variables: S3TABLES_BUCKET_ARN, S3TABLES_TABLE_ARN, AWS_REGION")
    print("- GizmoSQL configuration: GIZMOSQL_USERNAME, GIZMOSQL_PASSWORD")
    print("- GizmoSQL aliases: gizmosvr (start server), gizmo (client)")


# -----------------------------
# Main flow
# -----------------------------


def main():
    parser = argparse.ArgumentParser(description="Create tablesleuth EC2 environment")
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region to use (default: {DEFAULT_REGION})",
    )
    parser.add_argument(
        "--config",
        help="Path to configuration JSON file (default: config.json in script directory)",
    )
    parser.add_argument(
        "--instance-type",
        default=INSTANCE_TYPE,
        help=f"EC2 instance type (default: {INSTANCE_TYPE})",
    )
    parser.add_argument(
        "--use-spot",
        action="store_true",
        help="Use Spot instance instead of On-Demand (may be interrupted)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created or reused and exit without making changes",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    if args.dry_run:
        print_plan(args.region, config, args.instance_type, args.use_spot)
        return

    global ec2, iam, ssm
    ec2 = boto3.client("ec2", region_name=args.region)
    iam = boto3.client("iam", region_name=args.region)
    ssm = boto3.client("ssm", region_name=args.region)

    print("Ensuring key pair exists...")
    ensure_key_pair(dry_run=False)

    print("Getting or creating VPC...")
    vpc_id = get_or_create_vpc()

    print("Getting or creating Internet Gateway...")
    igw_id = get_or_create_internet_gateway(vpc_id)

    print("Getting or creating public subnet...")
    subnet_id = get_or_create_public_subnet(vpc_id)

    print("Getting or creating route table and default route...")
    get_or_create_public_route_table(vpc_id, igw_id, subnet_id)

    print("Getting or creating security group...")
    sg_id = get_or_create_security_group(vpc_id, config)

    print("Creating IAM role and instance profile...")
    instance_profile_name = create_iam_role_and_instance_profile(config)

    print("Looking up latest Amazon Linux AMI...")
    ami_id = get_latest_amazon_linux_ami()

    instance_type_str = "Spot instance" if args.use_spot else "On-Demand instance"
    print(f"Launching {instance_type_str} ({args.instance_type})...")
    instance = launch_instance(
        subnet_id,
        sg_id,
        instance_profile_name,
        ami_id,
        config,
        args.region,
        args.instance_type,
        args.use_spot,
    )
    instance_id = instance["InstanceId"]

    instance_desc = wait_for_instance_running(instance_id)

    public_ip = instance_desc.get("PublicIpAddress")
    public_dns = instance_desc.get("PublicDnsName")

    print("\n" + "=" * 80)
    print("Instance ready")
    print("=" * 80)
    print(f"Instance ID: {instance_id}")
    print(f"Instance Type: {instance_type_str} ({args.instance_type})")
    print(f"Public IP: {public_ip}")
    print(f"Public DNS: {public_dns}")
    print(f"Region: {args.region}")

    print("\n" + "=" * 80)
    print("SSH Access")
    print("=" * 80)
    print(f"ssh -i {KEY_PAIR_PRIVATE_KEY_PATH} ec2-user@{public_dns}")

    print("\n" + "=" * 80)
    print("On the instance")
    print("=" * 80)
    print("cd ~/Code/TableSleuth")
    print("source .venv/bin/activate")
    print("python --version  # should show 3.13.9")
    print("\n# Start GizmoSQL server with S3 Tables attached:")
    print("gizmosvr")
    print("\n# In another terminal, connect with GizmoSQL client:")
    print("gizmo")

    print("\n" + "=" * 80)
    print("Instance Management Commands")
    print("=" * 80)
    print("# Stop instance (saves costs, can restart later):")
    print(f"aws ec2 stop-instances --instance-ids {instance_id} --region {args.region}")
    print("\n# Start instance (after stopping):")
    print(f"aws ec2 start-instances --instance-ids {instance_id} --region {args.region}")
    print("\n# Terminate instance (permanent deletion):")
    print(f"aws ec2 terminate-instances --instance-ids {instance_id} --region {args.region}")
    print("\n# Check instance status:")
    print(
        f"aws ec2 describe-instances --instance-ids {instance_id} --region {args.region} --query 'Reservations[0].Instances[0].State.Name' --output text"
    )

    if not args.use_spot:
        print("\n" + "=" * 80)
        print("⚠️  COST WARNING - On-Demand Instance")
        print("=" * 80)
        print("This is an On-Demand instance that will continue running (and charging)")
        print("until you stop or terminate it. Remember to stop/terminate when done!")
        print("\nQuick stop command:")
        print(f"  aws ec2 stop-instances --instance-ids {instance_id} --region {args.region}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
