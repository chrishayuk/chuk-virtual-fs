#!/usr/bin/env python3
"""
List S3 Bucket Contents Script
Lists all contents from the configured S3 bucket with the specified prefix.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import the virtual fs
sys.path.insert(0, str(Path(__file__).parent.parent))

from chuk_virtual_fs import VirtualFileSystem
from dotenv import load_dotenv


async def list_s3_bucket():
    """List all contents from the S3 bucket"""
    
    # Load environment variables from parent directory
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print("✓ Loaded environment variables from .env file")
    else:
        load_dotenv()
    
    # Configuration
    BUCKET_NAME = os.environ.get("S3_BUCKET", "my-virtual-fs-bucket")
    PREFIX = os.environ.get("S3_PREFIX", "virtual-fs-demo/")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    
    print("=" * 60)
    print("S3 BUCKET CONTENTS LISTING")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  - Bucket: {BUCKET_NAME}")
    print(f"  - Prefix: {PREFIX}")
    print(f"  - Region: {AWS_REGION}")
    print()
    
    # Create virtual file system with S3 provider
    vfs = VirtualFileSystem(
        provider="s3",
        bucket_name=BUCKET_NAME,
        prefix=PREFIX,
        region_name=AWS_REGION
    )
    
    try:
        await vfs.initialize()
        print("✓ Connected to S3 successfully\n")
    except Exception as e:
        print(f"\n❌ Failed to connect to S3: {e}")
        print("\nPlease ensure:")
        print("  1. AWS credentials are configured")
        print("  2. The bucket exists and is accessible")
        return
    
    print("🔍 Scanning bucket contents...\n")
    
    # Find all files recursively
    all_files = await vfs.find(pattern="*", path="/", recursive=True)
    
    if not all_files:
        print("  📭 Bucket is empty (no files found)")
    else:
        print(f"  📁 Found {len(all_files)} files:\n")
        
        # Sort files by path
        all_files.sort()
        
        # Get details for each file
        total_size = 0
        for file_path in all_files:
            try:
                node_info = await vfs.get_node_info(file_path)
                if node_info:
                    size = node_info.size or 0
                    total_size += size
                    
                    # Format size
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    
                    # Format modified time if available
                    mod_time = ""
                    if node_info.modified_at:
                        try:
                            if isinstance(node_info.modified_at, str):
                                dt = datetime.fromisoformat(node_info.modified_at.replace('Z', '+00:00'))
                                mod_time = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            mod_time = str(node_info.modified_at)[:16]
                    
                    print(f"    📄 {file_path:<50} {size_str:>10}  {mod_time}")
                else:
                    print(f"    📄 {file_path}")
            except Exception as e:
                print(f"    ⚠️ {file_path} (error: {e})")
        
        # Summary
        print(f"\n  📊 Summary:")
        print(f"     - Total files: {len(all_files)}")
        print(f"     - Total size: {total_size:,} bytes ({total_size / (1024 * 1024):.2f} MB)")
    
    # List directories (just for information)
    print("\n  📂 Directory structure:")
    try:
        async def list_dirs(path, indent=0):
            """Recursively list directory structure"""
            items = await vfs.ls(path)
            dirs = []
            for item in items:
                item_path = f"{path}/{item}" if path != "/" else f"/{item}"
                node_info = await vfs.get_node_info(item_path)
                if node_info and node_info.is_dir:
                    dirs.append(item)
            
            for dir_name in sorted(dirs):
                print(f"    {'  ' * indent}📁 {dir_name}/")
                dir_path = f"{path}/{dir_name}" if path != "/" else f"/{dir_name}"
                await list_dirs(dir_path, indent + 1)
        
        await list_dirs("/")
        
        root_items = await vfs.ls("/")
        if not root_items:
            print("    (no directories)")
    except Exception as e:
        print(f"    ⚠️ Error listing directories: {e}")
    
    # Get storage statistics
    print("\n📈 Storage Statistics:")
    try:
        stats = await vfs.get_storage_stats()
        print(f"  - Total size: {stats.get('total_size', 0):,} bytes")
        print(f"  - File count: {stats.get('file_count', 0)}")
        print(f"  - Directory count: {stats.get('directory_count', 0)}")
        print(f"  - Cache entries: {stats.get('cache_entries', 0)}")
    except Exception as e:
        print(f"  ⚠️ Error getting statistics: {e}")
    
    await vfs.close()
    print("\n✅ Listing complete!")


if __name__ == "__main__":
    # Load env file first
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    # Check for AWS credentials
    if not (os.environ.get("AWS_ACCESS_KEY_ID") or 
            os.path.exists(os.path.expanduser("~/.aws/credentials"))):
        print("⚠️  Warning: AWS credentials not found!")
        print("Please configure AWS credentials using one of these methods:")
        print("  1. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        print("  2. Run 'aws configure' to set up credentials")
        print("  3. Use IAM roles if running on EC2")
        print("\nExample:")
        print("  export AWS_ACCESS_KEY_ID=your_access_key")
        print("  export AWS_SECRET_ACCESS_KEY=your_secret_key")
        print("  export AWS_REGION=us-east-1")
        sys.exit(1)
    
    try:
        asyncio.run(list_s3_bucket())
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)