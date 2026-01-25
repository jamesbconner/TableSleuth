#!/usr/bin/env python
"""Example: Delta Lake table forensics and optimization analysis.

Demonstrates using TableSleuth to analyze Delta tables for:
- Small file problems
- Storage waste (tombstones)
- DML operation patterns
- Optimization recommendations

Prerequisites:
    - deltalake package: pip install deltalake
    - AWS credentials (if analyzing S3 tables)

Usage:
    python resources/examples/delta_forensics.py path/to/delta/table
    python resources/examples/delta_forensics.py s3://bucket/path/to/delta/table
"""

import sys
from pathlib import Path

from tablesleuth.services.delta_forensics import DeltaForensics
from tablesleuth.services.formats.delta import DeltaAdapter


def analyze_delta_table(table_path: str):
    """Perform comprehensive Delta table analysis."""
    print(f"Analyzing Delta table: {table_path}")
    print("=" * 80)

    # Initialize adapter
    adapter = DeltaAdapter()

    # Open table
    try:
        table_handle = adapter.open_table(table_path)
    except Exception as e:
        print(f"Error opening table: {e}")
        sys.exit(1)

    # Get version history
    snapshots = adapter.list_snapshots(table_handle)
    print(f"\nTotal versions: {len(snapshots)}")

    if not snapshots:
        print("No versions found in table")
        return

    # Get current snapshot for analysis
    current_snapshot = snapshots[0]  # Most recent snapshot

    # Analyze file sizes (static method)
    print("\n" + "=" * 80)
    print("FILE SIZE ANALYSIS")
    print("=" * 80)

    file_analysis = DeltaForensics.analyze_file_sizes(current_snapshot)
    print(f"Total files: {file_analysis['total_file_count']}")
    print(f"Small files (<10MB): {file_analysis['small_file_count']}")
    print(f"Small files percentage: {file_analysis['small_file_percentage']:.1f}%")
    print(f"Median file size: {file_analysis['median_size_bytes'] / 1024**2:.2f} MB")

    if file_analysis["small_file_percentage"] > 30:
        print("\n⚠️  WARNING: High percentage of small files detected!")
        print("   Consider running OPTIMIZE to compact files")

    # Analyze storage waste (static method)
    print("\n" + "=" * 80)
    print("STORAGE WASTE ANALYSIS")
    print("=" * 80)

    waste_analysis = DeltaForensics.analyze_storage_waste(snapshots)
    print(f"Tombstoned files: {waste_analysis['tombstoned_file_count']}")
    print(f"Tombstoned size: {waste_analysis['tombstoned_size_bytes'] / 1024**3:.2f} GB")
    print(f"Reclaimable percentage: {waste_analysis['reclaimable_percentage']:.1f}%")

    if waste_analysis["reclaimable_percentage"] > 20:
        print("\n⚠️  WARNING: Significant storage waste detected!")
        print("   Consider running VACUUM to reclaim space")

    # Analyze DML operations (static method)
    print("\n" + "=" * 80)
    print("DML OPERATION ANALYSIS")
    print("=" * 80)

    dml_analysis = DeltaForensics.analyze_dml_operation(snapshots)
    print(f"Total operations: {dml_analysis['total_operations']}")
    print(f"MERGE operations: {dml_analysis['merge_operations']}")
    print(f"UPDATE operations: {dml_analysis['update_operations']}")
    print(f"DELETE operations: {dml_analysis['delete_operations']}")
    print(f"Average rewrite amplification: {dml_analysis['avg_rewrite_amplification']:.2f}x")

    if dml_analysis["avg_rewrite_amplification"] > 5:
        print("\n⚠️  WARNING: High rewrite amplification detected!")
        print("   Consider using partition pruning or Z-ORDER")

    # Get recommendations (static method)
    print("\n" + "=" * 80)
    print("OPTIMIZATION RECOMMENDATIONS")
    print("=" * 80)

    recommendations = DeltaForensics.get_recommendations(
        file_analysis, waste_analysis, dml_analysis, {}, {}
    )

    if not recommendations:
        print("\n✓ No optimization recommendations - table is healthy!")
    else:
        for i, rec in enumerate(recommendations, 1):
            priority_icon = (
                "🔴" if rec["priority"] == "high" else "🟡" if rec["priority"] == "medium" else "🟢"
            )
            print(f"\n{i}. {priority_icon} {rec['title']} (Priority: {rec['priority'].upper()})")
            print(f"   {rec['description']}")
            if rec.get("action"):
                print(f"   Action: {rec['action']}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Table: {table_path}")
    print(f"Versions: {len(snapshots)}")
    print(f"Files: {file_analysis['total_file_count']}")
    print(f"Total size: {file_analysis['total_size_bytes'] / 1024**3:.2f} GB")
    print(f"Recommendations: {len(recommendations)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python resources/examples/delta_forensics.py <table_path>")
        print("\nExamples:")
        print("  python resources/examples/delta_forensics.py ./data/events/")
        print("  python resources/examples/delta_forensics.py s3://bucket/warehouse/events/")
        sys.exit(1)

    analyze_delta_table(sys.argv[1])
