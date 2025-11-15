# Development Setup

## Quick Start

```bash
# Install dependencies with dev tools
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
make build            # Build distribution packages
make run              # Run table-sleuth CLI
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

## Development Workflow

1. Make your changes
2. Run `make format` to auto-format code
3. Run `make check` to verify quality
4. Commit (pre-commit hooks run automatically)
5. Push

## Tools Configuration

All tool configurations are in `pyproject.toml`:
- Ruff: Linting and formatting
- mypy: Type checking
- pytest: Testing
- bandit: Security scanning
