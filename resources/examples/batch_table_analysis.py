#!/usr/bin/env python
"""Example: Batch analyze multiple Iceberg tables.

Demonstrates analyzing multiple tables to generate a health report:
- Table sizes
- Snapshot counts
- File counts
- MOR overhead

Prerequisites:
    - PyIceberg with appropriate catalog extras
    - Configured .pyiceberg.yaml for catalog access

Usage:
    python resources/examples/batch_table_analysis.py --catalog local --tables db.table1,db.table2
    python resources/examples/batch_table_analysis.py --catalog glue --tables mydb.table1,mydb.table2,mydb.table3
"""

import argparse
import sys

from tablesleuth.services.formats.iceberg import IcebergAdapter


def analyze_table(adapter: IcebergAdapter, catalog: str, table: str) -> dict:
    """Analyze a single table and return metrics."""
    try:
        table_handle = adapter.open_table(table, catalog_name=catalog)
        snapshots = adapter.list_snapshots(table_handle)

        if not snapshots:
            return {"table": table, "error": "No snapshots"}

        latest = snapshots[-1]

        # Calculate metrics
        total_size = sum(f.file_size_bytes for f in latest.data_files)
        total_records = sum(f.record_count for f in latest.data_files if f.record_count is not None)

        # Calculate average file size
        avg_file_size_mb = (
            (total_size / len(latest.data_files) / 1024**2) if latest.data_files else 0
        )

        # Calculate MOR overhead
        mor_overhead_pct = (
            (len(latest.delete_files) / len(latest.data_files) * 100) if latest.data_files else 0
        )

        # Identify small files
        small_files = sum(1 for f in latest.data_files if f.file_size_bytes < 10 * 1024**2)  # <10MB
        small_files_pct = (small_files / len(latest.data_files) * 100) if latest.data_files else 0

        return {
            "table": table,
            "snapshots": len(snapshots),
            "data_files": len(latest.data_files),
            "delete_files": len(latest.delete_files),
            "total_size_gb": total_size / 1024**3,
            "total_records": total_records,
            "avg_file_size_mb": avg_file_size_mb,
            "mor_overhead_pct": mor_overhead_pct,
            "small_files": small_files,
            "small_files_pct": small_files_pct,
            "latest_operation": latest.operation,
        }
    except Exception as e:
        return {"table": table, "error": str(e)}


def batch_analyze(catalog: str, tables: list[str]):
    """Analyze multiple tables and generate report."""
    print(f"Analyzing {len(tables)} tables from catalog: {catalog}")
    print("=" * 80)

    adapter = IcebergAdapter()
    results = []

    for table in tables:
        print(f"\nAnalyzing: {table}...", end=" ")
        result = analyze_table(adapter, catalog, table)
        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            print("✓")
        results.append(result)

    # Generate report
    print("\n" + "=" * 80)
    print("ANALYSIS REPORT")
    print("=" * 80)

    for result in results:
        print(f"\n{result['table']}:")
        if "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  Snapshots: {result['snapshots']}")
            print(f"  Latest operation: {result['latest_operation']}")
            print(f"  Data files: {result['data_files']}")
            print(f"  Delete files: {result['delete_files']}")
            print(f"  Total size: {result['total_size_gb']:.2f} GB")
            print(f"  Total records: {result['total_records']:,}")
            print(f"  Avg file size: {result['avg_file_size_mb']:.2f} MB")
            print(f"  MOR overhead: {result['mor_overhead_pct']:.1f}%")
            print(
                f"  Small files (<10MB): {result['small_files']} ({result['small_files_pct']:.1f}%)"
            )

            # Health indicators
            issues = []
            if result["mor_overhead_pct"] > 20:
                issues.append("High MOR overhead")
            if result["small_files_pct"] > 30:
                issues.append("Many small files")
            if result["avg_file_size_mb"] < 50:
                issues.append("Low average file size")

            if issues:
                print(f"  ⚠️  Issues: {', '.join(issues)}")
            else:
                print("  ✓ Healthy")

    # Summary statistics
    successful = [r for r in results if "error" not in r]
    if successful:
        total_size = sum(r["total_size_gb"] for r in successful)
        total_files = sum(r["data_files"] for r in successful)
        total_records = sum(r["total_records"] for r in successful)
        avg_mor = sum(r["mor_overhead_pct"] for r in successful) / len(successful)
        avg_small_files = sum(r["small_files_pct"] for r in successful) / len(successful)

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Tables analyzed: {len(successful)}/{len(results)}")
        print(f"Total storage: {total_size:.2f} GB")
        print(f"Total data files: {total_files:,}")
        print(f"Total records: {total_records:,}")
        print(f"Average MOR overhead: {avg_mor:.1f}%")
        print(f"Average small files: {avg_small_files:.1f}%")

        # Overall health assessment
        print("\n" + "=" * 80)
        print("HEALTH ASSESSMENT")
        print("=" * 80)

        unhealthy_tables = [
            r["table"]
            for r in successful
            if r["mor_overhead_pct"] > 20 or r["small_files_pct"] > 30
        ]

        if unhealthy_tables:
            print(f"\n⚠️  {len(unhealthy_tables)} table(s) need attention:")
            for table in unhealthy_tables:
                print(f"  - {table}")
            print("\nRecommendations:")
            print("  - Run compaction on tables with high MOR overhead")
            print("  - Run OPTIMIZE on tables with many small files")
        else:
            print("\n✓ All tables are healthy!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch analyze Iceberg tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze multiple tables from local catalog
  python resources/examples/batch_table_analysis.py --catalog local --tables db.table1,db.table2

  # Analyze tables from Glue catalog
  python resources/examples/batch_table_analysis.py --catalog glue --tables mydb.orders,mydb.customers,mydb.products
        """,
    )
    parser.add_argument("--catalog", required=True, help="Catalog name")
    parser.add_argument(
        "--tables",
        required=True,
        help="Comma-separated table identifiers (e.g., db.table1,db.table2)",
    )

    args = parser.parse_args()
    tables = [t.strip() for t in args.tables.split(",")]

    if not tables:
        print("Error: No tables specified")
        sys.exit(1)

    batch_analyze(args.catalog, tables)
