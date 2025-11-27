#!/usr/bin/env python
import argparse
import time

import boto3
from botocore.exceptions import ClientError

DEFAULT_REGION = "us-east-2"
PROJECT_TAG_KEY = "Project"
PROJECT_TAG_VALUE = "tablesleuth"

VPC_NAME = "tablesleuth-vpc"
SECURITY_GROUP_NAME = "tablesleuth-sg-ssh-only"
ROUTE_TABLE_NAME = "tablesleuth-public-rt"
IAM_ROLE_NAME = "tablesleuth-ec2-s3-role"
INSTANCE_PROFILE_NAME = "tablesleuth-ec2-s3-instance-profile"


def find_vpc(ec2):
    resp = ec2.describe_vpcs(
        Filters=[
            {"Name": f"tag:{PROJECT_TAG_KEY}", "Values": [PROJECT_TAG_VALUE]},
            {"Name": "tag:Name", "Values": [VPC_NAME]},
        ]
    )
    vpcs = resp.get("Vpcs", [])
    if not vpcs:
        return None
    return vpcs[0]["VpcId"]


def terminate_instances(ec2, vpc_id):
    resp = ec2.describe_instances(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": f"tag:{PROJECT_TAG_KEY}", "Values": [PROJECT_TAG_VALUE]},
            {
                "Name": "instance-state-name",
                "Values": ["pending", "running", "stopping", "stopped"],
            },
        ]
    )
    instance_ids = []
    for res in resp.get("Reservations", []):
        for inst in res.get("Instances", []):
            instance_ids.append(inst["InstanceId"])

    if not instance_ids:
        print("No instances to terminate")
        return

    print(f"Terminating instances: {instance_ids}")
    ec2.terminate_instances(InstanceIds=instance_ids)

    waiter = ec2.get_waiter("instance_terminated")
    waiter.wait(InstanceIds=instance_ids)
    print("Instances terminated")


def delete_security_group(ec2, vpc_id):
    resp = ec2.describe_security_groups(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "group-name", "Values": [SECURITY_GROUP_NAME]},
        ]
    )
    sgs = resp.get("SecurityGroups", [])
    if not sgs:
        print("No security group to delete")
        return
    sg_id = sgs[0]["GroupId"]
    print(f"Deleting security group {sg_id}")
    ec2.delete_security_group(GroupId=sg_id)


def delete_route_table(ec2, vpc_id):
    resp = ec2.describe_route_tables(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "tag:Name", "Values": [ROUTE_TABLE_NAME]},
        ]
    )
    rts = resp.get("RouteTables", [])
    if not rts:
        print("No route table to delete")
        return
    rt = rts[0]
    rt_id = rt["RouteTableId"]

    # Disassociate subnets
    for assoc in rt.get("Associations", []):
        if not assoc.get("Main", False):
            assoc_id = assoc["RouteTableAssociationId"]
            print(f"Disassociating route table association {assoc_id}")
            ec2.disassociate_route_table(AssociationId=assoc_id)

    # Delete routes that point to IGW (other than local)
    for route in rt.get("Routes", []):
        if (
            route.get("GatewayId", "").startswith("igw-")
            and route.get("DestinationCidrBlock") == "0.0.0.0/0"
        ):
            print(f"Deleting route to {route['DestinationCidrBlock']} via {route['GatewayId']}")
            ec2.delete_route(RouteTableId=rt_id, DestinationCidrBlock="0.0.0.0/0")

    print(f"Deleting route table {rt_id}")
    ec2.delete_route_table(RouteTableId=rt_id)


def delete_internet_gateway(ec2, vpc_id):
    resp = ec2.describe_internet_gateways(
        Filters=[
            {"Name": f"tag:{PROJECT_TAG_KEY}", "Values": [PROJECT_TAG_VALUE]},
        ]
    )
    igws = resp.get("InternetGateways", [])
    if not igws:
        print("No internet gateway to delete")
        return
    igw = igws[0]
    igw_id = igw["InternetGatewayId"]

    # Detach from VPC
    for attach in igw.get("Attachments", []):
        if attach.get("VpcId") == vpc_id:
            print(f"Detaching IGW {igw_id} from VPC {vpc_id}")
            ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)

    print(f"Deleting internet gateway {igw_id}")
    ec2.delete_internet_gateway(InternetGatewayId=igw_id)


def delete_subnets(ec2, vpc_id):
    resp = ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": f"tag:{PROJECT_TAG_KEY}", "Values": [PROJECT_TAG_VALUE]},
        ]
    )
    subnets = resp.get("Subnets", [])
    if not subnets:
        print("No subnets to delete")
        return

    for subnet in subnets:
        subnet_id = subnet["SubnetId"]
        print(f"Deleting subnet {subnet_id}")
        ec2.delete_subnet(SubnetId=subnet_id)


def delete_vpc(ec2, vpc_id):
    print(f"Deleting VPC {vpc_id}")
    ec2.delete_vpc(VpcId=vpc_id)


def cleanup_iam(iam):
    # Delete inline S3Tables policy from role
    try:
        iam.delete_role_policy(
            RoleName=IAM_ROLE_NAME,
            PolicyName="tablesleuth-s3tables-access",
        )
        print(f"Deleted inline S3Tables policy from role {IAM_ROLE_NAME}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code != "NoSuchEntity":
            print(f"Warning: delete_role_policy failed: {e}")

    # Detach S3 policy from role
    try:
        iam.detach_role_policy(
            RoleName=IAM_ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
        )
        print(f"Detached AmazonS3FullAccess from role {IAM_ROLE_NAME}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code != "NoSuchEntity":
            print(f"Warning: detach_role_policy failed: {e}")

    # Remove role from instance profile
    try:
        iam.remove_role_from_instance_profile(
            InstanceProfileName=INSTANCE_PROFILE_NAME,
            RoleName=IAM_ROLE_NAME,
        )
        print(f"Removed role {IAM_ROLE_NAME} from instance profile {INSTANCE_PROFILE_NAME}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code != "NoSuchEntity":
            print(f"Warning: remove_role_from_instance_profile failed: {e}")

    # Delete instance profile
    try:
        iam.delete_instance_profile(InstanceProfileName=INSTANCE_PROFILE_NAME)
        print(f"Deleted instance profile {INSTANCE_PROFILE_NAME}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code != "NoSuchEntity":
            print(f"Warning: delete_instance_profile failed: {e}")

    # Delete role
    try:
        iam.delete_role(RoleName=IAM_ROLE_NAME)
        print(f"Deleted IAM role {IAM_ROLE_NAME}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code != "NoSuchEntity":
            print(f"Warning: delete_role failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Tear down tablesleuth EC2 Spot environment")
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region to use (default: {DEFAULT_REGION})",
    )
    args = parser.parse_args()

    ec2 = boto3.client("ec2", region_name=args.region)
    iam = boto3.client("iam", region_name=args.region)

    vpc_id = find_vpc(ec2)
    if not vpc_id:
        print("No tablesleuth VPC found. Nothing to tear down.")
        return

    print(f"Found VPC {vpc_id} for tablesleuth. Starting teardown.")

    terminate_instances(ec2, vpc_id)
    # Wait a bit in case network interfaces are still cleaning up
    time.sleep(5)

    delete_security_group(ec2, vpc_id)
    delete_route_table(ec2, vpc_id)
    delete_internet_gateway(ec2, vpc_id)
    delete_subnets(ec2, vpc_id)
    delete_vpc(ec2, vpc_id)

    cleanup_iam(iam)

    print(
        "Teardown complete. You may still have a key pair and local PEM file to remove manually if desired."
    )


if __name__ == "__main__":
    main()
