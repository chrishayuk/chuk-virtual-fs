# FUSE Mounting Examples

Native filesystem mounting with full POSIX semantics using FUSE.

## 🚀 Quick Start

### Option 1: Docker (Recommended - No System Changes!)

```bash
# Build Docker image
docker build -f examples/mounting/Dockerfile -t chuk-virtual-fs-mount .

# Run tests  
docker run --rm --privileged --device /dev/fuse chuk-virtual-fs-mount

# Or run from project root
python test_docker_mount_examples.py
```

**Result**: `4/4 tests passed` ✅

### Option 2: Local Installation

```bash
# Install FUSE first
# macOS: brew install macfuse
# Linux: sudo apt-get install fuse3 libfuse3-dev

# Install package
pip install chuk-virtual-fs[mount]

# Run example
python examples/mounting/01_basic_mount.py
```

---

## 📋 Examples

| # | Example | Description | Requirements |
|---|---------|-------------|--------------|
| 00 | test_without_fuse.py | Infrastructure tests | None |
| 01 | basic_mount.py | Basic mounting | FUSE |
| 02 | typescript_checker.py | AI + TypeScript integration | FUSE, TypeScript |
| 03 | react_component_generator.py | React component generation | FUSE, Node.js |
| 04 | redis_persistence.py | Redis-backed filesystem | FUSE, Redis |
| 05 | isolated_build_sandbox.py | Sandboxed builds | FUSE |

See [main examples README](../README.md) for complete documentation.
