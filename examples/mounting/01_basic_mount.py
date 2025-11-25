#!/usr/bin/env python3
"""
Example 1: Basic Mounting

This example demonstrates the simplest possible mount scenario:
- Create a VFS with some files
- Mount it at a local directory
- Access files from another terminal

Usage:
    python examples/mounting/01_basic_mount.py

    # In another terminal:
    ls /tmp/chukfs_basic
    cat /tmp/chukfs_basic/hello.txt
"""

import asyncio
import sys
from pathlib import Path

from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.mount import MountOptions, mount


async def main() -> None:
    print("=" * 60)
    print("Example 1: Basic Mounting")
    print("=" * 60)

    # Create VFS
    print("\n1. Creating virtual filesystem...")
    vfs = SyncVirtualFileSystem()

    # Add some files
    vfs.write_file("/hello.txt", "Hello from virtual filesystem!")
    vfs.write_file("/readme.md", "# Virtual Filesystem\n\nThis is mounted!")
    vfs.mkdir("/data")
    vfs.write_file("/data/config.json", '{"status": "mounted"}')

    print("   ✅ Created 3 files and 1 directory")

    # Setup mount point
    if sys.platform == "win32":
        mount_point = Path("Z:")
        print(f"\n2. Will mount at: {mount_point} (Windows drive)")
    else:
        mount_point = Path("/tmp/chukfs_basic")
        mount_point.mkdir(exist_ok=True)
        print(f"\n2. Will mount at: {mount_point}")

    # Mount
    print("\n3. Mounting filesystem...")
    options = MountOptions(readonly=False, debug=False)

    try:
        async with mount(vfs, mount_point, options):
            print("   ✅ Mounted successfully!")
            print("\n" + "=" * 60)
            print("Filesystem is now accessible!")
            print("=" * 60)
            print("\nTry these commands in another terminal:")
            print(f"  ls -la {mount_point}")
            print(f"  cat {mount_point}/hello.txt")
            print(f"  cat {mount_point}/data/config.json")
            print(f"  echo 'new content' > {mount_point}/new_file.txt")
            print("\nPress Ctrl+C to unmount and exit...")
            print("=" * 60 + "\n")

            # Keep running
            await asyncio.Event().wait()

    except KeyboardInterrupt:
        print("\n\n4. Unmounting...")
        print("   ✅ Unmounted successfully")
        print("\n✅ Example complete!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        print("\nMake sure FUSE is installed:", file=sys.stderr)
        print("  macOS: brew install macfuse", file=sys.stderr)
        print("  Linux: sudo apt-get install fuse3 libfuse3-dev", file=sys.stderr)
        sys.exit(1)
