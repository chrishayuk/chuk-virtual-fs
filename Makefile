.PHONY: clean build test lint format publish release install-dev

# Use the correct Python interpreter for your system
# Uncomment the line that works for your system
PYTHON := python3
# PYTHON := python
# PYTHON := $(shell which python)

# Package name
PACKAGE := chuk_virtual_fs

# Default target
all: test lint build

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	rm -rf .pytest_cache/ .coverage htmlcov/

# Build package
build: clean
	$(PYTHON) -m build

# Install development dependencies
install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

# Run tests
test:
	$(PYTHON) -m pytest

# Run tests with coverage
test-cov:
	$(PYTHON) -m pytest --cov=$(PACKAGE) --cov-report=term --cov-report=html

# Run linting checks
lint:
	$(PYTHON) -m flake8 $(PACKAGE) tests
	$(PYTHON) -m black --check $(PACKAGE) tests
	$(PYTHON) -m isort --check-only $(PACKAGE) tests

# Format code
format:
	$(PYTHON) -m black $(PACKAGE) tests
	$(PYTHON) -m isort $(PACKAGE) tests

# Publish to PyPI
publish:
	$(PYTHON) -m twine upload dist/*

# Publish to Test PyPI
publish-test:
	$(PYTHON) -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Complete release process: clean, build, and publish
release: clean build publish

# Test installation from Test PyPI
test-install:
	$(PYTHON) -m pip install --index-url https://test.pypi.org/simple/ chuk-virtual-fs

# Install locally
install: build
	$(PYTHON) -m pip install dist/chuk_virtual_fs-*.whl

# Update dependencies
update-deps:
	$(PYTHON) -m pip install -U pip setuptools wheel build twine
	$(PYTHON) -m pip install -e ".[dev]"