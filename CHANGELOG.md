# Changelog

All notable changes to this project will be documented in this file.

## [0.5.3] - 2026-01-25

### Changed

- **CLI Architecture Refactored** - Modular command structure with auto-loading
  - Split monolithic CLI file into focused command modules
  - Each command now in its own file: `init.py`, `config_check.py`, `parquet.py`, `iceberg.py`, `delta.py`
  - Implemented dynamic command discovery - new commands auto-register by convention
  - Shared utilities extracted to `helpers.py` module
  - Improved maintainability: 1000+ lines → ~200 lines per module (80% reduction)
  - Enhanced extensibility: adding new commands requires only dropping a file in `cli/` directory
  - All 110 CLI tests updated and passing
  - **Impact:** Significantly improved code organization and developer experience

- **Service Layer Improvements** - Enhanced abstraction and reduced coupling
  - **DeltaLogFileSystem abstraction** - Unified filesystem interface for Delta transaction logs
    - Eliminated ~250 lines of duplicated filesystem handling code
    - Single API for local and cloud storage operations
    - Reduced method complexity by 40% in forensics methods
  - **SnapshotPerformanceAnalyzer refactoring** - Explicit interface validation
    - Removed incomplete fallback logic that created misleading metrics
    - Added fail-fast validation at initialization with clear error messages
    - Eliminated code duplication: reduced from ~150 lines to ~90 lines (40% reduction)
    - Reduced cyclomatic complexity by 50% (8 → 4)
    - **Breaking change:** Profilers must implement `execute_query_with_metrics()` method

- **Code Metrics:**
  - Eliminated ~310 lines of duplicated code
  - Reduced complexity by 40-50% across refactored methods
  - All 165+ tests passing (110 CLI + 39 forensics + 16 analyzer)

### Documentation
- Updated architecture documentation to reflect modular CLI structure


## [0.5.2] - 2026-01-25

### Added

- **AWS CDK Infrastructure** - Production-ready CDK implementation for EC2 deployment
  - Complete infrastructure-as-code implementation replacing legacy boto3 scripts
  - Multi-environment support (dev, staging, prod) with CDK context-based configuration
  - Type-safe configuration using dataclasses and environment variables (no config.json anti-pattern)
  - Automated GizmoSQL service setup with systemd (auto-starts on boot)
  - Complete PyIceberg Glue integration pre-configured
  - Security best practices: least-privilege IAM, EBS encryption, VPC Flow Logs
  - Change preview with `cdk diff` before deployment
  - Comprehensive documentation in `resources/aws-cdk/`
- **Enhanced Iceberg Performance Analysis** - Comprehensive multi-factor performance comparison
  - Order-agnostic analysis that works regardless of snapshot chronology
  - Multi-factor attribution analyzing: data volume, file counts, MOR overhead, delete ratios, record counts, scan efficiency
  - Accurate MOR overhead detection (only shown when delete files actually exist)
  - Read amplification metrics comparing snapshots (e.g., 1.45x vs 1.00x)
  - Detailed contributing factors with specific metrics and percentages
  - Actionable compaction recommendations with specific thresholds (delete ratio > 10%, read amplification > 1.5x)
  - Comprehensive analysis output showing all performance factors, not just one

### Changed

- **AWS Deployment** - Migrated from boto3 scripts to AWS CDK
  - Removed legacy boto3 deployment scripts
  - Removed `config.json.template` in favor of CDK context and environment variables
  - Moved CDK infrastructure from `cdk/` to `resources/aws-cdk/`
  - Consolidated CDK documentation from 9 files to 5 files
- **PyIceberg Glue Integration** - Simplified dependency management
  - Added `glue` to main PyIceberg dependency: `pyiceberg[s3fs,sql-sqlite,glue]>=0.9.1`
  - Removed need for separate `tablesleuth[glue]` installation
  - Updated all documentation to reflect simplified installation
- **Performance Analysis** - Complete rewrite of `PerformanceComparison.analysis()` method
  - Changed from tracking delete file counts to passing full `IcebergSnapshotInfo` objects
  - Analyzes which snapshot is slower without assuming order
  - Considers multiple factors simultaneously instead of single-factor attribution
  - Provides structured output with bullet points and recommendations

### Fixed

- **MOR Overhead False Positive** - Fixed incorrect attribution of performance differences to MOR overhead
  - Performance analysis no longer assumes snapshot B is newer than snapshot A
  - MOR overhead only mentioned when slower snapshot has more delete files AND higher read amplification
  - Performance differences due to data volume now correctly identified with file count metrics
  - Analysis considers all contributing factors, not just delete files

### Documentation

- Updated README.md with v0.5.1 features and CDK deployment details
- Added `debug/MOR_OVERHEAD_FIX.md` documenting comprehensive performance analysis improvements
- Updated `resources/aws-cdk/README.md` with complete CDK deployment guide
- Consolidated CDK documentation (removed redundant Windows guide, merged spot instance limitation)
- Updated all GizmoSQL references to include full initialization commands
- Standardized GIZMOSQL_USERNAME and GIZMOSQL_PASSWORD references across documentation

## [0.5.0] - 2026-01-21

### Added

- **Glue Hive Table Support** - `parquet` command now supports AWS Glue Hive tables
  - Added `--region` flag to specify AWS region for Glue catalog queries
  - Automatic fallback from Iceberg to Glue Hive tables when catalog not found in `.pyiceberg.yaml`
  - Region resolution follows AWS conventions: `--region` flag > `AWS_REGION` env > `AWS_DEFAULT_REGION` env > default (`us-east-2`)
  - Helpful error messages when tables not found, with suggestions for troubleshooting
  - Detects Iceberg tables in Glue and provides configuration guidance
  - Caution: This is very slow to load if operated against a large table due to reading files for row counts.
- **Delta Lake Support** - Comprehensive forensic analysis for Delta Lake tables
  - New `delta` command for inspecting Delta Lake tables (local and S3)
  - Version history navigation and time travel support (`--version` flag)
  - File size analysis with small file detection and OPTIMIZE recommendations
  - Storage waste analysis tracking tombstoned files and reclaimable storage
  - DML operation forensics analyzing MERGE, UPDATE, DELETE with rewrite amplification
  - Z-Order effectiveness monitoring with data skipping metrics
  - Checkpoint health assessment with transaction log analysis
  - Intelligent optimization recommendations with priority levels (high/medium/low)
  - Partition distribution analysis with skew detection
  - Rewrite amplification trend tracking across operations
  - Support for cloud storage options (S3, Azure, GCS) via `--storage-option` flags
  - Schema change indicator in version history (asterisk marks versions with schema changes)
- **Delta Lake Services**
  - `DeltaAdapter` - Protocol-compliant adapter for Delta tables
  - `DeltaLogParser` - Transaction log parsing with commit info extraction
  - `DeltaForensics` - Static forensic analysis methods for optimization insights
- **Testing** - Comprehensive test suite with 78% overall coverage
  - 23 property-based tests using hypothesis (100 iterations each)
  - 29 unit tests for Delta forensics service
  - 33 unit tests for Delta adapter
  - 49 CLI tests covering all commands and options
  - Integration tests for adapter and protocol compliance
  - Parser tests for transaction log formats

### Changed

- **⚠️ BREAKING CHANGE: CLI Command Renamed** - `inspect` command renamed to `parquet`
  - The Parquet file analysis command has been renamed from `inspect` to `parquet` to establish a consistent format-oriented command structure
  - This change aligns the CLI with a clear pattern where top-level commands correspond to table format types
  - All functionality remains identical - only the command name has changed
- `parquet` command now tries Iceberg catalog first, then falls back to Glue database lookup
- Enhanced error messages for catalog-related failures with actionable suggestions
- Updated package description to explicitly mention Delta Lake support
- Added "delta-lake" to package keywords for better discoverability
- Enhanced documentation with Delta Lake features and examples
- **Refactored Delta Path Handling** - Eliminated code duplication
  - Extracted `get_filesystem_and_path()` into shared `delta_utils.py` module
  - Removed wrapper methods from both `DeltaAdapter` and `DeltaForensics`
  - Both classes now call the utility function directly
  - Reduces maintenance burden and ensures consistent behavior
  - Any future path handling fixes only need to be applied once
  - Code reduction: ~160 lines → ~100 lines (37% reduction)

### Documentation

- Added Delta Lake features section to README.md
- Added comprehensive Delta Lake guide to USER_GUIDE.md
- Updated CLI help text to include Delta Lake capabilities
- Created Delta Lake integration plan and implementation summary

### Performance

- **Delta Lake Version History Loading** - Fixed quadratic complexity (O(N²) → O(N))
  - Refactored `list_snapshots()` to use incremental state building
  - Each version file is now parsed exactly once instead of repeatedly
  - Performance improvement: 25x faster for 50 versions, 500x faster for 1000 versions
  - For a table with 1000 versions: ~180 seconds → ~0.36 seconds
  - Memory usage remains constant (O(F) where F = max active files)
  - Makes the tool usable for production Delta tables with substantial history

### Fixed

- S3 path discovery now properly handles S3 URIs (s3://bucket/path) for both single files and directories
- **s3a:// URI scheme support** - S3 paths using `s3a://` scheme (common in Spark/EMR) are now properly handled alongside `s3://` paths in all components (CLI, file discovery, and TUI display)
- **Non-Parquet S3 file error handling** - S3 files without `.parquet` or `.pq` extensions now raise a clear `ValueError` instead of silently returning an empty list
- **File list display consistency** - TUI file list now correctly strips both `s3://` and `s3a://` prefixes for consistent path display
- Glue Hive tables with S3 locations are now correctly discovered and inspected
- S3 file discovery now reads Parquet metadata to populate row counts (previously showed as None)
- File list view now displays partition directories in paths instead of just filenames, making it easier to distinguish files in partitioned tables
- Direct S3 path inspection now works correctly (e.g., `tablesleuth parquet s3://bucket/path/file.parquet`)
- Glue fallback error detection is now more specific - only triggers when catalog is missing from `.pyiceberg.yaml`, not when tables don't exist in a configured catalog
- Glue fallback now works correctly with mixed-case catalog names (e.g., "RateBeer")

### Migration Guide

**Update your command invocations:**

```bash
# Old (v0.4.x and earlier)
tablesleuth inspect data.parquet

# New (v0.5.0 and later)
tablesleuth parquet data.parquet
```

**Update your scripts and automation:**
- Replace all instances of `tablesleuth inspect` with `tablesleuth parquet`
- All command-line arguments and options remain unchanged
- Output format and behavior are identical

**Rationale:**
This change establishes a consistent, format-oriented command structure that improves clarity and supports future extensibility. The CLI now follows a clear pattern:
- `tablesleuth parquet <path>` - Analyze Parquet files
- `tablesleuth iceberg <metadata>` - Analyze Iceberg tables

This naming pattern makes it immediately clear which command analyzes which table format, improving the user experience and making the tool more intuitive for new users.

## [0.4.2.post1] - 2026-01-17

### Fixed
- **PyPI Package Display** - Fixed broken image links on PyPI project page
  - Changed relative image paths to absolute GitHub URLs
  - Images now display correctly on https://pypi.org/project/tablesleuth/
  - Uses `raw.githubusercontent.com` URLs for reliable image hosting

## [0.4.2] - 2026-01-17

### Added
- **Configuration Management Commands**
  - `tablesleuth init` - Interactive configuration file initialization
    - Creates `tablesleuth.toml` and `.pyiceberg.yaml` with comprehensive templates
    - Prompts for home directory (~/) or current directory (./) placement
    - Includes `--force` flag to overwrite existing files
    - Generates well-commented templates with multiple catalog examples
  - `tablesleuth config-check` - Configuration validation and testing
    - Validates all configuration files and syntax
    - Tests GizmoSQL connection
    - Checks PyIceberg catalog configuration
    - Shows configuration precedence and active values
    - Supports `-v/--verbose` flag for detailed output

### Changed
- **Configuration File Locations** - Simplified configuration paths
  - Removed `~/.config/tablesleuth/` directory approach
  - Now supports: `./tablesleuth.toml` (local) and `~/tablesleuth.toml` (home)
  - PyIceberg config: `./.pyiceberg.yaml` (local) and `~/.pyiceberg.yaml` (home)
  - Respects `PYICEBERG_HOME` environment variable for PyIceberg config location

- **Configuration Priority** - Clear precedence order
  1. Environment variables (`TABLESLEUTH_*`, `PYICEBERG_*`)
  2. Local config files (current directory)
  3. Home config files (home directory)
  4. Built-in defaults

- **Environment Variable Support**
  - `TABLESLEUTH_CONFIG` - Override config file path
  - Existing: `TABLESLEUTH_CATALOG_NAME`, `TABLESLEUTH_GIZMO_*`
  - PyIceberg native: `PYICEBERG_HOME`

- **Configuration File Renamed** - Consistency with package name
  - `table_sleuth.toml` → `tablesleuth.toml`
  - Updated all documentation and code references

### Fixed
- **Configuration Error Handling** - Improved error messages and handling
  - Fixed unhandled `FileNotFoundError` in `inspect` and `iceberg` commands when `TABLESLEUTH_CONFIG` points to non-existent file
  - Fixed unhandled exception in `config-check` command with invalid `TABLESLEUTH_CONFIG` environment variable
  - Both commands now show helpful error messages suggesting `tablesleuth init` instead of tracebacks
  - Added proper try-except blocks around `load_config()` calls in main CLI commands
  - Fixed misleading "No config file found (using defaults)" message after `TABLESLEUTH_CONFIG` error
  - Fixed incorrect init suggestion for non-config FileNotFoundError in `iceberg` command

- **Configuration Template TOML Syntax** - Fixed invalid TOML in generated config
  - Changed `default = null` to commented `# default = ""` (TOML doesn't support null type)
  - Generated config files now parse correctly without `TOMLDecodeError`
  - Affects `tablesleuth init` command output

- **Configuration Init Command** - Improved Windows compatibility
  - Removed backup file creation when using `--force` flag
  - Files are now directly overwritten instead of being backed up
  - Fixes Windows `FileExistsError` when running `init --force` multiple times
  - Simplifies the init process

- **S3 Tables Catalog Configuration** - Fixed incorrect catalog type and improved flexibility
  - Changed S3 Tables catalog from `type: glue` to `type: rest` with proper REST API settings
  - Added required REST API configuration: `uri`, `rest.sigv4-enabled`, `rest.signing-name`, `rest.signing-region`
  - Fixed hardcoded catalog name - now supports multiple S3 Tables catalogs
  - Users can specify which S3 Tables catalog to use with `--catalog` flag when using ARNs
  - Default catalog name "s3tables" is used when ARN is provided without `--catalog` flag
  - Added clear documentation and usage examples in template showing multiple S3 Tables catalogs
  - Clarified difference between Glue catalog and S3 Tables catalog

- **GizmoSQL Optional Component Handling** - Made GizmoSQL truly optional
  - `config-check` command no longer fails when GizmoSQL connection fails
  - Added `--with-gizmosql` flag to explicitly test GizmoSQL connection
  - GizmoSQL test is now skipped by default (shown as "⊘ Skipped")
  - Exit code 0 (success) when only optional components fail
  - Consistent with other optional checks like missing PyIceberg config

### Dependencies
- Added `pyyaml>=6.0.0` for PyIceberg config validation

## [0.4.1] - 2026-01-17

### Changed
- **Python Module Renamed to `tablesleuth`** - Complete consistency across package
  - Module directory renamed from `table_sleuth` to `tablesleuth`
  - All imports now use `from tablesleuth import ...`
  - Eliminates confusion between package name and import name
  - **Breaking Change:** Update all imports from `table_sleuth` to `tablesleuth`

### Migration
If upgrading from v0.4.0 (unreleased), update your imports:
```python
# Old
from table_sleuth import __version__
from table_sleuth.services import ParquetInspector

# New
from tablesleuth import __version__
from tablesleuth.services import ParquetInspector
```

## [0.4.0] - 2026-01-16 (Unreleased)

### Changed
- **Package Renamed to `tablesleuth`** - Unified package name for PyPI distribution
  - CLI command changed from `table-sleuth` to `tablesleuth`
  - Package name now matches tablesleuth.com domain
  - Improved discoverability on PyPI
- **Version Management** - Consolidated version to single source of truth in `__init__.py`
  - Removed hardcoded version from CLI
  - Version now imported from package
- **Enhanced PyPI Metadata**
  - Upgraded development status from Alpha to Beta
  - Added comprehensive classifiers for better discoverability
  - Added project URLs including homepage, documentation, and changelog
  - Added publishing tools (twine, build) to dev dependencies

### Added
- **GitHub Actions CI/CD** - Automated testing and publishing workflows
  - Multi-platform testing (Ubuntu, macOS, Windows)
  - Multi-version Python testing (3.13, 3.14)
  - Automated quality checks (ruff, mypy, bandit)
  - Automated PyPI publishing on release
  - Support for PyPI Trusted Publishing
- **PyPI Publishing Guide** - Comprehensive documentation for package publishing
  - Step-by-step publishing instructions
  - TestPyPI testing workflow
  - Automated release process documentation
  - Troubleshooting guide

## [0.3.0] - 2025-11-29

### Added
- **Strict MyPy Type Checking** - Comprehensive type annotations across the codebase
  - Enabled strict mypy configuration with `disallow_untyped_defs`, `disallow_incomplete_defs`, and `warn_return_any`
  - Added proper type annotations to all service classes and methods
  - Configured per-module overrides for third-party libraries without type stubs
  - Integrated mypy into pre-commit hooks with all required dependencies
  - Zero type errors in production code (only expected import-untyped warnings for PyArrow)

- **Enhanced Documentation**
  - Streamlined README.md with high-level feature overview and screenshot galleries
  - Organized documentation with clear navigation to detailed guides
  - Added visual comparison tables for Parquet and Iceberg interfaces
  - Improved quick start examples and configuration guidance

- **UI Improvements**
  - Removed subtitle from TUI header for cleaner interface
  - Updated application title to "Table Sleuth - Parquet Analysis"

### Changed
- **Code Quality Improvements**
  - Fixed import paths for IcebergAdapter (moved to `formats.iceberg`)
  - Removed unreachable backwards compatibility code in gizmo_duckdb.py
  - Added explicit type casts where needed for type safety
  - Improved error handling with proper type annotations

- **Pre-commit Configuration**
  - Added all required dependencies to mypy pre-commit hook
  - Configured proper module overrides for untyped libraries (pyarrow, fsspec, s3fs, etc.)
  - All pre-commit hooks now pass cleanly

### Fixed
- Type annotation issues in FileDiscoveryService, ParquetInspector, and GizmoDuckDbProfiler
- Missing return type annotations across multiple service classes
- Unused type ignore comments after fixing import paths
- Event handler type annotations in TUI views

## [Unreleased]

### Added

#### Performance Profiling for Merge-on-Read
- **Added performance profiling models** (`QueryPerformanceProfile`, `MergeOnReadPerformance`)
  - Measures query execution time with and without delete file application
  - Calculates merge-on-read overhead in milliseconds and percentage
  - Tracks rows scanned, rows returned, and rows deleted
  - Provides timing breakdown for data file scan, delete file scan, and merge operations
- **Extended ProfilingBackend protocol** with `profile_query_performance()` method
  - Allows backends to implement performance profiling
  - Optional method - backends can raise `NotImplementedError` if not supported
- **Comprehensive test suite** for performance profiling models
  - Tests overhead calculation, edge cases, and zero-division handling
- **Updated product specification** with performance profiling user story
  - Story 6: Performance profiling for merge-on-read queries
  - Helps engineers make data-driven decisions about table compaction
