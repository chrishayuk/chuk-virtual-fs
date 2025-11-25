#!/usr/bin/env python3
"""
Example 4: Redis-Backed Persistent Mount

This example demonstrates:
1. Using Redis as persistent backend
2. Multiple processes can share the same VFS
3. Changes persist across mount/unmount cycles
4. Perfect for distributed/collaborative workflows

Usage:
    # Terminal 1: Start Redis
    redis-server

    # Terminal 2: Run this script
    python examples/mounting/04_redis_persistence.py

    # Terminal 3: Access the mounted filesystem
    cd /tmp/chukfs_redis
    echo "Hello from terminal 3" > shared_file.txt

    # Back in Terminal 2: See the file appear in VFS
"""

import asyncio
import sys
import time
from pathlib import Path

from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.mount import MountOptions, mount


async def monitor_vfs(vfs: SyncVirtualFileSystem, interval: int = 2) -> None:
    """Monitor VFS for changes."""
    last_files = set()

    while True:
        try:
            current_files = set(vfs.ls("/"))

            # Check for new files
            new_files = current_files - last_files
            if new_files:
                print(f"\n📁 New files detected: {', '.join(new_files)}")
                for file in new_files:
                    try:
                        if vfs.is_file(f"/{file}"):
                            content = vfs.read_file(f"/{file}")
                            preview = content[:100] if len(content) > 100 else content
                            print(f"   Content: {preview}")
                    except Exception as e:
                        print(f"   (Could not read: {e})")

            # Check for removed files
            removed_files = last_files - current_files
            if removed_files:
                print(f"\n🗑️  Files removed: {', '.join(removed_files)}")

            last_files = current_files

        except Exception as e:
            print(f"Monitor error: {e}")

        await asyncio.sleep(interval)


async def main() -> None:
    print("=" * 70)
    print("Example 4: Redis-Backed Persistent Mount")
    print("=" * 70)

    # Check if Redis provider is available
    try:
        from chuk_virtual_fs.providers.redis_provider import RedisProvider
    except ImportError:
        print("\n❌ Redis provider not available!")
        print("   This is expected if redis dependencies aren't installed")
        return

    print("\n1. Connecting to Redis...")
    redis_url = "redis://localhost:6379"
    redis_prefix = "chuk_demo:"

    try:
        provider = RedisProvider(redis_url=redis_url, prefix=redis_prefix)
        print(f"   ✅ Connected to {redis_url}")
    except Exception as e:
        print(f"\n❌ Could not connect to Redis: {e}")
        print("\nMake sure Redis is running:")
        print("  brew install redis && redis-server")
        print("  # or")
        print("  docker run -p 6379:6379 redis")
        return

    # Create VFS with Redis backend
    print("\n2. Creating VFS with Redis backend...")
    vfs = SyncVirtualFileSystem()
    vfs.provider = provider

    # Check if there's existing data
    existing_files = vfs.ls("/")
    if existing_files:
        print(f"   📦 Found existing files in Redis: {existing_files}")
    else:
        print("   📦 No existing files (fresh start)")

        # Add some initial files
        print("\n3. Adding initial files...")
        vfs.write_file("/readme.md", "# Shared Filesystem\n\nThis is backed by Redis!")
        vfs.write_file("/timestamp.txt", f"Created at: {time.ctime()}")
        vfs.mkdir("/shared")
        vfs.write_file("/shared/info.txt", "Files here are shared across all mounts")
        print("   ✅ Added 3 files and 1 directory")

    # Setup mount point
    if sys.platform == "win32":
        mount_point = Path("Z:")
    else:
        mount_point = Path("/tmp/chukfs_redis")
        mount_point.mkdir(exist_ok=True)

    print(f"\n4. Mounting at {mount_point}...")

    try:
        async with mount(vfs, mount_point, MountOptions()):
            print("   ✅ Mounted!")

            print("\n" + "=" * 70)
            print("🔴 Redis-backed filesystem is live!")
            print("=" * 70)
            print("\n📝 Try these in another terminal:")
            print(f"  cd {mount_point}")
            print("  ls -la")
            print("  cat readme.md")
            print("  echo 'Hello World' > message.txt")
            print("  mkdir docs")
            print("  echo 'Documentation' > docs/guide.md")
            print("\n💡 All changes are persisted in Redis!")
            print("   You can unmount/remount and files will still be there.")
            print("\n📊 Monitoring for changes...")
            print("=" * 70)

            # Start monitoring
            monitor_task = asyncio.create_task(monitor_vfs(vfs))

            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                monitor_task.cancel()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

    print("\n\n5. Demonstrating persistence...")
    print("   Files remain in Redis after unmounting:")

    # Show what's still in Redis
    final_files = vfs.ls("/")
    print(f"   📦 Files in Redis: {final_files}")

    print("\n   You can mount again and they'll still be there!")
    print(
        f"   Try: chuk-vfs-mount --backend redis --redis-url {redis_url} --mount {mount_point}"
    )

    print("\n✅ Example complete!")
    print("\nKey takeaways:")
    print("  ✓ Changes persist across mount/unmount")
    print("  ✓ Multiple processes can share same VFS")
    print("  ✓ Perfect for distributed workflows")
    print("  ✓ No file system cleanup needed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
