.PHONY: help install dev-install clean test test-unit test-real-api test-watch test-fast test-file test-match test-coverage lint typecheck format check pre-commit ci build dashboard docker-build docker-run security dead-code docstrings deps-check spell-check complexity pyright-check quality-all

$(eval VERSION_DOCKER := $(shell uv run python3 deploy/scripts/format_version.py docker))

# Common variables
UV_RUN := uv run

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install production dependencies"
	@echo "  dev-install  - Install development dependencies"
	@echo "  clean        - Clean build artifacts"
	@echo ""
	@echo "Testing commands (all include type checking and linting as prerequisites):"
	@echo "  test         - Run all tests with coverage (after quality checks)"
	@echo "  test-unit    - Run fast unit tests only (marked 'unit' or no 'real_api' marker)"
	@echo "  test-real-api - Run tests with real API calls (marked 'real_api', slow)"
	@echo "  test-watch   - Auto-run tests on file changes (with quality checks)"
	@echo "  test-fast    - Run tests without coverage (quick, after quality checks)"
	@echo "  test-coverage - Run tests with detailed coverage report"
	@echo ""
	@echo "Code quality:"
	@echo "  lint         - Run linting checks (ruff)"
	@echo "  typecheck    - Run type checking (mypy)"
	@echo "  pyright-check - Run type checking (pyright, stricter)"
	@echo "  format       - Format code (ruff)"
	@echo "  check        - Run all basic checks (lint + typecheck + format-check)"
	@echo "  pre-commit   - Run pre-commit hooks (comprehensive checks + auto-fixes)"
	@echo "  ci           - Run full CI pipeline (pre-commit + test)"
	@echo ""
	@echo "Advanced code quality:"
	@echo "  security     - Run security scan (bandit)"
	@echo "  dead-code    - Check for unused code (vulture)"
	@echo "  docstrings   - Check docstring coverage (interrogate)"
	@echo "  deps-check   - Check dependency issues (deptry)"
	@echo "  spell-check  - Spell check code (codespell)"
	@echo "  complexity   - Check code complexity (radon + xenon)"
	@echo "  quality-all  - Run ALL quality checks at once"
	@echo ""
	@echo "Build and deployment:"
	@echo "  build        - Build Python package (includes dashboard)"
	@echo "  build-backend - Build Python package only (no dashboard)"
	@echo "  build-dashboard - Build dashboard only"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo ""
	@echo "Dashboard (frontend):"
	@echo "  dashboard         - Show dashboard commands (run make -C dashboard help)"

# Installation targets
install:
	uv sync --no-dev

dev-install:
	uv sync --all-extras --dev
	uv run pre-commit install
	@if command -v bun >/dev/null 2>&1; then \
		bun install -g @anthropic-ai/claude-code; \
	else \
		echo "Warning: Bun not available, skipping Claude Code and dashboard installation"; \
	fi

# Cleanup
clean:
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage/
	rm -rf node_modules/
	rm -f pnpm-lock.yaml
	# $(MAKE) -C dashboard clean

# Testing targets (all enforce type checking and linting)
#
# All test commands include quality checks (mypy + ruff) as prerequisites to ensure
# tests only run on properly formatted and type-checked code. This prevents wasting
# time running tests on code that would fail CI anyway.
#
# Test markers:
#   - 'real_api': Tests that make actual API calls (slow, require network/auth)
#   - 'unit': Fast unit tests (< 1s each, no external dependencies)
#   - Tests without 'real_api' marker are considered unit tests by default

# Fix code with unsafe fixes
fix-hard:
	uv run ruff check . --fix --unsafe-fixes
	uv run uv run ruff check . --select F401 --fix --unsafe-fixes # Used variable import
	uv run uv run ruff check . --select I --fix --unsafe-fixes  # Import order
	uv run ruff format .


fix: format lint-fix
	ruff check . --fix --unsafe-fixes

# Run all tests with coverage (after ensuring code quality)
test: check
	@echo "Running all tests with coverage..."
	@if [ ! -d "tests" ]; then echo "Error: tests/ directory not found. Create tests/ directory and add test files."; exit 1; fi
	$(UV_RUN) pytest tests/ -v --cov=src/ccproxy --cov-report=term-missing

# Run fast unit tests only (exclude tests marked with 'real_api')
test-unit: check
	@echo "Running fast unit tests (excluding real API calls)..."
	@if [ ! -d "tests" ]; then echo "Error: tests/ directory not found. Create tests/ directory and add test files."; exit 1; fi
	$(UV_RUN) pytest tests/ -v -m "not real_api" --tb=short

# Run tests with real API calls (marked with 'real_api')
test-real-api: check
	@echo "Running tests with real API calls (slow)..."
	@if [ ! -d "tests" ]; then echo "Error: tests/ directory not found. Create tests/ directory and add test files."; exit 1; fi
	$(UV_RUN) pytest tests/ -v -m "real_api" --tb=short

# Auto-run tests on file changes (requires entr or similar tool)
test-watch:
	@echo "Watching for file changes and running unit tests..."
	@echo "Note: Runs unit tests only (no real API calls) for faster feedback"
	@echo "Requires 'entr' tool: install with 'apt install entr' or 'brew install entr'"
	@echo "Use Ctrl+C to stop watching"
	@if command -v entr >/dev/null 2>&1; then \
		find src/ccproxy tests -name "*.py" | entr -c sh -c 'make check && $(UV_RUN) pytest tests/ -v -m "not real_api" --tb=short'; \
	else \
		echo "Error: 'entr' not found. Install with 'apt install entr' or 'brew install entr'"; \
		echo "Alternatively, use 'make test-unit' to run tests once"; \
		exit 1; \
	fi

# Quick test run (no coverage, but with quality checks)
test-fast: check
	@echo "Running fast tests without coverage..."
	@if [ ! -d "tests" ]; then echo "Error: tests/ directory not found. Create tests/ directory and add test files."; exit 1; fi
	$(UV_RUN) pytest tests/ -v --tb=short

# Run tests with detailed coverage report (HTML + terminal)
test-coverage: check
	@echo "Running tests with detailed coverage report..."
	@if [ ! -d "tests" ]; then echo "Error: tests/ directory not found. Create tests/ directory and add test files."; exit 1; fi
	$(UV_RUN) pytest tests/ -v --cov=src/ccproxy --cov-report=term-missing --cov-report=html:.coverage/html
	@echo "HTML coverage report generated in .coverage/html/"

# Run specific test file (with quality checks)
test-file: check
	@echo "Running specific test file: tests/$(FILE)"
	@if [ ! -d "tests" ]; then echo "Error: tests/ directory not found. Create tests/ directory and add test files."; exit 1; fi
	$(UV_RUN) pytest tests/$(FILE) -v

# Run tests matching a pattern (with quality checks)
test-match: check
	@echo "Running tests matching pattern: $(MATCH)"
	@if [ ! -d "tests" ]; then echo "Error: tests/ directory not found. Create tests/ directory and add test files."; exit 1; fi
	$(UV_RUN) pytest tests/ -k "$(MATCH)" -v

# Code quality
lint:
	uv run ruff check .

# Advanced code quality checks
security:
	@echo "Running security scan with bandit..."
	uv run bandit -c pyproject.toml -r src/ccproxy -q

dead-code:
	@echo "Checking for dead code with vulture..."
	uv run vulture src/ccproxy --min-confidence=80

docstrings:
	@echo "Checking docstring coverage..."
	uv run interrogate src/ccproxy --config pyproject.toml

deps-check:
	@echo "Checking dependencies with deptry..."
	uv run deptry .

spell-check:
	@echo "Spell checking with codespell..."
	uv run codespell src/ccproxy --toml pyproject.toml

complexity:
	@echo "Checking code complexity with radon..."
	uv run radon cc src/ccproxy -a -s
	@echo ""
	@echo "Checking complexity thresholds with xenon..."
	uv run xenon src/ccproxy --max-absolute C --max-modules B --max-average A || true

pyright-check:
	@echo "Running pyright type checker..."
	uv run pyright src/ccproxy

# Run all code quality checks at once
quality-all: lint typecheck security dead-code docstrings deps-check spell-check complexity
	@echo ""
	@echo "=== All code quality checks complete! ==="

lint-fix: format
	# fix F401 (unused import) errors
	uv run ruff check --select F401 --fix .
	# fix sort (import) errors
	uv run ruff check --select I --fix .
	# classic fix
	uv run ruff check --fix .
	# unsafe fix
	uv run ruff check --unsafe-fixes --fix .
	uv run ruff format .

typecheck:
	uv run mypy .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

# Combined checks (individual targets for granular control)
check: lint typecheck format-check

# Pre-commit hooks (comprehensive checks + auto-fixes)
pre-commit:
	uv run pre-commit run --all-files

# Full CI pipeline (comprehensive: pre-commit does more checks + auto-fixes)
ci:
	uv run pre-commit run --all-files
	$(MAKE) test
	# $(MAKE) -C dashboard test

# Build targets
build:
	uv build

build-backend:
	uv build

build-dashboard:
	$(MAKE) -C dashboard build

# Dashboard delegation
dashboard:
	@echo "Dashboard commands:"
	@echo "Use 'make -C dashboard <target>' to run dashboard commands"
	@echo "Available dashboard targets:"
	@$(MAKE) -C dashboard help

# Docker targets
docker-build:
	docker build -f docker/Dockerfile -t ccproxy:$(VERSION_DOCKER) .

docker-run:
	docker run --rm -p 8000:8000 ccproxy:$(VERSION_DOCKER)

docker-compose-up:
	docker compose -f docker/compose.yaml up --build

docker-compose-down:
	docker compose -f docker/compose.yaml down

# Development server
dev:
	# uv run fastapi dev ccproxy/main.py
	CCPROXY_REQUEST_LOG_DIR=/tmp/ccproxy/request \
	  CCPROXY_VERBOSE_API=true \
	  SERVER__LOG_FILE=/tmp/ccproxy/ccproxy.log \
	  SERVER__LOG_LEVEL=debug \
		uv run ccproxy serve --reload

prod:
	uv run ccproxy serve

# Quick development setup
setup: dev-install
	@echo "Development environment ready!"
	@echo "Run 'make dev' to start the server"
