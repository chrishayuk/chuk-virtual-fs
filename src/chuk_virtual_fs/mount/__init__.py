"""
Cross-platform filesystem mount support for chuk-virtual-fs.

This module provides abstractions for mounting virtual filesystems as real
operating system mount points on Linux, macOS, and Windows.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .base import MountAdapter, MountOptions
from .exceptions import MountError, MountNotSupportedError, UnmountError

if TYPE_CHECKING:
    from chuk_virtual_fs.fs_manager import AsyncVirtualFileSystem
    from chuk_virtual_fs.sync_wrapper import SyncVirtualFileSystem

    # Type alias for filesystems that work with mount adapters
    MountableVFS = AsyncVirtualFileSystem | SyncVirtualFileSystem


def mount(
    vfs: "MountableVFS",
    mount_point: str | Path,
    options: MountOptions | None = None,
) -> MountAdapter:
    """
    Mount a virtual filesystem at the specified mount point.

    This function automatically detects the platform and uses the appropriate
    mount adapter (FUSE for Linux/macOS, WinFsp for Windows).

    Args:
        vfs: The AsyncVirtualFileSystem instance to mount
        mount_point: Path where the filesystem should be mounted
        options: Optional mount configuration

    Returns:
        A MountAdapter instance that can be used to control the mount

    Raises:
        MountNotSupportedError: If the platform is not supported
        MountError: If mounting fails

    Example:
        >>> from chuk_virtual_fs import VirtualFS
        >>> from chuk_virtual_fs.mount import mount
        >>>
        >>> vfs = VirtualFS()
        >>> adapter = mount(vfs, "/mnt/chukfs")
        >>> adapter.start()  # Blocking
        >>>
        >>> # Or use async context manager
        >>> async with mount(vfs, "/mnt/chukfs") as adapter:
        ...     # Filesystem is mounted
        ...     pass
        >>> # Filesystem is automatically unmounted
    """
    mount_point = Path(mount_point)
    options = options or MountOptions()

    if sys.platform == "linux" or sys.platform == "darwin":
        from .fuse_adapter import FUSEAdapter

        return FUSEAdapter(vfs, mount_point, options)
    elif sys.platform == "win32":
        from .winfsp_adapter import WinFspAdapter

        return WinFspAdapter(vfs, mount_point, options)
    else:
        raise MountNotSupportedError(
            f"Platform {sys.platform} is not supported for filesystem mounting. "
            f"Supported platforms: linux, darwin (macOS), win32 (Windows)"
        )


__all__ = [
    "mount",
    "MountAdapter",
    "MountOptions",
    "MountError",
    "MountNotSupportedError",
    "UnmountError",
]
