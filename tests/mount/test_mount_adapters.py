"""Tests for cross-platform mount adapters (FUSE/WinFsp)."""

import errno
from pathlib import Path
from unittest.mock import patch

import pytest

from chuk_virtual_fs.mount import MountOptions, mount
from chuk_virtual_fs.mount.base import MountAdapter, StatInfo
from chuk_virtual_fs.mount.exceptions import (
    MountError,
    MountNotSupportedError,
    UnmountError,
)
from chuk_virtual_fs.sync_wrapper import SyncVirtualFileSystem


class TestMountOptions:
    """Test MountOptions configuration."""

    def test_mount_options_defaults(self):
        """Test default mount options."""
        options = MountOptions()
        assert options.readonly is False
        assert options.allow_other is False
        assert options.debug is False
        assert options.cache_timeout == 1.0
        assert options.max_read == 131072
        assert options.max_write == 131072
        assert options.extra_options == {}

    def test_mount_options_custom(self):
        """Test custom mount options."""
        options = MountOptions(
            readonly=True,
            allow_other=True,
            debug=True,
            cache_timeout=2.5,
            max_read=65536,
            max_write=65536,
            extra_options={"key": "value"},
        )
        assert options.readonly is True
        assert options.allow_other is True
        assert options.debug is True
        assert options.cache_timeout == 2.5
        assert options.max_read == 65536
        assert options.max_write == 65536
        assert options.extra_options == {"key": "value"}


class TestStatInfo:
    """Test StatInfo data structure."""

    def test_stat_info_creation(self):
        """Test creating StatInfo."""
        info = StatInfo(
            st_mode=0o644,
            st_ino=12345,
            st_size=1024,
            st_atime=1000.0,
            st_mtime=2000.0,
            st_ctime=3000.0,
        )
        assert info.st_mode == 0o644
        assert info.st_ino == 12345
        assert info.st_size == 1024
        assert info.st_atime == 1000.0
        assert info.st_mtime == 2000.0
        assert info.st_ctime == 3000.0

    def test_stat_info_to_dict(self):
        """Test converting StatInfo to dict."""
        info = StatInfo(st_mode=0o644, st_ino=12345, st_size=1024)
        d = info.to_dict()
        assert d["st_mode"] == 0o644
        assert d["st_ino"] == 12345
        assert d["st_size"] == 1024
        assert "st_atime" in d
        assert "st_mtime" in d
        assert "st_ctime" in d


class TestMountAdapterBase:
    """Test MountAdapter base class functionality."""

    def test_mount_adapter_initialization(self):
        """Test initializing mount adapter."""
        vfs = SyncVirtualFileSystem()
        mount_point = Path("/mnt/test")
        options = MountOptions()

        # Create a concrete subclass for testing
        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, mount_point, options)
        assert adapter.vfs == vfs
        assert adapter.mount_point == mount_point
        assert adapter.options == options
        assert adapter.is_mounted is False

    def test_path_to_vfs(self):
        """Test path conversion to VFS format."""
        vfs = SyncVirtualFileSystem()

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())

        assert adapter._path_to_vfs("/") == "/"
        assert adapter._path_to_vfs("/file.txt") == "/file.txt"
        assert adapter._path_to_vfs("file.txt") == "/file.txt"
        assert adapter._path_to_vfs("") == "/"

    def test_get_stat_file(self):
        """Test getting stat for a file."""
        vfs = SyncVirtualFileSystem()
        vfs.write_file("/test.txt", "hello")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        stat = adapter._get_stat("/test.txt")

        assert stat.st_mode & 0o100000  # Regular file
        assert stat.st_size == 5
        assert stat.st_nlink == 1

    def test_get_stat_directory(self):
        """Test getting stat for a directory."""
        vfs = SyncVirtualFileSystem()
        vfs.mkdir("/testdir")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        stat = adapter._get_stat("/testdir")

        assert stat.st_mode & 0o040000  # Directory
        assert stat.st_size == 4096
        assert stat.st_nlink == 2

    def test_get_stat_not_found(self):
        """Test getting stat for non-existent path."""
        vfs = SyncVirtualFileSystem()

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())

        with pytest.raises(FileNotFoundError):
            adapter._get_stat("/nonexistent")

    def test_read_file(self):
        """Test reading file content."""
        vfs = SyncVirtualFileSystem()
        vfs.write_file("/test.txt", "hello world")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        data = adapter._read_file("/test.txt", 0, 5)
        assert data == b"hello"

        data = adapter._read_file("/test.txt", 6, 5)
        assert data == b"world"

    def test_read_file_not_found(self):
        """Test reading non-existent file."""
        vfs = SyncVirtualFileSystem()

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())

        with pytest.raises(FileNotFoundError):
            adapter._read_file("/nonexistent", 0, 10)

    def test_read_directory_error(self):
        """Test reading a directory as file."""
        vfs = SyncVirtualFileSystem()
        vfs.mkdir("/testdir")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())

        with pytest.raises(IsADirectoryError):
            adapter._read_file("/testdir", 0, 10)

    def test_write_file(self):
        """Test writing to file."""
        vfs = SyncVirtualFileSystem()
        vfs.write_file("/test.txt", "initial")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        written = adapter._write_file("/test.txt", b"hello", 0)
        assert written == 5

        content = vfs.read_file("/test.txt")
        # Content may be string or bytes
        if isinstance(content, bytes):
            assert b"hello" in content
        else:
            assert "hello" in content

    def test_write_file_readonly(self):
        """Test writing to readonly filesystem."""
        vfs = SyncVirtualFileSystem()
        vfs.write_file("/test.txt", "")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions(readonly=True))

        with pytest.raises(PermissionError):
            adapter._write_file("/test.txt", b"hello", 0)

    def test_list_directory(self):
        """Test listing directory contents."""
        vfs = SyncVirtualFileSystem()
        vfs.mkdir("/testdir")
        vfs.write_file("/testdir/file1.txt", "")
        vfs.write_file("/testdir/file2.txt", "")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        entries = adapter._list_directory("/testdir")
        assert set(entries) == {"file1.txt", "file2.txt"}

    def test_list_directory_not_found(self):
        """Test listing non-existent directory."""
        vfs = SyncVirtualFileSystem()

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())

        with pytest.raises(FileNotFoundError):
            adapter._list_directory("/nonexistent")

    def test_list_file_as_directory(self):
        """Test listing a file as directory."""
        vfs = SyncVirtualFileSystem()
        vfs.write_file("/test.txt", "")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())

        with pytest.raises(NotADirectoryError):
            adapter._list_directory("/test.txt")

    def test_create_file(self):
        """Test creating a new file."""
        vfs = SyncVirtualFileSystem()

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        adapter._create_file("/newfile.txt", 0o644)
        assert vfs.exists("/newfile.txt")
        assert vfs.is_file("/newfile.txt")

    def test_create_file_readonly(self):
        """Test creating file in readonly filesystem."""
        vfs = SyncVirtualFileSystem()

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions(readonly=True))

        with pytest.raises(PermissionError):
            adapter._create_file("/newfile.txt", 0o644)

    def test_create_directory(self):
        """Test creating a new directory."""
        vfs = SyncVirtualFileSystem()

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        adapter._create_directory("/newdir", 0o755)
        assert vfs.exists("/newdir")
        assert vfs.is_dir("/newdir")

    def test_create_directory_readonly(self):
        """Test creating directory in readonly filesystem."""
        vfs = SyncVirtualFileSystem()

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions(readonly=True))

        with pytest.raises(PermissionError):
            adapter._create_directory("/newdir", 0o755)

    def test_delete_file(self):
        """Test deleting a file."""
        vfs = SyncVirtualFileSystem()
        vfs.write_file("/test.txt", "")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        adapter._delete_file("/test.txt")
        assert not vfs.exists("/test.txt")

    def test_delete_file_readonly(self):
        """Test deleting file from readonly filesystem."""
        vfs = SyncVirtualFileSystem()
        vfs.write_file("/test.txt", "")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions(readonly=True))

        with pytest.raises(PermissionError):
            adapter._delete_file("/test.txt")

    def test_delete_directory(self):
        """Test deleting an empty directory."""
        vfs = SyncVirtualFileSystem()
        vfs.mkdir("/testdir")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())
        adapter._delete_directory("/testdir")
        assert not vfs.exists("/testdir")

    def test_delete_directory_not_empty(self):
        """Test deleting a non-empty directory."""
        vfs = SyncVirtualFileSystem()
        vfs.mkdir("/testdir")
        vfs.write_file("/testdir/file.txt", "")

        class TestAdapter(MountAdapter):
            async def mount_async(self):
                pass

            async def unmount_async(self):
                pass

            def mount_blocking(self):
                pass

        adapter = TestAdapter(vfs, Path("/mnt/test"), MountOptions())

        with pytest.raises(OSError) as excinfo:
            adapter._delete_directory("/testdir")
        assert excinfo.value.errno == errno.ENOTEMPTY


class TestMountFunction:
    """Test the mount() factory function."""

    @pytest.mark.skip(reason="Requires FUSE libraries to be installed")
    @patch("sys.platform", "linux")
    @patch("chuk_virtual_fs.mount.fuse_adapter.HAS_PYFUSE3", True)
    def test_mount_linux(self):
        """Test mount() returns FUSE adapter on Linux."""
        vfs = SyncVirtualFileSystem()
        adapter = mount(vfs, "/mnt/test")
        from chuk_virtual_fs.mount.fuse_adapter import FUSEAdapter

        assert isinstance(adapter, FUSEAdapter)

    @pytest.mark.skip(reason="Requires FUSE libraries to be installed")
    @patch("sys.platform", "darwin")
    @patch("chuk_virtual_fs.mount.fuse_adapter.HAS_PYFUSE3", True)
    def test_mount_macos(self):
        """Test mount() returns FUSE adapter on macOS."""
        vfs = SyncVirtualFileSystem()
        adapter = mount(vfs, "/mnt/test")
        from chuk_virtual_fs.mount.fuse_adapter import FUSEAdapter

        assert isinstance(adapter, FUSEAdapter)

    @pytest.mark.skip(reason="Requires WinFsp libraries to be installed")
    @patch("sys.platform", "win32")
    @patch("chuk_virtual_fs.mount.winfsp_adapter.HAS_WINFSP", True)
    def test_mount_windows(self):
        """Test mount() returns WinFsp adapter on Windows."""
        vfs = SyncVirtualFileSystem()
        adapter = mount(vfs, "Z:")
        from chuk_virtual_fs.mount.winfsp_adapter import WinFspAdapter

        assert isinstance(adapter, WinFspAdapter)

    @patch("sys.platform", "unsupported")
    def test_mount_unsupported_platform(self):
        """Test mount() raises error on unsupported platform."""
        vfs = SyncVirtualFileSystem()
        with pytest.raises(MountNotSupportedError):
            mount(vfs, "/mnt/test")

    @pytest.mark.skip(reason="Requires FUSE libraries to be installed")
    @patch("chuk_virtual_fs.mount.fuse_adapter.HAS_PYFUSE3", True)
    def test_mount_with_options(self):
        """Test mount() with custom options."""
        vfs = SyncVirtualFileSystem()
        options = MountOptions(readonly=True, debug=True)
        adapter = mount(vfs, "/mnt/test", options)
        assert adapter.options.readonly is True
        assert adapter.options.debug is True


class TestExceptions:
    """Test mount exceptions."""

    def test_mount_error(self):
        """Test MountError exception."""
        err = MountError("Test error")
        assert str(err) == "Test error"

    def test_unmount_error(self):
        """Test UnmountError exception."""
        err = UnmountError("Test error")
        assert str(err) == "Test error"

    def test_mount_not_supported_error(self):
        """Test MountNotSupportedError exception."""
        err = MountNotSupportedError("Platform not supported")
        assert str(err) == "Platform not supported"
