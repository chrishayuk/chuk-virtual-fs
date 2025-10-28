"""
Tests for sync_wrapper.py - Synchronous wrapper for AsyncVirtualFileSystem
"""

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.sync_wrapper import SyncVirtualFileSystem


class TestSyncVirtualFileSystem:
    """Test the synchronous wrapper"""

    @pytest.fixture
    def sync_fs(self):
        """Create a sync filesystem for testing"""
        fs = SyncVirtualFileSystem(provider_name="memory")
        yield fs
        fs.close()

    def test_initialization(self):
        """Test filesystem initialization"""
        fs = SyncVirtualFileSystem(provider_name="memory")
        assert fs is not None
        assert not fs._initialized
        fs.close()

    def test_get_provider_name(self, sync_fs):
        """Test getting provider name"""
        name = sync_fs.get_provider_name()
        assert name == "memory"

    def test_pwd(self, sync_fs):
        """Test getting current working directory"""
        pwd = sync_fs.pwd()
        assert pwd == "/"

    def test_cd(self, sync_fs):
        """Test changing directory"""
        # Create a directory first
        assert sync_fs.mkdir("/test_dir")
        # Change to it
        assert sync_fs.cd("/test_dir")
        assert sync_fs.pwd() == "/test_dir"
        # Change back
        assert sync_fs.cd("/")
        assert sync_fs.pwd() == "/"

    def test_mkdir(self, sync_fs):
        """Test creating directories"""
        assert sync_fs.mkdir("/dir1")
        assert sync_fs.exists("/dir1")
        assert sync_fs.is_dir("/dir1")

    def test_touch(self, sync_fs):
        """Test creating files"""
        assert sync_fs.touch("/file1.txt")
        assert sync_fs.exists("/file1.txt")
        assert sync_fs.is_file("/file1.txt")

    def test_ls(self, sync_fs):
        """Test listing directory contents"""
        # Create some files and directories
        sync_fs.mkdir("/test_dir")
        sync_fs.touch("/file1.txt")
        sync_fs.touch("/file2.txt")

        # List root directory
        contents = sync_fs.ls("/")
        assert "test_dir" in contents
        assert "file1.txt" in contents
        assert "file2.txt" in contents

        # List with no path (current directory)
        contents = sync_fs.ls()
        assert "test_dir" in contents

    def test_rm(self, sync_fs):
        """Test removing files"""
        # Create and remove a file
        sync_fs.touch("/file_to_remove.txt")
        assert sync_fs.exists("/file_to_remove.txt")
        assert sync_fs.rm("/file_to_remove.txt")
        assert not sync_fs.exists("/file_to_remove.txt")

    def test_rmdir(self, sync_fs):
        """Test removing directories"""
        # Create and remove a directory
        sync_fs.mkdir("/dir_to_remove")
        assert sync_fs.exists("/dir_to_remove")
        assert sync_fs.rmdir("/dir_to_remove")
        assert not sync_fs.exists("/dir_to_remove")

    def test_write_and_read_file(self, sync_fs):
        """Test writing and reading files"""
        content = "Hello, World!"
        sync_fs.write_file("/test.txt", content)
        read_content = sync_fs.read_file("/test.txt")
        assert read_content == content.encode()  # Memory provider returns bytes

    def test_read_nonexistent_file(self, sync_fs):
        """Test reading a non-existent file"""
        result = sync_fs.read_file("/nonexistent.txt")
        assert result is None

    def test_cp(self, sync_fs):
        """Test copying files"""
        # Create a file and copy it
        sync_fs.write_file("/source.txt", "test content")
        assert sync_fs.cp("/source.txt", "/dest.txt")
        assert sync_fs.exists("/dest.txt")
        assert sync_fs.read_file("/dest.txt") == b"test content"

    def test_mv(self, sync_fs):
        """Test moving files"""
        # Create a file and move it
        sync_fs.write_file("/old.txt", "test content")
        assert sync_fs.mv("/old.txt", "/new.txt")
        assert not sync_fs.exists("/old.txt")
        assert sync_fs.exists("/new.txt")

    def test_exists(self, sync_fs):
        """Test checking if path exists"""
        assert not sync_fs.exists("/nonexistent")
        sync_fs.touch("/exists.txt")
        assert sync_fs.exists("/exists.txt")

    def test_is_file(self, sync_fs):
        """Test checking if path is a file"""
        sync_fs.touch("/file.txt")
        sync_fs.mkdir("/dir")
        assert sync_fs.is_file("/file.txt")
        assert not sync_fs.is_file("/dir")
        assert not sync_fs.is_file("/nonexistent")

    def test_is_dir(self, sync_fs):
        """Test checking if path is a directory"""
        sync_fs.mkdir("/dir")
        sync_fs.touch("/file.txt")
        assert sync_fs.is_dir("/dir")
        assert not sync_fs.is_dir("/file.txt")
        assert not sync_fs.is_dir("/nonexistent")

    def test_get_node_info(self, sync_fs):
        """Test getting node information"""
        sync_fs.touch("/file.txt")
        info = sync_fs.get_node_info("/file.txt")
        assert info is not None
        assert isinstance(info, EnhancedNodeInfo)
        assert info.name == "file.txt"
        assert not info.is_dir

        # Test non-existent file
        info = sync_fs.get_node_info("/nonexistent")
        assert info is None

    def test_resolve_path(self, sync_fs):
        """Test resolving paths"""
        # Change to a subdirectory
        sync_fs.mkdir("/subdir")
        sync_fs.cd("/subdir")

        # Resolve relative path
        resolved = sync_fs.resolve_path("file.txt")
        assert resolved == "/subdir/file.txt"

    def test_get_fs_info(self, sync_fs):
        """Test getting filesystem information"""
        info = sync_fs.get_fs_info()
        assert "provider" in info
        assert "cwd" in info
        assert "stats" in info
        assert info["provider"] == "memory"
        assert info["cwd"] == "/"

    def test_get_storage_stats(self, sync_fs):
        """Test getting storage statistics"""
        # Create some files
        sync_fs.write_file("/file1.txt", "content1")
        sync_fs.write_file("/file2.txt", "content2")

        stats = sync_fs.get_storage_stats()
        assert isinstance(stats, dict)

    def test_find(self, sync_fs):
        """Test finding files by pattern"""
        # Create some files
        sync_fs.touch("/file1.txt")
        sync_fs.touch("/file2.txt")
        sync_fs.touch("/file3.md")

        # Find all txt files
        results = sync_fs.find("*.txt")
        assert isinstance(results, list)

    def test_find_with_path(self, sync_fs):
        """Test finding files with specific path"""
        sync_fs.mkdir("/search_dir")
        sync_fs.touch("/search_dir/file.txt")

        results = sync_fs.find("*.txt", "/search_dir")
        assert isinstance(results, list)

    def test_search(self, sync_fs):
        """Test searching for pattern in files"""
        # Note: search method returns empty list as it's not implemented
        results = sync_fs.search("pattern")
        assert results == []

    def test_get_size(self, sync_fs):
        """Test getting file size"""
        sync_fs.write_file("/file.txt", "test content")
        size = sync_fs.get_size("/file.txt")
        assert size > 0

        # Test non-existent file
        size = sync_fs.get_size("/nonexistent")
        assert size == 0

    def test_provider_property(self, sync_fs):
        """Test accessing provider property"""
        provider = sync_fs.provider
        assert provider is not None

    def test_close(self, sync_fs):
        """Test closing the filesystem"""
        # Ensure initialized
        sync_fs.pwd()
        assert sync_fs._initialized

        # Close
        sync_fs.close()
        assert not sync_fs._initialized

    def test_multiple_operations(self, sync_fs):
        """Test multiple operations in sequence"""
        # Create directory structure
        sync_fs.mkdir("/project")
        sync_fs.cd("/project")
        sync_fs.mkdir("src")
        sync_fs.mkdir("tests")

        # Create files
        sync_fs.write_file("src/main.py", "print('hello')")
        sync_fs.write_file("tests/test_main.py", "def test(): pass")

        # Verify structure
        assert sync_fs.exists("src/main.py")
        assert sync_fs.exists("tests/test_main.py")

        # Copy file
        sync_fs.cp("src/main.py", "src/backup.py")
        assert sync_fs.exists("src/backup.py")

        # List contents
        contents = sync_fs.ls("src")
        assert len(contents) == 2


class TestSyncVirtualFileSystemEventLoop:
    """Test event loop handling in sync wrapper"""

    def test_run_async_creates_loop(self):
        """Test that _run_async creates an event loop if needed"""
        fs = SyncVirtualFileSystem(provider_name="memory")
        # This should create a loop internally
        fs.pwd()
        fs.close()

    def test_with_different_provider(self):
        """Test initialization with different provider"""
        fs = SyncVirtualFileSystem(provider_name="memory")
        assert fs.get_provider_name() == "memory"
        fs.close()
