"""WinFsp-based mount adapter for Windows."""

import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import MountAdapter, MountOptions
from .exceptions import MountError, UnmountError

if TYPE_CHECKING:
    from chuk_virtual_fs.fs_manager import AsyncVirtualFileSystem
    from chuk_virtual_fs.sync_wrapper import SyncVirtualFileSystem

    # Type alias for filesystems that work with mount adapters
    MountableVFS = AsyncVirtualFileSystem | SyncVirtualFileSystem

logger = logging.getLogger(__name__)

# Try to import winfspy
try:
    from winfspy import (
        CREATE_FILE_CREATE_OPTIONS,
        FILE_ATTRIBUTE,
        BaseFileSystemOperations,
        FileSystem,
        NTStatusDirectoryNotEmpty,
        NTStatusMediaWriteProtected,
        NTStatusNotADirectory,
        NTStatusObjectNameCollision,
        NTStatusObjectNameNotFound,
        enable_debug_log,
    )

    HAS_WINFSP = True
except ImportError:
    HAS_WINFSP = False


if not HAS_WINFSP:

    class WinFspAdapter(MountAdapter):
        """Stub adapter when WinFsp is not available."""

        def __init__(
            self,
            vfs: "MountableVFS",
            mount_point: Path,
            options: MountOptions,
        ) -> None:
            super().__init__(vfs, mount_point, options)
            raise MountError(
                "WinFsp support not available. Install with: "
                "pip install chuk-virtual-fs[mount]"
            )

        async def mount_async(self) -> None:
            pass

        async def unmount_async(self) -> None:
            pass

        def mount_blocking(self) -> None:
            pass


else:

    class VFSFileSystemOperations(BaseFileSystemOperations):
        """WinFsp operations that delegate to VirtualFS."""

        def __init__(self, adapter: "WinFspAdapter"):
            super().__init__()
            self.adapter = adapter
            self.logger = logging.getLogger(__name__ + ".VFSFileSystemOperations")

        def get_volume_info(self) -> dict[str, Any]:
            """Get volume information."""
            return {
                "total_size": 1024 * 1024 * 1024,  # 1GB
                "free_size": 512 * 1024 * 1024,  # 512MB
            }

        def get_security_by_name(self, file_name: str) -> tuple[int, dict[str, Any]]:
            """Get security information for a file."""
            try:
                vfs_path = self.adapter._path_to_vfs(file_name)

                if not self.adapter.vfs.exists(vfs_path):
                    raise NTStatusObjectNameNotFound()

                is_dir = self.adapter.vfs.is_dir(vfs_path)

                # Build file attributes
                attrs = FILE_ATTRIBUTE.FILE_ATTRIBUTE_NORMAL

                if is_dir:
                    attrs |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY

                if self.adapter.options.readonly:
                    attrs |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_READONLY

                # Get file info
                stat_info = self.adapter._get_stat(file_name)

                file_info = {
                    "file_attributes": attrs,
                    "allocation_size": stat_info.st_size,
                    "file_size": stat_info.st_size,
                    "creation_time": int(stat_info.st_ctime * 10000000),
                    "last_access_time": int(stat_info.st_atime * 10000000),
                    "last_write_time": int(stat_info.st_mtime * 10000000),
                    "change_time": int(stat_info.st_ctime * 10000000),
                    "index_number": stat_info.st_ino,
                }

                return (attrs, file_info)

            except FileNotFoundError:
                raise NTStatusObjectNameNotFound()
            except Exception as e:
                self.logger.error(f"get_security_by_name error: {e}")
                raise

        def open(
            self, file_name: str, create_options: int, granted_access: int
        ) -> dict[str, Any]:
            """Open a file."""
            try:
                vfs_path = self.adapter._path_to_vfs(file_name)

                if not self.adapter.vfs.exists(vfs_path):
                    raise NTStatusObjectNameNotFound()

                is_dir = self.adapter.vfs.is_dir(vfs_path)

                # Build file attributes
                attrs = FILE_ATTRIBUTE.FILE_ATTRIBUTE_NORMAL

                if is_dir:
                    attrs |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY

                if self.adapter.options.readonly:
                    attrs |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_READONLY

                # Get file info
                stat_info = self.adapter._get_stat(file_name)

                return {
                    "file_attributes": attrs,
                    "allocation_size": stat_info.st_size,
                    "file_size": stat_info.st_size,
                    "creation_time": int(stat_info.st_ctime * 10000000),
                    "last_access_time": int(stat_info.st_atime * 10000000),
                    "last_write_time": int(stat_info.st_mtime * 10000000),
                    "change_time": int(stat_info.st_ctime * 10000000),
                    "index_number": stat_info.st_ino,
                }

            except FileNotFoundError:
                raise NTStatusObjectNameNotFound()
            except Exception as e:
                self.logger.error(f"open error: {e}")
                raise

        def close(self, file_context: Any) -> None:
            """Close a file."""
            # Nothing to do for our implementation

        def read(self, file_context: Any, buffer: Any, offset: int) -> bytes:
            """Read from a file."""
            try:
                file_name = file_context.get("file_name", "")
                size = len(buffer)
                return self.adapter._read_file(file_name, offset, size)

            except FileNotFoundError:
                raise NTStatusObjectNameNotFound()
            except IsADirectoryError:
                raise NTStatusNotADirectory()
            except Exception as e:
                self.logger.error(f"read error: {e}")
                raise

        def write(
            self,
            file_context: Any,
            buffer: bytes,
            offset: int,
            write_to_end_of_file: bool,
            constrained_io: bool,
        ) -> int:
            """Write to a file."""
            try:
                if self.adapter.options.readonly:
                    raise NTStatusMediaWriteProtected()

                file_name = file_context.get("file_name", "")

                if write_to_end_of_file:
                    # Append mode
                    vfs_path = self.adapter._path_to_vfs(file_name)
                    if self.adapter.vfs.exists(vfs_path):
                        existing = self.adapter.vfs.read_file(vfs_path)
                        if isinstance(existing, str):
                            existing = existing.encode("utf-8")
                        offset = len(existing)  # type: ignore[arg-type]
                    else:
                        offset = 0

                return self.adapter._write_file(file_name, buffer, offset)

            except PermissionError:
                raise NTStatusMediaWriteProtected()
            except IsADirectoryError:
                raise NTStatusNotADirectory()
            except Exception as e:
                self.logger.error(f"write error: {e}")
                raise

        def get_file_info(self, file_context: Any) -> dict[str, Any]:
            """Get file information."""
            try:
                file_name = file_context.get("file_name", "")
                stat_info = self.adapter._get_stat(file_name)

                is_dir = self.adapter.vfs.is_dir(self.adapter._path_to_vfs(file_name))

                attrs = FILE_ATTRIBUTE.FILE_ATTRIBUTE_NORMAL
                if is_dir:
                    attrs |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY

                if self.adapter.options.readonly:
                    attrs |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_READONLY

                return {
                    "file_attributes": attrs,
                    "allocation_size": stat_info.st_size,
                    "file_size": stat_info.st_size,
                    "creation_time": int(stat_info.st_ctime * 10000000),
                    "last_access_time": int(stat_info.st_atime * 10000000),
                    "last_write_time": int(stat_info.st_mtime * 10000000),
                    "change_time": int(stat_info.st_ctime * 10000000),
                    "index_number": stat_info.st_ino,
                }

            except FileNotFoundError:
                raise NTStatusObjectNameNotFound()
            except Exception as e:
                self.logger.error(f"get_file_info error: {e}")
                raise

        def set_basic_info(
            self,
            file_context: Any,
            file_attributes: int,
            creation_time: int,
            last_access_time: int,
            last_write_time: int,
            change_time: int,
        ) -> dict[str, Any]:
            """Set basic file information."""
            # For a read-only implementation, just return current info
            return self.get_file_info(file_context)

        def read_directory(
            self, file_context: Any, marker: str | None
        ) -> list[dict[str, Any]]:
            """Read directory entries."""
            try:
                file_name = file_context.get("file_name", "")
                entries = self.adapter._list_directory(file_name)

                result = []

                # Add . and ..
                for name in [".", ".."]:
                    if marker and name <= marker:
                        continue

                    if name == ".":
                        entry_name = file_name
                    else:
                        parent_path = str(Path(file_name).parent)
                        entry_name = parent_path

                    stat_info = self.adapter._get_stat(entry_name)

                    result.append(
                        {
                            "file_name": name,
                            "file_attributes": FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
                            "allocation_size": 0,
                            "file_size": 0,
                            "creation_time": int(stat_info.st_ctime * 10000000),
                            "last_access_time": int(stat_info.st_atime * 10000000),
                            "last_write_time": int(stat_info.st_mtime * 10000000),
                            "change_time": int(stat_info.st_ctime * 10000000),
                        }
                    )

                # Add regular entries
                for entry in entries:
                    if marker and entry <= marker:
                        continue

                    if file_name == "/":
                        entry_path = f"/{entry}"
                    else:
                        entry_path = f"{file_name}/{entry}"

                    stat_info = self.adapter._get_stat(entry_path)

                    is_dir = self.adapter.vfs.is_dir(
                        self.adapter._path_to_vfs(entry_path)
                    )

                    attrs = FILE_ATTRIBUTE.FILE_ATTRIBUTE_NORMAL
                    if is_dir:
                        attrs |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY

                    result.append(
                        {
                            "file_name": entry,
                            "file_attributes": attrs,
                            "allocation_size": stat_info.st_size,
                            "file_size": stat_info.st_size,
                            "creation_time": int(stat_info.st_ctime * 10000000),
                            "last_access_time": int(stat_info.st_atime * 10000000),
                            "last_write_time": int(stat_info.st_mtime * 10000000),
                            "change_time": int(stat_info.st_ctime * 10000000),
                        }
                    )

                return result

            except FileNotFoundError:
                raise NTStatusObjectNameNotFound()
            except NotADirectoryError:
                raise NTStatusNotADirectory()
            except Exception as e:
                self.logger.error(f"read_directory error: {e}")
                raise

        def create(
            self,
            file_name: str,
            create_options: int,
            granted_access: int,
            file_attributes: int,
            security_descriptor: Any,
            allocation_size: int,
        ) -> dict[str, Any]:
            """Create a new file or directory."""
            try:
                if self.adapter.options.readonly:
                    raise NTStatusMediaWriteProtected()

                is_directory = bool(
                    create_options & CREATE_FILE_CREATE_OPTIONS.FILE_DIRECTORY_FILE
                )

                if is_directory:
                    self.adapter._create_directory(file_name, 0o755)
                else:
                    self.adapter._create_file(file_name, 0o644)

                # Get info for newly created file/dir
                stat_info = self.adapter._get_stat(file_name)

                attrs = FILE_ATTRIBUTE.FILE_ATTRIBUTE_NORMAL
                if is_directory:
                    attrs |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY

                return {
                    "file_attributes": attrs,
                    "allocation_size": stat_info.st_size,
                    "file_size": stat_info.st_size,
                    "creation_time": int(stat_info.st_ctime * 10000000),
                    "last_access_time": int(stat_info.st_atime * 10000000),
                    "last_write_time": int(stat_info.st_mtime * 10000000),
                    "change_time": int(stat_info.st_ctime * 10000000),
                    "index_number": stat_info.st_ino,
                }

            except PermissionError:
                raise NTStatusMediaWriteProtected()
            except FileExistsError:
                raise NTStatusObjectNameCollision()
            except Exception as e:
                self.logger.error(f"create error: {e}")
                raise

        def cleanup(self, file_context: Any, file_name: str | None, flags: int) -> None:
            """Cleanup file resources."""
            # Nothing to do for our implementation

        def overwrite(
            self,
            file_context: Any,
            file_attributes: int,
            replace_file_attributes: bool,
            allocation_size: int,
        ) -> dict[str, Any]:
            """Overwrite a file."""
            try:
                if self.adapter.options.readonly:
                    raise NTStatusMediaWriteProtected()

                file_name = file_context.get("file_name", "")

                # Truncate file
                vfs_path = self.adapter._path_to_vfs(file_name)
                self.adapter.vfs.write_file(vfs_path, "")

                return self.get_file_info(file_context)

            except PermissionError:
                raise NTStatusMediaWriteProtected()
            except Exception as e:
                self.logger.error(f"overwrite error: {e}")
                raise

        def can_delete(self, file_context: Any, file_name: str) -> None:
            """Check if a file can be deleted."""
            if self.adapter.options.readonly:
                raise NTStatusMediaWriteProtected()

            vfs_path = self.adapter._path_to_vfs(file_name)

            if not self.adapter.vfs.exists(vfs_path):
                raise NTStatusObjectNameNotFound()

            # Check if directory is empty
            if self.adapter.vfs.is_dir(vfs_path) and self.adapter.vfs.ls(vfs_path):
                raise NTStatusDirectoryNotEmpty()

        def rename(
            self,
            file_context: Any,
            file_name: str,
            new_file_name: str,
            replace_if_exists: bool,
        ) -> None:
            """Rename a file or directory."""
            # Not implemented in base VirtualFS yet
            raise NotImplementedError("Rename not supported")

    class WinFspAdapter(MountAdapter):  # type: ignore[no-redef]
        """WinFsp mount adapter for Windows."""

        def __init__(
            self,
            vfs: "MountableVFS",
            mount_point: Path,
            options: MountOptions,
        ) -> None:
            super().__init__(vfs, mount_point, options)
            self.operations: VFSFileSystemOperations | None = None
            self.fs: FileSystem | None = None

        async def mount_async(self) -> None:
            """Mount the filesystem asynchronously."""
            if self._mounted:
                raise MountError(f"Already mounted at {self.mount_point}")

            if self.options.debug:
                enable_debug_log()

            self.operations = VFSFileSystemOperations(self)

            try:
                # Create FileSystem instance
                self.fs = FileSystem(
                    str(self.mount_point),
                    self.operations,
                    sector_size=512,
                    sectors_per_allocation_unit=1,
                    volume_creation_time=int(time.time() * 10000000),
                    volume_serial_number=0,
                    file_info_timeout=1000,
                    case_sensitive_search=1,
                    case_preserved_names=1,
                    unicode_on_disk=1,
                    persistent_acls=0,
                    post_cleanup_when_modified_only=1,
                    pass_query_directory_pattern=0,
                    read_only_volume=1 if self.options.readonly else 0,
                )

                self._mounted = True
                logger.info(f"Mounted VFS at {self.mount_point}")

                # Start filesystem in background
                self._mount_task = asyncio.create_task(self._run_winfsp())

            except Exception as e:
                raise MountError(f"Failed to mount: {e}") from e

        async def _run_winfsp(self) -> None:
            """Run the WinFsp filesystem."""
            try:
                if self.fs:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.fs.start)
            except Exception as e:
                logger.error(f"WinFsp error: {e}")
            finally:
                self._mounted = False

        async def unmount_async(self) -> None:
            """Unmount the filesystem."""
            if not self._mounted:
                return

            try:
                if self.fs:
                    self.fs.stop()

                if self._mount_task:
                    await self._mount_task

                self._mounted = False
                logger.info(f"Unmounted VFS from {self.mount_point}")

            except Exception as e:
                raise UnmountError(f"Failed to unmount: {e}") from e

        def mount_blocking(self) -> None:
            """Mount the filesystem in blocking mode."""
            if self._mounted:
                raise MountError(f"Already mounted at {self.mount_point}")

            if self.options.debug:
                enable_debug_log()

            self.operations = VFSFileSystemOperations(self)

            try:
                # Create FileSystem instance
                self.fs = FileSystem(
                    str(self.mount_point),
                    self.operations,
                    sector_size=512,
                    sectors_per_allocation_unit=1,
                    volume_creation_time=int(time.time() * 10000000),
                    volume_serial_number=0,
                    file_info_timeout=1000,
                    case_sensitive_search=1,
                    case_preserved_names=1,
                    unicode_on_disk=1,
                    persistent_acls=0,
                    post_cleanup_when_modified_only=1,
                    pass_query_directory_pattern=0,
                    read_only_volume=1 if self.options.readonly else 0,
                )

                self._mounted = True
                logger.info(f"Mounted VFS at {self.mount_point}")

                # Start filesystem (blocking)
                self.fs.start()

            except KeyboardInterrupt:
                logger.info("Received interrupt, unmounting...")
                if self.fs:
                    self.fs.stop()
            except Exception as e:
                self._mounted = False
                raise MountError(f"Failed to mount: {e}") from e
            finally:
                self._mounted = False
