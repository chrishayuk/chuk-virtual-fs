# Build and Development Guide
This document provides instructions for developing, testing, and releasing the `chuk-virtual-fs` package.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/chrishayuk/chuk-virtual-fs.git
   cd chuk-virtual-fs
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

## Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=chuk_virtual_fs

# Create coverage report
pytest --cov=chuk_virtual_fs --cov-report=html
```

## Code Quality

```bash
# Format code with Black
black chuk_virtual_fs tests

# Sort imports
isort chuk_virtual_fs tests

# Run linting
flake8 chuk_virtual_fs tests
```

## Building the Package

```bash
# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Build source distribution and wheel
python -m build
```

The build process will create:
- A source distribution (`.tar.gz`) in the `dist/` directory
- A wheel (`.whl`) in the `dist/` directory

## Installing Locally

To test the package locally:

```bash
pip install dist/chuk_virtual_fs-*.whl
```

## Publishing to PyPI

1. **Test PyPI** (recommended first step):
   ```bash
   # Upload to Test PyPI
   python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
   
   # Install from Test PyPI
   pip install --index-url https://test.pypi.org/simple/ chuk-virtual-fs
   ```

2. **Production PyPI**:
   ```bash
   # Upload to PyPI
   python -m twine upload dist/*
   ```

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Commit changes: `git commit -m "Bump version to x.y.z"`
4. Create a git tag: `git tag vx.y.z`
5. Push changes: `git push && git push --tags`
6. Build package: `make build`
7. Upload to PyPI: `make publish`

## Using the Makefile

A Makefile is provided to simplify common development tasks:

```bash
# Clean, build, and publish
make release

# Just build
make build

# Run tests
make test

# Format code
make format

# Lint code
make lint

# Clean build artifacts
make clean
```