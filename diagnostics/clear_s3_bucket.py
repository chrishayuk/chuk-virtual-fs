#!/usr/bin/env python3
"""
Clear S3 Bucket Script
Deletes all contents from the configured S3 bucket with the specified prefix.
WARNING: This will permanently delete all files!
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import the virtual fs
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from chuk_virtual_fs import VirtualFileSystem


async def clear_s3_bucket(auto_confirm=False):
    """Clear all contents from the S3 bucket"""

    # Load environment variables from parent directory
    env_path = Path(__file__).parent.parent / ".env"
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
    print("S3 BUCKET CLEANUP SCRIPT")
    print("=" * 60)
    print("\nConfiguration:")
    print(f"  - Bucket: {BUCKET_NAME}")
    print(f"  - Prefix: {PREFIX}")
    print(f"  - Region: {AWS_REGION}")
    print()

    # Confirm with user
    if not auto_confirm:
        print("⚠️  WARNING: This will DELETE ALL contents from the bucket prefix!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return
    else:
        print("⚠️  Auto-confirm mode: Proceeding with deletion...")

    # Create virtual file system with S3 provider
    vfs = VirtualFileSystem(
        provider="s3", bucket_name=BUCKET_NAME, prefix=PREFIX, region_name=AWS_REGION
    )

    try:
        await vfs.initialize()
        print("\n✓ Connected to S3 successfully")
    except Exception as e:
        print(f"\n❌ Failed to connect to S3: {e}")
        print("\nPlease ensure:")
        print("  1. AWS credentials are configured")
        print("  2. The bucket exists and is accessible")
        return

    print("\n🔍 Scanning for files...")

    # Find all files recursively
    all_files = await vfs.find(pattern="*", path="/", recursive=True)

    if not all_files:
        print("  ✓ No files found in bucket. Already clean!")
        await vfs.close()
        return

    print(f"  Found {len(all_files)} files to delete:")

    # Show files to be deleted
    for i, file in enumerate(all_files[:10], 1):  # Show first 10
        print(f"    {i}. {file}")
    if len(all_files) > 10:
        print(f"    ... and {len(all_files) - 10} more files")

    # Final confirmation
    if not auto_confirm:
        print(f"\n⚠️  About to delete {len(all_files)} files!")
        response = input("Type 'DELETE' to confirm: ")
        if response != "DELETE":
            print("Cancelled.")
            await vfs.close()
            return
    else:
        print(f"\n⚠️  Auto-confirm: Deleting {len(all_files)} files...")

    print("\n🗑️  Deleting files...")

    # Delete all files
    deleted_count = 0
    failed_count = 0

    for i, file_path in enumerate(all_files, 1):
        try:
            if await vfs.rm(file_path):
                deleted_count += 1
                # Show progress every 10 files
                if i % 10 == 0:
                    print(f"  Progress: {i}/{len(all_files)} files processed...")
            else:
                failed_count += 1
                print(f"  ⚠️ Failed to delete: {file_path}")
        except Exception as e:
            failed_count += 1
            print(f"  ❌ Error deleting {file_path}: {e}")

    print("\n✅ Deletion complete!")
    print(f"  - Deleted: {deleted_count} files")
    if failed_count > 0:
        print(f"  - Failed: {failed_count} files")

    # Verify cleanup
    print("\n🔍 Verifying cleanup...")
    remaining_files = await vfs.find(pattern="*", path="/", recursive=True)

    if not remaining_files:
        print("  ✓ All files successfully deleted!")
    else:
        print(f"  ⚠️ {len(remaining_files)} files still remain:")
        for file in remaining_files[:5]:
            print(f"    - {file}")
        if len(remaining_files) > 5:
            print(f"    ... and {len(remaining_files) - 5} more")

    # Get final storage stats
    stats = await vfs.get_storage_stats()
    print("\n📊 Final storage statistics:")
    print(f"  - Total size: {stats.get('total_size', 0)} bytes")
    print(f"  - File count: {stats.get('file_count', 0)}")
    print(f"  - Directory count: {stats.get('directory_count', 0)}")

    await vfs.close()
    print("\n✅ Script completed!")


if __name__ == "__main__":
    # Load env file first
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Check for AWS credentials
    if not (
        os.environ.get("AWS_ACCESS_KEY_ID")
        or os.path.exists(os.path.expanduser("~/.aws/credentials"))
    ):
        print("⚠️  Warning: AWS credentials not found!")
        print("Please configure AWS credentials using one of these methods:")
        print(
            "  1. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
        )
        print("  2. Run 'aws configure' to set up credentials")
        print("  3. Use IAM roles if running on EC2")
        print("\nExample:")
        print("  export AWS_ACCESS_KEY_ID=your_access_key")
        print("  export AWS_SECRET_ACCESS_KEY=your_secret_key")
        print("  export AWS_REGION=us-east-1")
        sys.exit(1)

    # Check for --auto flag
    auto_confirm = "--auto" in sys.argv

    try:
        asyncio.run(clear_s3_bucket(auto_confirm=auto_confirm))
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
