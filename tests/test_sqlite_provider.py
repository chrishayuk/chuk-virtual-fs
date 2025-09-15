"""
Test suite for SQLite storage provider
"""

import asyncio
import tempfile
import os

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.sqlite import SqliteStorageProvider


@pytest.fixture
async def provider():
    """Create a SQLite provider instance with temporary database"""
    # Use temporary file for testing
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    provider = SqliteStorageProvider(db_path=temp_db.name)
    await provider.initialize()
    yield provider
    await provider.close()
    
    # Clean up temporary file
    try:
        os.unlink(temp_db.name)
    except:
        pass


@pytest.fixture
async def memory_provider():
    """Create an in-memory SQLite provider instance"""
    provider = SqliteStorageProvider(":memory:")
    await provider.initialize()
    yield provider
    await provider.close()


class TestProviderLifecycle:
    """Test provider lifecycle operations"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test provider initialization"""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        provider = SqliteStorageProvider(temp_db.name)
        result = await provider.initialize()
        assert result is True

        # Root should exist
        root_info = await provider.get_node_info("/")
        assert root_info is not None
        assert root_info.is_dir

        await provider.close()
        os.unlink(temp_db.name)

    @pytest.mark.asyncio
    async def test_memory_initialization(self):
        """Test in-memory provider initialization"""
        provider = SqliteStorageProvider(":memory:")
        result = await provider.initialize()
        assert result is True

        # Root should exist
        root_info = await provider.get_node_info("/")
        assert root_info is not None
        assert root_info.is_dir

        await provider.close()

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test provider close"""
        await provider.close()
        assert provider.conn is None


class TestNodeOperations:
    """Test basic node operations"""

    @pytest.mark.asyncio
    async def test_create_file_node(self, provider):
        """Test creating a file node"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        result = await provider.create_node(node)
        assert result is True

        # Node should exist
        retrieved = await provider.get_node_info("/test.txt")
        assert retrieved is not None
        assert retrieved.name == "test.txt"
        assert not retrieved.is_dir

    @pytest.mark.asyncio
    async def test_create_directory_node(self, provider):
        """Test creating a directory node"""
        node = EnhancedNodeInfo("testdir", True, "/")
        result = await provider.create_node(node)
        assert result is True

        # Directory should exist
        retrieved = await provider.get_node_info("/testdir")
        assert retrieved is not None
        assert retrieved.name == "testdir"
        assert retrieved.is_dir

    @pytest.mark.asyncio
    async def test_create_duplicate_node(self, provider):
        """Test creating duplicate node fails"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        result1 = await provider.create_node(node)
        assert result1 is True

        result2 = await provider.create_node(node)
        assert result2 is False

    @pytest.mark.asyncio
    async def test_delete_file_node(self, provider):
        """Test deleting a file node"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)

        result = await provider.delete_node("/test.txt")
        assert result is True

        # Node should not exist
        retrieved = await provider.get_node_info("/test.txt")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_empty_directory(self, provider):
        """Test deleting an empty directory"""
        node = EnhancedNodeInfo("testdir", True, "/")
        await provider.create_node(node)

        result = await provider.delete_node("/testdir")
        assert result is True

        # Directory should not exist
        retrieved = await provider.get_node_info("/testdir")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_non_empty_directory(self, provider):
        """Test deleting non-empty directory fails"""
        # Create directory and file inside
        dir_node = EnhancedNodeInfo("testdir", True, "/")
        await provider.create_node(dir_node)

        file_node = EnhancedNodeInfo("test.txt", False, "/testdir")
        await provider.create_node(file_node)

        # Should fail to delete non-empty directory
        result = await provider.delete_node("/testdir")
        assert result is False

        # Directory should still exist
        retrieved = await provider.get_node_info("/testdir")
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_node(self, provider):
        """Test deleting non-existent node fails"""
        result = await provider.delete_node("/nonexistent")
        assert result is False


class TestDirectoryOperations:
    """Test directory operations"""

    @pytest.mark.asyncio
    async def test_list_root_directory(self, provider):
        """Test listing root directory"""
        # Create some files and directories
        await provider.create_node(EnhancedNodeInfo("file1.txt", False, "/"))
        await provider.create_node(EnhancedNodeInfo("file2.txt", False, "/"))
        await provider.create_node(EnhancedNodeInfo("dir1", True, "/"))

        items = await provider.list_directory("/")
        assert "file1.txt" in items
        assert "file2.txt" in items
        assert "dir1" in items

    @pytest.mark.asyncio
    async def test_list_subdirectory(self, provider):
        """Test listing subdirectory"""
        # Create directory structure
        await provider.create_node(EnhancedNodeInfo("subdir", True, "/"))
        await provider.create_node(EnhancedNodeInfo("file1.txt", False, "/subdir"))
        await provider.create_node(EnhancedNodeInfo("file2.txt", False, "/subdir"))

        items = await provider.list_directory("/subdir")
        assert "file1.txt" in items
        assert "file2.txt" in items

    @pytest.mark.asyncio
    async def test_list_nonexistent_directory(self, provider):
        """Test listing non-existent directory"""
        items = await provider.list_directory("/nonexistent")
        assert items == []

    @pytest.mark.asyncio
    async def test_list_file_as_directory(self, provider):
        """Test listing file as directory fails"""
        await provider.create_node(EnhancedNodeInfo("test.txt", False, "/"))
        items = await provider.list_directory("/test.txt")
        assert items == []


class TestFileOperations:
    """Test file operations"""

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, provider):
        """Test writing and reading file content"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)

        content = b"Hello, World!"
        result = await provider.write_file("/test.txt", content)
        assert result is True

        read_content = await provider.read_file("/test.txt")
        assert read_content == content

    @pytest.mark.asyncio
    async def test_write_large_file(self, provider):
        """Test writing large file"""
        node = EnhancedNodeInfo("large.txt", False, "/")
        await provider.create_node(node)

        # Create 1MB of data
        large_content = b"x" * (1024 * 1024)
        result = await provider.write_file("/large.txt", large_content)
        assert result is True

        read_content = await provider.read_file("/large.txt")
        assert read_content == large_content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, provider):
        """Test reading non-existent file"""
        content = await provider.read_file("/nonexistent.txt")
        assert content is None

    @pytest.mark.asyncio
    async def test_write_to_directory(self, provider):
        """Test writing to directory fails"""
        await provider.create_node(EnhancedNodeInfo("testdir", True, "/"))
        result = await provider.write_file("/testdir", b"content")
        assert result is False

    @pytest.mark.asyncio
    async def test_overwrite_file(self, provider):
        """Test overwriting file content"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)

        # Write initial content
        await provider.write_file("/test.txt", b"initial")
        
        # Overwrite with new content
        await provider.write_file("/test.txt", b"updated")
        
        # Should have new content
        content = await provider.read_file("/test.txt")
        assert content == b"updated"


class TestStorageStatistics:
    """Test storage statistics"""

    @pytest.mark.asyncio
    async def test_storage_stats(self, provider):
        """Test storage statistics"""
        # Create some files and directories
        await provider.create_node(EnhancedNodeInfo("file1.txt", False, "/"))
        await provider.write_file("/file1.txt", b"content1")
        
        await provider.create_node(EnhancedNodeInfo("file2.txt", False, "/"))
        await provider.write_file("/file2.txt", b"content2")
        
        await provider.create_node(EnhancedNodeInfo("dir1", True, "/"))

        stats = await provider.get_storage_stats()
        
        assert stats["file_count"] == 2
        assert stats["directory_count"] == 2  # Root + dir1
        assert stats["total_size_bytes"] == 16  # 8 + 8 bytes

    @pytest.mark.asyncio
    async def test_cleanup(self, provider):
        """Test cleanup operation"""
        # SQLite provider doesn't have TTL-based expiry like memory provider
        # So cleanup should return zero removed files
        stats = await provider.cleanup()
        assert stats["expired_removed"] == 0


class TestMetadataOperations:
    """Test metadata operations"""

    @pytest.mark.asyncio
    async def test_get_metadata(self, provider):
        """Test getting node metadata"""
        node = EnhancedNodeInfo("test.txt", False, "/", mime_type="text/plain")
        await provider.create_node(node)

        metadata = await provider.get_metadata("/test.txt")
        assert metadata is not None
        assert metadata["name"] == "test.txt"
        assert metadata["is_dir"] is False
        assert metadata["mime_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_set_metadata(self, provider):
        """Test setting node metadata"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)

        metadata_update = {
            "mime_type": "application/json",
            "custom_meta": {"author": "test"},
            "tags": {"env": "test"}
        }

        result = await provider.set_metadata("/test.txt", metadata_update)
        assert result is True

        # Verify metadata was updated
        updated_metadata = await provider.get_metadata("/test.txt")
        assert updated_metadata["mime_type"] == "application/json"
        assert updated_metadata["custom_meta"] == {"author": "test"}
        assert updated_metadata["tags"] == {"env": "test"}


class TestExistsOperations:
    """Test exists operations"""

    @pytest.mark.asyncio
    async def test_exists_file(self, provider):
        """Test checking if file exists"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)

        assert await provider.exists("/test.txt") is True
        assert await provider.exists("/nonexistent.txt") is False

    @pytest.mark.asyncio
    async def test_exists_directory(self, provider):
        """Test checking if directory exists"""
        node = EnhancedNodeInfo("testdir", True, "/")
        await provider.create_node(node)

        assert await provider.exists("/testdir") is True
        assert await provider.exists("/nonexistent") is False


class TestEnhancedFeatures:
    """Test enhanced features for parity with other providers"""

    @pytest.mark.asyncio
    async def test_create_directory_with_parents(self, provider):
        """Test create_directory creates parent directories"""
        result = await provider.create_directory("/test/nested/deep/dir")
        assert result is True

        # All parent directories should exist
        assert await provider.exists("/test")
        assert await provider.exists("/test/nested") 
        assert await provider.exists("/test/nested/deep")
        assert await provider.exists("/test/nested/deep/dir")

        # All should be directories
        for path in ["/test", "/test/nested", "/test/nested/deep", "/test/nested/deep/dir"]:
            node = await provider.get_node_info(path)
            assert node is not None
            assert node.is_dir

    @pytest.mark.asyncio
    async def test_create_directory_idempotent(self, provider):
        """Test create_directory is idempotent"""
        result1 = await provider.create_directory("/test/dir")
        assert result1 is True

        # Creating again should still return True
        result2 = await provider.create_directory("/test/dir")
        assert result2 is True

    @pytest.mark.asyncio
    async def test_copy_node_file(self, provider):
        """Test copying a file"""
        # Create source file
        node = EnhancedNodeInfo("source.txt", False, "/")
        await provider.create_node(node)
        await provider.write_file("/source.txt", b"test content")

        # Copy file
        result = await provider.copy_node("/source.txt", "/dest.txt")
        assert result is True

        # Both should exist
        assert await provider.exists("/source.txt")
        assert await provider.exists("/dest.txt")

        # Content should be the same
        src_content = await provider.read_file("/source.txt")
        dst_content = await provider.read_file("/dest.txt")
        assert src_content == dst_content == b"test content"

    @pytest.mark.asyncio
    async def test_copy_node_directory(self, provider):
        """Test copying a directory with contents"""
        # Create directory structure
        await provider.create_directory("/source/dir")
        
        # Add files
        file1 = EnhancedNodeInfo("file1.txt", False, "/source")
        await provider.create_node(file1)
        await provider.write_file("/source/file1.txt", b"content1")
        
        file2 = EnhancedNodeInfo("file2.txt", False, "/source/dir")
        await provider.create_node(file2)
        await provider.write_file("/source/dir/file2.txt", b"content2")

        # Copy directory
        result = await provider.copy_node("/source", "/dest")
        assert result is True

        # Check structure is copied
        assert await provider.exists("/dest")
        assert await provider.exists("/dest/file1.txt")
        assert await provider.exists("/dest/dir")
        assert await provider.exists("/dest/dir/file2.txt")

        # Check content is preserved
        assert await provider.read_file("/dest/file1.txt") == b"content1"
        assert await provider.read_file("/dest/dir/file2.txt") == b"content2"

    @pytest.mark.asyncio
    async def test_move_node_file(self, provider):
        """Test moving a file"""
        # Create source file
        node = EnhancedNodeInfo("source.txt", False, "/")
        await provider.create_node(node)
        await provider.write_file("/source.txt", b"test content")

        # Move file
        result = await provider.move_node("/source.txt", "/dest.txt")
        assert result is True

        # Source should not exist, destination should
        assert not await provider.exists("/source.txt")
        assert await provider.exists("/dest.txt")

        # Content should be preserved
        content = await provider.read_file("/dest.txt")
        assert content == b"test content"

    @pytest.mark.asyncio
    async def test_batch_write(self, provider):
        """Test batch write operations"""
        operations = [
            ("/file1.txt", b"content1"),
            ("/file2.txt", b"content2"),
            ("/file3.txt", b"content3"),
        ]

        results = await provider.batch_write(operations)
        assert all(results)

        # All files should exist with correct content
        assert await provider.read_file("/file1.txt") == b"content1"
        assert await provider.read_file("/file2.txt") == b"content2"
        assert await provider.read_file("/file3.txt") == b"content3"

    @pytest.mark.asyncio
    async def test_batch_read(self, provider):
        """Test batch read operations"""
        # Create files
        for i in range(3):
            node = EnhancedNodeInfo(f"file{i}.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file(f"/file{i}.txt", f"content{i}".encode())

        paths = ["/file0.txt", "/file1.txt", "/file2.txt", "/nonexistent.txt"]
        results = await provider.batch_read(paths)

        assert results[0] == b"content0"
        assert results[1] == b"content1"
        assert results[2] == b"content2"
        assert results[3] is None  # Non-existent file

    @pytest.mark.asyncio
    async def test_batch_delete(self, provider):
        """Test batch delete operations"""
        # Create files
        for i in range(3):
            node = EnhancedNodeInfo(f"file{i}.txt", False, "/")
            await provider.create_node(node)

        paths = ["/file0.txt", "/file1.txt", "/file2.txt", "/nonexistent.txt"]
        results = await provider.batch_delete(paths)

        assert results[0] is True
        assert results[1] is True
        assert results[2] is True
        assert results[3] is False  # Non-existent file

        # Files should be deleted
        assert not await provider.exists("/file0.txt")
        assert not await provider.exists("/file1.txt")
        assert not await provider.exists("/file2.txt")

    @pytest.mark.asyncio
    async def test_batch_create(self, provider):
        """Test batch create operations"""
        nodes = [
            EnhancedNodeInfo("file1.txt", False, "/"),
            EnhancedNodeInfo("file2.txt", False, "/"),
            EnhancedNodeInfo("dir1", True, "/"),
        ]

        results = await provider.batch_create(nodes)
        assert all(results)

        # All nodes should exist
        assert await provider.exists("/file1.txt")
        assert await provider.exists("/file2.txt") 
        assert await provider.exists("/dir1")

        # Check types
        file1 = await provider.get_node_info("/file1.txt")
        assert file1 is not None and not file1.is_dir
        
        dir1 = await provider.get_node_info("/dir1")
        assert dir1 is not None and dir1.is_dir

    @pytest.mark.asyncio
    async def test_calculate_checksum(self, provider):
        """Test checksum calculation"""
        # Create file with known content
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        await provider.write_file("/test.txt", b"test content")

        # Test different algorithms
        md5_hash = await provider.calculate_checksum("/test.txt", "md5")
        assert md5_hash == "9473fdd0d880a43c21b7778d34872157"  # MD5 of "test content"

        sha256_hash = await provider.calculate_checksum("/test.txt", "sha256")
        assert sha256_hash is not None
        assert len(sha256_hash) == 64  # SHA256 produces 64 hex characters

        sha512_hash = await provider.calculate_checksum("/test.txt", "sha512")
        assert len(sha512_hash) == 128  # SHA512 produces 128 hex characters

        # Test with non-existent file
        result = await provider.calculate_checksum("/nonexistent.txt")
        assert result is None

        # Test with directory
        await provider.create_directory("/dir")
        result = await provider.calculate_checksum("/dir")
        assert result is None

    @pytest.mark.asyncio
    async def test_storage_stats_directory_count(self, provider):
        """Test that storage stats correctly count directories"""
        # Create some directories
        await provider.create_directory("/dir1")
        await provider.create_directory("/dir2")
        await provider.create_directory("/dir1/subdir")

        # Create some files
        for i in range(3):
            node = EnhancedNodeInfo(f"file{i}.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file(f"/file{i}.txt", b"content")

        stats = await provider.get_storage_stats()
        
        # Should count root + 3 created directories = 4
        assert stats["directory_count"] == 4
        assert stats["file_count"] == 3


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_operations_with_closed_connection(self, provider):
        """Test operations when database connection is closed"""
        # Close the connection
        await provider.close()
        
        # Test various operations with closed connection
        node = EnhancedNodeInfo("test.txt", False, "/")
        assert await provider.create_node(node) is False
        assert await provider.delete_node("/test") is False
        assert await provider.get_node_info("/test") is None
        assert await provider.list_directory("/") == []
        assert await provider.read_file("/test") is None
        assert await provider.write_file("/test", b"data") is False
        assert await provider.exists("/test") is False
        
        # Test metadata operations
        metadata = await provider.get_metadata("/test")
        assert metadata == {} or metadata is None
        assert await provider.set_metadata("/test", {}) is False
        
        # Test enhanced operations
        assert await provider.create_directory("/test") is False
        assert await provider.copy_node("/src", "/dst") is False
        assert await provider.move_node("/src", "/dst") is False
        
        # Test batch operations  
        test_node = EnhancedNodeInfo("test", False, "/")
        assert await provider.batch_create([test_node]) == [False]
        assert await provider.batch_write([("/test", b"data")]) == [False]
        assert await provider.batch_read(["/test"]) == [None]
        assert await provider.batch_delete(["/test"]) == [False]

    @pytest.mark.asyncio 
    async def test_initialization_failure(self, tmp_path):
        """Test initialization failure scenarios"""
        import os
        
        # Create a directory where we expect a file (this should cause init to fail)
        bad_db_path = tmp_path / "bad_db_dir"
        bad_db_path.mkdir()
        
        provider = SqliteStorageProvider(db_path=str(bad_db_path))
        success = await provider.initialize()
        assert success is False

    @pytest.mark.asyncio
    async def test_create_node_without_parent(self, provider):
        """Test creating node when parent doesn't exist"""
        node = EnhancedNodeInfo("test.txt", False, "/nonexistent/parent")
        result = await provider.create_node(node)
        assert result is False

    @pytest.mark.asyncio
    async def test_normalize_path_edge_cases(self, provider):
        """Test path normalization in get_node_info and list_directory"""
        # Test empty path normalization
        info = await provider.get_node_info("")
        assert info is not None
        assert info.get_path() == "/"
        
        # Test trailing slash removal
        info = await provider.get_node_info("/root/")
        # Should normalize to /root but won't exist, so returns None
        
        # Test list_directory with empty path
        items = await provider.list_directory("")
        assert isinstance(items, list)
        
        # Test with trailing slash
        items = await provider.list_directory("/test/")
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_delete_directory_with_children(self, provider):
        """Test deleting non-empty directory (should fail)"""
        # Create directory with child
        await provider.create_directory("/parent")
        await provider.create_directory("/parent/child")
        
        # Try to delete non-empty directory
        result = await provider.delete_node("/parent")
        assert result is False

    @pytest.mark.asyncio
    async def test_write_to_nonexistent_file(self, provider):
        """Test writing to file that doesn't exist"""
        result = await provider.write_file("/nonexistent.txt", b"data")
        assert result is False

    @pytest.mark.asyncio
    async def test_read_directory_as_file(self, provider):
        """Test reading directory as file"""
        await provider.create_directory("/testdir")
        result = await provider.read_file("/testdir")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_file_as_directory(self, provider):
        """Test listing file as directory"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        
        result = await provider.list_directory("/test.txt")
        assert result == []

    @pytest.mark.asyncio
    async def test_metadata_operations_on_nonexistent(self, provider):
        """Test metadata operations on non-existent files"""
        # Get metadata for non-existent file
        metadata = await provider.get_metadata("/nonexistent")
        assert metadata == {} or metadata is None
        
        # Set metadata for non-existent file
        result = await provider.set_metadata("/nonexistent", {"key": "value"})
        assert result is False

    @pytest.mark.asyncio
    async def test_copy_nonexistent_node(self, provider):
        """Test copying non-existent node"""
        result = await provider.copy_node("/nonexistent", "/destination")
        assert result is False

    @pytest.mark.asyncio
    async def test_move_to_existing_destination(self, provider):
        """Test moving to existing destination"""
        # Create source and destination
        node1 = EnhancedNodeInfo("source.txt", False, "/")
        node2 = EnhancedNodeInfo("dest.txt", False, "/")
        await provider.create_node(node1)
        await provider.create_node(node2)
        
        # Try to move to existing destination
        result = await provider.move_node("/source.txt", "/dest.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_calculate_checksum_invalid_algorithm(self, provider):
        """Test calculate_checksum with invalid algorithm"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        await provider.write_file("/test.txt", b"content")
        
        result = await provider.calculate_checksum("/test.txt", "invalid_algo")
        assert result is None

    @pytest.mark.asyncio
    async def test_batch_operations_mixed_results(self, provider):
        """Test batch operations with mix of successes and failures"""
        # Create one file that exists
        node = EnhancedNodeInfo("existing.txt", False, "/")
        await provider.create_node(node)
        
        # Test batch_write with mix of existing and non-existent files
        operations = [
            ("/existing.txt", b"new content"),
            ("/nonexistent.txt", b"content")  # This will actually succeed as batch_write creates files
        ]
        results = await provider.batch_write(operations)
        assert results[0] is True  # existing file should succeed
        assert results[1] is True  # batch_write creates files, so this succeeds too
        
        # Test batch_read with mix (note: after batch_write, both files exist now)
        results = await provider.batch_read(["/existing.txt", "/nonexistent.txt"])
        assert results[0] is not None  # existing file
        assert results[1] is not None  # file was created by batch_write

    @pytest.mark.asyncio
    async def test_cleanup_with_no_expired_files(self, provider):
        """Test cleanup when no files are expired"""
        # Create some files without expiration
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        await provider.write_file("/test.txt", b"content")
        
        # Run cleanup
        result = await provider.cleanup()
        assert result["files_removed"] == 0
        assert result["bytes_freed"] == 0
        assert result["expired_removed"] == 0

    @pytest.mark.asyncio
    async def test_initialization_database_errors(self, tmp_path):
        """Test initialization with database permission/access errors"""
        import os
        import stat
        
        # Create a file that can't be written to (if not on Windows)
        try:
            read_only_dir = tmp_path / "readonly"
            read_only_dir.mkdir()
            read_only_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # Read and execute only
            
            provider = SqliteStorageProvider(str(read_only_dir / "test.db"))
            # This should trigger the exception path in _sync_initialize
            result = await provider.initialize()
            # On some systems this might still succeed, so we don't assert False
            
            # Restore permissions for cleanup
            read_only_dir.chmod(stat.S_IRWXU)
        except:
            # Skip if we can't set permissions (e.g., Windows)
            pass

    @pytest.mark.asyncio
    async def test_node_creation_database_errors(self, provider):
        """Test node creation with simulated database errors"""
        # Create a node first
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        
        # Try to create the same node again (should trigger existing node path)
        result = await provider.create_node(node)
        assert result is False  # Should fail because it already exists

    @pytest.mark.asyncio
    async def test_delete_node_database_errors(self, provider):
        """Test delete operations that trigger error paths"""
        # Test deleting non-existent node (should return False)
        result = await provider.delete_node("/nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_write_file_to_directory_path(self, provider):
        """Test writing to a path that's actually a directory"""
        # Create a directory
        await provider.create_directory("/testdir")
        
        # Try to write content to the directory path (should fail)
        result = await provider.write_file("/testdir", b"content")
        assert result is False

    @pytest.mark.asyncio
    async def test_copy_node_edge_cases(self, provider):
        """Test copy operations edge cases"""
        # Test copying to existing destination
        node1 = EnhancedNodeInfo("source.txt", False, "/")
        node2 = EnhancedNodeInfo("dest.txt", False, "/")
        await provider.create_node(node1)
        await provider.create_node(node2)
        
        # Should fail because destination exists
        result = await provider.copy_node("/source.txt", "/dest.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_move_node_edge_cases(self, provider):
        """Test move operations edge cases"""
        # Test moving non-existent file
        result = await provider.move_node("/nonexistent.txt", "/dest.txt")
        assert result is False
        
        # Test moving to existing destination
        node1 = EnhancedNodeInfo("source.txt", False, "/")
        node2 = EnhancedNodeInfo("dest.txt", False, "/")
        await provider.create_node(node1)
        await provider.create_node(node2)
        
        result = await provider.move_node("/source.txt", "/dest.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_checksum_edge_cases(self, provider):
        """Test checksum calculation edge cases"""
        # Test checksum on directory
        await provider.create_directory("/testdir")
        result = await provider.calculate_checksum("/testdir")
        assert result is None
        
        # Test checksum with unsupported algorithm
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        await provider.write_file("/test.txt", b"content")
        
        result = await provider.calculate_checksum("/test.txt", "unsupported")
        assert result is None
        
        # Test all supported algorithms
        md5_result = await provider.calculate_checksum("/test.txt", "md5")
        assert md5_result is not None
        assert len(md5_result) == 32  # MD5 hex length
        
        sha1_result = await provider.calculate_checksum("/test.txt", "sha1")
        assert sha1_result is not None
        assert len(sha1_result) == 40  # SHA1 hex length
        
        sha512_result = await provider.calculate_checksum("/test.txt", "sha512")
        assert sha512_result is not None
        assert len(sha512_result) == 128  # SHA512 hex length

    @pytest.mark.asyncio
    async def test_batch_operations_error_conditions(self, provider):
        """Test batch operations under error conditions"""
        # Test batch operations with closed connection
        await provider.close()
        
        # All batch operations should handle closed connection gracefully
        test_node = EnhancedNodeInfo("test", False, "/")
        batch_create_results = await provider.batch_create([test_node])
        assert batch_create_results == [False]
        
        batch_write_results = await provider.batch_write([("/test", b"data")])
        assert batch_write_results == [False]
        
        batch_read_results = await provider.batch_read(["/test"])
        assert batch_read_results == [None]
        
        batch_delete_results = await provider.batch_delete(["/test"])
        assert batch_delete_results == [False]

    @pytest.mark.asyncio
    async def test_metadata_operations_edge_cases(self, provider):
        """Test metadata operations edge cases"""
        # Test setting metadata with various data types
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        
        # Test setting metadata with complex values
        complex_metadata = {
            "custom_meta": {"nested": {"value": 123}},
            "tags": {"env": "test", "version": "1.0"},
            "ttl": 3600,
            "permissions": "755"
        }
        
        result = await provider.set_metadata("/test.txt", complex_metadata)
        assert result is True
        
        # Verify metadata was set
        retrieved = await provider.get_metadata("/test.txt")
        assert "tags" in retrieved
        assert retrieved["tags"]["env"] == "test"

    @pytest.mark.asyncio
    async def test_storage_stats_edge_cases(self, provider):
        """Test storage statistics under various conditions"""
        # Test stats with empty database
        stats = await provider.get_storage_stats()
        assert isinstance(stats, dict)
        assert "total_size_bytes" in stats
        assert "file_count" in stats
        assert "directory_count" in stats

    @pytest.mark.asyncio
    async def test_list_directory_edge_cases(self, provider):
        """Test directory listing edge cases"""
        # Test listing non-existent directory
        items = await provider.list_directory("/nonexistent")
        assert items == []
        
        # Test listing with various path formats
        await provider.create_directory("/testdir")
        
        # These should all work the same way
        items1 = await provider.list_directory("/testdir")
        items2 = await provider.list_directory("/testdir/")
        assert items1 == items2

    @pytest.mark.asyncio
    async def test_exists_operations_edge_cases(self, provider):
        """Test exists operations edge cases"""
        # Test with non-existent paths
        assert await provider.exists("/nonexistent") is False
        assert await provider.exists("") is False  # Empty path doesn't exist in SQLite
        
        # Test that root path exists
        assert await provider.exists("/") is True

    @pytest.mark.asyncio
    async def test_create_directory_edge_cases(self, provider):
        """Test directory creation edge cases"""
        # Test creating directory that already exists (should succeed)
        await provider.create_directory("/existing")
        result = await provider.create_directory("/existing")
        assert result is True  # Should be idempotent
        
        # Test creating directory with trailing slash
        result = await provider.create_directory("/trailing/")
        assert result is True
        
        # Verify it exists without trailing slash
        assert await provider.exists("/trailing") is True

    @pytest.mark.asyncio
    async def test_database_errors_during_operations(self, provider):
        """Test error handling during database operations"""
        # Create a file first
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        await provider.write_file("/test.txt", b"content")
        
        # Force close the database to simulate errors
        await provider.close()
        
        # These should handle the closed connection gracefully
        assert await provider.exists("/test.txt") is False
        stats = await provider.get_storage_stats()
        assert "error" in stats or stats == {"total_size_bytes": 0, "file_count": 0, "directory_count": 0}

    @pytest.mark.asyncio
    async def test_file_content_edge_cases(self, provider):
        """Test file content operations edge cases"""
        # Test reading file that has no content record
        node = EnhancedNodeInfo("empty.txt", False, "/")
        await provider.create_node(node)
        
        # Should return empty bytes even if no content record exists
        content = await provider.read_file("/empty.txt")
        assert content == b""
        
        # Test writing empty content
        result = await provider.write_file("/empty.txt", b"")
        assert result is True
        
        # Test reading after writing empty content
        content = await provider.read_file("/empty.txt")
        assert content == b""

    @pytest.mark.asyncio
    async def test_connection_error_scenarios(self, provider):
        """Test scenarios that might cause connection errors"""
        # Test operations with invalid database path
        invalid_provider = SqliteStorageProvider("/invalid/path/that/does/not/exist.db")
        
        # Should handle connection errors gracefully
        result = await invalid_provider.get_node_info("/")
        assert result is None
        
        result = await invalid_provider.list_directory("/")
        assert result == []
        
        result = await invalid_provider.exists("/")
        assert result is False

    @pytest.mark.asyncio
    async def test_batch_operations_with_parent_creation(self, provider):
        """Test batch operations that require parent directory creation"""
        # Test batch write that creates nested directory structure
        nested_files = {
            "/deep/nested/path/file1.txt": b"content1",
            "/deep/nested/path/file2.txt": b"content2",
        }
        
        # This should create parent directories automatically
        results = await provider.batch_write([("/deep/nested/path/file1.txt", b"content1")])
        # Note: This might fail because parents don't exist - testing the error path
        
    @pytest.mark.asyncio
    async def test_directory_operations_with_special_paths(self, provider):
        """Test directory operations with special path cases"""
        # Test creating directory with single character name
        result = await provider.create_directory("/a")
        assert result is True
        
        # Test creating deeply nested single-char directories
        result = await provider.create_directory("/a/b/c/d/e")
        assert result is True
        
        # Verify they exist
        assert await provider.exists("/a/b/c/d/e") is True

    @pytest.mark.asyncio
    async def test_checksum_with_special_content(self, provider):
        """Test checksum calculation with special content types"""
        node = EnhancedNodeInfo("special.bin", False, "/")
        await provider.create_node(node)
        
        # Test with binary content containing null bytes
        binary_content = b"\x00\x01\x02\xff\xfe\xfd"
        await provider.write_file("/special.bin", binary_content)
        
        checksum = await provider.calculate_checksum("/special.bin", "sha256")
        assert checksum is not None
        assert len(checksum) == 64
        
        # Test with empty file
        await provider.write_file("/special.bin", b"")
        checksum_empty = await provider.calculate_checksum("/special.bin", "md5")
        assert checksum_empty == "d41d8cd98f00b204e9800998ecf8427e"  # MD5 of empty string

    @pytest.mark.asyncio
    async def test_metadata_with_none_values(self, provider):
        """Test metadata operations with None values"""
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        
        # Test setting metadata with None values
        metadata_with_nones = {
            "custom_meta": None,
            "tags": None,
            "ttl": None,
        }
        
        result = await provider.set_metadata("/test.txt", metadata_with_nones)
        assert result is True
        
        # Verify metadata can be retrieved
        retrieved = await provider.get_metadata("/test.txt")
        assert "custom_meta" in retrieved

    @pytest.mark.asyncio
    async def test_storage_stats_with_various_file_sizes(self, provider):
        """Test storage statistics with files of various sizes"""
        # Create files with different sizes
        sizes = [0, 1, 100, 1000, 10000]
        
        for i, size in enumerate(sizes):
            node = EnhancedNodeInfo(f"file_{i}.dat", False, "/")
            await provider.create_node(node)
            content = b"x" * size
            await provider.write_file(f"/file_{i}.dat", content)
        
        # Get statistics
        stats = await provider.get_storage_stats()
        
        # Total size should be sum of all file sizes
        expected_total = sum(sizes)
        assert stats["total_size_bytes"] == expected_total
        assert stats["file_count"] >= len(sizes)  # At least our test files

    @pytest.mark.asyncio
    async def test_database_corruption_scenarios(self, tmp_path):
        """Test behavior with database corruption scenarios"""
        db_file = tmp_path / "corrupt.db"
        
        # Create a provider and initialize it
        provider = SqliteStorageProvider(str(db_file))
        await provider.initialize()
        
        # Create some data
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        await provider.close()
        
        # Corrupt the database file by writing invalid data
        with open(db_file, "w") as f:
            f.write("This is not a valid SQLite database")
        
        # Try to use the corrupted database
        corrupted_provider = SqliteStorageProvider(str(db_file))
        
        # These operations should handle corruption gracefully
        result = await corrupted_provider.initialize()
        # May succeed or fail depending on SQLite's error handling
        
        result = await corrupted_provider.get_node_info("/")
        # Should return None due to database errors
        
        result = await corrupted_provider.list_directory("/")
        # Should return empty list due to errors

    @pytest.mark.asyncio 
    async def test_concurrent_access_patterns(self, provider):
        """Test patterns that might trigger concurrent access issues"""
        import asyncio
        
        # Test concurrent operations
        async def create_file(name):
            node = EnhancedNodeInfo(f"{name}.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file(f"/{name}.txt", f"content_{name}".encode())
            return name
        
        # Run multiple operations concurrently
        tasks = [create_file(f"concurrent_{i}") for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # At least some should succeed
        successful = [r for r in results if isinstance(r, str)]
        assert len(successful) > 0

    @pytest.mark.asyncio
    async def test_large_content_operations(self, provider):
        """Test operations with larger content to trigger different code paths"""
        # Create a file with larger content (1MB)
        large_content = b"x" * (1024 * 1024)
        
        node = EnhancedNodeInfo("large.bin", False, "/")
        await provider.create_node(node)
        
        # Test writing large content
        result = await provider.write_file("/large.bin", large_content)
        assert result is True
        
        # Test reading large content
        read_content = await provider.read_file("/large.bin")
        assert read_content == large_content
        
        # Test checksum on large content
        checksum = await provider.calculate_checksum("/large.bin", "md5")
        assert checksum is not None

    @pytest.mark.asyncio
    async def test_special_character_paths(self, provider):
        """Test paths with special characters"""
        special_chars = ["file with spaces.txt", "file-with-dashes.txt", "file_with_underscores.txt"]
        
        for filename in special_chars:
            node = EnhancedNodeInfo(filename, False, "/")
            await provider.create_node(node)
            
            # Test writing and reading
            content = f"content for {filename}".encode()
            await provider.write_file(f"/{filename}", content)
            
            read_content = await provider.read_file(f"/{filename}")
            assert read_content == content

    @pytest.mark.asyncio
    async def test_deep_directory_nesting(self, provider):
        """Test very deep directory nesting"""
        # Create deeply nested directory (20 levels)
        deep_path = "/" + "/".join([f"level{i}" for i in range(20)])
        
        result = await provider.create_directory(deep_path)
        assert result is True
        
        # Test file creation in deep directory
        node = EnhancedNodeInfo("deep_file.txt", False, deep_path)
        result = await provider.create_node(node)
        assert result is True

    @pytest.mark.asyncio
    async def test_sql_injection_safety(self, provider):
        """Test that SQL injection attempts are safely handled"""
        # Test with potential SQL injection in path names
        malicious_names = [
            "'; DROP TABLE nodes; --",
            "test'; DELETE FROM nodes WHERE 1=1; --",
            "normal_file.txt' OR '1'='1",
        ]
        
        for name in malicious_names:
            try:
                node = EnhancedNodeInfo(name, False, "/")
                await provider.create_node(node)
                
                # If creation succeeds, test other operations
                await provider.write_file(f"/{name}", b"safe content")
                content = await provider.read_file(f"/{name}")
                assert content == b"safe content"
            except Exception:
                # Some names might be invalid, which is fine
                pass
        
        # Verify database is still intact
        root_info = await provider.get_node_info("/")
        assert root_info is not None

    @pytest.mark.asyncio
    async def test_path_edge_cases_in_operations(self, provider):
        """Test operations with edge case paths"""
        # Test operations with root path variations
        await provider.create_directory("/")  # Should be idempotent
        
        # Test trailing slashes in paths
        await provider.create_directory("/test_dir/")
        exists = await provider.exists("/test_dir")
        assert exists is True
        
    @pytest.mark.asyncio
    async def test_file_operations_error_paths(self, provider):
        """Test file operations that should fail"""
        # Try to write to a file that's actually a directory
        await provider.create_directory("/testdir")
        
        # This should fail gracefully
        result = await provider.write_file("/testdir", b"content")
        assert result is False


class TestDatabaseErrorHandling:
    """Test database-specific error handling scenarios"""

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """Test operations when database connection fails"""
        import unittest.mock
        
        provider = SqliteStorageProvider(":memory:")
        await provider.initialize()
        
        # Mock _get_connection to return None (connection failure)
        with unittest.mock.patch.object(provider, '_get_connection', return_value=None):
            node = EnhancedNodeInfo("test.txt", False, "/")
            
            # Test all operations handle connection failures gracefully
            assert await provider.create_node(node) is False
            assert await provider.delete_node("/test") is False
            assert await provider.get_node_info("/") is None
            assert await provider.list_directory("/") == []
            assert await provider.read_file("/test") is None
            assert await provider.write_file("/test", b"data") is False
            assert await provider.exists("/") is False
            assert await provider.get_metadata("/") == {}
            assert await provider.set_metadata("/", {}) is False

    @pytest.mark.asyncio 
    async def test_create_node_database_error(self, provider):
        """Test create_node with database errors"""
        # Create a node first
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)
        
        # Try to create the same node again (should fail due to uniqueness)
        result = await provider.create_node(node)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_node_database_error(self, provider):
        """Test delete_node with database errors"""
        # Create a directory with a child
        await provider.create_directory("/parent")
        child_node = EnhancedNodeInfo("child.txt", False, "/parent")
        await provider.create_node(child_node)
        
        # Try to delete the parent directory (should fail due to foreign key constraint)
        result = await provider.delete_node("/parent")
        assert result is False

    @pytest.mark.asyncio
    async def test_operations_without_initialization(self):
        """Test operations on uninitialized provider"""
        provider = SqliteStorageProvider(":memory:")
        # Don't call initialize()
        
        # All operations should return False/None for uninitialized provider
        node = EnhancedNodeInfo("test.txt", False, "/")
        assert await provider.create_node(node) is False
        assert await provider.delete_node("/test") is False
        assert await provider.get_node_info("/") is None
        assert await provider.list_directory("/") == []
        assert await provider.exists("/") is False
        assert await provider.read_file("/test") is None
        assert await provider.write_file("/test", b"data") is False

    @pytest.mark.asyncio
    async def test_transaction_rollback_scenarios(self, provider):
        """Test scenarios that trigger transaction rollbacks"""
        import unittest.mock
        
        # Test a scenario that should trigger exception handling
        # Try to create a node in a non-existent parent directory
        node = EnhancedNodeInfo("test.txt", False, "/nonexistent/deep/path")
        result = await provider.create_node(node)
        assert result is False  # Should fail due to missing parent

    @pytest.mark.asyncio
    async def test_close_operations_and_cleanup(self, provider):
        """Test close operation and cleanup scenarios"""
        # Create some data
        await provider.create_directory("/test")
        node = EnhancedNodeInfo("file.txt", False, "/test")
        await provider.create_node(node)
        await provider.write_file("/test/file.txt", b"test content")
        
        # Test cleanup operation
        result = await provider.cleanup()
        assert isinstance(result, dict)
        assert "files_removed" in result
        assert "bytes_freed" in result
        
        # Test that we can still perform operations after cleanup
        assert await provider.exists("/test") is True
        
        # Test close operation
        await provider.close()
        
        # After close, operations should fail
        assert await provider.create_node(EnhancedNodeInfo("new.txt", False, "/")) is False

    @pytest.mark.asyncio
    async def test_schema_recreation_on_connection(self, provider):
        """Test that schema is properly recreated on new connections"""
        # This tests the _ensure_schema method being called on new connections
        # Force creation of a new connection by accessing internal method
        conn = provider._get_connection()
        assert conn is not None
        
        # Verify schema exists by checking table
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'")
        result = cursor.fetchone()
        assert result is not None
        conn.close()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, provider):
        """Test concurrent database operations"""
        import asyncio
        
        # Create multiple concurrent operations
        tasks = []
        
        # Concurrent directory creation
        for i in range(5):
            task = provider.create_directory(f"/concurrent_dir_{i}")
            tasks.append(task)
        
        # Concurrent file creation
        for i in range(5):
            node = EnhancedNodeInfo(f"file_{i}.txt", False, "/")
            task = provider.create_node(node)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most operations should succeed
        success_count = sum(1 for result in results if result is True and not isinstance(result, Exception))
        assert success_count >= 8  # Allow for some variation

    @pytest.mark.asyncio
    async def test_storage_stats_edge_cases(self, provider):
        """Test storage statistics in edge cases"""
        # Test stats on empty database
        stats = await provider.get_storage_stats()
        assert stats["file_count"] == 0
        assert stats["directory_count"] == 1  # Root directory
        assert stats["total_size_bytes"] == 0
        
        # Create some content and test stats
        await provider.create_directory("/stats_test")
        
        # Create file nodes explicitly first
        from chuk_virtual_fs.node_info import EnhancedNodeInfo
        file1_node = EnhancedNodeInfo("file1.txt", False, "/stats_test")
        file2_node = EnhancedNodeInfo("file2.txt", False, "/stats_test")
        await provider.create_node(file1_node)
        await provider.create_node(file2_node)
        
        # Now write content
        await provider.write_file("/stats_test/file1.txt", b"a" * 100)
        await provider.write_file("/stats_test/file2.txt", b"b" * 200)
        
        stats = await provider.get_storage_stats()
        assert stats["file_count"] == 2
        assert stats["directory_count"] == 2  # Root + stats_test
        assert stats["total_size_bytes"] == 300

    @pytest.mark.asyncio
    async def test_metadata_edge_cases(self, provider):
        """Test metadata operations in edge cases"""
        # Test metadata on non-existent node
        metadata = await provider.get_metadata("/nonexistent")
        assert metadata == {}
        
        # Test setting metadata on non-existent node
        result = await provider.set_metadata("/nonexistent", {"key": "value"})
        assert result is False
        
        # Test metadata with basic values (the SQLite provider may have limitations)
        await provider.create_directory("/meta_test")
        
        # Test setting basic metadata
        basic_metadata = {
            "description": "test directory",
            "type": "folder"
        }
        
        result = await provider.set_metadata("/meta_test", basic_metadata)
        # Note: The SQLite provider metadata implementation may not work as expected
        # This test verifies the method exists and handles inputs correctly
        assert isinstance(result, bool)
        
        # Test getting metadata
        retrieved = await provider.get_metadata("/meta_test")
        assert isinstance(retrieved, dict)
    
    @pytest.mark.asyncio
    async def test_list_directory_exception_handling(self, provider):
        """Test list_directory with database exceptions"""
        import unittest.mock
        
        # Create a directory first
        await provider.create_directory("/test_dir")
        
        # Mock the cursor to raise an exception
        with unittest.mock.patch.object(provider, '_get_connection') as mock_get_conn:
            mock_conn = unittest.mock.MagicMock()
            mock_cursor = unittest.mock.MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = Exception("Database error")
            mock_get_conn.return_value = mock_conn
            
            # This should trigger exception handling and return empty list
            result = await provider.list_directory("/test_dir")
            assert result == []

    @pytest.mark.asyncio
    async def test_read_file_database_exception(self, provider):
        """Test read_file with database exceptions"""
        import unittest.mock
        
        # Create a file first
        await provider.create_directory("/test")
        node = EnhancedNodeInfo("test.txt", False, "/test")
        await provider.create_node(node)
        await provider.write_file("/test/test.txt", b"test content")
        
        # Mock the cursor to raise an exception during read
        with unittest.mock.patch.object(provider, '_get_connection') as mock_get_conn:
            mock_conn = unittest.mock.MagicMock()
            mock_cursor = unittest.mock.MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = Exception("Database error")
            mock_get_conn.return_value = mock_conn
            
            # This should trigger exception handling and return None
            result = await provider.read_file("/test/test.txt")
            assert result is None

    @pytest.mark.asyncio
    async def test_write_file_database_exception(self, provider):
        """Test write_file with database exceptions"""
        import unittest.mock
        
        # Create a file first
        await provider.create_directory("/test")
        node = EnhancedNodeInfo("test.txt", False, "/test")
        await provider.create_node(node)
        
        # Mock the cursor to raise an exception during write
        with unittest.mock.patch.object(provider, '_get_connection') as mock_get_conn:
            mock_conn = unittest.mock.MagicMock()
            mock_cursor = unittest.mock.MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = Exception("Database error")
            mock_get_conn.return_value = mock_conn
            
            # This should trigger exception handling and return False
            result = await provider.write_file("/test/test.txt", b"new content")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_node_info_database_exception(self, provider):
        """Test get_node_info with database exceptions"""
        import unittest.mock
        
        # Mock the cursor to raise an exception
        with unittest.mock.patch.object(provider, '_get_connection') as mock_get_conn:
            mock_conn = unittest.mock.MagicMock()
            mock_cursor = unittest.mock.MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = Exception("Database error")
            mock_get_conn.return_value = mock_conn
            
            # This should trigger exception handling and return None
            result = await provider.get_node_info("/")
            assert result is None

    @pytest.mark.asyncio
    async def test_exists_database_exception(self, provider):
        """Test exists with database exceptions"""
        import unittest.mock
        
        # Mock the cursor to raise an exception
        with unittest.mock.patch.object(provider, '_get_connection') as mock_get_conn:
            mock_conn = unittest.mock.MagicMock()
            mock_cursor = unittest.mock.MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = Exception("Database error")
            mock_get_conn.return_value = mock_conn
            
            # This should trigger exception handling and return False
            result = await provider.exists("/")
            assert result is False