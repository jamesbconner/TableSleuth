#!/usr/bin/env python
"""Example: Discover Parquet files from multiple sources.

Demonstrates using FileDiscoveryService to find Parquet files from:
- Local directories
- S3 paths
- Iceberg tables
- Glue databases

Prerequisites:
    - boto3 (for S3 and Glue): pip install boto3
    - PyIceberg (for Iceberg tables): pip install pyiceberg

Usage:
    python resources/examples/discover_parquet_files.py --path /data/warehouse
    python resources/examples/discover_parquet_files.py --path s3://bucket/path/
    python resources/examples/discover_parquet_files.py --catalog local --table db.table
"""

import argparse
import sys

from tablesleuth.services.file_discovery import FileDiscoveryService
from tablesleuth.services.formats.iceberg import IcebergAdapter


def discover_from_path(path: str):
    """Discover Parquet files from a path."""
    print(f"Discovering files from: {path}")
    print("=" * 80)

    discovery = FileDiscoveryService()

    try:
        files = discovery.discover_from_path(path)
    except Exception as e:
        print(f"Error discovering files: {e}")
        sys.exit(1)

    print(f"\nFound {len(files)} Parquet files")

    if not files:
        print("No Parquet files found")
        return

    # Calculate statistics
    total_size = sum(f.file_size_bytes for f in files if f.file_size_bytes)
    total_rows = sum(f.record_count for f in files if f.record_count)

    print("\nStatistics:")
    print(f"  Total size: {total_size / 1024**3:.2f} GB")
    if total_rows > 0:
        print(f"  Total rows: {total_rows:,}")
    print(f"  Average file size: {total_size / len(files) / 1024**2:.2f} MB")

    # File size distribution
    small_files = sum(1 for f in files if f.file_size_bytes and f.file_size_bytes < 10 * 1024**2)
    medium_files = sum(
        1 for f in files if f.file_size_bytes and 10 * 1024**2 <= f.file_size_bytes < 100 * 1024**2
    )
    large_files = sum(1 for f in files if f.file_size_bytes and f.file_size_bytes >= 100 * 1024**2)

    print("\nFile size distribution:")
    print(f"  Small (<10MB): {small_files}")
    print(f"  Medium (10-100MB): {medium_files}")
    print(f"  Large (>100MB): {large_files}")

    # Show first few files
    print("\nFirst 5 files:")
    for i, file in enumerate(files[:5], 1):
        print(f"\n  {i}. {file.path}")
        if file.file_size_bytes:
            print(f"     Size: {file.file_size_bytes / 1024**2:.2f} MB")
        if file.record_count:
            print(f"     Rows: {file.record_count:,}")
        if file.source:
            print(f"     Source: {file.source}")


def discover_from_table(catalog: str, table: str):
    """Discover Parquet files from an Iceberg table."""
    print(f"Discovering files from table: {table} (catalog: {catalog})")
    print("=" * 80)

    adapter = IcebergAdapter()
    discovery = FileDiscoveryService(iceberg_adapter=adapter)

    try:
        files = discovery.discover_from_table(table, catalog)
    except Exception as e:
        print(f"Error discovering files: {e}")
        sys.exit(1)

    print(f"\nFound {len(files)} data files")

    if not files:
        print("No data files found")
        return

    # Calculate statistics
    total_size = sum(f.file_size_bytes for f in files if f.file_size_bytes)
    total_rows = sum(f.record_count for f in files if f.record_count)

    print("\nStatistics:")
    print(f"  Total size: {total_size / 1024**3:.2f} GB")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Average file size: {total_size / len(files) / 1024**2:.2f} MB")

    # Group by partition
    partitioned_files = {}
    for file in files:
        partition_key = str(file.partition) if file.partition else "unpartitioned"
        if partition_key not in partitioned_files:
            partitioned_files[partition_key] = []
        partitioned_files[partition_key].append(file)

    print(f"\nPartitions: {len(partitioned_files)}")

    # Show partition distribution
    if len(partitioned_files) <= 10:
        for partition, partition_files in partitioned_files.items():
            partition_size = sum(f.file_size_bytes for f in partition_files if f.file_size_bytes)
            print(f"  {partition}: {len(partition_files)} files, {partition_size / 1024**2:.2f} MB")
    else:
        # Show top 10 partitions by file count
        sorted_partitions = sorted(partitioned_files.items(), key=lambda x: len(x[1]), reverse=True)
        print("\nTop 10 partitions by file count:")
        for partition, partition_files in sorted_partitions[:10]:
            partition_size = sum(f.file_size_bytes for f in partition_files if f.file_size_bytes)
            print(f"  {partition}: {len(partition_files)} files, {partition_size / 1024**2:.2f} MB")

    # Show first few files
    print("\nFirst 5 files:")
    for i, file in enumerate(files[:5], 1):
        print(f"\n  {i}. {file.path}")
        if file.file_size_bytes:
            print(f"     Size: {file.file_size_bytes / 1024**2:.2f} MB")
        if file.record_count:
            print(f"     Rows: {file.record_count:,}")
        if file.partition:
            print(f"     Partition: {file.partition}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Discover Parquet files from various sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover from local directory
  python resources/examples/discover_parquet_files.py --path /data/warehouse

  # Discover from S3
  python resources/examples/discover_parquet_files.py --path s3://bucket/warehouse/

  # Discover from Iceberg table
  python resources/examples/discover_parquet_files.py --catalog local --table db.table
        """,
    )
    parser.add_argument("--path", help="Local or S3 path to scan")
    parser.add_argument("--catalog", help="Iceberg catalog name")
    parser.add_argument("--table", help="Table identifier (e.g., db.table)")

    args = parser.parse_args()

    if args.path:
        discover_from_path(args.path)
    elif args.catalog and args.table:
        discover_from_table(args.catalog, args.table)
    else:
        print("Error: Provide either --path or both --catalog and --table")
        parser.print_help()
        sys.exit(1)
