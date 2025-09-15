#!/usr/bin/env python3
"""
S3 Storage Provider Example
===========================
Demonstrates using the S3 storage provider for cloud-based file operations.
Perfect for scalable, persistent storage with AWS S3 or S3-compatible services.

Prerequisites:
- AWS credentials configured (via environment variables or ~/.aws/credentials)
- An S3 bucket with appropriate permissions
- boto3 library installed
"""

import asyncio
import json
import os
import posixpath
from datetime import datetime
from chuk_virtual_fs.fs_manager import VirtualFileSystem

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ Loaded environment variables from .env file")
except ImportError:
    print("ℹ️ python-dotenv not installed, using system environment variables")
    print("  Install with: pip install python-dotenv")


async def cleanup_demo_data(vfs):
    """Clean up all demo data from S3"""
    import logging
    
    # Temporarily suppress warning messages during cleanup
    original_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.ERROR)
    
    deleted_count = 0
    
    try:
        # Find and delete all files recursively
        all_files = await vfs.find(pattern="*", path="/", recursive=True)
        for file_path in all_files:
            try:
                if await vfs.rm(file_path):
                    deleted_count += 1
            except:
                pass
        
        # Also try to delete specific known files that might remain
        known_files = [
            "/config.ini",
            "/data/metrics.json",
            "/data/logs/app.log",
            "/data/logs/error.log",
            "/data/logs/warning.log",
            "/data/logs/info.log",
            "/data/exports/sensor_data.csv",
            "/backups/metrics_backup.json"
        ]
        
        for file_path in known_files:
            try:
                if await vfs.exists(file_path):
                    if await vfs.rm(file_path):
                        deleted_count += 1
            except:
                pass
        
        # Note: S3 doesn't have real directories, they're just prefixes
        # So we don't need to explicitly delete directories
        
    except Exception as e:
        # Silently handle cleanup errors
        pass
    finally:
        # Restore original logging level
        logging.getLogger().setLevel(original_level)
    
    return deleted_count


async def main():
    print("=" * 60)
    print("S3 Storage Provider Example")
    print("=" * 60)
    
    # Configuration - Update these with your S3 settings
    BUCKET_NAME = os.environ.get("S3_BUCKET", "my-virtual-fs-bucket")
    PREFIX = os.environ.get("S3_PREFIX", "virtual-fs-demo/")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    
    print(f"\nConfiguration:")
    print(f"  - Bucket: {BUCKET_NAME}")
    print(f"  - Prefix: {PREFIX}")
    print(f"  - Region: {AWS_REGION}")
    
    # Create a virtual file system with S3 provider
    vfs = VirtualFileSystem(
        provider="s3",
        bucket_name=BUCKET_NAME,
        prefix=PREFIX,
        region_name=AWS_REGION
    )
    
    try:
        await vfs.initialize()
        print("\n✓ Connected to S3 successfully")
    except Exception as e:
        print(f"\n❌ Failed to connect to S3: {e}")
        print("\nPlease ensure:")
        print("  1. AWS credentials are configured")
        print("  2. The bucket exists and is accessible")
        print("  3. boto3 is installed (pip install boto3)")
        return
    
    # Clean up any existing demo data first
    print("\n🧹 Cleaning up any existing demo data...")
    await cleanup_demo_data(vfs)
    print("  ✓ Ready for fresh demo")
    
    # 1. Create directory structure
    print("\n1. Creating directory structure in S3...")
    await vfs.mkdir("/data")
    await vfs.mkdir("/data/logs")
    await vfs.mkdir("/data/exports")
    await vfs.mkdir("/backups")
    print("  ✓ Created directory structure")
    
    # 2. Upload various file types
    print("\n2. Uploading files to S3...")
    
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
    print("  ✓ Uploaded metrics.json")
    
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
    print("  ✓ Uploaded app.log")
    
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
    print("  ✓ Uploaded sensor_data.csv")
    
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
    print("  ✓ Uploaded config.ini")
    
    # 3. List S3 contents
    print("\n3. Listing S3 contents:")
    
    async def list_s3_tree(path, indent=0):
        """List S3 objects in tree format"""
        try:
            items = await vfs.ls(path)
            for item in items:
                item_path = f"{path}/{item}" if path != "/" else f"/{item}"
                node_info = await vfs.get_node_info(item_path)
                
                if node_info and node_info.is_dir:
                    print(f"{'  ' * indent}📁 {item}/")
                    await list_s3_tree(item_path, indent + 1)
                else:
                    size = node_info.size if node_info and node_info.size else 0
                    print(f"{'  ' * indent}📄 {item} ({size} bytes)")
        except Exception as e:
            print(f"{'  ' * indent}⚠️ Error listing {path}: {e}")
    
    await list_s3_tree("/")
    
    # 4. Read files from S3
    print("\n4. Reading files from S3:")
    
    metrics_content = await vfs.read_file("/data/metrics.json")
    if metrics_content:
        metrics_data = json.loads(metrics_content.decode())
        print(f"\nMetrics data:")
        print(f"  - Timestamp: {metrics_data['timestamp']}")
        print(f"  - CPU: {metrics_data['metrics']['cpu']}%")
        print(f"  - Memory: {metrics_data['metrics']['memory']}%")
    
    # 5. Copy and move operations
    print("\n5. File operations in S3:")
    
    # Create backups directory first
    await vfs.mkdir("/backups")
    
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
    print("\n6. S3 object metadata:")
    
    metadata = await vfs.get_metadata("/data/exports/sensor_data.csv")
    if metadata:
        print(f"\nsensor_data.csv metadata:")
        print(f"  - Size: {metadata.get('ContentLength', 0)} bytes")
        print(f"  - Modified: {metadata.get('LastModified', 'N/A')}")
        print(f"  - MIME type: {metadata.get('ContentType', 'N/A')}")
    
    # 7. Generate presigned URL (S3 specific feature)
    print("\n7. S3 presigned URLs:")
    
    try:
        url = await vfs.generate_presigned_url("/data/exports/sensor_data.csv", expires_in=3600)
        if url:
            print(f"  ✓ Generated presigned URL (expires in 1 hour):")
            print(f"    {url[:80]}..." if len(url) > 80 else f"    {url}")
    except Exception as e:
        print(f"  ⚠️ Could not generate presigned URL: {e}")
    
    # 8. Batch operations
    print("\n8. Batch operations in S3:")
    
    # Create multiple files - using write_file to ensure content is properly saved
    # Note: batch_create_files has a race condition with content, so we use batch_write_files instead
    test_files = {
        "/data/logs/error.log": b"[ERROR] Sample error log\n",
        "/data/logs/warning.log": b"[WARNING] Sample warning log\n",
        "/data/logs/info.log": b"[INFO] Sample info log\n"
    }
    
    # Remove any existing files first
    for path in test_files.keys():
        if await vfs.exists(path):
            await vfs.rm(path)
    
    # Use batch_write_files for files with content
    results = await vfs.batch_write_files(test_files)
    successful = sum(1 for r in results if r)
    print(f"  ✓ Created {successful} new log files")
    
    # 9. Search operations
    print("\n9. Finding files in S3:")
    
    log_files = await vfs.find("*.log", "/", recursive=True)  # Search from root
    print(f"  ✓ Found {len(log_files)} log files:")
    for file in sorted(log_files):
        print(f"    - {file}")
    
    # 10. Cleanup (optional - be careful in production!)
    print("\n10. Cleanup operations:")
    
    # Delete backup file to demonstrate cleanup
    if await vfs.exists("/backups/metrics_backup.json"):
        await vfs.rm("/backups/metrics_backup.json")
        print("  ✓ Removed backup file")
    
    # Count remaining files before final cleanup
    all_files = await vfs.find(pattern="*", path="/", recursive=True)
    print(f"  ✓ {len(all_files)} files remaining before final cleanup")
    
    # 11. Storage statistics
    print("\n11. S3 storage statistics:")
    
    stats = await vfs.get_storage_stats()
    total_bytes = stats.get('total_size', 0)
    file_count = stats.get('file_count', 0)
    dir_count = stats.get('directory_count', 0)
    
    # Format size more intelligently
    if total_bytes < 1024:
        size_str = f"{total_bytes} bytes"
    elif total_bytes < 1024 * 1024:
        size_str = f"{total_bytes / 1024:.2f} KB"
    else:
        size_str = f"{total_bytes / (1024 * 1024):.2f} MB"
    
    print(f"  - Total size: {size_str}")
    print(f"  - File count: {file_count}")
    print(f"  - Directory count: {dir_count}")
    
    # 12. Final S3 structure
    print("\n12. Final S3 structure:")
    await list_s3_tree("/")
    
    # 13. Final cleanup - remove all demo data
    print("\n13. Final cleanup - removing all demo data...")
    deleted = await cleanup_demo_data(vfs)
    
    # Verify cleanup was successful
    remaining_files = await vfs.find(pattern="*", path="/", recursive=True)
    
    if len(remaining_files) == 0:
        print(f"  ✓ All demo data removed successfully ({deleted} files deleted)")
    else:
        print(f"  ⚠️ {len(remaining_files)} files may remain in S3")
        for f in remaining_files[:5]:  # Show first 5
            print(f"    - {f}")
    
    # Close the filesystem
    await vfs.close()
    print("\n✅ S3 example completed successfully!")
    
    print("\n💡 Tips for production use:")
    print("  - Use IAM roles for EC2/Lambda instead of keys")
    print("  - Enable versioning for important data")
    print("  - Set up lifecycle policies for log rotation")
    print("  - Use S3 Transfer Acceleration for large files")
    print("  - Consider using S3 Intelligent-Tiering for cost optimization")


if __name__ == "__main__":
    # Check for AWS credentials
    if not (os.environ.get("AWS_ACCESS_KEY_ID") or os.path.exists(os.path.expanduser("~/.aws/credentials"))):
        print("⚠️  Warning: AWS credentials not found!")
        print("Please configure AWS credentials using one of these methods:")
        print("  1. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        print("  2. Run 'aws configure' to set up credentials")
        print("  3. Use IAM roles if running on EC2")
        print("\nExample:")
        print("  export AWS_ACCESS_KEY_ID=your_access_key")
        print("  export AWS_SECRET_ACCESS_KEY=your_secret_key")
        print("  export AWS_REGION=us-east-1")
    else:
        asyncio.run(main())