# TableSleuth Test Suite

This directory contains the comprehensive test suite for TableSleuth, organized by test type and feature area.

## Directory Structure

```
tests/
├── unit/              # Unit tests (fast, isolated)
│   ├── adapters/      # Format adapter tests (Delta only - Iceberg moved to tests/iceberg/)
│   ├── services/      # Service layer tests (general services)
│   ├── profiling/     # Profiling-specific tests
│   ├── models/        # Data model tests
│   └── utils/         # Utility function tests
│
├── integration/       # Integration tests (multiple components)
├── cli/               # Command-line interface tests
├── tui/               # Terminal UI tests
│   ├── app/           # Main application tests
│   └── views/         # View component tests (general views)
│
├── delta/             # Delta Lake specific tests
├── iceberg/           # Iceberg specific tests
└── property/          # Property-based tests (Hypothesis)
```

## Running Tests

### All Tests
```bash
pytest tests/
```

### By Category
```bash
# Unit tests only (fast)
pytest tests/unit/

# Integration tests
pytest tests/integration/

# CLI tests
pytest tests/cli/

# TUI tests
pytest tests/tui/

# Delta Lake tests
pytest tests/delta/

# Iceberg tests
pytest tests/iceberg/

# Property-based tests
pytest tests/property/
```

### By Feature Area
```bash
# Format adapters (Delta only now)
pytest tests/unit/adapters/

# Services
pytest tests/unit/services/

# Profiling
pytest tests/unit/profiling/

# TUI views (general views only)
pytest tests/tui/views/

# Delta Lake features
pytest tests/delta/

# Iceberg features
pytest tests/iceberg/
```

### Specific Test File
```bash
pytest tests/unit/adapters/test_delta_adapter.py
pytest tests/delta/test_schema_evolution.py -v
```

### With Coverage
```bash
pytest tests/ --cov=src/tablesleuth --cov-report=html
```

## Test Types

### Unit Tests (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Speed**: Fast (< 1s per test)
- **Dependencies**: Minimal, use mocks/fixtures
- **Examples**: Adapter methods, utility functions, data models

### Integration Tests (`tests/integration/`)
- **Purpose**: Test multiple components working together
- **Speed**: Moderate (1-5s per test)
- **Dependencies**: May require test data or external services
- **Examples**: End-to-end workflows, service interactions

### Property Tests (`tests/property/`)
- **Purpose**: Test properties that should hold for all inputs
- **Framework**: Hypothesis
- **Speed**: Slower (generates many test cases)
- **Examples**: File analysis invariants, data validation

## Test Organization Principles

1. **By Test Type**: Unit, integration, property
2. **By Feature Area**: CLI, TUI, Delta, Iceberg, etc.
3. **By Layer**: Adapters, services, models, utils

Format-specific tests (Delta, Iceberg) get their own top-level directories due to significant functionality and feature sets.

## Writing New Tests

### Location Guidelines

- **New adapter**: `tests/unit/adapters/test_<format>_adapter.py` (for general adapters)
- **Delta feature**: `tests/delta/test_<feature>.py`
- **Iceberg feature**: `tests/iceberg/test_<feature>.py`
- **New service**: `tests/unit/services/test_<service>.py`
- **New CLI command**: `tests/cli/test_cli_<feature>.py`
- **New TUI view**: `tests/tui/views/test_<view>.py` (for general views)
- **Integration test**: `tests/integration/test_<feature>_integration.py`

### Naming Conventions

- Test files: `test_<module>.py`
- Test functions: `test_<functionality>()`
- Test classes: `Test<Feature>`
- Fixtures: Descriptive names in `conftest.py`

### Best Practices

1. **Keep tests focused**: One concept per test
2. **Use descriptive names**: Test name should describe what it tests
3. **Arrange-Act-Assert**: Clear test structure
4. **Use fixtures**: Share setup code via conftest.py
5. **Mock external dependencies**: Keep tests fast and reliable
6. **Test edge cases**: Not just happy paths
7. **Document complex tests**: Add docstrings explaining why

## Fixtures

Shared fixtures are defined in:
- `tests/conftest.py` - Global fixtures
- `tests/<category>/conftest.py` - Category-specific fixtures

Common fixtures:
- `tmp_path` - Temporary directory (pytest built-in)
- `sample_parquet_file` - Test Parquet file
- `delta_table_path` - Test Delta table
- `iceberg_table` - Test Iceberg table

## Continuous Integration

Tests run automatically on:
- Every commit (via pre-commit hooks)
- Pull requests (via GitHub Actions)
- Main branch merges

## Test Data

Test data is located in:
- `data/warehouse/` - Sample tables for testing
- `tests/fixtures/` - Small test files (if needed)
- Generated in tests - Use factories/builders

## Debugging Tests

### Run with verbose output
```bash
pytest tests/ -v
```

### Run with print statements
```bash
pytest tests/ -s
```

### Run specific test
```bash
pytest tests/unit/adapters/test_delta_adapter.py::test_open_table -v
```

### Debug with pdb
```bash
pytest tests/ --pdb
```

### Show test durations
```bash
pytest tests/ --durations=10
```

## Coverage Goals

- **Overall**: > 90%
- **Critical paths**: 100% (adapters, CLI commands)
- **UI components**: > 80%
- **Utilities**: > 95%

## Performance

- Unit tests should complete in < 5 seconds total
- Integration tests should complete in < 30 seconds total
- Full test suite should complete in < 2 minutes

## Maintenance

- Review and update tests when adding features
- Remove obsolete tests when removing features
- Keep test data minimal and focused
- Update this README when structure changes
