"""
Example demonstrating streaming and virtual mounts in chuk-virtual-fs

This example shows:
1. Streaming large files (write and read)
2. Mounting different providers at different paths
3. Cross-mount operations
"""

import asyncio
import tempfile
from pathlib import Path


async def streaming_example():
    """Demonstrate streaming file operations"""
    print("\n=== Streaming Example ===\n")

    from chuk_virtual_fs import AsyncVirtualFileSystem

    async with AsyncVirtualFileSystem(provider="memory") as fs:
        # Example 1: Stream write - Generate large file without loading all in memory
        print("1. Streaming write (simulating large file generation)")

        async def generate_large_data():
            """Async generator that yields chunks of data"""
            for i in range(1000):
                # Each chunk is 1KB, total 1MB file
                chunk = f"Line {i}: " + ("x" * 1000) + "\n"
                yield chunk.encode()

        # Write using streaming
        success = await fs.stream_write("/large_file.txt", generate_large_data())
        print(f"   Stream write successful: {success}")

        # Check file size
        node_info = await fs.get_node_info("/large_file.txt")
        print(f"   File size: {node_info.size / 1024:.2f} KB")

        # Example 2: Stream read - Read large file in chunks
        print("\n2. Streaming read (processing in chunks)")

        chunk_count = 0
        total_bytes = 0

        async for chunk in fs.stream_read("/large_file.txt", chunk_size=8192):
            chunk_count += 1
            total_bytes += len(chunk)
            if chunk_count <= 3:  # Show first 3 chunks
                print(f"   Chunk {chunk_count}: {len(chunk)} bytes")

        print(f"   Total chunks read: {chunk_count}")
        print(f"   Total bytes: {total_bytes}")


async def virtual_mounts_example():
    """Demonstrate virtual mounts with multiple providers"""
    print("\n=== Virtual Mounts Example ===\n")

    from chuk_virtual_fs import AsyncVirtualFileSystem

    # Create temporary directory for filesystem provider
    with tempfile.TemporaryDirectory() as tmpdir:
        # Start with memory provider as root
        async with AsyncVirtualFileSystem(
            provider="memory", enable_mounts=True
        ) as fs:
            # Create some files in root (memory)
            await fs.mkdir("/home")
            await fs.write_text("/home/readme.txt", "Root filesystem (memory)")

            print("1. Root filesystem (memory provider)")
            print(f"   Files in /home: {await fs.ls('/home')}")

            # Mount filesystem provider at /local
            print("\n2. Mounting filesystem provider at /local")
            mount_success = await fs.mount(
                "/local", provider="filesystem", root_path=tmpdir
            )
            print(f"   Mount successful: {mount_success}")

            # Mount another memory provider at /temp
            print("\n3. Mounting another memory provider at /temp")
            mount_success = await fs.mount("/temp", provider="memory")
            print(f"   Mount successful: {mount_success}")

            # List all mounts
            print("\n4. Active mounts:")
            for mount in fs.list_mounts():
                print(f"   {mount['mount_point']:20} -> {mount['provider']}")

            # Write to different mount points
            print("\n5. Writing to different mount points:")

            # Write to root (memory)
            await fs.write_text("/home/root_file.txt", "In root memory")
            print("   ✓ Written to /home/root_file.txt (root memory)")

            # Write to /local (filesystem)
            await fs.mkdir("/local/data")
            await fs.write_text(
                "/local/data/local_file.txt", "In local filesystem"
            )
            print("   ✓ Written to /local/data/local_file.txt (filesystem)")

            # Write to /temp (mounted memory)
            await fs.mkdir("/temp/scratch")
            await fs.write_text("/temp/scratch/temp_file.txt", "In temp memory")
            print("   ✓ Written to /temp/scratch/temp_file.txt (temp memory)")

            # Read from different mount points
            print("\n6. Reading from different mount points:")
            root_content = await fs.read_text("/home/root_file.txt")
            print(f"   /home/root_file.txt: {root_content}")

            local_content = await fs.read_text("/local/data/local_file.txt")
            print(f"   /local/data/local_file.txt: {local_content}")

            temp_content = await fs.read_text("/temp/scratch/temp_file.txt")
            print(f"   /temp/scratch/temp_file.txt: {temp_content}")

            # Verify files are on the real filesystem
            print("\n7. Verifying local mount (filesystem):")
            local_path = Path(tmpdir) / "data" / "local_file.txt"
            if local_path.exists():
                print(f"   ✓ File exists on real filesystem: {local_path}")
                print(f"   Content: {local_path.read_text()}")

            # Unmount
            print("\n8. Unmounting /temp:")
            unmount_success = await fs.unmount("/temp")
            print(f"   Unmount successful: {unmount_success}")

            # List mounts after unmount
            print("\n9. Active mounts after unmount:")
            for mount in fs.list_mounts():
                print(f"   {mount['mount_point']:20} -> {mount['provider']}")


async def combined_streaming_and_mounts():
    """Demonstrate streaming with virtual mounts"""
    print("\n=== Combined: Streaming + Mounts ===\n")

    from chuk_virtual_fs import AsyncVirtualFileSystem

    with tempfile.TemporaryDirectory() as tmpdir:
        async with AsyncVirtualFileSystem(
            provider="memory", enable_mounts=True
        ) as fs:
            # Mount filesystem at /backup
            await fs.mount("/backup", provider="filesystem", root_path=tmpdir)

            print("1. Generate large file in memory and stream to filesystem backup")

            # Generate data in memory
            async def generate_data():
                for i in range(500):
                    yield f"Record {i}: " + ("data" * 100) + "\n".encode()

            # Stream write to memory
            await fs.stream_write("/data.txt", generate_data())
            print("   ✓ Streamed to /data.txt (memory)")

            # Read from memory in chunks and process
            print("\n2. Stream from memory to backup (simulating backup process)")

            async def read_and_backup():
                """Read from one location and write to another"""
                chunks = []
                async for chunk in fs.stream_read("/data.txt", chunk_size=8192):
                    chunks.append(chunk)
                return chunks

            # Get data from memory
            backup_data = await read_and_backup()

            # Create backup stream
            async def backup_stream():
                for chunk in backup_data:
                    yield chunk

            # Stream to backup location
            await fs.stream_write("/backup/data_backup.txt", backup_stream())
            print("   ✓ Streamed to /backup/data_backup.txt (filesystem)")

            # Verify both exist
            memory_info = await fs.get_node_info("/data.txt")
            backup_info = await fs.get_node_info("/backup/data_backup.txt")

            print(f"\n3. Verification:")
            print(f"   Memory file: {memory_info.size / 1024:.2f} KB")
            print(f"   Backup file: {backup_info.size / 1024:.2f} KB")

            # Verify on real filesystem
            backup_path = Path(tmpdir) / "data_backup.txt"
            if backup_path.exists():
                print(
                    f"   ✓ Backup exists on filesystem: {backup_path.stat().st_size / 1024:.2f} KB"
                )


async def main():
    """Run all examples"""
    print("=" * 60)
    print("Chuk Virtual FS: Streaming and Virtual Mounts Examples")
    print("=" * 60)

    await streaming_example()
    await virtual_mounts_example()
    await combined_streaming_and_mounts()

    print("\n" + "=" * 60)
    print("Examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
