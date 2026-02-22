.PHONY: help install install-dev sync clean test test-cov lint format type-check security pre-commit check build run zip dev-api dev-web dev-web-install-npm build-web build-release start-web

# Default target
help:
	@echo "TableSleuth - Makefile Commands"
	@echo "================================="
	@echo "Setup:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install with dev dependencies"
	@echo "  make sync             Sync dependencies with uv"
	@echo ""
	@echo "Development:"
	@echo "  make test             Run tests with pytest"
	@echo "  make test-cov         Run tests with coverage report"
	@echo "  make lint             Run ruff linter"
	@echo "  make format           Format code with ruff"
	@echo "  make type-check       Run mypy type checking"
	@echo "  make security         Run bandit security scan"
	@echo "  make pre-commit       Run all pre-commit hooks"
	@echo ""
	@echo "Quality (runs all checks):"
	@echo "  make check            Run all quality checks"
	@echo ""
	@echo "Web UI Development:"
	@echo "  make dev-api              Start FastAPI dev server (localhost:8000, hot-reload)"
	@echo "  make dev-web-install-npm  Install Node.js dependencies (run once after checkout)"
	@echo "  make dev-web              Start Next.js dev server (localhost:3000)"
	@echo "  make build-web        Build Next.js static export"
	@echo "  make build-release    Build frontend and bundle into Python package"
	@echo "  make start-web        Build release and launch web UI"
	@echo ""
	@echo "Build & Run:"
	@echo "  make build            Build distribution packages"
	@echo "  make run              Run tablesleuth CLI"
	@echo "  make zip              Create source code archive"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove build artifacts and cache"

# Installation
install:
	uv sync

install-dev:
	uv sync --extra dev

sync:
	uv sync --extra dev

# Testing
test:
	uv run pytest

test-cov:
	uv run pytest --cov=tablesleuth --cov-report=html --cov-report=term

# Code quality
lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

type-check:
	uv run mypy src

security:
	uv run bandit -c pyproject.toml -r src/

# Pre-commit
pre-commit:
	uv run pre-commit run --all-files

# Run all quality checks
check: lint type-check security test

# Build
build:
	uv build

# Run the application
run:
	uv run tablesleuth

# Create source archive (excludes .gitignore files and untracked files)
zip:
	uv run python -c "import subprocess, tomllib, pathlib; v=tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version']; n=f'tablesleuth-{v}-src.zip'; subprocess.run(['git','archive','--format=zip','--prefix=tablesleuth/','-o',n,'HEAD'],check=True); print(f'Created {n} (excludes .gitignore patterns)')"

# Web UI development
dev-api:
	uv run uvicorn tablesleuth.api.main:app --host localhost --port 8000 --reload

dev-web-install-npm:
	cd web-ui && npm install

dev-web:
	cd web-ui && npm run dev

build-web:
	cd web-ui && npm run build

build-release: build-web
	uv run python -c "import shutil; shutil.rmtree('src/tablesleuth/web', ignore_errors=True); shutil.copytree('web-ui/out', 'src/tablesleuth/web')"

start-web: build-release
	uv run tablesleuth web

# Cleanup
clean:
	uv run python -c "import shutil, pathlib; [shutil.rmtree(d, ignore_errors=True) for d in ['build', 'dist', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'htmlcov', 'src/tablesleuth/web', 'web-ui/out', 'web-ui/.next']]; [p.unlink(missing_ok=True) for p in [*pathlib.Path('.').glob('.coverage'), *pathlib.Path('.').glob('*.zip'), *pathlib.Path('src').glob('**/*.egg-info')]]; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	-git restore src/tablesleuth/web/index.html
