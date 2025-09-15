"""
Test suite for async memory storage provider
"""

import asyncio

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider


@pytest.fixture
async def provider():
    """Create an async memory provider instance"""
    provider = AsyncMemoryStorageProvider()
    await provider.initialize()
    yield provider
    await provider.close()


class TestProviderLifecycle:
    """Test provider lifecycle operations"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test provider initialization"""
        provider = AsyncMemoryStorageProvider()
        assert not provider._initialized

        result = await provider.initialize()
        assert result is True
        assert provider._initialized

        # Root should exist
        root_info = await provider.get_node_info("/")
        assert root_info is not None
        assert root_info.is_dir

        await provider.close()

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test provider close"""
        await provider.close()
        assert provider._closed

        # Operations should fail after close
        with pytest.raises(RuntimeError, match="Provider is closed"):
            await provider.create_node(EnhancedNodeInfo("test", False, "/"))

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using provider as context manager"""
        async with AsyncMemoryStorageProvider() as provider:
            assert provider._initialized
            assert not provider._closed

            # Should be able to perform operations
            assert await provider.exists("/")

        # After context exit, should be closed
        assert provider._closed


class TestNodeOperations:
    """Test node creation and management"""

    @pytest.mark.asyncio
    async def test_create_file_node(self, provider):
        """Test creating file nodes"""
        node = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")

        assert await provider.create_node(node)
        assert await provider.exists("/test.txt")

        # Should not create duplicate
        assert not await provider.create_node(node)

    @pytest.mark.asyncio
    async def test_create_directory_node(self, provider):
        """Test creating directory nodes"""
        node = EnhancedNodeInfo(name="testdir", is_dir=True, parent_path="/")

        assert await provider.create_node(node)
        assert await provider.exists("/testdir")

        # Should be able to create child
        child = EnhancedNodeInfo(name="child", is_dir=False, parent_path="/testdir")
        assert await provider.create_node(child)

    @pytest.mark.asyncio
    async def test_delete_node(self, provider):
        """Test deleting nodes"""
        # Create and delete file
        file_node = EnhancedNodeInfo("file.txt", False, "/")
        await provider.create_node(file_node)
        await provider.write_file("/file.txt", b"content")

        assert await provider.delete_node("/file.txt")
        assert not await provider.exists("/file.txt")

        # Create and delete empty directory
        dir_node = EnhancedNodeInfo("dir", True, "/")
        await provider.create_node(dir_node)

        assert await provider.delete_node("/dir")
        assert not await provider.exists("/dir")

    @pytest.mark.asyncio
    async def test_cannot_delete_root(self, provider):
        """Test that root cannot be deleted"""
        assert not await provider.delete_node("/")
        assert await provider.exists("/")

    @pytest.mark.asyncio
    async def test_cannot_delete_non_empty_directory(self, provider):
        """Test that non-empty directories cannot be deleted"""
        # Create directory with child
        parent = EnhancedNodeInfo("parent", True, "/")
        child = EnhancedNodeInfo("child", False, "/parent")

        await provider.create_node(parent)
        await provider.create_node(child)

        # Should not be able to delete parent
        assert not await provider.delete_node("/parent")
        assert await provider.exists("/parent")


class TestFileOperations:
    """Test file read/write operations"""

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, provider):
        """Test writing and reading file content"""
        # Create file
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)

        # Write content
        content = b"Hello, World!"
        assert await provider.write_file("/test.txt", content)

        # Read content
        read_content = await provider.read_file("/test.txt")
        assert read_content == content

        # Node should have updated metadata
        node_info = await provider.get_node_info("/test.txt")
        assert node_info.size == len(content)
        assert node_info.sha256 is not None
        assert node_info.md5 is not None

    @pytest.mark.asyncio
    async def test_cannot_write_to_directory(self, provider):
        """Test that writing to directory fails"""
        dir_node = EnhancedNodeInfo("dir", True, "/")
        await provider.create_node(dir_node)

        assert not await provider.write_file("/dir", b"content")

    @pytest.mark.asyncio
    async def test_cannot_read_directory(self, provider):
        """Test that reading directory returns None"""
        dir_node = EnhancedNodeInfo("dir", True, "/")
        await provider.create_node(dir_node)

        content = await provider.read_file("/dir")
        assert content is None


class TestDirectoryOperations:
    """Test directory listing operations"""

    @pytest.mark.asyncio
    async def test_list_empty_directory(self, provider):
        """Test listing empty directory"""
        dir_node = EnhancedNodeInfo("empty", True, "/")
        await provider.create_node(dir_node)

        contents = await provider.list_directory("/empty")
        assert contents == []

    @pytest.mark.asyncio
    async def test_list_directory_with_contents(self, provider):
        """Test listing directory with contents"""
        # Create directory structure
        await provider.create_node(EnhancedNodeInfo("dir", True, "/"))
        await provider.create_node(EnhancedNodeInfo("file1.txt", False, "/dir"))
        await provider.create_node(EnhancedNodeInfo("file2.txt", False, "/dir"))
        await provider.create_node(EnhancedNodeInfo("subdir", True, "/dir"))

        contents = await provider.list_directory("/dir")
        assert len(contents) == 3
        assert "file1.txt" in contents
        assert "file2.txt" in contents
        assert "subdir" in contents

    @pytest.mark.asyncio
    async def test_list_non_directory(self, provider):
        """Test listing non-directory returns empty"""
        file_node = EnhancedNodeInfo("file.txt", False, "/")
        await provider.create_node(file_node)

        contents = await provider.list_directory("/file.txt")
        assert contents == []


class TestMetadataOperations:
    """Test metadata operations"""

    @pytest.mark.asyncio
    async def test_get_metadata(self, provider):
        """Test getting node metadata"""
        # Create file with content
        node = EnhancedNodeInfo(
            name="test.txt",
            is_dir=False,
            parent_path="/",
            mime_type="text/plain",
            owner="testuser",
        )
        await provider.create_node(node)
        await provider.write_file("/test.txt", b"content")

        metadata = await provider.get_metadata("/test.txt")

        assert metadata["name"] == "test.txt"
        assert metadata["is_dir"] is False
        assert metadata["mime_type"] == "text/plain"
        assert metadata["owner"] == "testuser"
        assert metadata["size"] == 7
        assert metadata["sha256"] is not None

    @pytest.mark.asyncio
    async def test_set_metadata(self, provider):
        """Test setting custom metadata"""
        # Create node
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)

        # Set metadata
        metadata = {
            "custom_meta": {"version": "1.0", "author": "test"},
            "tags": {"env": "test"},
            "mime_type": "application/json",
            "ttl": 3600,
        }

        assert await provider.set_metadata("/test.txt", metadata)

        # Verify metadata
        node_info = await provider.get_node_info("/test.txt")
        assert node_info.custom_meta["version"] == "1.0"
        assert node_info.tags["env"] == "test"
        assert node_info.mime_type == "application/json"
        assert node_info.ttl == 3600
        assert node_info.expires_at is not None

    @pytest.mark.asyncio
    async def test_timestamps_update(self, provider):
        """Test that timestamps are updated correctly"""
        # Create node
        node = EnhancedNodeInfo("test.txt", False, "/")
        await provider.create_node(node)

        initial_info = await provider.get_node_info("/test.txt")
        initial_modified = initial_info.modified_at

        # Wait a bit and modify
        await asyncio.sleep(0.1)
        await provider.write_file("/test.txt", b"new content")

        updated_info = await provider.get_node_info("/test.txt")
        assert updated_info.modified_at != initial_modified
        assert updated_info.accessed_at is not None


class TestSessionOperations:
    """Test session-based operations"""

    @pytest.mark.asyncio
    async def test_session_isolation(self):
        """Test that sessions can be isolated"""
        # Create two providers with different sessions
        provider1 = AsyncMemoryStorageProvider(session_id="session1")
        provider2 = AsyncMemoryStorageProvider(session_id="session2")

        await provider1.initialize()
        await provider2.initialize()

        # Create nodes in each session
        node1 = EnhancedNodeInfo("file1.txt", False, "/")
        node2 = EnhancedNodeInfo("file2.txt", False, "/")

        await provider1.create_node(node1)
        await provider2.create_node(node2)

        # List by session
        session1_files = await provider1.list_by_session("session1")
        session2_files = await provider2.list_by_session("session2")

        assert "/file1.txt" in session1_files
        assert "/file2.txt" in session2_files

        await provider1.close()
        await provider2.close()

    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Test deleting all nodes in a session"""
        provider = AsyncMemoryStorageProvider(session_id="test_session")
        await provider.initialize()

        # Create multiple nodes
        for i in range(5):
            node = EnhancedNodeInfo(f"file{i}.txt", False, "/")
            node.session_id = "test_session"
            await provider.create_node(node)

        # Delete session
        deleted = await provider.delete_session("test_session")
        assert deleted == 6  # 5 files + root directory

        # Verify nodes are gone
        session_files = await provider.list_by_session("test_session")
        assert len(session_files) == 0

        await provider.close()


class TestStorageStatistics:
    """Test storage statistics"""

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, provider):
        """Test getting storage statistics"""
        # Create some content
        await provider.create_node(EnhancedNodeInfo("file1.txt", False, "/"))
        await provider.create_node(EnhancedNodeInfo("file2.txt", False, "/"))
        await provider.create_node(EnhancedNodeInfo("dir", True, "/"))

        await provider.write_file("/file1.txt", b"content1")
        await provider.write_file("/file2.txt", b"content2")

        stats = await provider.get_storage_stats()

        assert stats["file_count"] == 2
        assert stats["directory_count"] == 2  # Including root
        assert stats["total_size_bytes"] == 16
        assert "operations" in stats

    @pytest.mark.asyncio
    async def test_cleanup(self, provider):
        """Test cleanup operations"""
        # Create temp files with TTL
        node1 = EnhancedNodeInfo("temp1.txt", False, "/tmp", ttl=1)
        node1.calculate_expiry()

        await provider.create_node(EnhancedNodeInfo("tmp", True, "/"))
        await provider.create_node(node1)
        await provider.write_file("/tmp/temp1.txt", b"temp content")

        # Wait for expiry
        await asyncio.sleep(1.1)

        # Run cleanup
        result = await provider.cleanup()

        assert result["files_removed"] > 0
        assert result["bytes_freed"] > 0


class TestCopyMoveOperations:
    """Test copy and move operations"""

    @pytest.mark.asyncio
    async def test_copy_file(self, provider):
        """Test copying a file"""
        # Create source file
        source = EnhancedNodeInfo("source.txt", False, "/")
        await provider.create_node(source)
        await provider.write_file("/source.txt", b"content")

        # Copy file
        assert await provider.copy_node("/source.txt", "/dest.txt")

        # Both should exist
        assert await provider.exists("/source.txt")
        assert await provider.exists("/dest.txt")

        # Content should be the same
        source_content = await provider.read_file("/source.txt")
        dest_content = await provider.read_file("/dest.txt")
        assert source_content == dest_content

    @pytest.mark.asyncio
    async def test_copy_directory(self, provider):
        """Test copying a directory"""
        # Create source directory structure
        await provider.create_node(EnhancedNodeInfo("source", True, "/"))
        await provider.create_node(EnhancedNodeInfo("file.txt", False, "/source"))
        await provider.write_file("/source/file.txt", b"content")

        # Copy directory
        assert await provider.copy_node("/source", "/dest")

        # Both should exist
        assert await provider.exists("/source")
        assert await provider.exists("/dest")
        assert await provider.exists("/dest/file.txt")

        # Content should be the same
        content = await provider.read_file("/dest/file.txt")
        assert content == b"content"

    @pytest.mark.asyncio
    async def test_move_file(self, provider):
        """Test moving a file"""
        # Create source file
        source = EnhancedNodeInfo("source.txt", False, "/")
        await provider.create_node(source)
        await provider.write_file("/source.txt", b"content")

        # Move file
        assert await provider.move_node("/source.txt", "/dest.txt")

        # Source should be gone, dest should exist
        assert not await provider.exists("/source.txt")
        assert await provider.exists("/dest.txt")

        # Content should be preserved
        content = await provider.read_file("/dest.txt")
        assert content == b"content"


class TestEnhancedFeatures:
    """Test enhanced features for parity with S3 provider"""

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
            ("/dir/file3.txt", b"content3"),  # Parent dir should be created
        ]

        # Create parent directory for file3
        await provider.create_directory("/dir")

        results = await provider.batch_write(operations)
        assert all(results)

        # All files should exist with correct content
        assert await provider.read_file("/file1.txt") == b"content1"
        assert await provider.read_file("/file2.txt") == b"content2"
        assert await provider.read_file("/dir/file3.txt") == b"content3"

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

    @pytest.mark.asyncio
    async def test_copy_preserves_metadata(self, provider):
        """Test that copying preserves node metadata"""
        # Create file with metadata
        node = EnhancedNodeInfo(
            name="source.txt",
            is_dir=False,
            parent_path="/",
            permissions="644",
            owner="1001",
            group="1001",
            mime_type="text/plain"
        )
        node.tags = {"env": "test", "version": "1.0"}
        node.custom_meta = {"author": "test"}
        
        await provider.create_node(node)
        await provider.write_file("/source.txt", b"content")

        # Copy file
        await provider.copy_node("/source.txt", "/dest.txt")

        # Check metadata is preserved
        dest_node = await provider.get_node_info("/dest.txt")
        assert dest_node.permissions == "644"
        assert dest_node.owner == "1001"
        assert dest_node.group == "1001"
        assert dest_node.mime_type == "text/plain"
        assert dest_node.tags == {"env": "test", "version": "1.0"}
        assert dest_node.custom_meta == {"author": "test"}

    @pytest.mark.asyncio
    async def test_nested_directory_operations(self, provider):
        """Test operations with deeply nested directories"""
        # Create nested structure
        deep_path = "/a/b/c/d/e/f/g"
        result = await provider.create_directory(deep_path)
        assert result is True

        # All intermediate directories should exist
        paths = ["/a", "/a/b", "/a/b/c", "/a/b/c/d", "/a/b/c/d/e", "/a/b/c/d/e/f", deep_path]
        for path in paths:
            assert await provider.exists(path)
            node = await provider.get_node_info(path)
            assert node.is_dir

        # List directory at each level
        items = await provider.list_directory("/a")
        assert "b" in items
        
        items = await provider.list_directory("/a/b/c")
        assert "d" in items
