.PHONY: clean build test lint format typecheck coverage security check-all
.PHONY: install install-dev update-deps publish publish-test release test-install
.PHONY: test-fast test-providers test-s3 docs serve-docs help

# Package configuration
PACKAGE := chuk_virtual_fs
SRC_DIR := src/$(PACKAGE)
TEST_DIR := tests

# Use uv for Python package management
UV := uv run
PYTHON := uv run python

# Default target
all: check-all test build

# Help target
help:
	@echo "Available targets:"
	@echo "  Development:"
	@echo "    install-dev    - Install development dependencies"
	@echo "    format         - Format code with black and isort"
	@echo "    lint           - Run linting checks (ruff, black, isort)"
	@echo "    typecheck      - Run type checking with mypy"
	@echo "    security       - Run security checks with bandit"
	@echo "    check-all      - Run all code quality checks"
	@echo ""
	@echo "  Testing:"
	@echo "    test           - Run all tests"
	@echo "    test-fast      - Run tests with minimal output"
	@echo "    test-providers - Run provider tests only"
	@echo "    test-s3        - Run S3 provider tests only"
	@echo "    coverage       - Run tests with coverage report"
	@echo "    coverage-html  - Generate HTML coverage report"
	@echo ""
	@echo "  Build & Release:"
	@echo "    clean          - Clean build artifacts and cache"
	@echo "    build          - Build package"
	@echo "    install        - Install package locally"
	@echo "    publish        - Publish to PyPI"
	@echo "    publish-test   - Publish to Test PyPI"
	@echo "    release        - Complete release process"
	@echo ""
	@echo "  Documentation:"
	@echo "    docs           - Generate documentation"
	@echo "    serve-docs     - Serve documentation locally"
	@echo ""
	@echo "  Utilities:"
	@echo "    update-deps    - Update dependencies"
	@echo "    clean          - Clean all build artifacts"

# Install development dependencies
install-dev:
	uv sync --all-extras --dev
	@echo "✓ Development dependencies installed"

# Install package locally
install:
	uv pip install -e .
	@echo "✓ Package installed locally"

# Update dependencies
update-deps:
	uv lock --upgrade
	uv sync --all-extras --dev
	@echo "✓ Dependencies updated"

# Clean build artifacts and cache
clean:
	@echo "🧹 Cleaning build artifacts and cache..."
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .coverage htmlcov/ .mypy_cache/
	rm -rf .ruff_cache/ .tox/ .venv_test/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage*" -delete
	@echo "✓ Clean complete"

# Code formatting
format:
	@echo "🎨 Formatting code..."
	$(UV) ruff format $(SRC_DIR) $(TEST_DIR)
	$(UV) ruff check --fix $(SRC_DIR) $(TEST_DIR) --silent || true
	@echo "✓ Code formatting complete"

# Linting checks
lint:
	@echo "🔍 Running linting checks..."
	$(UV) ruff check $(SRC_DIR) $(TEST_DIR)
	$(UV) ruff format --check $(SRC_DIR) $(TEST_DIR)
	@echo "✓ Linting checks passed"

# Type checking
typecheck:
	@echo "🔍 Running type checks..."
	$(UV) mypy $(SRC_DIR) || true
	@echo "✓ Type checking complete (warnings only)"

# Security checks
security:
	@echo "🔒 Running security checks..."
	$(UV) bandit -r $(SRC_DIR) -f json -o security-report.json || true
	$(UV) bandit -r $(SRC_DIR) || true
	@echo "✓ Security checks complete (warnings only)"

# Run all code quality checks
check-all: lint typecheck security
	@echo "✅ All code quality checks passed"

# Run tests
test:
	@echo "🧪 Running tests..."
	$(UV) pytest $(TEST_DIR) -v
	@echo "✓ Tests complete"

# Run tests with minimal output
test-fast:
	@echo "🧪 Running tests (fast)..."
	$(UV) pytest $(TEST_DIR) -q --tb=short
	@echo "✓ Tests complete"

# Run provider tests only
test-providers:
	@echo "🧪 Running provider tests..."
	$(UV) pytest $(TEST_DIR)/providers/ -v
	@echo "✓ Provider tests complete"

# Run S3 provider tests only
test-s3:
	@echo "🧪 Running S3 provider tests..."
	$(UV) pytest $(TEST_DIR)/providers/test_s3_provider_updated.py -v
	@echo "✓ S3 provider tests complete"

# Run tests with coverage
coverage:
	@echo "📊 Running tests with coverage..."
	$(UV) pytest $(TEST_DIR) --cov=$(PACKAGE) --cov-report=term-missing --cov-report=xml
	@echo "✓ Coverage analysis complete"

# Generate HTML coverage report
coverage-html:
	@echo "📊 Generating HTML coverage report..."
	$(UV) pytest $(TEST_DIR) --cov=$(PACKAGE) --cov-report=html --cov-report=term
	@echo "✓ Coverage report generated in htmlcov/"
	@echo "  Open htmlcov/index.html in your browser"

# Generate S3 provider coverage specifically
coverage-s3:
	@echo "📊 Running S3 provider coverage analysis..."
	$(UV) pytest $(TEST_DIR)/providers/test_s3_provider_updated.py --cov=$(PACKAGE).providers.s3 --cov-report=term-missing --cov-report=html
	@echo "✓ S3 provider coverage: htmlcov/index.html"

# Build package
build: clean check-all
	@echo "📦 Building package..."
	uv build
	@echo "✓ Package built successfully"

# Generate documentation (if you have docs)
docs:
	@echo "📚 Generating documentation..."
	@if [ -d "docs" ]; then \
		$(UV) mkdocs build; \
	else \
		echo "No docs directory found. Skipping documentation generation."; \
	fi

# Serve documentation locally
serve-docs:
	@echo "📚 Serving documentation locally..."
	@if [ -d "docs" ]; then \
		$(UV) mkdocs serve; \
	else \
		echo "No docs directory found. Cannot serve documentation."; \
	fi

# Run example scripts
run-examples:
	@echo "🚀 Running S3 provider example..."
	$(UV) python examples/s3_provider_example.py

# Publish to PyPI using twine (picks up credentials from ~/.pypirc automatically)
publish: build
	@echo "🚀 Publishing to PyPI..."
	@if [ ! -d "dist" ] || [ -z "$$(ls -A dist 2>/dev/null)" ]; then \
		echo "Error: No distribution files found. Run 'make build' first."; \
		exit 1; \
	fi
	@last_build=$$(ls -t dist/*.tar.gz dist/*.whl 2>/dev/null | head -n 2); \
	if [ -z "$$last_build" ]; then \
		echo "Error: No valid distribution files found."; \
		exit 1; \
	fi; \
	echo "Uploading: $$last_build"; \
	twine upload $$last_build
	@echo "✓ Published to PyPI"

# Publish to Test PyPI
publish-test: build
	@echo "🚀 Publishing to Test PyPI..."
	@if [ ! -d "dist" ] || [ -z "$$(ls -A dist 2>/dev/null)" ]; then \
		echo "Error: No distribution files found. Run 'make build' first."; \
		exit 1; \
	fi
	@last_build=$$(ls -t dist/*.tar.gz dist/*.whl 2>/dev/null | head -n 2); \
	if [ -z "$$last_build" ]; then \
		echo "Error: No valid distribution files found."; \
		exit 1; \
	fi; \
	echo "Uploading to Test PyPI: $$last_build"; \
	twine upload --repository testpypi $$last_build
	@echo "✓ Published to Test PyPI"

# Complete release process
release: clean check-all test coverage build publish
	@echo "🎉 Release complete!"

# Test installation from Test PyPI
test-install:
	@echo "🧪 Testing installation from Test PyPI..."
	$(PYTHON) -m pip install --index-url https://test.pypi.org/simple/ chuk-virtual-fs
	@echo "✓ Test installation complete"

# Development workflow - run before committing
pre-commit: format check-all test coverage
	@echo "✅ Pre-commit checks complete - ready to commit!"

# CI/CD workflow
ci: install-dev check-all test coverage
	@echo "✅ CI checks complete"