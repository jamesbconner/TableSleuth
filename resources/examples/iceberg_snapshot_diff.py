#!/usr/bin/env python
"""Example: Compare two Iceberg snapshots.

Demonstrates comparing snapshots to understand:
- File additions/deletions
- Record count changes
- Schema evolution
- Partition changes

Prerequisites:
    - PyIceberg with appropriate catalog extras
    - Configured .pyiceberg.yaml for catalog access

Usage:
    python resources/examples/iceberg_snapshot_diff.py --catalog local --table db.table --from 123 --to 456
"""

import argparse
import sys

from tablesleuth.services.formats.iceberg import IcebergAdapter


def compare_snapshots(catalog: str, table: str, snapshot_from: int, snapshot_to: int):
    """Compare two snapshots and show differences."""
    print(f"Comparing snapshots: {snapshot_from} → {snapshot_to}")
    print("=" * 80)

    adapter = IcebergAdapter()

    try:
        table_handle = adapter.open_table(table, catalog_name=catalog)
    except Exception as e:
        print(f"Error opening table: {e}")
        sys.exit(1)

    # Load both snapshots
    try:
        snap_from = adapter.load_snapshot(table_handle, snapshot_from)
        snap_to = adapter.load_snapshot(table_handle, snapshot_to)
    except ValueError as e:
        print(f"Error loading snapshots: {e}")
        sys.exit(1)

    # Compare operations
    print(f"\nSnapshot {snapshot_from}:")
    print(f"  Operation: {snap_from.operation}")
    print(f"  Timestamp: {snap_from.timestamp_ms}")
    print(f"  Data files: {len(snap_from.data_files)}")
    print(f"  Delete files: {len(snap_from.delete_files)}")

    print(f"\nSnapshot {snapshot_to}:")
    print(f"  Operation: {snap_to.operation}")
    print(f"  Timestamp: {snap_to.timestamp_ms}")
    print(f"  Data files: {len(snap_to.data_files)}")
    print(f"  Delete files: {len(snap_to.delete_files)}")

    # Calculate differences
    files_added = len(snap_to.data_files) - len(snap_from.data_files)
    deletes_added = len(snap_to.delete_files) - len(snap_from.delete_files)

    print("\n" + "=" * 80)
    print("CHANGES")
    print("=" * 80)
    print(f"Data files: {files_added:+d}")
    print(f"Delete files: {deletes_added:+d}")

    # Calculate size changes
    size_from = sum(f.file_size_bytes for f in snap_from.data_files)
    size_to = sum(f.file_size_bytes for f in snap_to.data_files)
    size_change = size_to - size_from

    print("\nStorage:")
    print(f"  From: {size_from / 1024**3:.2f} GB")
    print(f"  To: {size_to / 1024**3:.2f} GB")
    print(f"  Change: {size_change / 1024**3:+.2f} GB")

    # Calculate record changes
    records_from = sum(f.record_count for f in snap_from.data_files if f.record_count is not None)
    records_to = sum(f.record_count for f in snap_to.data_files if f.record_count is not None)
    records_change = records_to - records_from

    print("\nRecords:")
    print(f"  From: {records_from:,}")
    print(f"  To: {records_to:,}")
    print(f"  Change: {records_change:+,}")

    # Show summary changes
    if snap_from.summary and snap_to.summary:
        print("\nSummary changes:")
        changed = False
        for key in snap_to.summary:
            if key in snap_from.summary:
                old_val = snap_from.summary[key]
                new_val = snap_to.summary[key]
                if old_val != new_val:
                    print(f"  {key}: {old_val} → {new_val}")
                    changed = True
        if not changed:
            print("  (no changes)")

    # Analyze file changes in detail
    print("\n" + "=" * 80)
    print("FILE ANALYSIS")
    print("=" * 80)

    # Get file paths for comparison
    files_from_paths = {f.path for f in snap_from.data_files}
    files_to_paths = {f.path for f in snap_to.data_files}

    added_files = files_to_paths - files_from_paths
    removed_files = files_from_paths - files_to_paths

    print(f"Files added: {len(added_files)}")
    print(f"Files removed: {len(removed_files)}")
    print(f"Files unchanged: {len(files_from_paths & files_to_paths)}")

    if added_files:
        print("\nFirst 5 added files:")
        for i, path in enumerate(list(added_files)[:5], 1):
            print(f"  {i}. {path}")

    if removed_files:
        print("\nFirst 5 removed files:")
        for i, path in enumerate(list(removed_files)[:5], 1):
            print(f"  {i}. {path}")

    # MOR analysis
    print("\n" + "=" * 80)
    print("MERGE-ON-READ (MOR) ANALYSIS")
    print("=" * 80)

    mor_from = (
        len(snap_from.delete_files) / len(snap_from.data_files) * 100 if snap_from.data_files else 0
    )
    mor_to = len(snap_to.delete_files) / len(snap_to.data_files) * 100 if snap_to.data_files else 0

    print(f"MOR overhead (from): {mor_from:.1f}%")
    print(f"MOR overhead (to): {mor_to:.1f}%")
    print(f"Change: {mor_to - mor_from:+.1f}%")

    if mor_to > 20:
        print("\n⚠️  WARNING: High MOR overhead detected!")
        print("   Consider running compaction to merge delete files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare Iceberg snapshots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python resources/examples/iceberg_snapshot_diff.py --catalog local --table db.table --from 123 --to 456
  python resources/examples/iceberg_snapshot_diff.py --catalog glue --table mydb.mytable --from 100 --to 105
        """,
    )
    parser.add_argument("--catalog", required=True, help="Catalog name")
    parser.add_argument("--table", required=True, help="Table identifier (e.g., db.table)")
    parser.add_argument(
        "--from", dest="snapshot_from", type=int, required=True, help="From snapshot ID"
    )
    parser.add_argument("--to", dest="snapshot_to", type=int, required=True, help="To snapshot ID")

    args = parser.parse_args()
    compare_snapshots(args.catalog, args.table, args.snapshot_from, args.snapshot_to)
