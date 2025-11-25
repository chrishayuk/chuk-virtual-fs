# WebDAV Examples

Examples demonstrating how to use the WebDAV adapter to expose chuk-virtual-fs without kernel extensions.

## Installation

```bash
pip install chuk-virtual-fs[webdav]
# or
uv add chuk-virtual-fs[webdav]
```

## Examples

### 01_basic_webdav.py - Basic WebDAV Server

The simplest way to get started with WebDAV.

```bash
python examples/webdav/01_basic_webdav.py
```

**What it does:**
- Creates a VFS with sample files
- Starts a WebDAV server on port 8080
- Provides instructions for mounting in Finder/Explorer

**To mount:**
- macOS: Press Cmd+K, enter `http://localhost:8080`
- Windows: Map network drive to `http://localhost:8080`
- Linux: `sudo mount -t davfs http://localhost:8080 ~/mnt/chukfs`

### 02_background_server.py - Background Server

Shows how to run WebDAV in the background while continuing to work.

```bash
python examples/webdav/02_background_server.py
```

**What it does:**
- Starts server in background thread
- Adds files dynamically every 2 seconds
- Shows how VFS changes are immediately visible in mounted drive

**Use case**: Development servers, live data exports

### 03_readonly_server.py - Read-Only Server

Demonstrates serving files in read-only mode.

```bash
python examples/webdav/03_readonly_server.py
```

**What it does:**
- Creates sample reports
- Exposes them as read-only
- Clients can view and copy but not modify

**Use case**: Report sharing, snapshot distribution

## Quick Reference

### Start a Server

```python
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.adapters import WebDAVAdapter

vfs = SyncVirtualFileSystem()
vfs.write_file("/test.txt", "Hello!")

adapter = WebDAVAdapter(vfs, port=8080)
adapter.start()  # Blocking
```

### Mount in macOS Finder

1. Open Finder
2. Press `Cmd+K`
3. Enter: `http://localhost:8080`
4. Click "Connect"

### Mount in Terminal

```bash
# macOS
mkdir ~/mnt/chukfs
mount_webdav http://localhost:8080 ~/mnt/chukfs

# Linux
mkdir ~/mnt/chukfs
sudo mount -t davfs http://localhost:8080 ~/mnt/chukfs

# Windows PowerShell
net use Z: http://localhost:8080
```

## Features

- ✅ No kernel extensions required
- ✅ Works on all platforms
- ✅ Read/write support
- ✅ Directory browsing
- ✅ Background operation
- ✅ Read-only mode
- ✅ MIME type detection

## Advantages Over FUSE

| Feature | WebDAV | FUSE |
|---------|--------|------|
| Kernel Extension | ❌ Not needed | ✅ Required |
| System Restart | ❌ Not needed | ⚠️ Sometimes |
| Admin Rights | ❌ Not needed | ✅ Required |
| Setup Time | < 1 minute | 5-10 minutes |

## Common Use Cases

### Development Server
```python
# Share build output
vfs = SyncVirtualFileSystem()
vfs.write_file("/dist/app.js", compiled_code)

adapter = WebDAVAdapter(vfs, port=8080)
adapter.start_background()
```

### Data Export
```python
# Export database to browsable format
for table in database.tables():
    vfs.write_file(f"/export/{table.name}.csv", table.to_csv())

adapter = WebDAVAdapter(vfs, port=8080, readonly=True)
adapter.start()
```

### Testing
```python
# Create test fixtures
vfs = SyncVirtualFileSystem()
vfs.write_file("/fixtures/test-data.json", test_data)

with WebDAVAdapter(vfs, port=8080) as adapter:
    run_integration_tests(adapter.url)
```

## Documentation

- [WebDAV Documentation](../../docs/WEBDAV.md) - Complete guide
- [API Reference](../../docs/WEBDAV.md#api-reference) - Full API docs
- [Troubleshooting](../../docs/WEBDAV.md#troubleshooting) - Common issues

## Testing

### Test All Examples

```bash
# From project root
python test_all_examples.py
```

**Expected**: `4/4 tests passed` ✅

### Manual Testing

```bash
# Start server
python examples/webdav/01_basic_webdav.py

# In another terminal
curl http://localhost:8080/
# Should see directory listing

# Mount in Finder (macOS)
# Cmd+K → http://localhost:8080
```

## Next Steps

After trying these examples:

1. Read the [main examples guide](../README.md)
2. Try mounting the server in your OS
3. Experiment with different configurations
4. Check out the [FUSE examples](../mounting/) for native mounting

## Tips

- Use `host="0.0.0.0"` to allow remote access (be careful!)
- Set `readonly=True` for sharing snapshots
- Run in background with `start_background()` for long-running servers
- Use context manager (`with`) for automatic cleanup
