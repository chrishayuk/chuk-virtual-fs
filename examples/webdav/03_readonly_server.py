#!/usr/bin/env python3
"""
Read-Only WebDAV Server Example

Shows how to expose a VFS as read-only via WebDAV.

Usage:
    python examples/webdav/03_readonly_server.py
"""

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def main():
    """Run read-only WebDAV server."""
    from chuk_virtual_fs import SyncVirtualFileSystem
    from chuk_virtual_fs.adapters import WebDAVAdapter

    print("Creating read-only WebDAV server...\n")

    # Create VFS with data
    vfs = SyncVirtualFileSystem()

    # Simulate a data export/snapshot
    vfs.mkdir("/reports")
    vfs.write_file(
        "/reports/summary.txt",
        """Annual Report 2024

Total Users: 10,000
Total Revenue: $1M
Growth: 150%

This is a read-only export. You can view but not modify these files.
""",
    )

    vfs.write_file(
        "/reports/data.csv",
        """Date,Users,Revenue
2024-01,1000,$100k
2024-02,2000,$200k
2024-03,3500,$350k
""",
    )

    print("✅ Created sample reports")
    print()

    # Start read-only server
    adapter = WebDAVAdapter(
        vfs,
        port=8080,
        readonly=True,  # Read-only mode
    )

    print(f"🔒 Read-only server running at {adapter.url}")
    print()
    print("Users can:")
    print("  ✅ View files")
    print("  ✅ Copy files")
    print("  ✅ Download files")
    print()
    print("Users cannot:")
    print("  ❌ Create files")
    print("  ❌ Modify files")
    print("  ❌ Delete files")
    print()
    print("Press Ctrl+C to stop")
    print()

    try:
        adapter.start()
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped")
        adapter.stop()


if __name__ == "__main__":
    main()
