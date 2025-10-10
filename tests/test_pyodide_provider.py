"""
Test module for PyodideStorageProvider
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.pyodide import PyodideStorageProvider


class TestPyodideProvider:
    """Test PyodideStorageProvider functionality"""

    @pytest.fixture
    async def temp_dir(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp(prefix="pyodide_test_")
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    async def provider(self, temp_dir):
        """Create an initialized PyodideStorageProvider"""
        provider = PyodideStorageProvider(base_path=temp_dir)
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_initialization(self, temp_dir):
        """Test provider initialization"""
        provider = PyodideStorageProvider(base_path=temp_dir)
        result = await provider.initialize()

        assert result is True
        # Check that base directories were created
        assert os.path.exists(os.path.join(temp_dir, "bin"))
        assert os.path.exists(os.path.join(temp_dir, "home"))
        assert os.path.exists(os.path.join(temp_dir, "tmp"))
        assert os.path.exists(os.path.join(temp_dir, "etc"))

        # Check default files
        motd_path = os.path.join(temp_dir, "etc", "motd")
        assert os.path.exists(motd_path)

        await provider.close()

    @pytest.mark.asyncio
    async def test_create_file(self, provider):
        """Test creating a file"""
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")

        result = await provider.create_node(node_info)
        assert result is True

        # Verify file exists
        assert await provider.exists("/test.txt")

    @pytest.mark.asyncio
    async def test_create_directory(self, provider):
        """Test creating a directory"""
        node_info = EnhancedNodeInfo(name="test_dir", is_dir=True, parent_path="/")

        result = await provider.create_node(node_info)
        assert result is True

        # Verify directory exists
        assert await provider.exists("/test_dir")

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, provider):
        """Test writing and reading file content"""
        # Create file
        node_info = EnhancedNodeInfo(name="data.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Write content
        content = b"Hello Pyodide!"
        result = await provider.write_file("/data.txt", content)
        assert result is True

        # Read content
        read_content = await provider.read_file("/data.txt")
        assert read_content == content

    @pytest.mark.asyncio
    async def test_delete_file(self, provider):
        """Test deleting a file"""
        # Create file
        node_info = EnhancedNodeInfo(
            name="delete_me.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(node_info)
        await provider.write_file("/delete_me.txt", b"content")

        # Delete file
        result = await provider.delete_node("/delete_me.txt")
        assert result is True

        # Verify file is deleted
        assert not await provider.exists("/delete_me.txt")

    @pytest.mark.asyncio
    async def test_delete_directory(self, provider):
        """Test deleting a directory"""
        # Create directory
        node_info = EnhancedNodeInfo(name="delete_dir", is_dir=True, parent_path="/")
        await provider.create_node(node_info)

        # Delete directory
        result = await provider.delete_node("/delete_dir")
        assert result is True

        # Verify directory is deleted
        assert not await provider.exists("/delete_dir")

    @pytest.mark.asyncio
    async def test_list_directory(self, provider):
        """Test listing directory contents"""
        # Create some files and directories
        file_node = EnhancedNodeInfo("file1.txt", False, "/")
        dir_node = EnhancedNodeInfo("subdir", True, "/")

        await provider.create_node(file_node)
        await provider.create_node(dir_node)

        # List root directory
        contents = await provider.list_directory("/")

        assert "file1.txt" in contents
        assert "subdir" in contents

    @pytest.mark.asyncio
    async def test_get_node_info(self, provider):
        """Test getting node information"""
        # Create a file
        node_info = EnhancedNodeInfo(
            name="info_test.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(node_info)
        await provider.write_file("/info_test.txt", b"test content")

        # Get node info
        info = await provider.get_node_info("/info_test.txt")

        assert info is not None
        assert info.name == "info_test.txt"
        assert info.is_dir is False
        assert info.size >= 0  # Size may be 0 initially

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, provider):
        """Test getting storage statistics"""
        # Create some files
        for i in range(3):
            node = EnhancedNodeInfo(f"file{i}.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file(f"/file{i}.txt", b"content" * i)

        stats = await provider.get_storage_stats()

        # Check for the actual keys returned by pyodide provider
        assert "total_size_bytes" in stats or "total_size" in stats
        assert "file_count" in stats or "total_files" in stats
        assert "directory_count" in stats or "total_directories" in stats

        # Check counts
        file_count = stats.get("file_count", stats.get("total_files", 0))
        assert file_count >= 3

    @pytest.mark.asyncio
    async def test_cleanup(self, provider):
        """Test cleanup operation"""
        # Create temp files
        tmp_node = EnhancedNodeInfo("temp.txt", False, "/tmp")
        await provider.create_node(tmp_node)
        await provider.write_file("/tmp/temp.txt", b"temporary")

        # Perform cleanup
        result = await provider.cleanup()

        # Check for cleanup result keys
        assert result is not None
        assert "files_removed" in result or "cleaned_up" in result

    @pytest.mark.asyncio
    async def test_copy_file(self, provider):
        """Test copying a file"""
        # Create source file
        source_node = EnhancedNodeInfo("source.txt", False, "/")
        await provider.create_node(source_node)
        await provider.write_file("/source.txt", b"source content")

        # Copy file
        result = await provider.copy_node("/source.txt", "/dest.txt")
        assert result is True

        # Verify both files exist with same content
        assert await provider.exists("/source.txt")
        assert await provider.exists("/dest.txt")

        source_content = await provider.read_file("/source.txt")
        dest_content = await provider.read_file("/dest.txt")
        assert source_content == dest_content

    @pytest.mark.asyncio
    async def test_move_file(self, provider):
        """Test moving a file"""
        # Create source file
        source_node = EnhancedNodeInfo("move_source.txt", False, "/")
        await provider.create_node(source_node)
        await provider.write_file("/move_source.txt", b"move content")

        # Move file
        result = await provider.move_node("/move_source.txt", "/move_dest.txt")
        assert result is True

        # Verify source doesn't exist and destination does
        assert not await provider.exists("/move_source.txt")
        assert await provider.exists("/move_dest.txt")

        dest_content = await provider.read_file("/move_dest.txt")
        assert dest_content == b"move content"

    @pytest.mark.asyncio
    async def test_metadata_operations(self, provider):
        """Test metadata get and set operations"""
        # Create a file
        node = EnhancedNodeInfo("meta_test.txt", False, "/")
        await provider.create_node(node)

        # Set metadata
        metadata = {
            "author": "test_user",
            "version": "1.0",
            "tags": ["test", "pyodide"],
        }
        result = await provider.set_metadata("/meta_test.txt", metadata)
        assert result is True

        # Get metadata
        retrieved = await provider.get_metadata("/meta_test.txt")
        # Check if metadata was stored (may be in custom_meta or directly)
        author = retrieved.get("author") or retrieved.get("custom_meta", {}).get(
            "author"
        )
        version = retrieved.get("version") or retrieved.get("custom_meta", {}).get(
            "version"
        )
        tags = retrieved.get("tags") or retrieved.get("custom_meta", {}).get("tags")

        assert author == "test_user"
        assert version == "1.0"
        assert tags == ["test", "pyodide"]

    @pytest.mark.asyncio
    async def test_batch_operations(self, provider):
        """Test batch operations"""
        # Batch create
        nodes = [EnhancedNodeInfo(f"batch{i}.txt", False, "/") for i in range(3)]
        results = await provider.batch_create(nodes)
        assert all(results)

        # Batch write
        operations = [(f"/batch{i}.txt", f"content{i}".encode()) for i in range(3)]
        results = await provider.batch_write(operations)
        assert all(results)

        # Batch read
        paths = [f"/batch{i}.txt" for i in range(3)]
        contents = await provider.batch_read(paths)
        assert len(contents) == 3
        assert all(c is not None for c in contents)

        # Batch delete
        results = await provider.batch_delete(paths)
        assert all(results)

    @pytest.mark.asyncio
    async def test_error_handling(self, provider):
        """Test error handling for various operations"""
        # Read non-existent file
        content = await provider.read_file("/nonexistent.txt")
        assert content is None

        # Delete non-existent file
        result = await provider.delete_node("/nonexistent.txt")
        assert result is False

        # Get info for non-existent file
        info = await provider.get_node_info("/nonexistent.txt")
        assert info is None

        # List non-existent directory
        contents = await provider.list_directory("/nonexistent_dir")
        assert contents == []

    @pytest.mark.asyncio
    async def test_nested_directories(self, provider):
        """Test operations with nested directories"""
        # Create nested structure
        await provider.create_node(EnhancedNodeInfo("level1", True, "/"))
        await provider.create_node(EnhancedNodeInfo("level2", True, "/level1"))
        await provider.create_node(
            EnhancedNodeInfo("file.txt", False, "/level1/level2")
        )

        # Write to nested file
        result = await provider.write_file("/level1/level2/file.txt", b"nested content")
        assert result is True

        # Read nested file
        content = await provider.read_file("/level1/level2/file.txt")
        assert content == b"nested content"

        # List nested directory
        contents = await provider.list_directory("/level1/level2")
        assert "file.txt" in contents

    @pytest.mark.asyncio
    async def test_initialization_failure(self):
        """Test handling initialization failure"""
        with patch("os.makedirs", side_effect=OSError("Permission denied")):
            provider = PyodideStorageProvider("/invalid/path")
            result = await provider.initialize()
            assert result is False

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_dir):
        """Test using provider as async context manager"""
        async with PyodideStorageProvider(base_path=temp_dir) as provider:
            assert provider is not None
            # Provider should be initialized
            assert os.path.exists(temp_dir)

            # Perform operations
            node = EnhancedNodeInfo("test.txt", False, "/")
            result = await provider.create_node(node)
            assert result is True

    def test_initialization_sync(self):
        """Test that provider requires async initialization"""
        provider = PyodideStorageProvider()
        # Provider should not be initialized yet
        assert hasattr(provider, "base_path")
        assert provider.base_path == "/home/pyodide"

    @pytest.mark.asyncio
    async def test_create_node_error(self, provider):
        """Test error handling when creating node fails"""
        # Mock os.makedirs to raise an exception
        with patch("os.makedirs", side_effect=PermissionError("Permission denied")):
            node_info = EnhancedNodeInfo(
                name="error_file.txt", is_dir=False, parent_path="/invalid"
            )
            result = await provider.create_node(node_info)
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_non_empty_directory(self, provider):
        """Test deleting a non-empty directory returns False"""
        # Create directory with content
        await provider.create_node(EnhancedNodeInfo("dir_with_files", True, "/"))
        await provider.create_node(
            EnhancedNodeInfo("file.txt", False, "/dir_with_files")
        )

        # Try to delete non-empty directory
        result = await provider.delete_node("/dir_with_files")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_node_info_error(self, provider):
        """Test error handling when getting node info fails"""
        # Mock os.stat to raise an exception
        with patch("os.stat", side_effect=OSError("Stat failed")):
            node_info = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node_info)

            info = await provider.get_node_info("/test.txt")
            assert info is None

    @pytest.mark.asyncio
    async def test_list_directory_error(self, provider):
        """Test error handling when listing directory fails"""
        # Mock os.listdir to raise an exception
        with patch("os.listdir", side_effect=PermissionError("Permission denied")):
            contents = await provider.list_directory("/")
            assert contents == []

    @pytest.mark.asyncio
    async def test_write_file_error(self, provider):
        """Test error handling when writing file fails"""
        # Mock open to raise an exception
        with patch("builtins.open", side_effect=OSError("Write failed")):
            result = await provider.write_file("/error.txt", b"content")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_storage_stats_error(self, provider):
        """Test error handling when getting storage stats fails"""
        # Mock os.walk to raise an exception
        with patch("os.walk", side_effect=OSError("Walk failed")):
            stats = await provider.get_storage_stats()
            # Should return default empty stats
            assert stats["total_size_bytes"] == 0
            assert stats["file_count"] == 0
            assert stats["directory_count"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_with_file_removal_error(self, provider):
        """Test cleanup handling individual file deletion errors"""
        # Create temp file
        await provider.create_node(EnhancedNodeInfo("temp.txt", False, "/tmp"))
        await provider.write_file("/tmp/temp.txt", b"content")

        # Mock os.remove to raise an exception for some files
        original_remove = os.remove
        remove_count = [0]

        def mock_remove(path):
            remove_count[0] += 1
            if remove_count[0] == 1:
                raise OSError("Remove failed")
            else:
                original_remove(path)

        with patch("os.remove", side_effect=mock_remove):
            # Create another temp file
            await provider.create_node(EnhancedNodeInfo("temp2.txt", False, "/tmp"))
            await provider.write_file("/tmp/temp2.txt", b"content2")

            result = await provider.cleanup()
            # Should still return result even if some removals fail
            assert "files_removed" in result
            assert "bytes_freed" in result

    @pytest.mark.asyncio
    async def test_cleanup_error(self, provider):
        """Test error handling when cleanup fails completely"""
        # Mock os.walk to raise an exception
        with patch("os.walk", side_effect=OSError("Walk failed")):
            result = await provider.cleanup()
            # Should return default empty result
            assert result["bytes_freed"] == 0
            assert result["files_removed"] == 0

    @pytest.mark.asyncio
    async def test_get_metadata_nonexistent(self, provider):
        """Test getting metadata for non-existent path"""
        metadata = await provider.get_metadata("/nonexistent.txt")
        assert metadata == {}

    @pytest.mark.asyncio
    async def test_set_metadata_nonexistent(self, provider):
        """Test setting metadata for non-existent path"""
        result = await provider.set_metadata("/nonexistent.txt", {"key": "value"})
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
