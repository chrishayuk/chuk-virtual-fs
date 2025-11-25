#!/usr/bin/env python3
"""
Simple demo of mounting chuk-virtual-fs.

This script creates a virtual filesystem, adds some files, and mounts it.
You can then access the files from any application on your system.

Usage:
    python examples/mount_demo.py
"""

import asyncio
import sys
from pathlib import Path

from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.mount import MountOptions, mount


async def main() -> None:
    """Run the mount demo."""
    # Create a virtual filesystem
    print("Creating virtual filesystem...")
    vfs = SyncVirtualFileSystem()

    # Add some demo files
    vfs.mkdir("/docs")
    vfs.write_file("/docs/README.md", "# Virtual Filesystem Demo\n\nThis is a demo!")
    vfs.write_file("/docs/hello.txt", "Hello from chuk-virtual-fs!")

    vfs.mkdir("/src")
    vfs.write_file(
        "/src/example.py",
        '''#!/usr/bin/env python3
"""Example Python file in virtual filesystem."""

def hello():
    print("Hello from virtual filesystem!")

if __name__ == "__main__":
    hello()
''',
    )

    vfs.mkdir("/data")
    vfs.write_file("/data/config.json", '{"name": "demo", "version": "1.0.0"}')

    print("\nVirtual filesystem contents:")
    for path in [
        "/docs/README.md",
        "/docs/hello.txt",
        "/src/example.py",
        "/data/config.json",
    ]:
        print(f"  {path}")

    # Determine mount point based on platform
    if sys.platform == "win32":
        mount_point = Path("Z:")
        print("\n⚠️  Windows detected. Will mount as Z: drive.")
        print("⚠️  Ensure Z: is not already in use.")
    else:
        mount_point = Path("/tmp/chukfs_demo")
        mount_point.mkdir(exist_ok=True)

    print(f"\n📁 Mount point: {mount_point}")
    print("\n🚀 Mounting filesystem...")
    print("   Press Ctrl+C to unmount and exit\n")

    # Create mount options
    options = MountOptions(
        readonly=False,
        debug=False,
    )

    # Mount the filesystem
    try:
        async with mount(vfs, mount_point, options) as _:
            print(f"✅ Mounted at {mount_point}")
            print("\nYou can now access the files:")
            print(f"  ls {mount_point}")
            print(f"  cat {mount_point}/docs/README.md")
            print(f"  python {mount_point}/src/example.py")
            print("\nThe filesystem will remain mounted until you press Ctrl+C\n")

            # Wait indefinitely
            await asyncio.Event().wait()

    except KeyboardInterrupt:
        print("\n\n👋 Unmounting filesystem...")

    print("✅ Unmounted successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        print("\nTroubleshooting:", file=sys.stderr)
        print(
            "- Ensure FUSE is installed (Linux: fuse3, macOS: macfuse)", file=sys.stderr
        )
        print("- Install with: pip install chuk-virtual-fs[mount]", file=sys.stderr)
        print("- Check mount point is not already in use", file=sys.stderr)
        sys.exit(1)
