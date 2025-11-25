#!/usr/bin/env python3
"""
Background WebDAV Server Example

Shows how to run a WebDAV server in the background while doing other work.

Usage:
    python examples/webdav/02_background_server.py
"""

import sys
import time
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def main():
    """Run WebDAV server in background."""
    from chuk_virtual_fs import SyncVirtualFileSystem
    from chuk_virtual_fs.adapters import WebDAVAdapter

    print("Starting WebDAV server in background...\n")

    # Create VFS and add initial content
    vfs = SyncVirtualFileSystem()
    vfs.mkdir("/workspace")
    vfs.write_file("/demo.txt", "Hello from background server!")
    vfs.write_file("/readme.txt", "This server adds files dynamically!")

    # Start server in background
    adapter = WebDAVAdapter(vfs, port=8080)
    adapter.start_background()

    # Give server a moment to fully initialize
    time.sleep(1)

    print(f"✅ Server running at {adapter.url}")
    print()
    print("You can now:")
    print("1. Mount in Finder: Cmd+K → http://localhost:8080")
    print("2. Continue working with the VFS in Python")
    print()

    # Simulate doing other work while server runs
    try:
        for i in range(10):
            time.sleep(2)

            # Add a new file every 2 seconds
            filename = f"/workspace/file_{i}.txt"
            content = f"File #{i} created at {time.strftime('%H:%M:%S')}"
            vfs.write_file(filename, content)

            print(
                f"Added {filename} - Total files in workspace: {len(vfs.ls('/workspace'))}"
            )

        print("\nDemo complete! Server still running...")
        print("Press Ctrl+C to stop")

        # Keep server running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nStopping server...")
        adapter.stop()
        print("✅ Server stopped")


if __name__ == "__main__":
    main()
