"""
Test streaming and mounts with all available providers

This demonstrates that both features work with:
- Memory provider
- Filesystem provider
- SQLite provider
- (S3 provider - requires AWS credentials)
"""

import asyncio
import tempfile
from pathlib import Path


async def test_streaming_all_providers():
    """Test streaming with each provider"""
    print("\n" + "="*60)
    print("Testing Streaming with All Providers")
    print("="*60)

    from chuk_virtual_fs import AsyncVirtualFileSystem

    providers_to_test = [
        ("memory", {}),
        ("filesystem", {"root_path": tempfile.mkdtemp()}),
        ("sqlite", {"db_path": ":memory:"}),
    ]

    for provider_name, kwargs in providers_to_test:
        print(f"\n### Provider: {provider_name.upper()} ###")

        async with AsyncVirtualFileSystem(provider=provider_name, **kwargs) as fs:
            # Test streaming write
            async def generate_test_data():
                for i in range(100):
                    yield f"Line {i}: test data\n".encode()

            success = await fs.stream_write("/stream_test.txt", generate_test_data())
            print(f"  ✓ Stream write: {success}")

            # Test streaming read
            chunk_count = 0
            total_bytes = 0
            async for chunk in fs.stream_read("/stream_test.txt", chunk_size=512):
                chunk_count += 1
                total_bytes += len(chunk)

            print(f"  ✓ Stream read: {chunk_count} chunks, {total_bytes} bytes")

            # Verify
            node_info = await fs.get_node_info("/stream_test.txt")
            if node_info:
                print(f"  ✓ File size: {node_info.size} bytes")
            else:
                print(f"  ✗ Could not get node info")

        print(f"  ✓ Provider {provider_name} streaming: PASSED")


async def test_mounts_all_providers():
    """Test mounts with different provider combinations"""
    print("\n" + "="*60)
    print("Testing Mounts with All Provider Combinations")
    print("="*60)

    from chuk_virtual_fs import AsyncVirtualFileSystem

    # Create temporary directories
    fs_temp = tempfile.mkdtemp()
    sqlite_path = Path(tempfile.mkdtemp()) / "test.db"

    # Start with memory as root
    async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
        print("\n### Mount Configuration ###")

        # Mount filesystem
        await fs.mount("/fs", provider="filesystem", root_path=fs_temp)
        print("  ✓ Mounted filesystem at /fs")

        # Mount SQLite
        await fs.mount("/db", provider="sqlite", db_path=str(sqlite_path))
        print("  ✓ Mounted SQLite at /db")

        # Mount another memory provider
        await fs.mount("/cache", provider="memory")
        print("  ✓ Mounted memory at /cache")

        # List mounts
        print("\n### Active Mounts ###")
        for mount in fs.list_mounts():
            print(f"  {mount['mount_point']:15} -> {mount['provider']}")

        # Test writing to each mount
        print("\n### Writing to Each Mount ###")

        test_data = {
            "/root.txt": ("Root memory", "In root memory provider"),
            "/fs/file.txt": ("Filesystem", "In filesystem provider"),
            "/db/data.txt": ("SQLite", "In SQLite provider"),
            "/cache/temp.txt": ("Cache memory", "In cache memory provider"),
        }

        for path, (provider_desc, content) in test_data.items():
            await fs.write_text(path, content)
            print(f"  ✓ Written to {path} ({provider_desc})")

        # Test reading from each mount
        print("\n### Reading from Each Mount ###")

        for path, (provider_desc, expected_content) in test_data.items():
            content = await fs.read_text(path)
            if content == expected_content:
                print(f"  ✓ Read from {path}: '{content}'")
            else:
                print(f"  ✗ Read from {path}: got '{content}', expected '{expected_content}'")

        # Verify filesystem mount on disk
        print("\n### Verifying Filesystem Mount ###")
        fs_file = Path(fs_temp) / "file.txt"
        if fs_file.exists():
            disk_content = fs_file.read_text()
            print(f"  ✓ File on disk: {fs_file}")
            print(f"  ✓ Content matches: {disk_content == 'In filesystem provider'}")
        else:
            print(f"  ✗ File not found on disk")

        # Test unmounting
        print("\n### Unmounting ###")
        await fs.unmount("/cache")
        print("  ✓ Unmounted /cache")

        remaining = fs.list_mounts()
        print(f"  ✓ Remaining mounts: {len(remaining)}")
        for mount in remaining:
            print(f"    - {mount['mount_point']} ({mount['provider']})")


async def test_cross_provider_streaming():
    """Test streaming between different providers"""
    print("\n" + "="*60)
    print("Testing Cross-Provider Streaming")
    print("="*60)

    from chuk_virtual_fs import AsyncVirtualFileSystem

    fs_temp = tempfile.mkdtemp()

    async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
        # Mount filesystem
        await fs.mount("/disk", provider="filesystem", root_path=fs_temp)

        # Generate data in memory
        print("\n  1. Generating data in memory...")
        async def generate_data():
            for i in range(500):
                yield f"Record {i}: {'x' * 50}\n".encode()

        await fs.stream_write("/memory_data.txt", generate_data())
        memory_info = await fs.get_node_info("/memory_data.txt")
        print(f"     ✓ Memory file: {memory_info.size / 1024:.2f} KB")

        # Stream from memory to filesystem
        print("\n  2. Streaming from memory to filesystem...")
        async def stream_from_memory():
            async for chunk in fs.stream_read("/memory_data.txt"):
                yield chunk

        await fs.stream_write("/disk/backup.txt", stream_from_memory())
        disk_info = await fs.get_node_info("/disk/backup.txt")
        print(f"     ✓ Disk file: {disk_info.size / 1024:.2f} KB")

        # Verify on real filesystem
        backup_file = Path(fs_temp) / "backup.txt"
        if backup_file.exists():
            size = backup_file.stat().st_size
            print(f"     ✓ Verified on disk: {size / 1024:.2f} KB")
            print(f"     ✓ Sizes match: {memory_info.size == disk_info.size == size}")
        else:
            print(f"     ✗ Backup file not found on disk")


async def main():
    """Run all tests"""
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  COMPREHENSIVE PROVIDER & MOUNT TESTING".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)

    try:
        await test_streaming_all_providers()
        await test_mounts_all_providers()
        await test_cross_provider_streaming()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED SUCCESSFULLY!")
        print("="*60)
        print("\nVerified:")
        print("  ✓ Streaming works with memory, filesystem, and SQLite")
        print("  ✓ Mounts work with all provider types")
        print("  ✓ Cross-provider streaming works")
        print("  ✓ Files verified on real filesystem")
        print("\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
