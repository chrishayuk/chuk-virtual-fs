#!/usr/bin/env python3
"""
CLI tool for mounting chuk-virtual-fs as a real filesystem.

This tool allows you to mount a virtual filesystem at a real mount point,
making it accessible to any application on your system.

Examples:
    # Mount in-memory VFS
    chuk-vfs-mount --backend memory --mount /mnt/chukfs

    # Mount Redis-backed VFS
    chuk-vfs-mount --backend redis --mount /mnt/chukfs --redis-url redis://localhost

    # Mount S3-backed VFS (readonly)
    chuk-vfs-mount --backend s3 --mount /mnt/chukfs --bucket my-bucket --readonly

    # Mount on Windows
    chuk-vfs-mount --backend memory --mount Z:
"""

import argparse
import logging
import sys
from pathlib import Path

from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.mount import MountOptions, mount


def setup_logging(debug: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def create_vfs(args: argparse.Namespace) -> SyncVirtualFileSystem:
    """
    Create a VirtualFS instance based on CLI arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Configured VirtualFS instance
    """
    backend = args.backend.lower()

    if backend == "memory":
        # In-memory backend
        vfs = SyncVirtualFileSystem()

    elif backend == "redis":
        # Redis backend
        redis_url = args.redis_url or "redis://localhost:6379"
        prefix = args.redis_prefix or "chuk_vfs:"

        vfs = SyncVirtualFileSystem(
            provider="redis", redis_url=redis_url, prefix=prefix
        )

    elif backend == "s3":
        # S3 backend
        if not args.bucket:
            raise ValueError("--bucket is required for S3 backend")

        vfs = SyncVirtualFileSystem(
            provider="s3",
            bucket_name=args.bucket,
            prefix=args.s3_prefix or "",
            region=args.region,
        )

    elif backend == "sqlite":
        # SQLite backend
        db_path = args.db_path or "virtual_fs.db"
        vfs = SyncVirtualFileSystem(provider="sqlite", db_path=db_path)

    else:
        raise ValueError(f"Unsupported backend: {backend}")

    return vfs


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mount chuk-virtual-fs as a real filesystem",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Mount configuration
    parser.add_argument(
        "--mount",
        "-m",
        type=str,
        required=True,
        help="Mount point path (e.g., /mnt/chukfs or Z: on Windows)",
    )

    parser.add_argument(
        "--backend",
        "-b",
        type=str,
        default="memory",
        choices=["memory", "redis", "s3", "sqlite"],
        help="VFS backend to use (default: memory)",
    )

    # Mount options
    parser.add_argument(
        "--readonly",
        "-r",
        action="store_true",
        help="Mount filesystem as read-only",
    )

    parser.add_argument(
        "--allow-other",
        action="store_true",
        help="Allow other users to access the mount (requires root)",
    )

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--foreground",
        "-f",
        action="store_true",
        default=True,
        help="Run in foreground (default: True)",
    )

    # Backend-specific options
    # Redis
    parser.add_argument(
        "--redis-url",
        type=str,
        help="Redis connection URL (default: redis://localhost:6379)",
    )

    parser.add_argument(
        "--redis-prefix",
        type=str,
        help="Redis key prefix (default: chuk_vfs:)",
    )

    # S3
    parser.add_argument(
        "--bucket",
        type=str,
        help="S3 bucket name (required for S3 backend)",
    )

    parser.add_argument(
        "--s3-prefix",
        type=str,
        help="S3 key prefix (optional)",
    )

    parser.add_argument(
        "--region",
        type=str,
        help="AWS region (optional, uses default if not specified)",
    )

    # SQLite
    parser.add_argument(
        "--db-path",
        type=str,
        help="SQLite database path (default: virtual_fs.db)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)

    try:
        # Create VFS
        logger.info(f"Creating VFS with backend: {args.backend}")
        vfs = create_vfs(args)

        # Create mount options
        options = MountOptions(
            readonly=args.readonly,
            allow_other=args.allow_other,
            debug=args.debug,
        )

        # Create mount point path
        mount_point = Path(args.mount)

        # Mount filesystem
        logger.info(f"Mounting VFS at {mount_point}")
        adapter = mount(vfs, mount_point, options)

        # Run in blocking mode
        adapter.mount_blocking()

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.debug)
        return 1


if __name__ == "__main__":
    sys.exit(main())
