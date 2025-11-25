# Mount Feature Overview

## What is Mounting?

The mount feature allows you to expose `chuk-virtual-fs` as a **real operating system mount point** that any application can access, just like a regular directory or drive.

This transforms chuk-virtual-fs from a Python-only abstraction into a **universal filesystem** accessible by:
- Native applications
- Build tools (Vite, Webpack, TypeScript)
- Linters and formatters (ESLint, Prettier)
- IDEs and editors (VSCode, Vim)
- Command-line tools
- Any program that reads/writes files

## Why Mount?

### 🎯 Universal Tool Access

Without mounting:
```python
# Only Python can access
vfs.write_file("/src/App.tsx", code)
# Now what? Other tools can't see it!
```

With mounting:
```bash
# Mount once
chuk-vfs-mount --backend memory --mount /mnt/project

# Now everything works
cd /mnt/project
npm run build     # ✅ Vite/Webpack can read files
tsc --noEmit      # ✅ TypeScript checks types
eslint .          # ✅ ESLint can lint
code .            # ✅ VSCode can edit
```

### 🤖 AI + Tools Integration

Mount enables AI agents to manipulate a virtual filesystem while regular tools process the changes:

```python
# AI agent generates code
agent.write_code(vfs, "/src/components/Button.tsx", generated_code)

# Tools immediately see and process it:
# - TypeScript compiler checks types
# - ESLint runs lints
# - Vite hot-reloads the browser
# - Tests run automatically

# Agent reads the results from the VFS
errors = vfs.read_file("/logs/tsc_errors.json")
agent.fix_errors(errors)
```

This is **the missing link** between AI code generation and existing tooling.

### 🔌 Backend Flexibility

Mount any VFS backend as a real filesystem:

```bash
# In-memory (fast, ephemeral)
chuk-vfs-mount --backend memory --mount /mnt/workspace

# Redis (persistent, shared)
chuk-vfs-mount --backend redis --mount /mnt/workspace

# S3 (cloud-native, distributed)
chuk-vfs-mount --backend s3 --bucket builds --mount /mnt/artifacts

# SQLite (local, portable)
chuk-vfs-mount --backend sqlite --mount /mnt/data
```

Each backend behaves identically to applications - they just see files.

## Cross-Platform Architecture

### Linux

**Technology**: FUSE (Filesystem in Userspace)
**Library**: `pyfuse3` (async, modern) or `fusepy` (sync, fallback)

```bash
# Install
sudo apt-get install fuse3 libfuse3-dev
pip install chuk-virtual-fs[mount]

# Mount
chuk-vfs-mount --mount /mnt/chukfs --backend memory
```

### macOS

**Technology**: macFUSE (formerly OSXFUSE)
**Library**: `pyfuse3` (same as Linux)

```bash
# Install
brew install macfuse
pip install chuk-virtual-fs[mount]

# Mount
chuk-vfs-mount --mount /Volumes/chukfs --backend memory
```

### Windows

**Technology**: WinFsp (Windows File System Proxy)
**Library**: `winfspy`

```bash
# Install WinFsp from winfsp.dev
pip install chuk-virtual-fs[mount]

# Mount
chuk-vfs-mount --mount Z: --backend memory
```

## How It Works

```
┌──────────────────────────────────────────┐
│  Applications (Node, Python, VSCode)     │
│        (read/write files normally)       │
└────────────────┬─────────────────────────┘
                 │
                 ▼ (OS filesystem API)
┌──────────────────────────────────────────┐
│        OS Mount Point                    │
│   /mnt/chukfs  or  Z:                    │
└────────────────┬─────────────────────────┘
                 │
                 ▼ (FUSE/WinFsp)
┌──────────────────────────────────────────┐
│    chuk-virtual-fs Mount Adapter         │
│    • fuse_adapter.py (Linux/macOS)       │
│    • winfsp_adapter.py (Windows)         │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│       VirtualFS Core                     │
│    (provider-agnostic interface)         │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│  Backend (Memory/Redis/S3/SQLite)        │
└──────────────────────────────────────────┘
```

Key insight: **FUSE/WinFsp intercept OS filesystem calls** and translate them to VirtualFS operations.

When an app does:
```python
with open("/mnt/chukfs/file.txt") as f:
    content = f.read()
```

Behind the scenes:
1. OS sends `read()` syscall to mount point
2. FUSE intercepts and routes to our adapter
3. Adapter calls `vfs.read_file("/file.txt")`
4. VFS reads from backend (memory/Redis/S3)
5. Data flows back through FUSE to application

The app never knows it's not a "real" filesystem.

## Key Components

### 1. Base Abstraction (`base.py`)

Defines the platform-independent interface:

```python
class MountAdapter(ABC):
    """Cross-platform mount adapter interface"""

    @abstractmethod
    async def mount_async(self) -> None:
        """Mount asynchronously"""

    @abstractmethod
    async def unmount_async(self) -> None:
        """Unmount asynchronously"""

    @abstractmethod
    def mount_blocking(self) -> None:
        """Mount in blocking mode (for CLIs)"""
```

All adapters implement these methods.

### 2. FUSE Adapter (`fuse_adapter.py`)

Linux/macOS implementation using pyfuse3:

- Translates FUSE operations → VFS calls
- Handles inodes, file handles, directory entries
- Supports async operations (high performance)

### 3. WinFsp Adapter (`winfsp_adapter.py`)

Windows implementation using winfspy:

- Translates WinFsp callbacks → VFS calls
- Handles Windows-specific attributes
- Converts Unix paths to Windows drive letters

### 4. Mount Factory (`__init__.py`)

Auto-detects platform and creates appropriate adapter:

```python
def mount(vfs, mount_point, options):
    if sys.platform == "linux":
        return FUSEAdapter(vfs, mount_point, options)
    elif sys.platform == "darwin":
        return FUSEAdapter(vfs, mount_point, options)
    elif sys.platform == "win32":
        return WinFspAdapter(vfs, mount_point, options)
```

### 5. CLI Tool (`cli/mount_cli.py`)

User-friendly command-line interface:

```bash
chuk-vfs-mount --backend redis --mount /mnt/shared --readonly
```

Handles:
- Argument parsing
- VFS backend initialization
- Mount adapter creation
- Signal handling (Ctrl+C)

## Usage Patterns

### Pattern 1: Quick Mount (CLI)

For ad-hoc mounting:

```bash
chuk-vfs-mount --backend memory --mount /tmp/workspace
```

### Pattern 2: Programmatic Mount (Python)

For scripts and automation:

```python
from chuk_virtual_fs import VirtualFS
from chuk_virtual_fs.mount import mount

vfs = VirtualFS()
adapter = mount(vfs, "/mnt/workspace")
adapter.mount_blocking()  # Blocks until Ctrl+C
```

### Pattern 3: Async Context Manager

For async applications:

```python
async with mount(vfs, "/mnt/workspace") as adapter:
    # Mounted here
    await do_work()
# Auto-unmounted
```

### Pattern 4: Background Mount

For long-running services:

```python
adapter = mount(vfs, "/mnt/workspace")
await adapter.mount_async()  # Non-blocking

# Do other work
await process_files()

await adapter.unmount_async()
```

## Real-World Use Cases

### 1. AI Code Assistant with Live Feedback

```python
# Mount workspace
vfs = VirtualFS()
adapter = mount(vfs, "/workspace")
await adapter.mount_async()

# AI generates code
vfs.write_file("/src/App.tsx", generated_code)

# TypeScript checks it (seeing mounted files)
result = subprocess.run(["tsc", "--noEmit"], cwd="/workspace")

# AI reads type errors from mount point
errors = open("/workspace/.tsc-output").read()
vfs.write_file("/src/App.tsx", ai.fix(errors))
```

### 2. Storybook Design System + MCP

```bash
# Mount shared component library
chuk-vfs-mount --backend redis --mount ./components

# Storybook MCP generates Button.tsx → appears in ./components/
# Storybook dev server picks it up immediately
# Designer previews in browser
# AI iterates based on screenshots
```

### 3. Distributed Build System

```python
# Mount S3 bucket as local directory
mount(s3_vfs, "/build-cache", MountOptions(readonly=True))

# Build tools access cache transparently
subprocess.run(["cargo", "build"])
# Cargo reads from /build-cache/target/ (actually S3!)
```

### 4. Test Isolation

```python
# Each test gets isolated VFS
test_vfs = VirtualFS()
mount(test_vfs, f"/tmp/test-{test_id}")

# Run test with real tools
subprocess.run(["pytest", "/tmp/test-{test_id}"])

# Cleanup is just unmount (no disk cleanup needed)
```

## Performance Characteristics

| Backend | Read Speed | Write Speed | Persistence | Use Case |
|---------|------------|-------------|-------------|----------|
| Memory | ⚡⚡⚡ | ⚡⚡⚡ | ❌ | Dev workflows, temporary workspaces |
| Redis | ⚡⚡ | ⚡⚡ | ✅ | Shared state, multi-process |
| SQLite | ⚡⚡ | ⚡ | ✅ | Local persistence, portability |
| S3 | ⚡ | ⚡ | ✅ | Cloud storage, build artifacts |

**Tips:**
- Enable caching with `MountOptions(cache_timeout=5.0)`
- Use `readonly=True` when possible (faster)
- Keep files <1MB for best performance
- Use memory backend for hot paths

## Security

### Isolation

Mounted filesystems respect VFS security:

```python
from chuk_virtual_fs import SecurityConfig

config = SecurityConfig(
    max_file_size=10 * 1024 * 1024,  # 10MB
    allowed_extensions={".txt", ".py"},
    blocked_paths={"/etc", "/admin"}
)

vfs = VirtualFS(security_config=config)
mount(vfs, "/mnt/sandbox")  # Inherits restrictions
```

### Read-Only Mounts

For untrusted workloads:

```bash
chuk-vfs-mount --backend s3 --mount /mnt/public --readonly
```

Applications can read but not write.

### User Permissions

Control who can access:

```bash
# Default: only mounting user
chuk-vfs-mount --mount /mnt/private

# Allow all users (requires root)
sudo chuk-vfs-mount --mount /mnt/shared --allow-other
```

## Limitations

### Current Limitations

1. **No rename operation** - VirtualFS doesn't support rename yet
2. **Inode consistency** - Inode numbers may not be stable across remounts
3. **No extended attributes** - xattrs not supported
4. **No file locking** - flock/fcntl not implemented
5. **Limited metadata** - Timestamps approximate, no true ownership

### Platform Limitations

- **Linux**: `allow_other` requires `/etc/fuse.conf` config
- **macOS**: macFUSE requires kernel extension approval
- **Windows**: Drive letters only (no arbitrary paths)

## Troubleshooting

See [MOUNTING.md](./MOUNTING.md#troubleshooting) for detailed troubleshooting guide.

## Future Enhancements

Planned features:

- [ ] Inode table for stable file handles
- [ ] Extended attribute support
- [ ] File locking (flock)
- [ ] Symbolic link support
- [ ] Hard link support
- [ ] Rename operation
- [ ] Change notification (inotify/FSEvents)
- [ ] Memory-mapped file support

## Contributing

We welcome contributions! Areas needing help:

- Windows WinFsp testing
- Performance optimization
- Extended attribute support
- Documentation improvements

See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Related Documentation

- **[Full Mount Guide](./MOUNTING.md)** - Comprehensive usage guide
- **[API Reference](./API.md)** - Python API documentation
- **[Examples](../examples/)** - Working code examples
- **[MCP Integration](./MCP_INTEGRATION.md)** - Using with MCP servers

## License

MIT - See [LICENSE](../LICENSE.md)
