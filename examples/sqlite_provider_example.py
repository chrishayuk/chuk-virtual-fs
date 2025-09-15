#!/usr/bin/env python3
"""
SQLite Storage Provider Example
===============================
Demonstrates using the SQLite storage provider for persistent, local file operations.
Perfect for applications requiring local persistence with SQL database benefits.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from chuk_virtual_fs.fs_manager import VirtualFileSystem


async def main():
    print("=" * 60)
    print("SQLite Storage Provider Example")
    print("=" * 60)
    
    # Create a temporary database file for the demo
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    db_path = temp_db.name
    
    print(f"\nConfiguration:")
    print(f"  - Provider: SQLite")
    print(f"  - Database: {db_path}")
    print(f"  - Persistent: Yes")
    
    # Create a virtual file system with SQLite provider
    vfs = VirtualFileSystem(
        provider="sqlite",
        db_path=db_path
    )
    
    await vfs.initialize()
    print("\n✓ SQLite provider initialized successfully")
    
    # 1. Create directory structure
    print("\n1. Creating directory structure in SQLite...")
    await vfs.mkdir("/data")
    await vfs.mkdir("/data/logs")
    await vfs.mkdir("/data/exports")
    await vfs.mkdir("/backups")
    print("  ✓ Created directory structure")
    
    # 2. Create various file types
    print("\n2. Creating files in SQLite...")
    
    # JSON data file
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "virtual-fs-demo",
        "status": "active",
        "metrics": {
            "cpu": 45.2,
            "memory": 78.5,
            "disk": 62.3
        }
    }
    await vfs.write_file(
        "/data/metrics.json",
        json.dumps(data, indent=2).encode()
    )
    print("  ✓ Created metrics.json")
    
    # Log file
    log_content = f"""[{datetime.utcnow().isoformat()}] Service started
[{datetime.utcnow().isoformat()}] Connected to database
[{datetime.utcnow().isoformat()}] Processing queue
[{datetime.utcnow().isoformat()}] Health check passed
"""
    await vfs.write_file(
        "/data/logs/app.log",
        log_content.encode()
    )
    print("  ✓ Created app.log")
    
    # CSV export
    csv_content = """id,name,value,timestamp
1,temperature,22.5,2024-01-01T10:00:00
2,humidity,65.3,2024-01-01T10:00:00
3,pressure,1013.25,2024-01-01T10:00:00
"""
    await vfs.write_file(
        "/data/exports/sensor_data.csv",
        csv_content.encode()
    )
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
    await vfs.write_file(
        "/config.ini",
        config.encode()
    )
    print("  ✓ Created config.ini")
    
    # 3. List SQLite contents
    print("\n3. Listing SQLite contents:")
    
    async def list_sqlite_tree(path, indent=0):
        """List SQLite objects in tree format"""
        try:
            items = await vfs.ls(path)
            for item in items:
                item_path = f"{path}/{item}" if path != "/" else f"/{item}"
                node_info = await vfs.get_node_info(item_path)
                
                if node_info and node_info.is_dir:
                    print(f"{'  ' * indent}📁 {item}/")
                    await list_sqlite_tree(item_path, indent + 1)
                else:
                    size = node_info.size if node_info and node_info.size else 0
                    print(f"{'  ' * indent}📄 {item} ({size} bytes)")
        except Exception as e:
            print(f"{'  ' * indent}⚠️ Error listing {path}: {e}")
    
    await list_sqlite_tree("/")
    
    # 4. Read files from SQLite
    print("\n4. Reading files from SQLite:")
    
    metrics_content = await vfs.read_file("/data/metrics.json")
    if metrics_content:
        metrics_data = json.loads(metrics_content.decode())
        print(f"\nMetrics data:")
        print(f"  - Timestamp: {metrics_data['timestamp']}")
        print(f"  - CPU: {metrics_data['metrics']['cpu']}%")
        print(f"  - Memory: {metrics_data['metrics']['memory']}%")
    
    # 5. Copy and move operations
    print("\n5. File operations in SQLite:")
    
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
    print("\n6. SQLite node metadata:")
    
    metadata = await vfs.get_metadata("/data/exports/sensor_data.csv")
    if metadata:
        print(f"\nsensor_data.csv metadata:")
        print(f"  - Size: {metadata.get('size', 0)} bytes")
        print(f"  - Created: {metadata.get('created_at', 'N/A')}")
        print(f"  - Modified: {metadata.get('modified_at', 'N/A')}")
        print(f"  - MIME type: {metadata.get('mime_type', 'N/A')}")
    
    # 7. SQLite-specific features
    print("\n7. SQLite-specific features:")
    
    # Calculate checksums
    try:
        checksum = await vfs.provider.calculate_checksum("/data/exports/sensor_data.csv", "md5")
        if checksum:
            print(f"  ✓ MD5 checksum: {checksum[:32]}...")
    except Exception as e:
        print(f"  ⚠️ Could not calculate checksum: {e}")
    
    # Database file size
    db_size = os.path.getsize(db_path)
    print(f"  ✓ Database file size: {db_size} bytes")
    
    # 8. Batch operations
    print("\n8. Batch operations in SQLite:")
    
    # Use batch_write_files for files with content
    test_files = {
        "/data/logs/error.log": b"[ERROR] Sample error log\n",
        "/data/logs/warning.log": b"[WARNING] Sample warning log\n",
        "/data/logs/info.log": b"[INFO] Sample info log\n"
    }
    
    results = await vfs.batch_write_files(test_files)
    successful = sum(1 for r in results if r)
    print(f"  ✓ Created {successful} new log files")
    
    # 9. Search operations
    print("\n9. Finding files in SQLite:")
    
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
    print("\n12. SQLite storage statistics:")
    
    stats = await vfs.get_storage_stats()
    total_bytes = stats.get('total_size_bytes', 0)
    file_count = stats.get('file_count', 0)
    dir_count = stats.get('directory_count', 0)
    
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
    print(f"  - Database file: {db_size} bytes")
    
    # 13. Final SQLite structure
    print("\n13. Final SQLite structure:")
    await list_sqlite_tree("/")
    
    # 14. Persistence demonstration
    print("\n14. Persistence demonstration:")
    
    # Close and reopen the database
    await vfs.close()
    print("  ✓ Closed database connection")
    
    # Create new VFS instance with same database
    vfs2 = VirtualFileSystem(
        provider="sqlite",
        db_path=db_path
    )
    await vfs2.initialize()
    print("  ✓ Reopened database connection")
    
    # Verify data persisted
    persisted_files = await vfs2.find("*", "/", recursive=True)
    print(f"  ✓ {len(persisted_files)} files persisted after restart")
    
    # Verify content is intact
    persisted_content = await vfs2.read_file("/data/metrics.json")
    if persisted_content:
        persisted_data = json.loads(persisted_content.decode())
        print(f"  ✓ Data integrity verified: {persisted_data['service']}")
    
    # 15. Cleanup operations
    print("\n15. Cleanup operations:")
    
    # Perform cleanup (removes /tmp files)
    cleanup_stats = await vfs2.provider.cleanup()
    print(f"  ✓ Cleanup completed:")
    print(f"    - Bytes freed: {cleanup_stats.get('bytes_freed', 0)}")
    print(f"    - Files removed: {cleanup_stats.get('files_removed', 0)}")
    
    # Close the filesystem
    await vfs2.close()
    print("\n✅ SQLite provider example completed successfully!")
    
    print(f"\n📁 Database file location: {db_path}")
    print("💡 Tips for using SQLite provider:")
    print("  - Provides ACID transactions and data integrity")
    print("  - Perfect for local applications requiring persistence")
    print("  - Handles concurrent access automatically")
    print("  - No external database server required")
    print("  - Excellent for development and small to medium datasets")
    
    # Automatically clean up the temporary database file for demo
    try:
        os.unlink(db_path)
        print(f"\n✓ Automatically cleaned up temporary database: {db_path}")
    except Exception as e:
        print(f"\n⚠️ Could not delete temporary database: {e}")
        print(f"📂 Database preserved at: {db_path}")


if __name__ == "__main__":
    asyncio.run(main())