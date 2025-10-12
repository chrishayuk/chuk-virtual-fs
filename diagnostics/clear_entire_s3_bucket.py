#!/usr/bin/env python3
"""
Clear ENTIRE S3 Bucket Script
Deletes ALL contents from the S3 bucket, not just a specific prefix.
WARNING: This will permanently delete ALL files in the entire bucket!
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv


async def clear_entire_s3_bucket(auto_confirm=False):
    """Clear ALL contents from the entire S3 bucket"""

    # Load environment variables from parent directory
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print("✓ Loaded environment variables from .env file")
    else:
        load_dotenv()

    # Configuration
    BUCKET_NAME = os.environ.get("S3_BUCKET", "my-virtual-fs-bucket")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

    print("=" * 60)
    print("S3 ENTIRE BUCKET CLEANUP SCRIPT")
    print("=" * 60)
    print("\nConfiguration:")
    print(f"  - Bucket: {BUCKET_NAME}")
    print(f"  - Region: {AWS_REGION}")
    print("  - Scope: ENTIRE BUCKET (all prefixes)")
    print()

    # Confirm with user
    if not auto_confirm:
        print("⚠️  WARNING: This will DELETE ALL contents from the ENTIRE bucket!")
        print("⚠️  This includes ALL prefixes, not just virtual-fs-demo/")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return
    else:
        print("⚠️  Auto-confirm mode: Proceeding with ENTIRE bucket deletion...")

    try:
        import aioboto3
    except ImportError:
        print("❌ aioboto3 is required. Install with: pip install aioboto3")
        return

    # Create session
    session_kwargs = {}
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        session_kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID")
    if os.environ.get("AWS_SECRET_ACCESS_KEY"):
        session_kwargs["aws_secret_access_key"] = os.environ.get(
            "AWS_SECRET_ACCESS_KEY"
        )
    if AWS_REGION:
        session_kwargs["region_name"] = AWS_REGION

    session = aioboto3.Session(**session_kwargs)

    async with session.client("s3") as s3_client:
        try:
            # Test connection
            await s3_client.head_bucket(Bucket=BUCKET_NAME)
            print("✓ Connected to S3 successfully\n")
        except Exception as e:
            print(f"❌ Failed to connect to S3: {e}")
            return

        print("🔍 Scanning ENTIRE bucket for all objects...")

        all_objects = []

        # List all objects in the entire bucket (no prefix filter)
        paginator = s3_client.get_paginator("list_objects_v2")

        async for page in paginator.paginate(Bucket=BUCKET_NAME):
            if "Contents" in page:
                for obj in page["Contents"]:
                    all_objects.append(obj["Key"])

        if not all_objects:
            print("  ✓ No objects found in bucket. Already clean!")
            return

        print(f"  Found {len(all_objects)} objects to delete:")

        # Show objects to be deleted
        for i, key in enumerate(all_objects[:20], 1):  # Show first 20
            print(f"    {i}. {key}")
        if len(all_objects) > 20:
            print(f"    ... and {len(all_objects) - 20} more objects")

        # Final confirmation
        if not auto_confirm:
            print(
                f"\n⚠️  About to delete {len(all_objects)} objects from the ENTIRE bucket!"
            )
            response = input("Type 'DELETE ALL' to confirm: ")
            if response != "DELETE ALL":
                print("Cancelled.")
                return
        else:
            print(f"\n⚠️  Auto-confirm: Deleting {len(all_objects)} objects...")

        print("\n🗑️  Deleting objects...")

        # Delete in batches of 1000 (S3 limit)
        deleted_count = 0
        failed_count = 0

        for i in range(0, len(all_objects), 1000):
            batch = all_objects[i : i + 1000]
            delete_objects = [{"Key": key} for key in batch]

            try:
                response = await s3_client.delete_objects(
                    Bucket=BUCKET_NAME,
                    Delete={"Objects": delete_objects, "Quiet": False},
                )

                # Count successful deletions
                if "Deleted" in response:
                    deleted_count += len(response["Deleted"])

                # Count errors
                if "Errors" in response:
                    failed_count += len(response["Errors"])
                    for error in response["Errors"]:
                        print(
                            f"  ❌ Failed to delete {error['Key']}: {error['Message']}"
                        )

                # Show progress
                print(
                    f"  Progress: {min(i + 1000, len(all_objects))}/{len(all_objects)} objects processed..."
                )

            except Exception as e:
                print(f"  ❌ Error deleting batch: {e}")
                failed_count += len(batch)

        print("\n✅ Deletion complete!")
        print(f"  - Deleted: {deleted_count} objects")
        if failed_count > 0:
            print(f"  - Failed: {failed_count} objects")

        # Verify cleanup
        print("\n🔍 Verifying cleanup...")

        remaining_objects = []
        async for page in paginator.paginate(Bucket=BUCKET_NAME):
            if "Contents" in page:
                for obj in page["Contents"]:
                    remaining_objects.append(obj["Key"])

        if not remaining_objects:
            print("  ✓ All objects successfully deleted!")
            print("  ✓ Bucket is now completely empty!")
        else:
            print(f"  ⚠️ {len(remaining_objects)} objects still remain:")
            for key in remaining_objects[:10]:
                print(f"    - {key}")
            if len(remaining_objects) > 10:
                print(f"    ... and {len(remaining_objects) - 10} more")

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
        sys.exit(1)

    # Check for --auto flag
    auto_confirm = "--auto" in sys.argv

    try:
        asyncio.run(clear_entire_s3_bucket(auto_confirm=auto_confirm))
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
