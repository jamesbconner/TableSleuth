# Creating Iceberg Delete Files for Testing

## Problem

To properly test Iceberg merge-on-read functionality, we need to create **position delete files** or **equality delete files**. However, most Python libraries don't support this natively.

## Current Situation

- **PyIceberg**: The `table.delete()` method falls back to copy-on-write and rewrites data files instead of creating delete files
- **DuckDB**: The Iceberg extension is read-only and doesn't support DELETE operations
- **PySpark**: Can create proper delete files but requires Java/JVM to be installed

## Options

### Option 1: Install Java and Use PySpark (Recommended)

PySpark with Iceberg support can properly create delete files.

**Requirements:**
- Java 11 or 17 installed
- PySpark (already in dependencies)

**Installation:**
```bash
# On macOS with Homebrew
brew install openjdk@17

# Add to shell profile (~/.zshrc or ~/.bash_profile)
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export PATH="$JAVA_HOME/bin:$PATH"

# Reload shell
source ~/.zshrc
```

**Usage:**
```bash
# Dry run
python scripts/create_delete_files_spark.py ratebeer.reviews "overall = 9" --dry-run

# Actual delete (creates delete files)
python scripts/create_delete_files_spark.py ratebeer.reviews "overall = 9"
```

### Option 2: Manually Create Delete Files

We can manually create Iceberg delete files using PyIceberg's lower-level APIs. This requires:
1. Reading the data files to identify records to delete
2. Creating position delete files in Avro format
3. Updating the table metadata with new manifest files

This is complex but doesn't require Java.

### Option 3: Use Pre-existing Test Data

Find or create a test dataset that already has delete files. This could be:
- Downloaded from Iceberg test suites
- Created once with PySpark and committed to the repository
- Generated using Iceberg's Java CLI tools

### Option 4: Use Iceberg REST Catalog with Write Support

Some Iceberg REST catalog implementations support DELETE operations that create delete files. However, this requires setting up additional infrastructure.

## Recommendation

**Install Java and use PySpark** (Option 1). This is the most straightforward approach and aligns with standard Iceberg workflows. Java is a common requirement for big data tools anyway.

## Current Scripts

- `scripts/create_delete_files.py` - PyIceberg (doesn't create delete files, falls back to COW)
- `scripts/create_delete_files_spark.py` - PySpark (requires Java, creates proper delete files)
- `scripts/create_delete_files_duckdb.py` - DuckDB (read-only, can't perform deletes)

## Testing Without Delete Files

If you can't install Java immediately, you can still test other aspects:
- Reading Iceberg tables
- Snapshot management
- Schema evolution
- Partition evolution
- Time travel queries

Delete file handling can be added later once Java is available.
