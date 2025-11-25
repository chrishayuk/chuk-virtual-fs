"""FUSE-based mount adapter for Linux and macOS."""

import asyncio
import errno
import logging
import subprocess
import sys
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

# Try to import pyfuse3 (preferred)
try:
    import pyfuse3

    HAS_PYFUSE3 = True
    HAS_FUSE = False
except ImportError:
    HAS_PYFUSE3 = False
    # Fall back to fusepy
    try:
        from fuse import FUSE, FuseOSError, LoggingMixIn, Operations

        HAS_FUSE = True
    except ImportError:
        HAS_FUSE = False


if not HAS_PYFUSE3 and not HAS_FUSE:

    class FUSEAdapter(MountAdapter):
        """Stub adapter when FUSE is not available."""

        def __init__(
            self,
            vfs: "MountableVFS",
            mount_point: Path,
            options: MountOptions,
        ) -> None:
            super().__init__(vfs, mount_point, options)
            raise MountError(
                "FUSE support not available. Install with: "
                "pip install chuk-virtual-fs[mount]"
            )

        async def mount_async(self) -> None:
            pass

        async def unmount_async(self) -> None:
            pass

        def mount_blocking(self) -> None:
            pass


elif HAS_PYFUSE3:
    # Modern async FUSE implementation using pyfuse3

    class VFSOperations(pyfuse3.Operations):
        """pyfuse3 operations that delegate to VirtualFS."""

        def __init__(self, adapter: "FUSEAdapter"):
            super().__init__()
            self.adapter = adapter
            self.logger = logging.getLogger(__name__ + ".VFSOperations")

        async def getattr(
            self, inode: int, ctx: pyfuse3.RequestContext
        ) -> pyfuse3.EntryAttributes:
            """Get file attributes."""
            try:
                path = self._inode_to_path(inode)
                stat_info = self.adapter._get_stat(path)

                attrs = pyfuse3.EntryAttributes()
                attrs.st_ino = stat_info.st_ino
                attrs.st_mode = stat_info.st_mode
                attrs.st_nlink = stat_info.st_nlink
                attrs.st_uid = stat_info.st_uid
                attrs.st_gid = stat_info.st_gid
                attrs.st_rdev = 0
                attrs.st_size = stat_info.st_size
                attrs.st_blksize = 512
                attrs.st_blocks = (stat_info.st_size + 511) // 512
                attrs.st_atime_ns = int(stat_info.st_atime * 1e9)
                attrs.st_mtime_ns = int(stat_info.st_mtime * 1e9)
                attrs.st_ctime_ns = int(stat_info.st_ctime * 1e9)

                return attrs

            except FileNotFoundError:
                raise pyfuse3.FUSEError(errno.ENOENT)
            except Exception as e:
                self.logger.error(f"getattr error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        async def lookup(
            self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext
        ) -> pyfuse3.EntryAttributes:
            """Look up a directory entry."""
            try:
                parent_path = self._inode_to_path(parent_inode)
                name_str = name.decode("utf-8")

                if parent_path == "/":
                    path = f"/{name_str}"
                else:
                    path = f"{parent_path}/{name_str}"

                stat_info = self.adapter._get_stat(path)

                attrs = pyfuse3.EntryAttributes()
                attrs.st_ino = stat_info.st_ino
                attrs.st_mode = stat_info.st_mode
                attrs.st_nlink = stat_info.st_nlink
                attrs.st_uid = stat_info.st_uid
                attrs.st_gid = stat_info.st_gid
                attrs.st_rdev = 0
                attrs.st_size = stat_info.st_size
                attrs.st_blksize = 512
                attrs.st_blocks = (stat_info.st_size + 511) // 512
                attrs.st_atime_ns = int(stat_info.st_atime * 1e9)
                attrs.st_mtime_ns = int(stat_info.st_mtime * 1e9)
                attrs.st_ctime_ns = int(stat_info.st_ctime * 1e9)

                return attrs

            except FileNotFoundError:
                raise pyfuse3.FUSEError(errno.ENOENT)
            except Exception as e:
                self.logger.error(f"lookup error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        async def opendir(self, inode: int, ctx: pyfuse3.RequestContext) -> int:
            """Open a directory."""
            # Return inode as handle
            return inode

        async def readdir(
            self, fh: int, start_id: int, token: pyfuse3.ReaddirToken
        ) -> None:
            """Read directory entries."""
            try:
                path = self._inode_to_path(fh)
                entries = self.adapter._list_directory(path)

                # Add . and ..
                all_entries = [".", ".."] + entries

                for i, name in enumerate(all_entries[start_id:], start=start_id):
                    if name == ".":
                        stat_info = self.adapter._get_stat(path)
                    elif name == "..":
                        parent_path = str(Path(path).parent)
                        stat_info = self.adapter._get_stat(parent_path)
                    else:
                        entry_path = f"/{name}" if path == "/" else f"{path}/{name}"
                        stat_info = self.adapter._get_stat(entry_path)

                    attrs = pyfuse3.EntryAttributes()
                    attrs.st_ino = stat_info.st_ino
                    attrs.st_mode = stat_info.st_mode
                    attrs.st_nlink = stat_info.st_nlink
                    attrs.st_uid = stat_info.st_uid
                    attrs.st_gid = stat_info.st_gid
                    attrs.st_rdev = 0
                    attrs.st_size = stat_info.st_size
                    attrs.st_blksize = 512
                    attrs.st_blocks = (stat_info.st_size + 511) // 512
                    attrs.st_atime_ns = int(stat_info.st_atime * 1e9)
                    attrs.st_mtime_ns = int(stat_info.st_mtime * 1e9)
                    attrs.st_ctime_ns = int(stat_info.st_ctime * 1e9)

                    if not pyfuse3.readdir_reply(
                        token, name.encode("utf-8"), attrs, i + 1
                    ):
                        break

            except Exception as e:
                self.logger.error(f"readdir error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        async def open(
            self, inode: int, flags: int, ctx: pyfuse3.RequestContext
        ) -> pyfuse3.FileInfo:
            """Open a file."""
            # Return inode as handle
            info = pyfuse3.FileInfo()
            info.fh = inode
            return info

        async def read(self, fh: int, offset: int, length: int) -> bytes:
            """Read from a file."""
            try:
                path = self._inode_to_path(fh)
                return self.adapter._read_file(path, offset, length)
            except FileNotFoundError:
                raise pyfuse3.FUSEError(errno.ENOENT)
            except Exception as e:
                self.logger.error(f"read error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        async def write(self, fh: int, offset: int, buf: bytes) -> int:
            """Write to a file."""
            try:
                path = self._inode_to_path(fh)
                return self.adapter._write_file(path, buf, offset)
            except PermissionError:
                raise pyfuse3.FUSEError(errno.EROFS)
            except Exception as e:
                self.logger.error(f"write error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        async def create(
            self,
            parent_inode: int,
            name: bytes,
            mode: int,
            flags: int,
            ctx: pyfuse3.RequestContext,
        ) -> tuple[pyfuse3.FileInfo, pyfuse3.EntryAttributes]:
            """Create a new file."""
            try:
                parent_path = self._inode_to_path(parent_inode)
                name_str = name.decode("utf-8")

                if parent_path == "/":
                    path = f"/{name_str}"
                else:
                    path = f"{parent_path}/{name_str}"

                self.adapter._create_file(path, mode)

                # Get attributes of newly created file
                stat_info = self.adapter._get_stat(path)

                info = pyfuse3.FileInfo()
                info.fh = stat_info.st_ino

                attrs = pyfuse3.EntryAttributes()
                attrs.st_ino = stat_info.st_ino
                attrs.st_mode = stat_info.st_mode
                attrs.st_nlink = stat_info.st_nlink
                attrs.st_uid = stat_info.st_uid
                attrs.st_gid = stat_info.st_gid
                attrs.st_rdev = 0
                attrs.st_size = stat_info.st_size
                attrs.st_blksize = 512
                attrs.st_blocks = (stat_info.st_size + 511) // 512
                attrs.st_atime_ns = int(stat_info.st_atime * 1e9)
                attrs.st_mtime_ns = int(stat_info.st_mtime * 1e9)
                attrs.st_ctime_ns = int(stat_info.st_ctime * 1e9)

                return (info, attrs)

            except PermissionError:
                raise pyfuse3.FUSEError(errno.EROFS)
            except FileExistsError:
                raise pyfuse3.FUSEError(errno.EEXIST)
            except Exception as e:
                self.logger.error(f"create error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        async def mkdir(
            self,
            parent_inode: int,
            name: bytes,
            mode: int,
            ctx: pyfuse3.RequestContext,
        ) -> pyfuse3.EntryAttributes:
            """Create a directory."""
            try:
                parent_path = self._inode_to_path(parent_inode)
                name_str = name.decode("utf-8")

                if parent_path == "/":
                    path = f"/{name_str}"
                else:
                    path = f"{parent_path}/{name_str}"

                self.adapter._create_directory(path, mode)

                # Get attributes of newly created directory
                stat_info = self.adapter._get_stat(path)

                attrs = pyfuse3.EntryAttributes()
                attrs.st_ino = stat_info.st_ino
                attrs.st_mode = stat_info.st_mode
                attrs.st_nlink = stat_info.st_nlink
                attrs.st_uid = stat_info.st_uid
                attrs.st_gid = stat_info.st_gid
                attrs.st_rdev = 0
                attrs.st_size = stat_info.st_size
                attrs.st_blksize = 512
                attrs.st_blocks = (stat_info.st_size + 511) // 512
                attrs.st_atime_ns = int(stat_info.st_atime * 1e9)
                attrs.st_mtime_ns = int(stat_info.st_mtime * 1e9)
                attrs.st_ctime_ns = int(stat_info.st_ctime * 1e9)

                return attrs

            except PermissionError:
                raise pyfuse3.FUSEError(errno.EROFS)
            except FileExistsError:
                raise pyfuse3.FUSEError(errno.EEXIST)
            except Exception as e:
                self.logger.error(f"mkdir error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        async def unlink(
            self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext
        ) -> None:
            """Delete a file."""
            try:
                parent_path = self._inode_to_path(parent_inode)
                name_str = name.decode("utf-8")

                if parent_path == "/":
                    path = f"/{name_str}"
                else:
                    path = f"{parent_path}/{name_str}"

                self.adapter._delete_file(path)

            except PermissionError:
                raise pyfuse3.FUSEError(errno.EROFS)
            except FileNotFoundError:
                raise pyfuse3.FUSEError(errno.ENOENT)
            except Exception as e:
                self.logger.error(f"unlink error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        async def rmdir(
            self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext
        ) -> None:
            """Delete a directory."""
            try:
                parent_path = self._inode_to_path(parent_inode)
                name_str = name.decode("utf-8")

                if parent_path == "/":
                    path = f"/{name_str}"
                else:
                    path = f"{parent_path}/{name_str}"

                self.adapter._delete_directory(path)

            except PermissionError:
                raise pyfuse3.FUSEError(errno.EROFS)
            except FileNotFoundError:
                raise pyfuse3.FUSEError(errno.ENOENT)
            except OSError as e:
                if e.errno == errno.ENOTEMPTY:
                    raise pyfuse3.FUSEError(errno.ENOTEMPTY)
                raise
            except Exception as e:
                self.logger.error(f"rmdir error: {e}")
                raise pyfuse3.FUSEError(errno.EIO)

        def _inode_to_path(self, inode: int) -> str:
            """Convert an inode to a VFS path."""
            # Root always has inode 1
            if inode == pyfuse3.ROOT_INODE:
                return "/"

            # For simplicity, we'll need to maintain an inode->path mapping
            # This is a limitation of the current implementation
            # A production version would maintain a proper inode table

            # For now, we'll reconstruct from the VFS
            # This is inefficient but works for the prototype
            return self._find_path_by_inode(inode, "/")

        def _find_path_by_inode(self, target_inode: int, current_path: str) -> str:
            """Recursively find a path by inode (inefficient but functional)."""
            # Check current path
            try:
                stat_info = self.adapter._get_stat(current_path)
                if stat_info.st_ino == target_inode:
                    return current_path
            except Exception:
                pass

            # Check children if directory
            try:
                if self.adapter.vfs.is_dir(self.adapter._path_to_vfs(current_path)):
                    entries = self.adapter._list_directory(current_path)
                    for entry in entries:
                        if current_path == "/":
                            child_path = f"/{entry}"
                        else:
                            child_path = f"{current_path}/{entry}"

                        result = self._find_path_by_inode(target_inode, child_path)
                        if result:
                            return result
            except Exception:
                pass

            return ""

    class FUSEAdapter(MountAdapter):  # type: ignore[no-redef]
        """FUSE mount adapter using pyfuse3."""

        def __init__(
            self,
            vfs: "MountableVFS",
            mount_point: Path,
            options: MountOptions,
        ) -> None:
            super().__init__(vfs, mount_point, options)
            self.operations: VFSOperations | None = None

        async def mount_async(self) -> None:
            """Mount the filesystem asynchronously."""
            if self._mounted:
                raise MountError(f"Already mounted at {self.mount_point}")

            # Ensure mount point exists
            self.mount_point.mkdir(parents=True, exist_ok=True)

            # Build FUSE options
            fuse_options = set()

            if self.options.allow_other:
                fuse_options.add("allow_other")

            if self.options.readonly:
                fuse_options.add("ro")

            if self.options.debug:
                fuse_options.add("debug")

            # Initialize FUSE
            self.operations = VFSOperations(self)

            try:
                pyfuse3.init(self.operations, str(self.mount_point), fuse_options)
                self._mounted = True
                logger.info(f"Mounted VFS at {self.mount_point}")

                # Start FUSE main loop in background
                self._mount_task = asyncio.create_task(self._run_fuse())

            except Exception as e:
                raise MountError(f"Failed to mount: {e}") from e

        async def _run_fuse(self) -> None:
            """Run the FUSE main loop."""
            try:
                await pyfuse3.main()
            except Exception as e:
                logger.error(f"FUSE main loop error: {e}")
            finally:
                self._mounted = False

        async def unmount_async(self) -> None:
            """Unmount the filesystem."""
            if not self._mounted:
                return

            try:
                pyfuse3.close()

                if self._mount_task:
                    await self._mount_task

                self._mounted = False
                logger.info(f"Unmounted VFS from {self.mount_point}")

            except Exception as e:
                raise UnmountError(f"Failed to unmount: {e}") from e

        def mount_blocking(self) -> None:
            """Mount the filesystem in blocking mode."""
            asyncio.run(self._mount_blocking_impl())

        async def _mount_blocking_impl(self) -> None:
            """Implementation of blocking mount."""
            await self.mount_async()

            # Wait for interrupt
            try:
                if self._mount_task:
                    await self._mount_task
            except KeyboardInterrupt:
                logger.info("Received interrupt, unmounting...")
            finally:
                await self.unmount_async()


else:  # HAS_FUSE (fusepy fallback)

    class VFSOperations(LoggingMixIn, Operations):  # type: ignore
        """fusepy operations that delegate to VirtualFS."""

        def __init__(self, adapter: "FUSEAdapter"):
            super().__init__()
            self.adapter = adapter

        def getattr(self, path: str, fh: Any = None) -> dict[str, Any]:
            """Get file attributes."""
            try:
                stat_info = self.adapter._get_stat(path)
                return stat_info.to_dict()
            except FileNotFoundError:
                raise FuseOSError(errno.ENOENT)
            except Exception:
                raise FuseOSError(errno.EIO)

        def readdir(self, path: str, fh: Any) -> list[str]:
            """Read directory entries."""
            try:
                entries = self.adapter._list_directory(path)
                return [".", ".."] + entries
            except FileNotFoundError:
                raise FuseOSError(errno.ENOENT)
            except Exception:
                raise FuseOSError(errno.EIO)

        def read(self, path: str, size: int, offset: int, fh: Any) -> bytes:
            """Read from file."""
            try:
                return self.adapter._read_file(path, offset, size)
            except FileNotFoundError:
                raise FuseOSError(errno.ENOENT)
            except Exception:
                raise FuseOSError(errno.EIO)

        def write(self, path: str, data: bytes, offset: int, fh: Any) -> int:
            """Write to file."""
            try:
                return self.adapter._write_file(path, data, offset)
            except PermissionError:
                raise FuseOSError(errno.EROFS)
            except Exception:
                raise FuseOSError(errno.EIO)

        def create(self, path: str, mode: int) -> int:
            """Create file."""
            try:
                self.adapter._create_file(path, mode)
                return 0
            except PermissionError:
                raise FuseOSError(errno.EROFS)
            except FileExistsError:
                raise FuseOSError(errno.EEXIST)
            except Exception:
                raise FuseOSError(errno.EIO)

        def mkdir(self, path: str, mode: int) -> None:
            """Create directory."""
            try:
                self.adapter._create_directory(path, mode)
            except PermissionError:
                raise FuseOSError(errno.EROFS)
            except FileExistsError:
                raise FuseOSError(errno.EEXIST)
            except Exception:
                raise FuseOSError(errno.EIO)

        def unlink(self, path: str) -> None:
            """Delete file."""
            try:
                self.adapter._delete_file(path)
            except PermissionError:
                raise FuseOSError(errno.EROFS)
            except FileNotFoundError:
                raise FuseOSError(errno.ENOENT)
            except Exception:
                raise FuseOSError(errno.EIO)

        def rmdir(self, path: str) -> None:
            """Delete directory."""
            try:
                self.adapter._delete_directory(path)
            except PermissionError:
                raise FuseOSError(errno.EROFS)
            except FileNotFoundError:
                raise FuseOSError(errno.ENOENT)
            except OSError as e:
                if e.errno == errno.ENOTEMPTY:
                    raise FuseOSError(errno.ENOTEMPTY)
                raise
            except Exception:
                raise FuseOSError(errno.EIO)

    class FUSEAdapter(MountAdapter):  # type: ignore[no-redef]
        """FUSE mount adapter using fusepy."""

        def __init__(
            self,
            vfs: "MountableVFS",
            mount_point: Path,
            options: MountOptions,
        ) -> None:
            super().__init__(vfs, mount_point, options)
            self.operations: VFSOperations | None = None
            self._fuse: FUSE | None = None

        async def mount_async(self) -> None:
            """Mount the filesystem asynchronously."""
            # fusepy is synchronous, so we run it in a thread
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.mount_blocking)

        async def unmount_async(self) -> None:
            """Unmount the filesystem."""
            if not self._mounted:
                return

            try:
                # Send SIGTERM to unmount
                if sys.platform == "darwin":
                    subprocess.run(["umount", str(self.mount_point)], check=True)
                else:
                    subprocess.run(
                        ["fusermount", "-u", str(self.mount_point)], check=True
                    )

                self._mounted = False
                logger.info(f"Unmounted VFS from {self.mount_point}")

            except Exception as e:
                raise UnmountError(f"Failed to unmount: {e}") from e

        def mount_blocking(self) -> None:
            """Mount the filesystem in blocking mode."""
            if self._mounted:
                raise MountError(f"Already mounted at {self.mount_point}")

            # Ensure mount point exists
            self.mount_point.mkdir(parents=True, exist_ok=True)

            self.operations = VFSOperations(self)

            try:
                self._mounted = True
                logger.info(f"Mounting VFS at {self.mount_point}")

                FUSE(
                    self.operations,
                    str(self.mount_point),
                    foreground=True,
                    allow_other=self.options.allow_other,
                    ro=self.options.readonly,
                    debug=self.options.debug,
                )

            except Exception as e:
                self._mounted = False
                raise MountError(f"Failed to mount: {e}") from e
