# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - 2026-01-18

### Changed

- **⚠️ BREAKING CHANGE: CLI Command Renamed** - `inspect` command renamed to `parquet`
  - The Parquet file analysis command has been renamed from `inspect` to `parquet` to establish a consistent format-oriented command structure
  - This change aligns the CLI with a clear pattern where top-level commands correspond to table format types
  - All functionality remains identical - only the command name has changed

### Migration Guide

**Update your command invocations:**

```bash
# Old (v0.4.x and earlier)
tablesleuth inspect data.parquet
tablesleuth inspect data.parquet --profile

# New (v0.5.0 and later)
tablesleuth parquet data.parquet
tablesleuth parquet data.parquet --profile
```

**Update your scripts and automation:**
- Replace all instances of `tablesleuth inspect` with `tablesleuth parquet`
- All command-line arguments and options remain unchanged
- Output format and behavior are identical

**Rationale:**
This change establishes a consistent, format-oriented command structure that improves clarity and supports future extensibility. The CLI now follows a clear pattern:
- `tablesleuth parquet <path>` - Analyze Parquet files
- `tablesleuth iceberg <metadata>` - Analyze Iceberg tables
- Future: `tablesleuth delta <path>` - Analyze Delta Lake tables (planned for v1.0.0)

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
