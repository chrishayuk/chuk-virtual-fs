# Dockerfile for testing chuk-virtual-fs mounting functionality
# NOTE: This Dockerfile must be run from the project root, not from examples/mounting/
# Build from project root: docker build -f examples/mounting/Dockerfile -t chuk-virtual-fs-mount .
FROM python:3.11-slim

# Install system dependencies: FUSE3, Node.js, and build tools
RUN apt-get update && apt-get install -y \
    fuse3 \
    libfuse3-dev \
    pkg-config \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm (for TypeScript examples)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install TypeScript globally
RUN npm install -g typescript

# Set up working directory
WORKDIR /app

# Copy pyproject.toml and src first for better caching
COPY pyproject.toml .
COPY README.md .
COPY src/ src/
COPY examples/ examples/

# Install uv (fast Python package installer)
RUN pip install uv

# Install the package with mount dependencies
RUN uv pip install --system -e ".[mount]"

# Create mount point
RUN mkdir -p /mnt/chukfs

# Set environment variables for FUSE
ENV FUSE_LIBRARY_PATH=/lib/x86_64-linux-gnu/libfuse3.so.3

# Default command - run the Docker-specific test
CMD ["python", "examples/mounting/docker_mount_test.py"]
