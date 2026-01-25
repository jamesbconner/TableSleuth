# TableSleuth Quick Reference

## Installation

```bash
# From PyPI (recommended)
pip install tablesleuth

# From source
git clone https://github.com/jamesbconner/TableSleuth
cd TableSleuth
uv sync
```

## Basic Usage

```bash
# Inspect a Parquet file
tablesleuth parquet file.parquet

# Inspect a directory
tablesleuth parquet /path/to/data/

# Inspect S3 file
tablesleuth parquet s3://bucket/path/file.parquet

# Inspect Iceberg table from catalog
tablesleuth iceberg --catalog local --table db.table

# Inspect Iceberg table from metadata file
tablesleuth iceberg /path/to/metadata.json

# Inspect AWS S3 Tables (use parquet command with ARN)
tablesleuth parquet "arn:aws:s3tables:region:account:bucket/name/table/db.table"
```

## Development Commands

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
make test
pytest

# Run tests with coverage
make test-cov
pytest --cov=tablesleuth --cov-report=html

# Run linter
make lint
uv run ruff check .

# Format code
make format
uv run ruff format .

# Type checking
make type-check
uv run mypy src

# Security scan
make security
uv run bandit -c pyproject.toml -r src/

# Run all quality checks
make check

# Run pre-commit hooks
make pre-commit
uv run pre-commit run --all-files
```

## Build & Release

```bash
# Clean build artifacts
make clean

# Build package
make build
uv build

# Check package
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*

# Create release tag
git tag -a v0.4.0 -m "Release v0.4.0"
git push origin v0.4.0
```

## Version Management

```bash
# Update version (edit this file only)
vim src/tablesleuth/__init__.py

# Update changelog
vim CHANGELOG.md

# Verify version
python -c "from tablesleuth import __version__; print(__version__)"

# Build and verify
uv build
python -m zipfile -l dist/tablesleuth-*.whl | grep METADATA
```

## TUI Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `r` | Refresh current view |
| `f` | Filter columns |
| `Tab` | Switch between tabs |
| `↑/↓` | Navigate up/down |
| `←/→` | Navigate left/right |
| `Enter` | Select item |
| `Esc` | Cancel/Go back |
| `?` | Show help |

## Configuration

### Basic Config (`tablesleuth.toml`)

```toml
[catalog]
default = "local"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "gizmosql_username"
password = "gizmosql_password"
tls_skip_verify = false
```

### PyIceberg Config (`~/.pyiceberg.yaml`)

```yaml
catalog:
  local:
    type: sql
    uri: sqlite:////path/to/catalog.db
    warehouse: file:///path/to/warehouse

  glue:
    type: glue

  s3tables:
    type: glue
    glue.skip-name-validation: true
```

## Common Tasks

### Test Installation Locally

```bash
# Build package
uv build

# Install locally
pip install dist/tablesleuth-0.4.0-py3-none-any.whl

# Test it
tablesleuth --version
tablesleuth --help

# Uninstall
pip uninstall tablesleuth
```

### Test on TestPyPI

```bash
# Upload
twine upload --repository testpypi dist/*

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    tablesleuth

# Test
tablesleuth --version

# Uninstall
pip uninstall tablesleuth
```

### Create GitHub Release

```bash
# Commit changes
git add .
git commit -m "Release v0.4.0"
git push origin main

# Create and push tag
git tag -a v0.4.0 -m "Release v0.4.0"
git push origin v0.4.0

# Go to GitHub and create release from tag
# GitHub Actions will automatically publish to PyPI
```

## Troubleshooting

### Build Fails

```bash
# Clean everything
make clean
rm -rf .venv

# Reinstall
uv sync --extra dev

# Try again
uv build
```

### Import Errors

```bash
# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Check package location
pip show tablesleuth

# Reinstall
pip uninstall tablesleuth
pip install tablesleuth
```

### Version Mismatch

```bash
# Check all versions
grep -r "0\.4\.0" .

# Update version in __init__.py
vim src/tablesleuth/__init__.py

# Rebuild
make clean
uv build
```

## Useful Links

- **PyPI**: https://pypi.org/project/tablesleuth/
- **Repository**: https://github.com/jamesbconner/TableSleuth
- **Documentation**: https://github.com/jamesbconner/TableSleuth/tree/main/docs
- **Issues**: https://github.com/jamesbconner/TableSleuth/issues
- **Homepage**: https://tablesleuth.com

## Documentation Files

- `README.md` - Project overview
- `QUICKSTART.md` - Getting started
- `TABLESLEUTH_SETUP.md` - Installation guide
- `PYPI_PUBLISHING.md` - Publishing guide
- `VERSION_MANAGEMENT.md` - Version updates
- `PYPI_READY_CHECKLIST.md` - Pre-publication checklist
- `RELEASE_SUMMARY.md` - Release notes
- `CHANGELOG.md` - Version history
- `CONTRIBUTING.md` - Contribution guide
- `docs/USER_GUIDE.md` - User documentation
- `docs/DEVELOPER_GUIDE.md` - Developer documentation
- `docs/ARCHITECTURE.md` - Architecture overview
