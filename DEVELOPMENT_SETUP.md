# TableSleuth Development Setup

This guide covers setting up TableSleuth for development, testing, and contributing.

## Prerequisites

- Python 3.13+
- `uv` package manager
- Git
- Node.js 20+ and npm (required to rebuild the web UI frontend)
- AWS CLI (for AWS-related development)

## Quick Start

```bash
# Clone repository
git clone https://github.com/jamesbconner/TableSleuth.git
cd TableSleuth

# Install dependencies with dev tools (includes web extras)
make install-dev

# Install pre-commit hooks
uv run pre-commit install

# Run all quality checks
make check
```

## Available Commands

### Setup
```bash
make install          # Install production dependencies
make install-dev      # Install with dev dependencies
make sync             # Sync dependencies with uv
```

### Testing
```bash
make test             # Run tests
make test-cov         # Run tests with coverage report
```

### Code Quality
```bash
make lint             # Run ruff linter
make format           # Format code with ruff
make type-check       # Run mypy type checking
make security         # Run bandit security scan
make pre-commit       # Run all pre-commit hooks
make check            # Run all quality checks
```

### Build & Run
```bash
make build            # Build wheel + sdist (for releases)
make run              # Run tablesleuth CLI
```

### Web UI Development (v0.6.0+)
```bash
make dev-web-install-npm  # Install Node.js dependencies (run once after checkout)
make dev-api              # Start FastAPI server at localhost:8000 (hot-reload)
make dev-web              # Start Next.js dev server at localhost:3000 (hot-reload)
make build-web            # Build Next.js static export only
make build-release        # Build frontend and copy into src/tablesleuth/web/
make start-web            # build-release then launch tablesleuth web
```

### Cleanup
```bash
make clean            # Remove build artifacts and cache
```

## Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality. Hooks run automatically on `git commit`.

**Installed hooks:**
- Ruff (linting + formatting)
- mypy (type checking)
- bandit (security scanning)
- Standard checks (trailing whitespace, YAML/TOML validation, etc.)

**Manual execution:**
```bash
# Run on all files
make pre-commit

# Or directly
uv run pre-commit run --all-files
```

## Development Environment Setup

### Test Data Setup

```bash
# Create test data directory
mkdir -p tests/data

# Create test catalog
mkdir -p tests/catalogs
sqlite3 tests/catalogs/test.db "CREATE TABLE IF NOT EXISTS test (id INTEGER);"

# Create test warehouse
mkdir -p tests/warehouse
```

### PyIceberg Development Catalog

Create `~/.pyiceberg.yaml` for development:

```yaml
catalog:
  # Local development catalog
  local:
    type: sql
    uri: sqlite:///tests/catalogs/test.db
    warehouse: file:///$(pwd)/tests/warehouse

  # Test catalog for unit tests
  test:
    type: sql
    uri: sqlite:///:memory:
    warehouse: file:///tmp/test_warehouse
```

### GizmoSQL Development Setup

```bash
# Install GizmoSQL for development
pip install gizmosql

# Generate test certificates
mkdir -p ~/.certs
openssl req -x509 -newkey rsa:2048 -keyout ~/.certs/test.key -out ~/.certs/test.pem -days 365 -nodes -subj "/CN=localhost"

# Start test server
gizmosql_server -U test_user -P test_password -Q \
  -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain);" \
  -T ~/.certs/test.pem ~/.certs/test.key
```

## Development Workflow

### Code Quality Workflow

1. Make your changes
2. Run `make format` to auto-format code
3. Run `make lint` to check for issues
4. Run `make type-check` for type validation
5. Run `make test` to verify functionality
6. Run `make check` to run all quality checks
7. Commit (pre-commit hooks run automatically)
8. Push

### Running from Source

```bash
# Run TUI from source
uv run tablesleuth parquet data/sample.parquet
uv run tablesleuth iceberg --catalog local --table db.table
uv run tablesleuth delta path/to/table

# Run with verbose logging for debugging
uv run tablesleuth parquet data/sample.parquet -v
```

## Web UI Development

The web UI consists of a FastAPI backend and a Next.js frontend. During development you run them separately for hot-reload.

### First-Time Setup

```bash
# Install Node.js dependencies (once after checkout)
make dev-web-install-npm

# Install Python web extras
uv sync --extra web
```

### Hot-Reload Development (two terminals)

**Terminal 1 — FastAPI backend:**
```bash
make dev-api          # http://localhost:8000/api/...
```

**Terminal 2 — Next.js frontend:**
```bash
make dev-web          # http://localhost:3000
```

The Next.js dev server proxies API calls to `localhost:8000`. Edit files in `web-ui/src/` and Python source normally; both servers reload automatically.

### Building the Frontend for Inclusion in the Wheel

```bash
make build-release    # npm run build → copies web-ui/out/ to src/tablesleuth/web/
```

This is required before `uv build` so the compiled static export is bundled in the wheel. The GitHub Actions publish workflow runs this step automatically; you only need it locally when verifying the built package or committing an updated `src/tablesleuth/web/index.html`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TABLESLEUTH_WEB_UI_DIR` | package `web/` dir | Override path to static Next.js export |
| `TABLESLEUTH_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed CORS origins |

## Testing

### Unit Tests

```bash
# Run unit tests only
pytest tests/unit/ -v

# Test specific module
pytest tests/test_parquet_service.py::test_inspect_file -v

# Run with coverage
pytest --cov=src/tablesleuth --cov-report=html --cov-report=term-missing
```

### API Tests (v0.6.0+)

```bash
# Requires web extras installed
uv sync --extra web --extra dev

# Run API smoke tests
pytest tests/api/ -v
```

### Integration Tests

```bash
# Set up test environment
export TEST_GIZMOSQL_URI="grpc+tls://localhost:31337"
export TEST_GIZMOSQL_USERNAME="test_user"
export TEST_GIZMOSQL_PASSWORD="test_password"

# Run integration tests
pytest -m integration -v

# Run end-to-end tests
pytest tests/test_end_to_end.py -v
```

### Test Markers

```bash
# Run unit tests only
pytest -m unit

# Run integration tests only
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Debugging

### Debug Mode

```bash
# Run with debug logging
tablesleuth inspect file.parquet -v

# Enable Python debugging
PYTHONPATH=src python -m pdb -m tablesleuth.cli inspect file.parquet

# Use debugger in tests
pytest --pdb tests/test_specific.py
```

### Logging Configuration

```python
# Add to your test files for detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### TUI Debugging

```bash
# Run TUI with console logging
tablesleuth inspect file.parquet -v 2> debug.log

# Use textual development console
textual console
# Then run tablesleuth in another terminal
```

## Contributing

### Development Workflow

1. **Fork and clone** the repository
2. **Create feature branch**: `git checkout -b feature/your-feature`
3. **Make changes** with tests
4. **Run quality checks**: `make check`
5. **Commit changes**: Follow conventional commit format
6. **Push and create PR**

### Code Style Guidelines

- Use **ruff** for formatting and linting
- Follow **PEP 8** style guidelines
- Add **type hints** for all functions (Python 3.13+ syntax)
- Write **Google-style docstrings** for public APIs
- Keep **line length** under 100 characters
- Use **explicit over implicit** code

### Testing Guidelines

- Write **unit tests** for all new functions
- Add **integration tests** for new features
- Mock **external dependencies** in unit tests
- Use **pytest fixtures** for common test data
- Aim for **>90% code coverage**
- Test both **happy paths** and **edge cases**

### Documentation Requirements

- Update **docstrings** for API changes
- Add **usage examples** to docstrings
- Update **README.md** for new features
- Add **CHANGELOG.md** entries
- Update **user guides** as needed

## Troubleshooting Development Issues

### Common Issues

#### Import errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall in development mode
uv pip install -e .
```

#### Missing dependencies
```bash
# Sync all dependencies
uv sync --all-extras
```

#### Test failures
```bash
# Clean test cache
pytest --cache-clear

# Regenerate test data
python scripts/generate_test_data.py
```

#### Type checking errors
```bash
# Install type stubs
uv add --dev types-requests types-PyYAML
```

#### GizmoSQL connection issues
```bash
# Check server is running
ps aux | grep gizmosql_server

# Test connection
gizmosql_client --command Execute --use-tls --tls-skip-verify "SELECT 1"
```

## Tools Configuration

All tool configurations are in `pyproject.toml`:
- **Ruff**: Linting and formatting
- **mypy**: Type checking
- **pytest**: Testing framework
- **bandit**: Security scanning
- **coverage**: Code coverage reporting

## Next Steps

After development setup:

1. Review [TABLESLEUTH_SETUP.md](TABLESLEUTH_SETUP.md) for user setup
2. Check [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
3. Read [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
4. See [QUICKSTART.md](QUICKSTART.md) for usage examples
5. See [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for API reference and component interfaces
