#!/usr/bin/env python3
"""
Basic WebDAV Server Example

This example shows how to expose a VirtualFileSystem via WebDAV protocol.
No kernel extensions or system modifications required!

Usage:
    python examples/webdav/01_basic_webdav.py

Then mount in Finder (macOS):
    1. Finder → Go → Connect to Server (Cmd+K)
    2. Enter: http://localhost:8080
    3. Click Connect

Or on command line:
    # macOS
    mkdir ~/mnt/chukfs
    mount_webdav http://localhost:8080 ~/mnt/chukfs

    # Linux
    mkdir ~/mnt/chukfs
    sudo mount -t davfs http://localhost:8080 ~/mnt/chukfs
"""

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def main():
    """Run basic WebDAV server."""
    from chuk_virtual_fs import SyncVirtualFileSystem
    from chuk_virtual_fs.adapters import WebDAVAdapter

    print("=" * 70)
    print("  chuk-virtual-fs WebDAV Server")
    print("=" * 70)
    print()

    # Create VFS and populate with sample data
    print("Creating virtual filesystem...")
    vfs = SyncVirtualFileSystem()

    # Create directory structure
    vfs.mkdir("/documents")
    vfs.mkdir("/code")
    vfs.mkdir("/data")

    # Add some files
    vfs.write_file("/documents/readme.txt", "Welcome to chuk-virtual-fs!")
    vfs.write_file(
        "/documents/getting-started.md",
        """# Getting Started

This is a virtual filesystem exposed via WebDAV.

## Features
- No kernel extensions required
- Works on macOS, Windows, Linux
- Standard WebDAV protocol
- Full read/write support

## Usage
You can browse and edit these files just like a regular disk!
""",
    )

    vfs.write_file(
        "/code/hello.py",
        """#!/usr/bin/env python3
print("Hello from the virtual filesystem!")
""",
    )

    vfs.write_file(
        "/data/config.json",
        """{
  "name": "chuk-vfs",
  "version": "1.0.0",
  "features": ["webdav", "memory", "s3"]
}
""",
    )

    print(f"✅ Created {len(vfs.ls('/'))} directories with sample files")
    print()

    # Create and start WebDAV server
    print("Starting WebDAV server...")
    adapter = WebDAVAdapter(
        vfs,
        host="127.0.0.1",
        port=8080,
        readonly=False,  # Allow writes
    )

    print()
    print("🎉 WebDAV server is running!")
    print()
    print("=" * 70)
    print("  How to Mount")
    print("=" * 70)
    print()
    print("macOS:")
    print("  1. Open Finder")
    print("  2. Press Cmd+K (Go → Connect to Server)")
    print("  3. Enter: http://localhost:8080")
    print("  4. Click Connect")
    print()
    print("Windows:")
    print("  1. Open File Explorer")
    print("  2. Right-click 'This PC' → Map network drive")
    print("  3. Enter: http://localhost:8080")
    print()
    print("Linux:")
    print("  mkdir ~/mnt/chukfs")
    print("  sudo mount -t davfs http://localhost:8080 ~/mnt/chukfs")
    print()
    print("=" * 70)
    print()
    print("Press Ctrl+C to stop the server")
    print()

    # Start server (blocking)
    try:
        adapter.start()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
        adapter.stop()


if __name__ == "__main__":
    main()
