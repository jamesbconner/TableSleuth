#!/usr/bin/env python
"""Example: Inspect AWS S3 Tables Iceberg tables.

This script demonstrates how to use TableSleuth to inspect Iceberg tables
stored in AWS S3 Tables service using ARN-based references.

Prerequisites:
    - AWS credentials configured (aws configure or environment variables)
    - S3 Tables permissions (GetTable, GetTableData, etc.)
    - PyIceberg with AWS extras: pip install "pyiceberg[glue,s3fs]"

Usage:
    python resources/examples/inspect_s3_tables.py
"""

from tablesleuth.services.formats.iceberg import IcebergAdapter


def inspect_s3_table_by_arn():
    """Inspect an S3 Tables Iceberg table using its ARN."""
    # Example S3 Tables ARN (replace with your actual ARN)
    table_arn = "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.customer"

    print(f"Inspecting S3 Table: {table_arn}")
    print("=" * 80)

    # Initialize adapter
    adapter = IcebergAdapter()

    # Open table using ARN
    table_handle = adapter.open_table(table_arn)

    print(f"\nTable Format: {table_handle.format_name}")
    print(f"Native Table Type: {type(table_handle.native).__name__}")

    # Get table metadata
    table = table_handle.native
    print(f"\nTable Location: {table.metadata.location}")

    # Handle both Table and StaticTable types
    identifier = getattr(table, "identifier", "N/A")
    print(f"Table Identifier: {identifier}")

    # List snapshots
    snapshots = adapter.list_snapshots(table_handle)
    print(f"\nTotal Snapshots: {len(snapshots)}")

    if snapshots:
        latest = snapshots[-1]
        print("\nLatest Snapshot:")
        print(f"  ID: {latest.snapshot_id}")
        print(f"  Timestamp: {latest.timestamp_ms}")
        print(f"  Operation: {latest.operation}")
        print(f"  Data Files: {len(latest.data_files)}")
        print(f"  Delete Files: {len(latest.delete_files)}")

        # Show summary
        if latest.summary:
            print("\n  Summary:")
            for key, value in latest.summary.items():
                print(f"    {key}: {value}")

    # Get data files
    print("\nFetching data files...")
    data_files = adapter.get_data_files(table_arn)

    print(f"Total Data Files: {len(data_files)}")

    if data_files:
        print("\nFirst 5 Data Files:")
        for i, file in enumerate(data_files[:5], 1):
            print(f"\n  File {i}:")
            print(f"    Path: {file.path}")
            print(f"    Size: {file.file_size_bytes:,} bytes")
            print(f"    Records: {file.record_count:,}")
            if file.partition:
                print(f"    Partition: {file.partition}")

        # Calculate totals
        total_size = sum(f.file_size_bytes for f in data_files)
        total_records = sum(f.record_count for f in data_files if f.record_count is not None)

        print("\nTotals:")
        print(f"  Total Size: {total_size:,} bytes ({total_size / 1024**3:.2f} GB)")
        print(f"  Total Records: {total_records:,}")
        print(f"  Average File Size: {total_size / len(data_files):,.0f} bytes")
        if total_records > 0:
            files_with_counts = [f for f in data_files if f.record_count is not None]
            if files_with_counts:
                print(f"  Average Records per File: {total_records / len(files_with_counts):,.0f}")


def inspect_s3_table_by_catalog():
    """Inspect an S3 Tables Iceberg table using catalog name."""
    # Example using catalog name
    table_identifier = "tpch.customer"
    catalog_name = "s3tables"

    print(f"\nInspecting S3 Table: {table_identifier} (catalog: {catalog_name})")
    print("=" * 80)

    adapter = IcebergAdapter()

    # Open table using catalog
    table_handle = adapter.open_table(table_identifier, catalog_name=catalog_name)

    print(f"Table Format: {table_handle.format_name}")

    # Get data files
    data_files = adapter.get_data_files(table_identifier, catalog_name=catalog_name)
    print(f"Total Data Files: {len(data_files)}")


def test_arn_parsing():
    """Test S3 Tables ARN parsing."""
    print("\nTesting ARN Parsing")
    print("=" * 80)

    adapter = IcebergAdapter()

    test_arns = [
        "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.customer",
        "arn:aws:s3tables:eu-west-1:123456789012:bucket/my-bucket/table/db.schema.table",
        "not-an-arn",
        "db.table",
    ]

    for arn in test_arns:
        result = adapter._parse_s3_tables_arn(arn)
        if result:
            catalog, table = result
            print(f"✓ {arn}")
            print(f"  → Catalog: {catalog}, Table: {table}")
        else:
            print(f"✗ {arn}")
            print("  → Not an S3 Tables ARN")


if __name__ == "__main__":
    print("AWS S3 Tables Inspection Example")
    print("=" * 80)

    # Test ARN parsing first
    test_arn_parsing()

    # Uncomment to inspect actual S3 Tables (requires AWS credentials)
    # inspect_s3_table_by_arn()
    # inspect_s3_table_by_catalog()

    print("\n" + "=" * 80)
    print("To inspect actual S3 Tables, uncomment the function calls above")
    print("and ensure you have AWS credentials configured.")
