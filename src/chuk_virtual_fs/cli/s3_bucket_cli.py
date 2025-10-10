#!/usr/bin/env python
"""
s3_bucket_cli.py - Command Line Interface for S3 bucket management

This CLI tool provides commands for managing S3 buckets, particularly for use with
the virtual filesystem. It supports operations like creating, listing, deleting,
and cleaning buckets, as well as getting detailed information about them.

Usage:
  python s3_bucket_cli.py [command] [options]

Examples:
  python s3_bucket_cli.py list                # List all buckets
  python s3_bucket_cli.py create my-bucket    # Create a new bucket
  python s3_bucket_cli.py info my-bucket      # Show bucket information
  python s3_bucket_cli.py clear my-bucket     # Clear all objects in a bucket
  python s3_bucket_cli.py delete my-bucket    # Delete a bucket
"""

import argparse
import logging
import os

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("s3-bucket-cli")

# Load environment variables from .env file if it exists
load_dotenv()


def get_s3_client():
    """Create and return an S3 client using environment variables or parameters"""
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    region_name = os.environ.get("AWS_REGION", "us-east-1")

    client_kwargs = {}
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    if region_name:
        client_kwargs["region_name"] = region_name

    return boto3.client("s3", **client_kwargs)


def format_size(size_bytes):
    """Format bytes into a human-readable string"""
    if size_bytes == 0:
        return "0 B"

    size_names = ("B", "KB", "MB", "GB", "TB", "PB")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1

    return f"{size_bytes:.2f} {size_names[i]}"


def list_buckets(args):
    """List all available buckets"""
    s3 = get_s3_client()

    try:
        response = s3.list_buckets()

        if "Buckets" not in response or not response["Buckets"]:
            print("No buckets found.")
            return

        print("\nAvailable buckets:")
        print("-" * 60)
        print(f"{'Name':<30} {'Creation Date':<20} {'Region':<15}")
        print("-" * 60)

        for bucket in response["Buckets"]:
            # Get bucket region if possible
            try:
                region = s3.get_bucket_location(Bucket=bucket["Name"])
                region_name = (
                    region.get("LocationConstraint", "us-east-1") or "us-east-1"
                )
            except Exception:
                region_name = "unknown"

            print(
                f"{bucket['Name']:<30} {bucket['CreationDate'].strftime('%Y-%m-%d %H:%M:%S'):<20} {region_name:<15}"
            )

        print(f"\nTotal buckets: {len(response['Buckets'])}")

    except Exception as e:
        logger.error(f"Error listing buckets: {e}")
        print(f"Error: {e}")


def create_bucket(args):
    """Create a new bucket"""
    s3 = get_s3_client()
    bucket_name = args.bucket_name

    try:
        # Check if bucket already exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' already exists.")
            return
        except ClientError as e:
            # 404 means bucket doesn't exist, any other error is a problem
            if e.response["Error"]["Code"] != "404":
                raise e

        # Try to create the bucket
        region = os.environ.get("AWS_REGION", "us-east-1")

        # First try with no configuration
        try:
            if region == "us-east-1":
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            print(f"Bucket '{bucket_name}' created successfully in region {region}.")
            return
        except ClientError as e:
            logger.warning(f"First create attempt failed: {e}")

            # Try with empty configuration
            try:
                s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={})
                print(
                    f"Bucket '{bucket_name}' created successfully with empty configuration."
                )
                return
            except ClientError as e2:
                logger.warning(f"Second create attempt failed: {e2}")

                # Try with region us-east-1 explicitly
                try:
                    s3.create_bucket(Bucket=bucket_name)
                    print(
                        f"Bucket '{bucket_name}' created successfully without region constraint."
                    )
                    return
                except Exception as e3:
                    logger.error(f"All create attempts failed. Last error: {e3}")
                    print(f"Error: Unable to create bucket. {e3}")

    except Exception as e:
        logger.error(f"Error creating bucket: {e}")
        print(f"Error: {e}")


def delete_bucket(args):
    """Delete a bucket (must be empty)"""
    s3 = get_s3_client()
    bucket_name = args.bucket_name

    try:
        # Check if bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError:
            print(f"Bucket '{bucket_name}' does not exist.")
            return

        if args.force:
            print(f"Clearing bucket '{bucket_name}' before deletion...")
            clear_bucket({"bucket_name": bucket_name, "prefix": None, "force": True})

        # Try to delete the bucket
        s3.delete_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' deleted successfully.")

    except Exception as e:
        logger.error(f"Error deleting bucket: {e}")
        if "BucketNotEmpty" in str(e):
            print(
                f"Error: Bucket '{bucket_name}' is not empty. Use --force to delete all objects first."
            )
        else:
            print(f"Error: {e}")


def clear_bucket(args):
    """Clear all objects in a bucket"""
    s3 = get_s3_client()
    bucket_name = args.bucket_name
    prefix = args.prefix

    try:
        # Check if bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError:
            print(f"Bucket '{bucket_name}' does not exist.")
            return

        if not args.force:
            prefix_msg = f"with prefix '{prefix}'" if prefix else ""
            confirmation = input(
                f"Are you sure you want to delete all objects {prefix_msg} from bucket '{bucket_name}'? (y/n): "
            )
            if confirmation.lower() != "y":
                print("Operation canceled.")
                return

        # List and delete objects (handles paging automatically)
        paginator = s3.get_paginator("list_objects_v2")

        list_kwargs = {"Bucket": bucket_name}
        if prefix:
            list_kwargs["Prefix"] = prefix

        page_iterator = paginator.paginate(**list_kwargs)

        total_objects = 0
        deleted_objects = 0

        for page in page_iterator:
            if "Contents" not in page:
                continue

            objects_to_delete = [{"Key": obj["Key"]} for obj in page["Contents"]]
            total_objects += len(objects_to_delete)

            if objects_to_delete:
                response = s3.delete_objects(
                    Bucket=bucket_name, Delete={"Objects": objects_to_delete}
                )

                if "Deleted" in response:
                    deleted_objects += len(response["Deleted"])

                if "Errors" in response and response["Errors"]:
                    for error in response["Errors"]:
                        logger.error(
                            f"Error deleting {error['Key']}: {error['Code']} - {error['Message']}"
                        )

        # Also delete all versions if versioning is enabled
        try:
            paginator = s3.get_paginator("list_object_versions")
            page_iterator = paginator.paginate(**list_kwargs)

            version_objects = 0

            for page in page_iterator:
                delete_list = []

                # Handle versions
                if "Versions" in page:
                    for version in page["Versions"]:
                        delete_list.append(
                            {"Key": version["Key"], "VersionId": version["VersionId"]}
                        )

                # Handle delete markers
                if "DeleteMarkers" in page:
                    for marker in page["DeleteMarkers"]:
                        delete_list.append(
                            {"Key": marker["Key"], "VersionId": marker["VersionId"]}
                        )

                if delete_list:
                    version_objects += len(delete_list)
                    s3.delete_objects(
                        Bucket=bucket_name, Delete={"Objects": delete_list}
                    )

            if version_objects > 0:
                print(f"Deleted {version_objects} object versions.")

        except Exception as version_e:
            # Versioning might not be supported or enabled
            logger.debug(f"Skipped version cleanup: {version_e}")

        prefix_msg = f" with prefix '{prefix}'" if prefix else ""
        print(
            f"Successfully cleared {deleted_objects}/{total_objects} objects{prefix_msg} from bucket '{bucket_name}'."
        )

    except Exception as e:
        logger.error(f"Error clearing bucket: {e}")
        print(f"Error: {e}")


def get_bucket_info(args):
    """Get detailed information about a bucket"""
    s3 = get_s3_client()
    bucket_name = args.bucket_name

    try:
        # Check if bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError:
            print(f"Bucket '{bucket_name}' does not exist.")
            return

        print(f"\nBucket Information: {bucket_name}")
        print("-" * 60)

        # Get creation date
        response = s3.list_buckets()
        bucket_data = next(
            (b for b in response["Buckets"] if b["Name"] == bucket_name), None
        )
        if bucket_data:
            print(
                f"Creation Date: {bucket_data['CreationDate'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # Get region
        try:
            region = s3.get_bucket_location(Bucket=bucket_name)
            region_name = region.get("LocationConstraint", "us-east-1") or "us-east-1"
            print(f"Region: {region_name}")
        except Exception as e:
            print(f"Region: Unknown ({e})")

        # Get versioning status
        try:
            versioning = s3.get_bucket_versioning(Bucket=bucket_name)
            status = versioning.get("Status", "Disabled")
            print(f"Versioning: {status}")
        except Exception:
            print("Versioning: Unknown")

        # Count objects and calculate size
        try:
            paginator = s3.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(Bucket=bucket_name)

            total_size = 0
            object_count = 0

            for page in page_iterator:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        object_count += 1
                        total_size += obj["Size"]

            print(f"Total Objects: {object_count}")
            print(f"Total Size: {format_size(total_size)} ({total_size} bytes)")

            # Get largest objects
            if args.show_top and object_count > 0:
                paginator = s3.get_paginator("list_objects_v2")
                page_iterator = paginator.paginate(Bucket=bucket_name)

                all_objects = []
                for page in page_iterator:
                    if "Contents" in page:
                        for obj in page["Contents"]:
                            all_objects.append(
                                {
                                    "Key": obj["Key"],
                                    "Size": obj["Size"],
                                    "LastModified": obj["LastModified"],
                                }
                            )

                # Sort by size (largest first)
                all_objects.sort(key=lambda x: x["Size"], reverse=True)

                # Show top N objects
                top_n = min(args.show_top, len(all_objects))
                if top_n > 0:
                    print(f"\nTop {top_n} largest objects:")
                    print(f"{'Size':<15} {'Last Modified':<20} {'Key'}")
                    print("-" * 80)
                    for obj in all_objects[:top_n]:
                        print(
                            f"{format_size(obj['Size']):<15} {obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S'):<20} {obj['Key']}"
                        )

        except Exception as e:
            print(f"Error getting object information: {e}")

        # List common prefixes (like directories)
        if args.list_prefixes:
            try:
                print("\nCommon prefixes (like directories):")
                response = s3.list_objects_v2(Bucket=bucket_name, Delimiter="/")

                if "CommonPrefixes" in response:
                    for prefix in response["CommonPrefixes"]:
                        print(f"  {prefix['Prefix']}")
                else:
                    print("  No common prefixes found.")
            except Exception as e:
                print(f"Error listing prefixes: {e}")

    except Exception as e:
        logger.error(f"Error getting bucket info: {e}")
        print(f"Error: {e}")


def copy_objects(args):
    """Copy objects between buckets or prefixes"""
    s3 = get_s3_client()
    source_bucket = args.source_bucket
    source_prefix = args.source_prefix or ""
    dest_bucket = args.dest_bucket
    dest_prefix = args.dest_prefix or ""

    try:
        # Check if source bucket exists
        try:
            s3.head_bucket(Bucket=source_bucket)
        except ClientError:
            print(f"Source bucket '{source_bucket}' does not exist.")
            return

        # Check if destination bucket exists
        try:
            s3.head_bucket(Bucket=dest_bucket)
        except ClientError:
            print(f"Destination bucket '{dest_bucket}' does not exist.")
            return

        # List objects in source
        paginator = s3.get_paginator("list_objects_v2")
        list_kwargs = {"Bucket": source_bucket}
        if source_prefix:
            list_kwargs["Prefix"] = source_prefix

        page_iterator = paginator.paginate(**list_kwargs)

        total_objects = 0
        copied_objects = 0

        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                source_key = obj["Key"]

                # Skip if object doesn't match source prefix
                if source_prefix and not source_key.startswith(source_prefix):
                    continue

                # Create destination key by replacing source prefix with destination prefix
                if source_prefix:
                    relative_path = source_key[len(source_prefix) :]
                    dest_key = dest_prefix + relative_path
                else:
                    dest_key = dest_prefix + source_key

                total_objects += 1

                # Copy the object
                try:
                    copy_source = {"Bucket": source_bucket, "Key": source_key}
                    s3.copy_object(
                        CopySource=copy_source, Bucket=dest_bucket, Key=dest_key
                    )
                    copied_objects += 1

                    if args.verbose:
                        print(
                            f"Copied: {source_bucket}/{source_key} -> {dest_bucket}/{dest_key}"
                        )

                except Exception as copy_e:
                    logger.error(f"Error copying {source_key}: {copy_e}")
                    if args.verbose:
                        print(f"Error copying {source_key}: {copy_e}")

        print(
            f"Successfully copied {copied_objects}/{total_objects} objects from '{source_bucket}/{source_prefix}' to '{dest_bucket}/{dest_prefix}'."
        )

    except Exception as e:
        logger.error(f"Error copying objects: {e}")
        print(f"Error: {e}")


def list_objects(args):
    """List objects in a bucket, optionally with a prefix"""
    s3 = get_s3_client()
    bucket_name = args.bucket_name
    prefix = args.prefix or ""
    max_items = args.max_items

    try:
        # Check if bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError:
            print(f"Bucket '{bucket_name}' does not exist.")
            return

        print(
            f"\nObjects in bucket: {bucket_name}{f' (prefix: {prefix})' if prefix else ''}"
        )
        print("-" * 80)
        print(f"{'Size':<15} {'Last Modified':<20} {'Key'}")
        print("-" * 80)

        # List objects
        paginator = s3.get_paginator("list_objects_v2")
        list_kwargs = {"Bucket": bucket_name}
        if prefix:
            list_kwargs["Prefix"] = prefix

        page_iterator = paginator.paginate(**list_kwargs)

        count = 0
        total_size = 0

        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                print(
                    f"{format_size(obj['Size']):<15} {obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S'):<20} {obj['Key']}"
                )
                count += 1
                total_size += obj["Size"]

                if max_items and count >= max_items:
                    break

            if max_items and count >= max_items:
                break

        print("-" * 80)
        print(f"Total: {count} objects, {format_size(total_size)}")

        if max_items and count >= max_items:
            print(
                f"Note: Only showing first {max_items} objects. Use --max-items to adjust."
            )

    except Exception as e:
        logger.error(f"Error listing objects: {e}")
        print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="S3 Bucket CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List buckets command
    subparsers.add_parser("list", help="List all buckets")

    # Create bucket command
    create_parser = subparsers.add_parser("create", help="Create a new bucket")
    create_parser.add_argument("bucket_name", help="Name of the bucket to create")

    # Delete bucket command
    delete_parser = subparsers.add_parser("delete", help="Delete a bucket")
    delete_parser.add_argument("bucket_name", help="Name of the bucket to delete")
    delete_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force deletion by removing all objects first",
    )

    # Clear bucket command
    clear_parser = subparsers.add_parser("clear", help="Clear all objects in a bucket")
    clear_parser.add_argument("bucket_name", help="Name of the bucket to clear")
    clear_parser.add_argument(
        "--prefix", "-p", help="Only clear objects with this prefix"
    )
    clear_parser.add_argument(
        "--force", "-f", action="store_true", help="Force deletion without confirmation"
    )

    # Bucket info command
    info_parser = subparsers.add_parser(
        "info", help="Get detailed information about a bucket"
    )
    info_parser.add_argument("bucket_name", help="Name of the bucket")
    info_parser.add_argument(
        "--list-prefixes",
        "-l",
        action="store_true",
        help="List common prefixes (like directories)",
    )
    info_parser.add_argument(
        "--show-top", "-t", type=int, default=10, help="Show the top N largest objects"
    )

    # Copy objects command
    copy_parser = subparsers.add_parser(
        "copy", help="Copy objects between buckets or prefixes"
    )
    copy_parser.add_argument("source_bucket", help="Source bucket name")
    copy_parser.add_argument("dest_bucket", help="Destination bucket name")
    copy_parser.add_argument("--source-prefix", "-s", help="Source prefix (folder)")
    copy_parser.add_argument("--dest-prefix", "-d", help="Destination prefix (folder)")
    copy_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed progress"
    )

    # List objects command
    ls_parser = subparsers.add_parser("ls", help="List objects in a bucket")
    ls_parser.add_argument("bucket_name", help="Name of the bucket")
    ls_parser.add_argument("--prefix", "-p", help="Only list objects with this prefix")
    ls_parser.add_argument(
        "--max-items", "-m", type=int, help="Maximum number of items to show"
    )

    args = parser.parse_args()

    if args.command == "list":
        list_buckets(args)
    elif args.command == "create":
        create_bucket(args)
    elif args.command == "delete":
        delete_bucket(args)
    elif args.command == "clear":
        clear_bucket(args)
    elif args.command == "info":
        get_bucket_info(args)
    elif args.command == "copy":
        copy_objects(args)
    elif args.command == "ls":
        list_objects(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
