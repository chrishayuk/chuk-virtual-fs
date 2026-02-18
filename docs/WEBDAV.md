# WebDAV Support for chuk-virtual-fs

## Overview

The WebDAV adapter allows you to expose a `VirtualFileSystem` via the WebDAV protocol, making it accessible as a network drive **without requiring kernel extensions or system modifications**.

### Benefits

- ✅ **No Kernel Extensions**: Works without macFUSE, FUSE, or WinFsp
- ✅ **Cross-Platform**: Works on macOS, Windows, and Linux
- ✅ **Standard Protocol**: Uses industry-standard WebDAV
- ✅ **Easy Setup**: Just install Python dependencies
- ✅ **Network Access**: Can be accessed remotely (with proper security)
- ✅ **Read/Write Support**: Full filesystem operations

## Installation

```bash
# Install with WebDAV support
pip install chuk-virtual-fs[webdav]

# Or with uv
uv add chuk-virtual-fs[webdav]
```

## Quick Start

### Basic Server

```python
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.adapters import WebDAVAdapter

# Create VFS and add files
vfs = SyncVirtualFileSystem()
vfs.mkdir("/documents")
vfs.write_file("/documents/readme.txt", "Hello WebDAV!")

# Start WebDAV server
adapter = WebDAVAdapter(vfs, host="127.0.0.1", port=8080)
adapter.start()  # Blocking - runs until Ctrl+C
```

### Background Server

```python
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.adapters import WebDAVAdapter
import time

# Create VFS
vfs = SyncVirtualFileSystem()
vfs.write_file("/test.txt", "Hello!")

# Start server in background
adapter = WebDAVAdapter(vfs, port=8080)
adapter.start_background()

print(f"Server running at {adapter.url}")

# Continue working...
vfs.write_file("/another.txt", "More data!")

# When done
adapter.stop()
```

### Read-Only Server

```python
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.adapters import WebDAVAdapter

vfs = SyncVirtualFileSystem()
vfs.write_file("/report.txt", "Quarterly Report")

# Read-only mode
adapter = WebDAVAdapter(vfs, port=8080, readonly=True)
adapter.start()
```

### Context Manager

```python
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.adapters import WebDAVAdapter
import time

vfs = SyncVirtualFileSystem()
vfs.write_file("/test.txt", "Hello!")

# Auto-start and auto-stop
with WebDAVAdapter(vfs, port=8080) as adapter:
    print(f"Server running at {adapter.url}")
    time.sleep(10)  # Do work...
# Server automatically stopped
```

## Mounting in Different Operating Systems

### macOS (Finder)

**Method 1: Finder UI**
1. Open Finder
2. Press `Cmd+K` (Go → Connect to Server)
3. Enter: `http://localhost:8080`
4. Click "Connect"
5. The drive will appear in Finder sidebar

**Method 2: Command Line**
```bash
mkdir ~/mnt/chukfs
mount_webdav http://localhost:8080 ~/mnt/chukfs

# Unmount
umount ~/mnt/chukfs
```

### Windows

**Method 1: File Explorer**
1. Open File Explorer
2. Right-click "This PC" → "Map network drive"
3. Enter: `http://localhost:8080`
4. Choose a drive letter
5. Click "Finish"

**Method 2: Command Line**
```cmd
net use Z: http://localhost:8080

# Disconnect
net use Z: /delete
```

### Linux

```bash
# Install davfs2
sudo apt-get install davfs2

# Mount
mkdir ~/mnt/chukfs
sudo mount -t davfs http://localhost:8080 ~/mnt/chukfs

# Unmount
sudo umount ~/mnt/chukfs
```

## Configuration Options

```python
from chuk_virtual_fs.adapters import WebDAVAdapter

adapter = WebDAVAdapter(
    vfs,
    host="127.0.0.1",  # Bind address
    port=8080,          # Port number
    readonly=False,     # Read-only mode
    verbose=1,          # Logging level (0-5)
)
```

## Examples

### Example 1: Basic WebDAV Server
```bash
python examples/webdav/01_basic_webdav.py
```

Creates a server with sample files and provides mounting instructions.

### Example 2: Background Server
```bash
python examples/webdav/02_background_server.py
```

Shows how to run the server in the background while continuing to work with the VFS.

### Example 3: Read-Only Server
```bash
python examples/webdav/03_readonly_server.py
```

Demonstrates a read-only server for sharing snapshots or reports.

## Use Cases

### 1. Development and Testing
```python
# Share build artifacts
vfs = SyncVirtualFileSystem()
vfs.mkdir("/builds")
vfs.write_file("/builds/app.js", compiled_code)

adapter = WebDAVAdapter(vfs, port=8080)
adapter.start_background()

# Developers can mount and access files
```

### 2. Data Export
```python
# Export reports as mountable drive
vfs = SyncVirtualFileSystem()
vfs.mkdir("/reports")
for report in generate_reports():
    vfs.write_file(f"/reports/{report.name}", report.data)

adapter = WebDAVAdapter(vfs, port=8080, readonly=True)
adapter.start()
```

### 3. Temporary File Sharing
```python
# Quick file share
vfs = SyncVirtualFileSystem()
vfs.write_file("/shared/data.csv", csv_data)

with WebDAVAdapter(vfs, port=8080) as adapter:
    print(f"Share this URL: {adapter.url}")
    input("Press Enter to stop...")
```

### 4. Remote Access
```python
# Allow remote access (use with authentication!)
adapter = WebDAVAdapter(
    vfs,
    host="0.0.0.0",  # Listen on all interfaces
    port=8080,
)
adapter.start()
```

## Security Considerations

### Local Access Only (Default)
```python
# Binds to 127.0.0.1 - only accessible from same machine
adapter = WebDAVAdapter(vfs, host="127.0.0.1", port=8080)
```

### Remote Access
```python
# IMPORTANT: Only use this on trusted networks!
# Consider adding authentication

adapter = WebDAVAdapter(vfs, host="0.0.0.0", port=8080)
```

### Read-Only Mode
```python
# Prevent modifications
adapter = WebDAVAdapter(vfs, readonly=True)
```

### HTTPS/SSL
For remote access, run behind a reverse proxy like nginx or Apache with SSL.

## Comparison with FUSE

| Feature | WebDAV | FUSE/macFUSE |
|---------|--------|--------------|
| Kernel Extension | ❌ Not needed | ✅ Required |
| System Restart | ❌ Not needed | ⚠️ May be needed |
| Admin Rights | ❌ Not needed | ✅ Required |
| Cross-Platform | ✅ Yes | ⚠️ Platform-specific |
| Performance | ⚠️ Network overhead | ✅ Native speed |
| Setup Complexity | ✅ Very easy | ⚠️ Complex |
| Remote Access | ✅ Built-in | ❌ Not supported |

**Recommendation**: Use WebDAV for development, testing, and scenarios where you can't install system extensions. Use FUSE when you need maximum performance.

## Troubleshooting

### Port Already in Use
```python
# Change the port
adapter = WebDAVAdapter(vfs, port=8081)
```

### Cannot Connect from Finder
- Make sure server is running: `curl http://localhost:8080`
- Check firewall settings
- Try using IP address instead: `http://127.0.0.1:8080`

### Slow Performance
```python
# Increase cache timeout
adapter = WebDAVAdapter(vfs, port=8080, cache_timeout=5.0)
```

### Permission Errors on Linux
```bash
# Add user to davfs2 group
sudo usermod -aG davfs2 $USER
```

## Advanced Configuration

### Custom WsgiDAV Options
```python
adapter = WebDAVAdapter(
    vfs,
    port=8080,
    verbose=2,  # More logging
    # Pass additional wsgidav options
    http_authenticator={
        "accept_basic": True,
        "accept_digest": True,
    },
)
```

### Multiple VFS Instances
```python
# Run multiple servers on different ports
vfs1 = SyncVirtualFileSystem()
vfs2 = SyncVirtualFileSystem()

adapter1 = WebDAVAdapter(vfs1, port=8080)
adapter2 = WebDAVAdapter(vfs2, port=8081)

adapter1.start_background()
adapter2.start_background()
```

## API Reference

### WebDAVAdapter

```python
class WebDAVAdapter:
    def __init__(
        self,
        vfs: SyncVirtualFileSystem,
        host: str = "127.0.0.1",
        port: int = 8080,
        readonly: bool = False,
        **kwargs
    ):
        """Initialize WebDAV adapter."""

    def start(self) -> None:
        """Start server (blocking)."""

    def start_background(self) -> None:
        """Start server in background thread."""

    def stop(self) -> None:
        """Stop server."""

    @property
    def url(self) -> str:
        """Get server URL."""
```

## See Also

- [FUSE Mounting](MOUNTING.md) - Native filesystem mounting
- [Mount Alternatives](MOUNT_ALTERNATIVES.md) - Comparison of mounting approaches
- [Examples](/examples/webdav/) - Complete working examples
