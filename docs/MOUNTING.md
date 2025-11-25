# Mounting chuk-virtual-fs as a Real Filesystem

This guide explains how to mount `chuk-virtual-fs` as a real filesystem on your operating system, making it accessible to any application.

## Overview

The mount functionality allows you to expose a virtual filesystem as a native mount point that any application can access. This enables:

- **Universal Tool Access**: Linters, compilers, bundlers, and dev servers can operate on virtual files
- **Cross-Platform Support**: Works on Linux, macOS, and Windows
- **Backend Flexibility**: Mount any VFS backend (memory, Redis, S3, SQLite)
- **AI Integration**: LLMs can manipulate files that tools can immediately process

## Installation

### Linux (Ubuntu/Debian)

```bash
# Install FUSE library
sudo apt-get install fuse3 libfuse3-dev

# Install chuk-virtual-fs with mount support
pip install chuk-virtual-fs[mount]
```

### macOS

```bash
# Install macFUSE
brew install macfuse

# Install chuk-virtual-fs with mount support
pip install chuk-virtual-fs[mount]
```

### Windows

```bash
# Download and install WinFsp from:
# https://winfsp.dev/rel/

# Install chuk-virtual-fs with mount support
pip install chuk-virtual-fs[mount]
```

## Quick Start

### Basic In-Memory Mount

```bash
# Create mount point
mkdir -p /mnt/chukfs

# Mount in-memory VFS
chuk-vfs-mount --backend memory --mount /mnt/chukfs
```

Now you can use the filesystem like any other directory:

```bash
# In another terminal
echo "Hello World" > /mnt/chukfs/hello.txt
cat /mnt/chukfs/hello.txt
ls -la /mnt/chukfs/
```

Press `Ctrl+C` in the mount terminal to unmount.

## CLI Reference

```bash
chuk-vfs-mount [OPTIONS]
```

### Required Options

- `--mount`, `-m PATH` - Mount point path
  - Linux/macOS: `/mnt/chukfs`, `~/mnt/vfs`
  - Windows: `Z:`, `X:`

### Backend Options

- `--backend`, `-b BACKEND` - VFS backend to use
  - `memory` - In-memory (default)
  - `redis` - Redis-backed
  - `s3` - AWS S3-backed
  - `sqlite` - SQLite-backed

### Mount Options

- `--readonly`, `-r` - Mount as read-only
- `--allow-other` - Allow other users to access (requires root)
- `--debug`, `-d` - Enable debug logging
- `--foreground`, `-f` - Run in foreground (default: True)

### Backend-Specific Options

#### Redis Backend

- `--redis-url URL` - Redis connection URL (default: `redis://localhost:6379`)
- `--redis-prefix PREFIX` - Key prefix (default: `chuk_vfs:`)

#### S3 Backend

- `--bucket NAME` - S3 bucket name (required)
- `--s3-prefix PREFIX` - S3 key prefix
- `--region REGION` - AWS region

#### SQLite Backend

- `--db-path PATH` - Database file path (default: `virtual_fs.db`)

## Usage Examples

### 1. Mount Redis-Backed VFS

```bash
# Start Redis (if not running)
redis-server

# Mount Redis-backed VFS
chuk-vfs-mount \
  --backend redis \
  --mount /mnt/chukfs \
  --redis-url redis://localhost:6379

# Files written here are persisted in Redis
echo "data" > /mnt/chukfs/file.txt
```

### 2. Mount S3-Backed VFS (Read-Only)

```bash
# Mount S3 bucket as read-only filesystem
chuk-vfs-mount \
  --backend s3 \
  --bucket my-bucket \
  --mount /mnt/s3fs \
  --readonly \
  --region us-west-2
```

### 3. Development with Hot Reload

```bash
# Mount VFS for a Node.js project
chuk-vfs-mount --backend memory --mount ./my-project

# In another terminal, run dev server
cd my-project
npm install
npm run dev

# Edit files - hot reload works automatically!
```

### 4. Windows Drive Letter Mount

```bash
# Mount as Z: drive on Windows
chuk-vfs-mount --backend memory --mount Z:

# Access like any drive
dir Z:\
echo "test" > Z:\test.txt
```

## Programmatic API

You can also mount programmatically in Python:

### Async Context Manager (Recommended)

```python
import asyncio
from pathlib import Path
from chuk_virtual_fs import VirtualFS
from chuk_virtual_fs.mount import mount, MountOptions

async def main():
    vfs = VirtualFS()

    # Add some files
    vfs.write_file("/hello.txt", "Hello World")
    vfs.create_directory("/src")

    # Mount with async context manager
    options = MountOptions(readonly=False, debug=True)
    async with mount(vfs, Path("/mnt/chukfs"), options) as adapter:
        print("Mounted! Press Ctrl+C to unmount")
        # Filesystem is mounted here
        await asyncio.Event().wait()  # Wait forever
    # Automatically unmounted

if __name__ == "__main__":
    asyncio.run(main())
```

### Blocking Mode (Simple Scripts)

```python
from pathlib import Path
from chuk_virtual_fs import VirtualFS
from chuk_virtual_fs.mount import mount, MountOptions

vfs = VirtualFS()
vfs.write_file("/test.txt", "Test content")

options = MountOptions(readonly=False)
adapter = mount(vfs, Path("/mnt/chukfs"), options)

# This blocks until unmounted (Ctrl+C)
adapter.mount_blocking()
```

### Background Mount (Non-Blocking)

```python
import asyncio
from pathlib import Path
from chuk_virtual_fs import VirtualFS
from chuk_virtual_fs.mount import mount, MountOptions

async def main():
    vfs = VirtualFS()
    options = MountOptions()
    adapter = mount(vfs, Path("/mnt/chukfs"), options)

    # Mount in background
    await adapter.mount_async()

    # Do other work while mounted
    print("Filesystem is mounted!")

    # Modify VFS - changes visible immediately
    vfs.write_file("/new_file.txt", "New content")

    # Unmount when done
    await adapter.unmount_async()

asyncio.run(main())
```

## Use Cases

### 1. AI-Powered Development

Mount a VFS that an AI agent can manipulate, while your local tools process the changes:

```python
# AI agent writes code
vfs.write_file("/src/component.tsx", generated_code)

# TypeScript compiler reads it immediately
# Vite dev server hot-reloads
# ESLint checks it
# All without the AI needing custom integrations!
```

### 2. Storybook + MCP Integration

```bash
# Mount VFS with component library
chuk-vfs-mount --backend redis --mount ./design-system

# Storybook MCP generates components
# They appear in ./design-system immediately
# Storybook dev server picks them up
```

### 3. Remote Build System

```bash
# Mount S3-backed VFS containing build artifacts
chuk-vfs-mount \
  --backend s3 \
  --bucket build-artifacts \
  --mount ./dist \
  --readonly

# Local tools can now access remote builds
npm run test:integration
```

### 4. Sandboxed CI/CD

```python
# Create isolated build environment
build_vfs = VirtualFS()  # In-memory
adapter = mount(build_vfs, Path("/build"))

await adapter.mount_async()

# Run build inside mounted VFS
subprocess.run(["make", "build"], cwd="/build")

# Collect artifacts from VFS
artifacts = build_vfs.list_directory("/dist")
```

## Platform-Specific Notes

### Linux

- FUSE 3.x is preferred (install `fuse3` package)
- `allow_other` option requires `/etc/fuse.conf` to have `user_allow_other`
- Run as root for privileged mount points like `/mnt`

### macOS

- Requires macFUSE (successor to OSXFUSE)
- May need to allow kernel extension in System Preferences → Security
- First mount may prompt for password

### Windows

- Requires WinFsp installation
- Mount points must be drive letters (`Z:`) or empty directories
- Administrator rights needed for system-level mounts

## Troubleshooting

### "Mount point is busy"

```bash
# Linux
fusermount -u /mnt/chukfs

# macOS
umount /mnt/chukfs

# Windows
net use Z: /delete
```

### "Permission denied"

- Ensure mount point directory exists and is empty
- Check you have write permissions to the mount point
- Use `--allow-other` if other users need access (requires root)

### "FUSE not installed"

```bash
# Linux
sudo apt-get install fuse3 libfuse3-dev

# macOS
brew install macfuse

# Windows - download installer from winfsp.dev
```

### Mount doesn't appear

- Check logs with `--debug` flag
- Ensure VFS backend is accessible (Redis running, S3 credentials valid, etc.)
- Try mounting with `--foreground` to see errors

## Performance Considerations

- **In-Memory**: Fastest, but limited by RAM
- **Redis**: Good balance of speed and persistence
- **S3**: Slower, best for read-heavy workloads
- **SQLite**: Good for moderate file counts

Tips:
- Use `cache_timeout` in MountOptions for better read performance
- Enable `readonly` mode when possible (faster)
- Large files (>10MB) may be slow depending on backend

## Security

- Mounted filesystems inherit VFS security policies
- Use `readonly` mount for untrusted workloads
- `allow_other` can expose files to all users - use carefully
- Backend credentials (S3, Redis) should be properly secured

## Integration Examples

### With Vite

```bash
# Mount VFS for Vite project
chuk-vfs-mount --backend memory --mount ./my-app

cd my-app
vite dev
# Hot reload works automatically!
```

### With TypeScript

```bash
chuk-vfs-mount --backend redis --mount ./project

cd project
tsc --watch
# Type checking against virtual files!
```

### With Docker

```bash
# Mount VFS as volume
chuk-vfs-mount --backend redis --mount /mnt/shared

docker run -v /mnt/shared:/app/data my-image
```

## Architecture

```
┌─────────────────────────────────────┐
│   Your Application / Build Tools    │
│   (Node, Python, TypeScript, etc.)  │
└─────────────────┬───────────────────┘
                  │ (normal file I/O)
┌─────────────────▼───────────────────┐
│        OS Filesystem Layer          │
│         /mnt/chukfs (Linux)         │
│       /Volumes/chukfs (macOS)       │
│            Z: (Windows)             │
└─────────────────┬───────────────────┘
                  │ (FUSE/WinFsp)
┌─────────────────▼───────────────────┐
│      chuk-virtual-fs Mount          │
│       (Platform Adapter)            │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│        VirtualFS Core               │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│   Backend (Memory/Redis/S3/...)     │
└─────────────────────────────────────┘
```

## Next Steps

- **[MCP Integration](./MCP_INTEGRATION.md)**: Connect with Model Context Protocol servers
- **[Tool Adapters](./TOOL_ADAPTERS.md)**: Build wrappers for linters, compilers, etc.
- **[Examples](../examples/mounting/)**: Full working examples

## Contributing

Found an issue or want to add a feature? See [CONTRIBUTING.md](../CONTRIBUTING.md).

## License

MIT - See [LICENSE](../LICENSE.md) for details.
