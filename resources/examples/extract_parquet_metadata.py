#!/usr/bin/env python
"""Example: Extract Parquet metadata programmatically.

Demonstrates using ParquetService to extract metadata without TUI:
- Schema information
- Row group statistics
- Column statistics
- File-level metadata

Prerequisites:
    - pyarrow: pip install pyarrow

Usage:
    python resources/examples/extract_parquet_metadata.py file.parquet
    python resources/examples/extract_parquet_metadata.py file.parquet --output json
    python resources/examples/extract_parquet_metadata.py s3://bucket/path/file.parquet
"""

import argparse
import json
import sys

from tablesleuth.services.parquet_service import ParquetService


def extract_metadata(file_path: str, output_format: str = "text"):
    """Extract comprehensive metadata from a Parquet file."""
    print(f"Extracting metadata from: {file_path}")
    print("=" * 80)

    service = ParquetService()

    # Get file metadata
    try:
        metadata = service.get_file_metadata(file_path)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    # Build metadata dictionary
    result = {
        "file_path": file_path,
        "num_rows": metadata.num_rows,
        "num_row_groups": metadata.num_row_groups,
        "num_columns": metadata.num_columns,
        "created_by": metadata.created_by,
        "format_version": metadata.format_version,
        "serialized_size": metadata.serialized_size,
        "schema": [],
        "row_groups": [],
    }

    # Extract schema
    schema = metadata.schema
    for i in range(len(schema)):
        col = schema.column(i)
        result["schema"].append(
            {
                "name": col.name,
                "physical_type": col.physical_type,
                "logical_type": str(col.logical_type) if col.logical_type else None,
                "max_definition_level": col.max_definition_level,
                "max_repetition_level": col.max_repetition_level,
            }
        )

    # Extract row group statistics
    for rg_idx in range(metadata.num_row_groups):
        rg = metadata.row_group(rg_idx)
        rg_info = {
            "index": rg_idx,
            "num_rows": rg.num_rows,
            "total_byte_size": rg.total_byte_size,
            "columns": [],
        }

        for col_idx in range(rg.num_columns):
            col = rg.column(col_idx)
            col_info = {
                "path": col.path_in_schema,
                "compression": col.compression,
                "total_compressed_size": col.total_compressed_size,
                "total_uncompressed_size": col.total_uncompressed_size,
            }

            # Add statistics if available
            if col.is_stats_set:
                stats = col.statistics
                col_info["statistics"] = {
                    "min": str(stats.min) if stats.has_min_max else None,
                    "max": str(stats.max) if stats.has_min_max else None,
                    "null_count": stats.null_count,
                    "distinct_count": stats.distinct_count if stats.has_distinct_count else None,
                }

            rg_info["columns"].append(col_info)

        result["row_groups"].append(rg_info)

    # Output results
    if output_format == "json":
        print(json.dumps(result, indent=2))
    else:
        # Pretty print summary
        print(f"\nFile: {result['file_path']}")
        print(f"Rows: {result['num_rows']:,}")
        print(f"Row Groups: {result['num_row_groups']}")
        print(f"Columns: {result['num_columns']}")
        print(f"Created by: {result['created_by']}")
        print(f"Format version: {result['format_version']}")

        print(f"\nSchema:")
        for col in result["schema"]:
            logical = f" ({col['logical_type']})" if col["logical_type"] else ""
            print(f"  - {col['name']}: {col['physical_type']}{logical}")

        print(f"\nRow Groups:")
        for rg in result["row_groups"]:
            print(f"\n  Row Group {rg['index']}:")
            print(f"    Rows: {rg['num_rows']:,}")
            print(f"    Size: {rg['total_byte_size'] / 1024**2:.2f} MB")

            # Show compression stats for first row group
            if rg["index"] == 0:
                print(f"    Columns:")
                for col in rg["columns"][:5]:  # Show first 5 columns
                    compression_ratio = (
                        col["total_uncompressed_size"] / col["total_compressed_size"]
                        if col["total_compressed_size"] > 0
                        else 1.0
                    )
                    print(f"      - {col['path']}: {col['compression']} ({compression_ratio:.2f}x)")

                    if "statistics" in col and col["statistics"]["min"]:
                        stats = col["statistics"]
                        print(f"        Min: {stats['min']}, Max: {stats['max']}")
                        print(f"        Nulls: {stats['null_count']}")

        # Calculate totals
        total_compressed = sum(
            col["total_compressed_size"]
            for rg in result["row_groups"]
            for col in rg["columns"]
        )
        total_uncompressed = sum(
            col["total_uncompressed_size"]
            for rg in result["row_groups"]
            for col in rg["columns"]
        )

        print(f"\nTotals:")
        print(f"  Compressed size: {total_compressed / 1024**2:.2f} MB")
        print(f"  Uncompressed size: {total_uncompressed / 1024**2:.2f} MB")
        print(f"  Compression ratio: {total_uncompressed / total_compressed:.2f}x")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract Parquet metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract and display summary
  python resources/examples/extract_parquet_metadata.py file.parquet

  # Extract as JSON
  python resources/examples/extract_parquet_metadata.py file.parquet --output json

  # Extract from S3
  python resources/examples/extract_parquet_metadata.py s3://bucket/path/file.parquet
        """,
    )
    parser.add_argument("file", help="Parquet file path (local or S3)")
    parser.add_argument(
        "--output", choices=["json", "text"], default="text", help="Output format"
    )

    args = parser.parse_args()
    extract_metadata(args.file, args.output)
