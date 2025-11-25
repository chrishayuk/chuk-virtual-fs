#!/usr/bin/env python3
"""
Memory Storage Provider Example
================================
Demonstrates using the in-memory storage provider for fast, temporary file operations.
Perfect for testing, caching, and ephemeral data that doesn't need persistence.
"""

import asyncio
import json
from datetime import datetime

from chuk_virtual_fs.fs_manager import VirtualFileSystem


async def main():
    print("=" * 60)
    print("Memory Storage Provider Example")
    print("=" * 60)

    print("\nConfiguration:")
    print("  - Provider: In-Memory")
    print("  - Session ID: demo-session")
    print("  - Sandbox ID: default")

    # Create a virtual file system with memory provider
    vfs = VirtualFileSystem(provider="memory", session_id="demo-session")

    await vfs.initialize()
    print("\n✓ Memory provider initialized successfully")

    # 1. Create directory structure
    print("\n1. Creating directory structure in memory...")
    await vfs.mkdir("/data")
    await vfs.mkdir("/data/logs")
    await vfs.mkdir("/data/exports")
    await vfs.mkdir("/backups")
    print("  ✓ Created directory structure")

    # 2. Upload various file types
    print("\n2. Creating files in memory...")

    # JSON data file
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "virtual-fs-demo",
        "status": "active",
        "metrics": {"cpu": 45.2, "memory": 78.5, "disk": 62.3},
    }
    await vfs.write_file("/data/metrics.json", json.dumps(data, indent=2).encode())
    print("  ✓ Created metrics.json")

    # Log file
    log_content = f"""[{datetime.utcnow().isoformat()}] Service started
[{datetime.utcnow().isoformat()}] Connected to database
[{datetime.utcnow().isoformat()}] Processing queue
[{datetime.utcnow().isoformat()}] Health check passed
"""
    await vfs.write_file("/data/logs/app.log", log_content.encode())
    print("  ✓ Created app.log")

    # CSV export
    csv_content = """id,name,value,timestamp
1,temperature,22.5,2024-01-01T10:00:00
2,humidity,65.3,2024-01-01T10:00:00
3,pressure,1013.25,2024-01-01T10:00:00
"""
    await vfs.write_file("/data/exports/sensor_data.csv", csv_content.encode())
    print("  ✓ Created sensor_data.csv")

    # Configuration file
    config = """# Application Configuration
app_name = VirtualFS Demo
environment = production
debug = false

[database]
host = localhost
port = 5432
name = virtualfs

[cache]
enabled = true
ttl = 3600
"""
    await vfs.write_file("/config.ini", config.encode())
    print("  ✓ Created config.ini")

    # 3. List memory contents
    print("\n3. Listing memory contents:")

    async def list_memory_tree(path, indent=0):
        """List memory objects in tree format"""
        try:
            items = await vfs.ls(path)
            for item in items:
                item_path = f"{path}/{item}" if path != "/" else f"/{item}"
                node_info = await vfs.get_node_info(item_path)

                if node_info and node_info.is_dir:
                    print(f"{'  ' * indent}📁 {item}/")
                    await list_memory_tree(item_path, indent + 1)
                else:
                    size = node_info.size if node_info and node_info.size else 0
                    print(f"{'  ' * indent}📄 {item} ({size} bytes)")
        except Exception as e:
            print(f"{'  ' * indent}⚠️ Error listing {path}: {e}")

    await list_memory_tree("/")

    # 4. Read files from memory
    print("\n4. Reading files from memory:")

    metrics_content = await vfs.read_file("/data/metrics.json")
    if metrics_content:
        metrics_data = json.loads(metrics_content.decode())
        print("\nMetrics data:")
        print(f"  - Timestamp: {metrics_data['timestamp']}")
        print(f"  - CPU: {metrics_data['metrics']['cpu']}%")
        print(f"  - Memory: {metrics_data['metrics']['memory']}%")

    # 5. Copy and move operations
    print("\n5. File operations in memory:")

    # Copy file
    success = await vfs.cp("/data/metrics.json", "/backups/metrics_backup.json")
    if success:
        print("  ✓ Copied metrics.json to backups")
    else:
        print("  ❌ Failed to copy metrics.json")

    # Check if backup exists
    exists = await vfs.exists("/backups/metrics_backup.json")
    print(f"  ✓ Backup exists: {exists}")

    # 6. Metadata operations
    print("\n6. Memory node metadata:")

    metadata = await vfs.get_metadata("/data/exports/sensor_data.csv")
    if metadata:
        print("\nsensor_data.csv metadata:")
        print(f"  - Size: {metadata.get('size', 0)} bytes")
        print(f"  - Created: {metadata.get('created_at', 'N/A')}")
        print(f"  - Modified: {metadata.get('modified_at', 'N/A')}")
        print(f"  - MIME type: {metadata.get('mime_type', 'N/A')}")

    # 7. Memory-specific features
    print("\n7. Memory-specific features:")

    # Calculate checksums
    try:
        # Read the file content first
        content = await vfs.read_file("/data/exports/sensor_data.csv")
        content_bytes = content.encode() if isinstance(content, str) else content
        checksum = await vfs.provider.calculate_checksum(content_bytes)
        if checksum:
            print(f"  ✓ SHA256 checksum: {checksum[:32]}...")
    except Exception as e:
        print(f"  ⚠️ Could not calculate checksum: {e}")

    # Session operations
    session_files = await vfs.provider.list_by_session("demo-session")
    print(f"  ✓ Files in session 'demo-session': {len(session_files)}")

    # 8. Batch operations
    print("\n8. Batch operations in memory:")

    # Use batch_write_files for files with content
    test_files = {
        "/data/logs/error.log": b"[ERROR] Sample error log\n",
        "/data/logs/warning.log": b"[WARNING] Sample warning log\n",
        "/data/logs/info.log": b"[INFO] Sample info log\n",
    }

    results = await vfs.batch_write_files(test_files)
    successful = sum(1 for r in results if r)
    print(f"  ✓ Created {successful} new log files")

    # 9. Search operations
    print("\n9. Finding files in memory:")

    log_files = await vfs.find("*.log", "/", recursive=True)
    print(f"  ✓ Found {len(log_files)} log files:")
    for file in sorted(log_files):
        print(f"    - {file}")

    # 10. Directory operations with nested paths
    print("\n10. Advanced directory operations:")

    # Create deeply nested directory
    deep_path = "/projects/2024/q1/reports/final"
    success = await vfs.provider.create_directory(deep_path)
    if success:
        print(f"  ✓ Created nested directory: {deep_path}")

        # List parent directories
        items = await vfs.ls("/projects/2024")
        print(f"  ✓ Items in /projects/2024: {items}")

    # 11. Copy directory with contents
    print("\n11. Copying directory with contents:")

    # Create a source directory with files
    await vfs.mkdir("/source")
    await vfs.write_file("/source/file1.txt", b"File 1 content")
    await vfs.write_file("/source/file2.txt", b"File 2 content")
    await vfs.mkdir("/source/subdir")
    await vfs.write_file("/source/subdir/file3.txt", b"File 3 content")

    # Copy the entire directory
    success = await vfs.provider.copy_node("/source", "/destination")
    if success:
        print("  ✓ Copied /source to /destination")

        # Verify the copy
        dest_files = await vfs.find("*", "/destination", recursive=True)
        print(f"  ✓ Files in destination: {len(dest_files)}")
        for file in sorted(dest_files):
            print(f"    - {file}")

    # 12. Storage statistics
    print("\n12. Memory storage statistics:")

    stats = await vfs.get_storage_stats()
    total_bytes = stats.get("total_size_bytes", 0)
    file_count = stats.get("file_count", 0)
    dir_count = stats.get("directory_count", 0)

    # Format size
    if total_bytes < 1024:
        size_str = f"{total_bytes} bytes"
    elif total_bytes < 1024 * 1024:
        size_str = f"{total_bytes / 1024:.2f} KB"
    else:
        size_str = f"{total_bytes / (1024 * 1024):.2f} MB"

    print(f"  - Total size: {size_str}")
    print(f"  - File count: {file_count}")
    print(f"  - Directory count: {dir_count}")
    print(f"  - Operations: {stats.get('operations', {})}")

    # 13. Final memory structure
    print("\n13. Final memory structure:")
    await list_memory_tree("/")

    # 14. Streaming with progress reporting and atomic writes
    print("\n14. Streaming large files with progress tracking:")

    # Progress tracking
    progress_data = {"bytes": 0, "updates": 0}

    def track_progress(bytes_written, total_bytes):
        """Track progress during streaming write"""
        progress_data["bytes"] = bytes_written
        progress_data["updates"] += 1

        # Show progress every 50KB
        if bytes_written % (50 * 1024) < 1024:
            print(f"  Progress: {bytes_written / 1024:.1f} KB written...")

    # Generate large file
    async def generate_large_data():
        """Generate ~500KB of data"""
        for i in range(500):
            yield (f"Record {i:04d}: " + ("data" * 100) + "\n").encode()

    # Stream write with progress callback
    await vfs.stream_write(
        "/data/large_export.dat",
        generate_large_data(),
        progress_callback=track_progress,
    )
    print(f"  ✓ Streaming complete: {progress_data['bytes'] / 1024:.1f} KB written")
    print(f"  ✓ Progress updates: {progress_data['updates']}")
    print("  ✓ Atomic write ensured no corruption on errors")

    # Verify the file
    node_info = await vfs.get_node_info("/data/large_export.dat")
    print(f"  ✓ Final file size: {node_info.size / 1024:.1f} KB")

    # 15. Cleanup demonstration
    print("\n15. Cleanup operations:")

    # Delete a specific session's files (optional)
    if False:  # Set to True to demonstrate session cleanup
        deleted = await vfs.provider.delete_session("demo-session")
        print(f"  ✓ Deleted {deleted} files from session 'demo-session'")

    # Perform general cleanup
    cleanup_stats = await vfs.provider.cleanup()
    print("  ✓ Cleanup completed:")
    print(f"    - Bytes freed: {cleanup_stats.get('bytes_freed', 0)}")
    print(f"    - Files removed: {cleanup_stats.get('files_removed', 0)}")

    # Close the filesystem
    await vfs.close()
    print("\n✅ Memory provider example completed successfully!")

    print("\n💡 Tips for using memory provider:")
    print("  - Perfect for unit tests and temporary data")
    print("  - Ultra-fast operations with no I/O overhead")
    print("  - Data is lost when process ends")
    print("  - Use session IDs to isolate different contexts")
    print("  - Great for caching and intermediate processing")


if __name__ == "__main__":
    asyncio.run(main())
