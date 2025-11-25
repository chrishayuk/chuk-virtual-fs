# chuk-virtual-fs Examples

This directory contains comprehensive examples demonstrating all features of chuk-virtual-fs.

## Quick Start

```bash
# Install the package
pip install chuk-virtual-fs

# Use the one-click runner (easiest!)
cd examples
./run_example.sh

# Or run examples directly
python providers/memory_provider_example.py
```

## 📁 Example Categories

### 🌐 WebDAV Mounting (Easiest - No Kernel Extensions!)

**Recommended for most users** - Mount virtual filesystems without system modifications.

| Example | Description | Run |
|---------|-------------|-----|
| [01_basic_webdav.py](webdav/01_basic_webdav.py) | Basic WebDAV server | `python examples/webdav/01_basic_webdav.py` |
| [02_background_server.py](webdav/02_background_server.py) | Background server with dynamic files | `python examples/webdav/02_background_server.py` |
| [03_readonly_server.py](webdav/03_readonly_server.py) | Read-only WebDAV share | `python examples/webdav/03_readonly_server.py` |

**See**: [webdav/README.md](webdav/README.md) for detailed instructions

**Requirements**: `pip install chuk-virtual-fs[webdav]`

**Mounting**:
- **macOS**: Finder → Cmd+K → `http://localhost:8080`
- **Windows**: Map Network Drive → `http://localhost:8080`
- **Linux**: `davfs2` or file manager

---

### 🔌 FUSE Mounting (Advanced - Full POSIX)

Native filesystem mounting with full POSIX semantics.

| Example | Description | Run |
|---------|-------------|-----|
| [00_test_without_fuse.py](mounting/00_test_without_fuse.py) | Test infrastructure | `python examples/mounting/00_test_without_fuse.py` |
| [01_basic_mount.py](mounting/01_basic_mount.py) | Basic FUSE mount | `python examples/mounting/01_basic_mount.py` |
| [02_typescript_checker.py](mounting/02_typescript_checker.py) | AI + TypeScript integration | `python examples/mounting/02_typescript_checker.py` |
| [03_react_component_generator.py](mounting/03_react_component_generator.py) | React component generation | `python examples/mounting/03_react_component_generator.py` |
| [04_redis_persistence.py](mounting/04_redis_persistence.py) | Redis-backed filesystem | `python examples/mounting/04_redis_persistence.py` |
| [05_isolated_build_sandbox.py](mounting/05_isolated_build_sandbox.py) | Sandboxed build environment | `python examples/mounting/05_isolated_build_sandbox.py` |

**See**: [mounting/README.md](mounting/README.md) for detailed instructions

**Requirements**:
- **Local**: Install FUSE (macFUSE on macOS, fuse3 on Linux)
- **Docker**: No system modifications needed! See [mounting/README.md](mounting/README.md#docker-testing)

---

### 💾 Storage Providers

Examples demonstrating different storage backends.

| Example | Description | Run |
|---------|-------------|-----|
| [memory_provider_example.py](providers/memory_provider_example.py) | In-memory filesystem | `python examples/providers/memory_provider_example.py` |
| [filesystem_provider_example.py](providers/filesystem_provider_example.py) | Local disk storage | `python examples/providers/filesystem_provider_example.py` |
| [sqlite_provider_example.py](providers/sqlite_provider_example.py) | SQLite database backend | `python examples/providers/sqlite_provider_example.py` |
| [s3_provider_example.py](providers/s3_provider_example.py) | Amazon S3 storage | `python examples/providers/s3_provider_example.py` |
| [e2b_provider_example.py](providers/e2b_provider_example.py) | E2B sandbox integration | `python examples/providers/e2b_provider_example.py` |

**See**: [providers/README.md](providers/README.md) for detailed instructions

**Requirements**: Provider-specific (see each file's docstring)

---

### 🔐 Advanced Features

| Example | Description | Run |
|---------|-------------|-----|
| [secure_filesystem_example.py](providers/secure_filesystem_example.py) | Encryption and security | `python examples/providers/secure_filesystem_example.py` |
| [binary_files_example.py](providers/binary_files_example.py) | Binary file handling | `python examples/providers/binary_files_example.py` |
| [streaming_and_mounts_example.py](providers/streaming_and_mounts_example.py) | Streaming operations | `python examples/providers/streaming_and_mounts_example.py` |

---

## 🚀 Recommended Path for New Users

### 1. Start with Basic Examples (5 minutes)
```bash
# Try the simplest example first
python examples/providers/memory_provider_example.py
```

### 2. Try WebDAV Mounting (10 minutes)
```bash
# Install WebDAV support
pip install chuk-virtual-fs[webdav]

# Start a WebDAV server
python examples/webdav/01_basic_webdav.py

# In Finder: Cmd+K → http://localhost:8080
# Browse files like any mounted drive!
```

**Why WebDAV?**
- ✅ No kernel extensions required
- ✅ Works immediately on macOS/Windows/Linux
- ✅ Perfect for AI coding assistants
- ✅ Easy to deploy

### 3. Try FUSE Mounting in Docker (Optional)
```bash
# No system modifications needed!
docker build -f examples/mounting/Dockerfile -t chuk-virtual-fs-mount .
docker run --rm --privileged --device /dev/fuse chuk-virtual-fs-mount
```

---

## 📖 Example Details

### WebDAV Examples

#### 01_basic_webdav.py - Basic WebDAV Server
Creates a simple WebDAV server that you can mount in your file manager.

```python
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.adapters import WebDAVAdapter

vfs = SyncVirtualFileSystem()
vfs.write_file("/hello.txt", "Hello World!")

adapter = WebDAVAdapter(vfs, port=8080)
adapter.start()  # Server at http://localhost:8080
```

#### 02_background_server.py - Background Operation
Shows how to run WebDAV server in background while doing other work.

```python
adapter.start_background()  # Non-blocking
# Continue working...
vfs.write_file("/new_file.txt", "Added while running!")
adapter.stop()
```

#### 03_readonly_server.py - Read-Only Mode
Share files in read-only mode.

```python
adapter = WebDAVAdapter(vfs, readonly=True)
# Clients can view/download but not modify
```

### FUSE Mounting Examples

#### 01_basic_mount.py - Basic Mounting
Mount a virtual filesystem at a local path.

```python
from chuk_virtual_fs.mount import mount, MountOptions

vfs = SyncVirtualFileSystem()
vfs.write_file("/hello.txt", "Mounted!")

async with mount(vfs, "/tmp/mymount", MountOptions()) as adapter:
    # Filesystem accessible at /tmp/mymount
    await asyncio.Event().wait()
```

#### 02_typescript_checker.py - AI Integration Pattern
Demonstrates the core "AI + Tools" pattern:
1. AI generates TypeScript code
2. Mount it so TypeScript can check it
3. Read type errors
4. AI fixes the code
5. Verify it compiles

**Perfect example for AI coding assistants!**

### Storage Provider Examples

Each provider example shows:
- How to set up the provider
- Basic operations (read, write, list)
- Provider-specific features
- Error handling

---

## 🐳 Docker Testing

All mounting examples can be tested in Docker without system modifications:

```bash
# Build image (includes FUSE, TypeScript, etc.)
docker build -f examples/mounting/Dockerfile -t chuk-virtual-fs-mount .

# Run infrastructure tests
docker run --rm --privileged --device /dev/fuse chuk-virtual-fs-mount

# Run specific example
docker run --rm --privileged --device /dev/fuse chuk-virtual-fs-mount \
  python examples/mounting/01_basic_mount.py
```

**Includes**:
- ✅ FUSE3
- ✅ TypeScript 5.9.3
- ✅ Node.js 20.x
- ✅ All Python dependencies

---

## 🧪 Testing Examples

### Test All WebDAV Examples
```bash
python test_all_examples.py
```

Expected output: `4/4 tests passed`

### Test All Docker Mount Examples
```bash
python test_docker_mount_examples.py
```

Expected output: `4/4 tests passed`

---

## 📦 Installation Options

### Minimal (Core only)
```bash
pip install chuk-virtual-fs
```

### With WebDAV Support (Recommended)
```bash
pip install chuk-virtual-fs[webdav]
```

### With FUSE Support
```bash
pip install chuk-virtual-fs[mount]

# Also need system FUSE:
# macOS: brew install macfuse
# Linux: sudo apt-get install fuse3 libfuse3-dev
```

### With S3 Support
```bash
pip install chuk-virtual-fs[s3]
```

### Everything
```bash
pip install chuk-virtual-fs[all]
```

---

## 🛠️ Development Setup

```bash
# Clone repository
git clone https://github.com/ccmitchellusa/chuk-virtual-fs.git
cd chuk-virtual-fs

# Install with uv (recommended)
uv pip install -e ".[dev,webdav,mount]"

# Or with pip
pip install -e ".[dev,webdav,mount]"

# Run examples
python examples/memory_provider_example.py
```

---

## 🆘 Troubleshooting

### WebDAV Issues

**Problem**: Can't mount in Finder
**Solution**:
1. Check server is running: `curl http://localhost:8080`
2. Use full URL in Finder: `http://localhost:8080` (not `localhost:8080`)
3. Try a different port if 8080 is busy

**Problem**: "Connection failed" error
**Solution**: Check firewall settings, try `127.0.0.1` instead of `localhost`

### FUSE Issues

**Problem**: "FUSE support not available"
**Solution**:
- **Test in Docker**: No installation needed
- **Or install FUSE**:
  - macOS: `brew install macfuse` (requires system extension approval)
  - Linux: `sudo apt-get install fuse3 libfuse3-dev`

**Problem**: "Operation not permitted" on mount
**Solution**:
- macOS: System Settings → Privacy & Security → Allow macFUSE
- Linux: Add user to `fuse` group: `sudo usermod -a -G fuse $USER`

### Port Already in Use

```bash
# Kill process on port 8080
lsof -ti:8080 | xargs kill -9
```

---

## 📚 Additional Resources

- **Main Documentation**: [README.md](../README.md)
- **WebDAV Guide**: [webdav/README.md](webdav/README.md)
- **FUSE Mounting Guide**: [mounting/README.md](mounting/README.md)
- **API Reference**: See docstrings in source code
- **Test Reports**:
  - [EXAMPLES_TEST_REPORT.md](../EXAMPLES_TEST_REPORT.md)
  - [DOCKER_MOUNT_TEST_REPORT.md](../DOCKER_MOUNT_TEST_REPORT.md)
  - [FINAL_TEST_SUMMARY.md](../FINAL_TEST_SUMMARY.md)

---

## 💡 Use Cases

### AI Coding Assistants
- Generate code in virtual filesystem
- Tools can access it (TypeScript, linters, etc.)
- Read results back to AI
- See: `02_typescript_checker.py`

### Temporary Build Environments
- Create isolated build sandboxes
- No cleanup needed (virtual!)
- See: `05_isolated_build_sandbox.py`

### Development Workflows
- Mount S3 buckets as local drives
- Test with multiple storage backends
- Share filesystems via WebDAV

### Testing & CI/CD
- Run tests in Docker containers
- No host system modifications
- Reproducible environments

---

## 🤝 Contributing

Found a bug or want to add an example?

1. Check existing examples for patterns
2. Add comprehensive docstrings
3. Include usage instructions
4. Test with both WebDAV and FUSE if applicable
5. Update this README

---

## ✅ Quick Reference

| I want to... | Use this |
|--------------|----------|
| Mount without system changes | WebDAV examples |
| Get started quickly | `memory_provider_example.py` |
| Test AI + tools integration | `02_typescript_checker.py` |
| Use in production | WebDAV or S3 provider |
| Full POSIX semantics | FUSE mounting (or Docker) |
| No Docker, no FUSE install | WebDAV examples |

---

**All examples tested and working** ✅

Last updated: 2025-11-25
