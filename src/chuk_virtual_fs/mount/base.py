"""Base abstractions for cross-platform filesystem mounting."""

import asyncio
import errno
import stat
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chuk_virtual_fs.fs_manager import AsyncVirtualFileSystem
    from chuk_virtual_fs.sync_wrapper import SyncVirtualFileSystem

    # Type alias for filesystems that work with mount adapters
    MountableVFS = AsyncVirtualFileSystem | SyncVirtualFileSystem


@dataclass
class MountOptions:
    """Configuration options for mounting a virtual filesystem."""

    # General options
    readonly: bool = False
    allow_other: bool = False  # Allow other users to access
    debug: bool = False

    # Performance options
    cache_timeout: float = 1.0  # seconds
    max_read: int = 131072  # 128KB
    max_write: int = 131072  # 128KB

    # Platform-specific options
    extra_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatInfo:
    """File/directory stat information."""

    st_mode: int  # File mode (type and permissions)
    st_ino: int  # Inode number
    st_dev: int = 0  # Device ID
    st_nlink: int = 1  # Number of hard links
    st_uid: int = 1000  # User ID
    st_gid: int = 1000  # Group ID
    st_size: int = 0  # Size in bytes
    st_atime: float = 0.0  # Access time
    st_mtime: float = 0.0  # Modification time
    st_ctime: float = 0.0  # Change time

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for FUSE operations."""
        return {
            "st_mode": self.st_mode,
            "st_ino": self.st_ino,
            "st_dev": self.st_dev,
            "st_nlink": self.st_nlink,
            "st_uid": self.st_uid,
            "st_gid": self.st_gid,
            "st_size": self.st_size,
            "st_atime": self.st_atime,
            "st_mtime": self.st_mtime,
            "st_ctime": self.st_ctime,
        }


class MountAdapter(ABC):
    """
    Abstract base class for platform-specific mount adapters.

    This provides a common interface for mounting virtual filesystems
    across different platforms (Linux/macOS via FUSE, Windows via WinFsp).
    """

    def __init__(
        self, vfs: "MountableVFS", mount_point: Path, options: MountOptions
    ) -> None:
        """
        Initialize the mount adapter.

        Args:
            vfs: The VirtualFileSystem instance to mount (Async or Sync)
            mount_point: Path where filesystem will be mounted
            options: Mount configuration options
        """
        self.vfs = vfs
        self.mount_point = mount_point
        self.options = options
        self._mounted = False
        self._mount_task: asyncio.Task[Any] | None = None

    @abstractmethod
    async def mount_async(self) -> None:
        """
        Mount the filesystem asynchronously.

        This method should set up the mount and return immediately,
        leaving the filesystem mounted in the background.

        Raises:
            MountError: If mounting fails
        """

    @abstractmethod
    async def unmount_async(self) -> None:
        """
        Unmount the filesystem asynchronously.

        Raises:
            UnmountError: If unmounting fails
        """

    @abstractmethod
    def mount_blocking(self) -> None:
        """
        Mount the filesystem in blocking mode.

        This method blocks until the filesystem is unmounted.
        Useful for CLI tools and simple scripts.

        Raises:
            MountError: If mounting fails
        """

    @property
    def is_mounted(self) -> bool:
        """Check if the filesystem is currently mounted."""
        return self._mounted

    async def __aenter__(self) -> "MountAdapter":
        """Async context manager entry."""
        await self.mount_async()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.unmount_async()

    # Helper methods for VFS operations

    def _path_to_vfs(self, path: str) -> str:
        """Convert a mount-relative path to a VFS path."""
        # Remove leading slash and ensure clean path
        if path.startswith("/"):
            path = path[1:]
        return f"/{path}" if path else "/"

    def _get_stat(self, path: str) -> StatInfo:
        """
        Get stat information for a path.

        Args:
            path: VFS path to stat

        Returns:
            StatInfo with file/directory metadata

        Raises:
            FileNotFoundError: If path doesn't exist
        """
        vfs_path = self._path_to_vfs(path)

        try:
            if not self.vfs.exists(vfs_path):
                raise FileNotFoundError(errno.ENOENT, f"No such file: {path}")

            is_dir = self.vfs.is_dir(vfs_path)
            now = time.time()

            # Get inode number (use hash of path for consistency)
            inode = hash(vfs_path) & 0xFFFFFFFF

            if is_dir:
                mode = stat.S_IFDIR | 0o755
                size = 4096  # Standard directory size
            else:
                mode = stat.S_IFREG | 0o644
                try:
                    content = self.vfs.read_file(vfs_path)
                    size = (
                        len(content)
                        if isinstance(content, bytes)
                        else len(content.encode("utf-8"))  # type: ignore[union-attr]
                    )
                except Exception:
                    size = 0

            return StatInfo(
                st_mode=mode,
                st_ino=inode,
                st_size=size,
                st_atime=now,
                st_mtime=now,
                st_ctime=now,
                st_nlink=2 if is_dir else 1,
            )

        except FileNotFoundError:
            raise
        except Exception as e:
            raise OSError(errno.EIO, f"I/O error: {e}")

    def _read_file(self, path: str, offset: int, size: int) -> bytes:
        """
        Read data from a file.

        Args:
            path: VFS path to read
            offset: Byte offset to start reading
            size: Number of bytes to read

        Returns:
            File data as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IsADirectoryError: If path is a directory
        """
        vfs_path = self._path_to_vfs(path)

        if not self.vfs.exists(vfs_path):
            raise FileNotFoundError(errno.ENOENT, f"No such file: {path}")

        if self.vfs.is_dir(vfs_path):
            raise IsADirectoryError(errno.EISDIR, f"Is a directory: {path}")

        try:
            content = self.vfs.read_file(vfs_path)
            content_bytes: bytes
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content  # type: ignore[assignment]

            # Return requested slice
            return content_bytes[offset : offset + size]

        except Exception as e:
            raise OSError(errno.EIO, f"I/O error: {e}")

    def _write_file(self, path: str, data: bytes, offset: int) -> int:
        """
        Write data to a file.

        Args:
            path: VFS path to write
            data: Data to write
            offset: Byte offset to start writing

        Returns:
            Number of bytes written

        Raises:
            FileNotFoundError: If file doesn't exist
            IsADirectoryError: If path is a directory
            PermissionError: If filesystem is readonly
        """
        if self.options.readonly:
            raise PermissionError(errno.EROFS, "Read-only filesystem")

        vfs_path = self._path_to_vfs(path)

        if self.vfs.is_dir(vfs_path):
            raise IsADirectoryError(errno.EISDIR, f"Is a directory: {path}")

        try:
            # Read existing content
            if self.vfs.exists(vfs_path):
                existing = self.vfs.read_file(vfs_path)
                if isinstance(existing, str):
                    existing = existing.encode("utf-8")
            else:
                existing = b""

            # Insert new data at offset
            new_content = existing[:offset] + data + existing[offset + len(data) :]  # type: ignore[index]

            # Write back - decode to string for write_file
            self.vfs.write_file(vfs_path, new_content.decode("utf-8", errors="replace"))

            return len(data)

        except Exception as e:
            raise OSError(errno.EIO, f"I/O error: {e}")

    def _list_directory(self, path: str) -> list[str]:
        """
        List directory contents.

        Args:
            path: VFS path to list

        Returns:
            List of entry names (not including . and ..)

        Raises:
            FileNotFoundError: If directory doesn't exist
            NotADirectoryError: If path is not a directory
        """
        vfs_path = self._path_to_vfs(path)

        if not self.vfs.exists(vfs_path):
            raise FileNotFoundError(errno.ENOENT, f"No such directory: {path}")

        if not self.vfs.is_dir(vfs_path):
            raise NotADirectoryError(errno.ENOTDIR, f"Not a directory: {path}")

        try:
            entries = self.vfs.ls(vfs_path)
            # Return just the names, FUSE will add . and ..
            return [Path(e).name for e in entries]  # type: ignore[union-attr]

        except Exception as e:
            raise OSError(errno.EIO, f"I/O error: {e}")

    def _create_file(self, path: str, mode: int) -> None:
        """
        Create a new file.

        Args:
            path: VFS path to create
            mode: File permissions (ignored, for FUSE compatibility)

        Raises:
            FileExistsError: If file already exists
            PermissionError: If filesystem is readonly
        """
        if self.options.readonly:
            raise PermissionError(errno.EROFS, "Read-only filesystem")

        vfs_path = self._path_to_vfs(path)

        if self.vfs.exists(vfs_path):
            raise FileExistsError(errno.EEXIST, f"File exists: {path}")

        try:
            self.vfs.write_file(vfs_path, "")
        except Exception as e:
            raise OSError(errno.EIO, f"I/O error: {e}")

    def _create_directory(self, path: str, mode: int) -> None:
        """
        Create a new directory.

        Args:
            path: VFS path to create
            mode: Directory permissions (ignored, for FUSE compatibility)

        Raises:
            FileExistsError: If directory already exists
            PermissionError: If filesystem is readonly
        """
        if self.options.readonly:
            raise PermissionError(errno.EROFS, "Read-only filesystem")

        vfs_path = self._path_to_vfs(path)

        if self.vfs.exists(vfs_path):
            raise FileExistsError(errno.EEXIST, f"File exists: {path}")

        try:
            self.vfs.mkdir(vfs_path)
        except Exception as e:
            raise OSError(errno.EIO, f"I/O error: {e}")

    def _delete_file(self, path: str) -> None:
        """
        Delete a file.

        Args:
            path: VFS path to delete

        Raises:
            FileNotFoundError: If file doesn't exist
            IsADirectoryError: If path is a directory
            PermissionError: If filesystem is readonly
        """
        if self.options.readonly:
            raise PermissionError(errno.EROFS, "Read-only filesystem")

        vfs_path = self._path_to_vfs(path)

        if not self.vfs.exists(vfs_path):
            raise FileNotFoundError(errno.ENOENT, f"No such file: {path}")

        if self.vfs.is_dir(vfs_path):
            raise IsADirectoryError(errno.EISDIR, f"Is a directory: {path}")

        try:
            self.vfs.rm(vfs_path)
        except Exception as e:
            raise OSError(errno.EIO, f"I/O error: {e}")

    def _delete_directory(self, path: str) -> None:
        """
        Delete a directory.

        Args:
            path: VFS path to delete

        Raises:
            FileNotFoundError: If directory doesn't exist
            NotADirectoryError: If path is not a directory
            OSError: If directory is not empty
            PermissionError: If filesystem is readonly
        """
        if self.options.readonly:
            raise PermissionError(errno.EROFS, "Read-only filesystem")

        vfs_path = self._path_to_vfs(path)

        if not self.vfs.exists(vfs_path):
            raise FileNotFoundError(errno.ENOENT, f"No such directory: {path}")

        if not self.vfs.is_dir(vfs_path):
            raise NotADirectoryError(errno.ENOTDIR, f"Not a directory: {path}")

        # Check if empty
        if self.vfs.ls(vfs_path):
            raise OSError(errno.ENOTEMPTY, f"Directory not empty: {path}")

        try:
            self.vfs.rm(vfs_path)
        except Exception as e:
            raise OSError(errno.EIO, f"I/O error: {e}")
