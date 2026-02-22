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
	@echo "Creating source code archive..."
	@VERSION=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	ARCHIVE_NAME="tablesleuth-$$VERSION-src.zip"; \
	git archive --format=zip --prefix=tablesleuth/ -o $$ARCHIVE_NAME HEAD; \
	echo "Created $$ARCHIVE_NAME (excludes .gitignore patterns)"

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
	rm -rf src/tablesleuth/web
	cp -r web-ui/out src/tablesleuth/web

start-web: build-release
	uv run tablesleuth web

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf *.zip
	rm -rf src/tablesleuth/web
	rm -rf web-ui/out
	rm -rf web-ui/.next
	git restore src/tablesleuth/web/index.html 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name __pycache__ -delete
