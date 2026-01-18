# Contributing to Table Sleuth

Thank you for your interest in contributing to Table Sleuth! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors. We expect all participants to:

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, trolling, or discriminatory comments
- Personal attacks or insults
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Prerequisites

- Python 3.13 or higher
- `uv` for dependency management
- Git for version control
- Local GizmoSQL server (optional, for integration tests)

### Setting Up Development Environment

1. **Fork the Repository**

   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/TableSleuth.git
   cd TableSleuth
   ```

2. **Add Upstream Remote**

   ```bash
   git remote add upstream https://github.com/jamesbconner/TableSleuth.git
   ```

3. **Install Dependencies**

   ```bash
   # Using uv
   uv sync
   ```

4. **Activate Virtual Environment**

   ```bash
   source .venv/bin/activate  # macOS/Linux
   .venv\Scripts\activate     # Windows
   ```

5. **Install Pre-commit Hooks**

   ```bash
   pre-commit install
   ```

6. **Verify Setup**

   ```bash
   # Run tests
   pytest

   # Check code quality
   ruff check .
   mypy src/tablesleuth
   ```

## Development Workflow

### 1. Create a Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
```

**Branch Naming Conventions**:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `test/` - Test additions or changes
- `refactor/` - Code refactoring
- `perf/` - Performance improvements

### 2. Make Your Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

### 3. Test Your Changes

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/tablesleuth --cov-report=html

# Run specific test file
pytest tests/test_parquet_inspector.py

# Run integration tests (requires local GizmoSQL server)
# Set TEST_GIZMOSQL_URI environment variable first
export TEST_GIZMOSQL_URI="grpc+tls://localhost:31337"
pytest -m integration
```

### 4. Check Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/tablesleuth

# Run all checks
pre-commit run --all-files
```

### 5. Commit Your Changes

```bash
git add .
git commit -m "feat: add new profiling backend"
```

**Commit Message Format**:

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions or changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Build/tooling changes
- `style`: Code style changes (formatting)

**Examples**:

```
feat(profiling): add Spark profiling backend

Implement SparkProfiler class that uses PySpark for column profiling.
Supports single and multi-column profiling with optional filters.

Closes #123
```

```
fix(tui): handle missing column statistics gracefully

Display "N/A" instead of crashing when column statistics are not
available in Parquet metadata.

Fixes #456
```

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
```

## Coding Standards

### Python Style Guide

We follow PEP 8 with some modifications enforced by Ruff:

- **Line Length**: 100 characters (soft limit), 120 (hard limit)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings
- **Imports**: Organized by standard library, third-party, local

### Type Annotations

All functions must have complete type annotations:

```python
# Good ✓
def inspect_file(self, file_path: str | Path) -> ParquetFileInfo:
    """Extract metadata from a Parquet file."""
    ...

# Bad ✗
def inspect_file(self, file_path):
    """Extract metadata from a Parquet file."""
    ...
```

Use modern Python 3.13+ type syntax:
- `list[str]` instead of `List[str]`
- `dict[str, int]` instead of `Dict[str, int]`
- `str | None` instead of `Optional[str]`

### Docstrings

Use Google-style docstrings for all public functions, classes, and modules:

```python
def profile_single_column(
    self,
    view_name: str,
    column: str,
    filters: str | None = None
) -> ColumnProfile:
    """Profile a single column with optional filters.

    Args:
        view_name: Name of the registered view
        column: Column name to profile
        filters: Optional SQL WHERE clause filters

    Returns:
        ColumnProfile with statistics including row count, null count,
        distinct count, and min/max values

    Raises:
        ConnectionError: If backend connection fails
        ValueError: If column doesn't exist in view

    Example:
        >>> profiler = GizmoDuckDbProfiler(uri, user, password)
        >>> view = profiler.register_file_view(["data.parquet"])
        >>> profile = profiler.profile_single_column(view, "customer_id")
        >>> print(f"Distinct: {profile.distinct_count}")
    """
    ...
```

### Error Handling

Use specific exceptions and provide context:

```python
# Good ✓
try:
    file_info = inspector.inspect_file(file_path)
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    raise
except pa.ArrowInvalid as e:
    logger.error(f"Invalid Parquet file: {file_path}", exc_info=True)
    raise ValueError(f"Not a valid Parquet file: {file_path}") from e

# Bad ✗
try:
    file_info = inspector.inspect_file(file_path)
except Exception as e:
    print(f"Error: {e}")
```

### Logging

Use structured logging with appropriate levels:

```python
import logging

logger = logging.getLogger(__name__)

# Info: Normal operations
logger.info("Inspecting file", extra={"file_path": file_path, "size_bytes": size})

# Warning: Recoverable issues
logger.warning("Missing column statistics", extra={"column": column_name})

# Error: Operation failures
logger.error("Failed to connect to GizmoSQL", extra={"uri": uri}, exc_info=True)

# Debug: Detailed information
logger.debug("Executing query", extra={"query": query, "view": view_name})
```

### Code Organization

- **Single Responsibility**: Each class/function should have one clear purpose
- **DRY Principle**: Don't repeat yourself - extract common logic
- **SOLID Principles**: Follow SOLID design principles
- **Small Functions**: Keep functions focused and under 50 lines when possible
- **Clear Naming**: Use descriptive names that explain intent

## Testing Guidelines

### Test Coverage

- Aim for 90%+ test coverage for core services
- All new features must include tests
- Bug fixes should include regression tests

### Test Structure

```python
# tests/test_parquet_inspector.py
import pytest
from tablesleuth.services.parquet_service import ParquetInspector

class TestParquetInspector:
    """Tests for ParquetInspector service."""

    def test_inspect_file_basic_metadata(self, test_parquet_file):
        """Test that basic file metadata is extracted correctly."""
        inspector = ParquetInspector()
        info = inspector.inspect_file(test_parquet_file)

        assert info.num_rows == 1000
        assert info.num_row_groups == 1
        assert info.num_columns == 5
        assert info.file_size_bytes > 0

    def test_inspect_file_missing_statistics(self, parquet_file_no_stats):
        """Test that missing statistics are handled gracefully."""
        inspector = ParquetInspector()
        info = inspector.inspect_file(parquet_file_no_stats)

        # Should handle missing stats gracefully
        assert info.columns[0].null_count is None
        assert info.columns[0].min_value is None
```

### Test Types

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test component interactions (mark with `@pytest.mark.integration`)
3. **End-to-End Tests**: Test complete workflows

### Test Fixtures

Use pytest fixtures for common test data:

```python
# tests/conftest.py
@pytest.fixture
def test_parquet_file(tmp_path: Path) -> Path:
    """Create a test Parquet file with known data."""
    data = {
        "id": list(range(1000)),
        "name": [f"user_{i}" for i in range(1000)],
    }
    table = pa.table(data)
    file_path = tmp_path / "test.parquet"
    pq.write_table(table, file_path, compression="snappy")
    return file_path
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/tablesleuth --cov-report=html

# Run specific test file
pytest tests/test_parquet_inspector.py

# Run specific test
pytest tests/test_parquet_inspector.py::test_inspect_file_basic_metadata

# Run integration tests only (requires local GizmoSQL)
export TEST_GIZMOSQL_URI="grpc+tls://localhost:31337"
pytest -m integration

# Run with verbose output
pytest -v

# Run with print statements
pytest -s
```

## Documentation

### Code Documentation

- All public APIs must have docstrings
- Complex logic should have inline comments
- Use type hints for all function signatures

### User Documentation

When adding features, update:
- `README.md` - If it affects quick start or overview
- `QUICKSTART.md` - If it affects basic usage
- `docs/USER_GUIDE.md` - For detailed user-facing changes

### Developer Documentation

When adding features, update:
- `docs/DEVELOPER_GUIDE.md` - For architecture or design changes
- `CONTRIBUTING.md` - For contribution process changes
- Inline code comments - For complex implementation details

### Documentation Style

- Use clear, concise language
- Provide examples where helpful
- Keep documentation up-to-date with code changes
- Use proper Markdown formatting

## Pull Request Process

### Before Submitting

- [ ] All tests pass
- [ ] Code follows style guidelines
- [ ] New functionality has tests
- [ ] Documentation is updated
- [ ] Commit messages follow convention
- [ ] No merge conflicts with main branch

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed

## Checklist
- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

## Related Issues
Closes #123
```

### Review Process

1. **Automated Checks**: CI/CD runs tests and linters
2. **Code Review**: Maintainers review code
3. **Feedback**: Address review comments
4. **Approval**: At least one maintainer approval required
5. **Merge**: Maintainer merges PR

### Review Checklist

Reviewers will check:
- [ ] Code quality and style
- [ ] Test coverage
- [ ] Documentation completeness
- [ ] Performance implications
- [ ] Security considerations
- [ ] Breaking changes documented

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Steps

1. **Update Version**: Update version in `pyproject.toml`
2. **Update Changelog**: Add release notes to `CHANGELOG.md`
3. **Create Tag**: `git tag -a v1.0.0 -m "Release v1.0.0"`
4. **Push Tag**: `git push origin v1.0.0`
5. **Create Release**: Create GitHub release with notes

## Getting Help

### Resources

- [Developer Guide](docs/DEVELOPER_GUIDE.md) - Architecture and design
- [User Guide](docs/USER_GUIDE.md) - Usage documentation
- [Architecture](docs/ARCHITECTURE.md) - System architecture and technical details
- [GitHub Issues](https://github.com/jamesbconner/TableSleuth/issues) - Bug reports and features

### Communication

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Pull Requests**: For code contributions

### Questions?

If you have questions about contributing:
1. Check existing documentation
2. Search GitHub issues
3. Open a new issue with the "question" label

## Recognition

Contributors will be recognized in:
- `CHANGELOG.md` for their contributions
- GitHub contributors page
- Release notes

Thank you for contributing to Table Sleuth! 🎉
