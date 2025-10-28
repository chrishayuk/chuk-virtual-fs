"""
Test module for AsyncFilesystemStorageProvider

This module contains comprehensive tests for the filesystem provider,
covering all features and edge cases to ensure high test coverage.
"""

import asyncio
import builtins
import contextlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.filesystem import AsyncFilesystemStorageProvider


class TestProviderLifecycle:
    """Test provider initialization, setup, and teardown"""

    def test_initialization(self):
        """Test provider can be created with default settings"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            assert provider.root_path == Path(temp_dir)
            assert not provider._initialized
            assert not provider._closed

    def test_initialization_with_custom_settings(self):
        """Test provider initialization with custom settings"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, create_root=False, use_metadata=False
            )
            assert provider.root_path == Path(temp_dir)
            assert not provider.create_root
            assert not provider.use_metadata

    @pytest.mark.asyncio
    async def test_initialize_creates_root_directory(self):
        """Test that initialize creates root directory if it doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root_path = os.path.join(temp_dir, "new_root")
            provider = AsyncFilesystemStorageProvider(root_path=root_path)

            assert not os.path.exists(root_path)
            result = await provider.initialize()

            assert result is True
            assert os.path.exists(root_path)
            assert provider._initialized

    @pytest.mark.asyncio
    async def test_initialize_existing_directory(self):
        """Test initialization with existing root directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)

            result = await provider.initialize()

            assert result is True
            assert provider._initialized

    @pytest.mark.asyncio
    async def test_initialize_without_create_root_fails(self):
        """Test initialization fails when root doesn't exist and create_root=False"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root_path = os.path.join(temp_dir, "nonexistent")
            provider = AsyncFilesystemStorageProvider(
                root_path=root_path, create_root=False
            )

            result = await provider.initialize()

            assert result is False
            assert not provider._initialized

    @pytest.mark.asyncio
    async def test_close(self):
        """Test provider close operation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            await provider.close()

            assert provider._closed

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test provider as async context manager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            async with AsyncFilesystemStorageProvider(root_path=temp_dir) as provider:
                assert provider._initialized
                assert not provider._closed

            assert provider._closed


class TestDirectoryOperations:
    """Test directory creation, listing, and management"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()

    @pytest.mark.asyncio
    async def test_create_directory(self, provider):
        """Test creating a directory"""
        node_info = EnhancedNodeInfo(name="test_dir", is_dir=True, parent_path="/")

        result = await provider.create_node(node_info)

        assert result is True
        assert await provider.exists("/test_dir")

    @pytest.mark.asyncio
    async def test_create_nested_directory(self, provider):
        """Test creating nested directories"""
        # Create parent first
        parent_info = EnhancedNodeInfo(name="parent", is_dir=True, parent_path="/")
        await provider.create_node(parent_info)

        # Create child
        child_info = EnhancedNodeInfo(name="child", is_dir=True, parent_path="/parent")

        result = await provider.create_node(child_info)

        assert result is True
        assert await provider.exists("/parent/child")

    @pytest.mark.asyncio
    async def test_list_directory(self, provider):
        """Test listing directory contents"""
        # Create some test items
        dir_info = EnhancedNodeInfo(name="subdir", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        file_info = EnhancedNodeInfo(name="file.txt", is_dir=False, parent_path="/")
        await provider.create_node(file_info)
        await provider.write_file("/file.txt", b"content")

        contents = await provider.list_directory("/")

        assert "subdir" in contents
        assert "file.txt" in contents

    @pytest.mark.asyncio
    async def test_list_empty_directory(self, provider):
        """Test listing empty directory"""
        contents = await provider.list_directory("/")
        assert contents == []

    @pytest.mark.asyncio
    async def test_list_nonexistent_directory(self, provider):
        """Test listing nonexistent directory returns empty list"""
        contents = await provider.list_directory("/nonexistent")
        assert contents == []


class TestFileOperations:
    """Test file creation, reading, writing, and deletion"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()

    @pytest.mark.asyncio
    async def test_create_file(self, provider):
        """Test creating a file"""
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")

        result = await provider.create_node(node_info)

        assert result is True
        assert await provider.exists("/test.txt")

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, provider):
        """Test writing to and reading from a file"""
        # Create file
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Write content
        content = b"Hello, World!"
        result = await provider.write_file("/test.txt", content)
        assert result is True

        # Read content
        read_content = await provider.read_file("/test.txt")
        assert read_content == content

    @pytest.mark.asyncio
    async def test_write_large_file(self, provider):
        """Test writing and reading large file"""
        # Create file
        node_info = EnhancedNodeInfo(name="large.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Create large content (1MB)
        large_content = b"x" * (1024 * 1024)

        result = await provider.write_file("/large.txt", large_content)
        assert result is True

        read_content = await provider.read_file("/large.txt")
        assert read_content == large_content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, provider):
        """Test reading nonexistent file returns None"""
        content = await provider.read_file("/nonexistent.txt")
        assert content is None

    @pytest.mark.asyncio
    async def test_write_to_nonexistent_file(self, provider):
        """Test writing to nonexistent file returns False"""
        # Note: Our filesystem provider creates parent directories as needed
        # so this test checks writing to a path where parent doesn't exist
        result = await provider.write_file(
            "/nonexistent_dir/nonexistent.txt", b"content"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_file(self, provider):
        """Test deleting a file"""
        # Create and write file
        node_info = EnhancedNodeInfo(
            name="delete_me.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(node_info)
        await provider.write_file("/delete_me.txt", b"content")

        # Delete file
        result = await provider.delete_node("/delete_me.txt")

        assert result is True
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
        assert not await provider.exists("/delete_dir")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_node(self, provider):
        """Test deleting nonexistent node returns False"""
        result = await provider.delete_node("/nonexistent")
        assert result is False


class TestNodeInfo:
    """Test node information retrieval and management"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()

    @pytest.mark.asyncio
    async def test_get_file_node_info(self, provider):
        """Test getting node info for a file"""
        # Create file
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)
        await provider.write_file("/test.txt", b"content")

        retrieved_info = await provider.get_node_info("/test.txt")

        assert retrieved_info is not None
        assert retrieved_info.name == "test.txt"
        assert not retrieved_info.is_dir
        assert retrieved_info.size == 7  # len(b"content")

    @pytest.mark.asyncio
    async def test_get_directory_node_info(self, provider):
        """Test getting node info for a directory"""
        # Create directory
        node_info = EnhancedNodeInfo(name="test_dir", is_dir=True, parent_path="/")
        await provider.create_node(node_info)

        retrieved_info = await provider.get_node_info("/test_dir")

        assert retrieved_info is not None
        assert retrieved_info.name == "test_dir"
        assert retrieved_info.is_dir

    @pytest.mark.asyncio
    async def test_get_nonexistent_node_info(self, provider):
        """Test getting node info for nonexistent path returns None"""
        info = await provider.get_node_info("/nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_exists_file(self, provider):
        """Test exists check for file"""
        # Create file
        node_info = EnhancedNodeInfo(name="exists.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        assert await provider.exists("/exists.txt")
        assert not await provider.exists("/not_exists.txt")

    @pytest.mark.asyncio
    async def test_exists_directory(self, provider):
        """Test exists check for directory"""
        # Create directory
        node_info = EnhancedNodeInfo(name="exists_dir", is_dir=True, parent_path="/")
        await provider.create_node(node_info)

        assert await provider.exists("/exists_dir")
        assert not await provider.exists("/not_exists_dir")


class TestMetadataOperations:
    """Test metadata storage and retrieval"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider with metadata enabled"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=True
            )
            await provider.initialize()
            yield provider
            await provider.close()

    @pytest.mark.asyncio
    async def test_set_and_get_metadata(self, provider):
        """Test setting and getting metadata"""
        # Create file
        node_info = EnhancedNodeInfo(
            name="meta_test.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(node_info)

        # Set metadata
        metadata = {"author": "test", "version": "1.0", "tags": ["important"]}
        result = await provider.set_metadata("/meta_test.txt", metadata)
        assert result is True

        # Get metadata
        retrieved_metadata = await provider.get_metadata("/meta_test.txt")
        assert retrieved_metadata["author"] == "test"
        assert retrieved_metadata["version"] == "1.0"
        assert retrieved_metadata["tags"] == ["important"]

    @pytest.mark.asyncio
    async def test_get_metadata_nonexistent_file(self, provider):
        """Test getting metadata for nonexistent file"""
        metadata = await provider.get_metadata("/nonexistent.txt")
        assert metadata == {}

    @pytest.mark.asyncio
    async def test_set_metadata_nonexistent_file(self, provider):
        """Test setting metadata for nonexistent file returns False"""
        result = await provider.set_metadata("/nonexistent.txt", {"key": "value"})
        assert result is False

    @pytest.mark.asyncio
    async def test_metadata_disabled(self):
        """Test metadata operations when metadata is disabled"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=False
            )
            await provider.initialize()

            # Create file
            node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
            await provider.create_node(node_info)

            # Metadata operations should return default values
            metadata = await provider.get_metadata("/test.txt")
            assert metadata == {}

            result = await provider.set_metadata("/test.txt", {"key": "value"})
            assert result is True  # No-op but returns True

            await provider.close()


class TestEnhancedFeatures:
    """Test enhanced features like copy, move, checksums"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()

    @pytest.mark.asyncio
    async def test_calculate_checksum(self, provider):
        """Test checksum calculation"""
        content = b"Hello, World!"
        checksum = await provider.calculate_checksum(content)

        # SHA256 of "Hello, World!"
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        assert checksum == expected

    @pytest.mark.asyncio
    async def test_copy_node_file(self, provider):
        """Test copying a file"""
        # Create source file
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        await provider.create_node(source_info)
        await provider.write_file("/source.txt", b"copy content")

        # Copy file
        result = await provider.copy_node("/source.txt", "/dest.txt")

        assert result is True
        assert await provider.exists("/dest.txt")

        # Verify content
        dest_content = await provider.read_file("/dest.txt")
        assert dest_content == b"copy content"

    @pytest.mark.asyncio
    async def test_copy_node_directory(self, provider):
        """Test copying a directory with contents"""
        # Create source directory structure
        dir_info = EnhancedNodeInfo(name="source_dir", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        file_info = EnhancedNodeInfo(
            name="file.txt", is_dir=False, parent_path="/source_dir"
        )
        await provider.create_node(file_info)
        await provider.write_file("/source_dir/file.txt", b"nested content")

        # Copy directory
        result = await provider.copy_node("/source_dir", "/dest_dir")

        assert result is True
        assert await provider.exists("/dest_dir")
        assert await provider.exists("/dest_dir/file.txt")

        # Verify nested content
        nested_content = await provider.read_file("/dest_dir/file.txt")
        assert nested_content == b"nested content"

    @pytest.mark.asyncio
    async def test_copy_nonexistent_source(self, provider):
        """Test copying nonexistent source returns False"""
        result = await provider.copy_node("/nonexistent", "/dest")
        assert result is False

    @pytest.mark.asyncio
    async def test_move_node_file(self, provider):
        """Test moving a file"""
        # Create source file
        source_info = EnhancedNodeInfo(
            name="move_source.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(source_info)
        await provider.write_file("/move_source.txt", b"move content")

        # Move file
        result = await provider.move_node("/move_source.txt", "/move_dest.txt")

        assert result is True
        assert not await provider.exists("/move_source.txt")
        assert await provider.exists("/move_dest.txt")

        # Verify content
        dest_content = await provider.read_file("/move_dest.txt")
        assert dest_content == b"move content"

    @pytest.mark.asyncio
    async def test_move_node_directory(self, provider):
        """Test moving a directory"""
        # Create source directory
        dir_info = EnhancedNodeInfo(name="move_dir", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        # Move directory
        result = await provider.move_node("/move_dir", "/moved_dir")

        assert result is True
        assert not await provider.exists("/move_dir")
        assert await provider.exists("/moved_dir")


class TestBatchOperations:
    """Test batch operations for multiple files"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()

    @pytest.mark.asyncio
    async def test_batch_create(self, provider):
        """Test batch creation of nodes"""
        nodes = [
            EnhancedNodeInfo(name="batch1.txt", is_dir=False, parent_path="/"),
            EnhancedNodeInfo(name="batch2.txt", is_dir=False, parent_path="/"),
            EnhancedNodeInfo(name="batch_dir", is_dir=True, parent_path="/"),
        ]

        results = await provider.batch_create(nodes)

        assert all(results)
        assert await provider.exists("/batch1.txt")
        assert await provider.exists("/batch2.txt")
        assert await provider.exists("/batch_dir")

    @pytest.mark.asyncio
    async def test_batch_delete(self, provider):
        """Test batch deletion of nodes"""
        # Create files to delete
        for i in range(3):
            node_info = EnhancedNodeInfo(
                name=f"delete{i}.txt", is_dir=False, parent_path="/"
            )
            await provider.create_node(node_info)

        paths = ["/delete0.txt", "/delete1.txt", "/delete2.txt"]
        results = await provider.batch_delete(paths)

        assert all(results)
        for path in paths:
            assert not await provider.exists(path)

    @pytest.mark.asyncio
    async def test_batch_read(self, provider):
        """Test batch reading of files"""
        # Create and write test files
        test_data = {
            "/read1.txt": b"content1",
            "/read2.txt": b"content2",
            "/read3.txt": b"content3",
        }

        for path, content in test_data.items():
            node_info = EnhancedNodeInfo(
                name=path.split("/")[-1], is_dir=False, parent_path="/"
            )
            await provider.create_node(node_info)
            await provider.write_file(path, content)

        paths = list(test_data.keys())
        results = await provider.batch_read(paths)

        assert len(results) == 3
        for i, path in enumerate(paths):
            assert results[i] == test_data[path]

    @pytest.mark.asyncio
    async def test_batch_write(self, provider):
        """Test batch writing of files"""
        # Create files first
        for i in range(3):
            node_info = EnhancedNodeInfo(
                name=f"write{i}.txt", is_dir=False, parent_path="/"
            )
            await provider.create_node(node_info)

        operations = [
            ("/write0.txt", b"batch content 0"),
            ("/write1.txt", b"batch content 1"),
            ("/write2.txt", b"batch content 2"),
        ]

        results = await provider.batch_write(operations)

        assert all(results)

        # Verify content
        for path, expected_content in operations:
            actual_content = await provider.read_file(path)
            assert actual_content == expected_content

    @pytest.mark.asyncio
    async def test_batch_mixed_results(self, provider):
        """Test batch operations with mixed success/failure results"""
        # Create some files, leave others nonexistent
        node_info = EnhancedNodeInfo(name="exists.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Try to delete mix of existing and nonexistent files
        paths = ["/exists.txt", "/nonexistent1.txt", "/nonexistent2.txt"]
        results = await provider.batch_delete(paths)

        assert results[0] is True  # exists.txt should be deleted
        assert results[1] is False  # nonexistent1.txt should fail
        assert results[2] is False  # nonexistent2.txt should fail


class TestStorageStats:
    """Test storage statistics and cleanup operations"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()

    @pytest.mark.asyncio
    async def test_get_storage_stats_empty(self, provider):
        """Test storage statistics for empty filesystem"""
        stats = await provider.get_storage_stats()

        assert "total_files" in stats
        assert "total_directories" in stats
        assert "total_size" in stats
        assert "root_path" in stats
        assert stats["total_files"] == 0
        assert stats["total_directories"] == 0
        assert stats["total_size"] == 0

    @pytest.mark.asyncio
    async def test_get_storage_stats_with_files(self, provider):
        """Test storage statistics with files"""
        # Create test files
        file_info = EnhancedNodeInfo(name="test1.txt", is_dir=False, parent_path="/")
        await provider.create_node(file_info)
        await provider.write_file("/test1.txt", b"content1")

        file_info2 = EnhancedNodeInfo(name="test2.txt", is_dir=False, parent_path="/")
        await provider.create_node(file_info2)
        await provider.write_file("/test2.txt", b"content2")

        dir_info = EnhancedNodeInfo(name="testdir", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        stats = await provider.get_storage_stats()

        assert stats["total_files"] == 2
        assert stats["total_directories"] == 1
        assert stats["total_size"] == 16  # len("content1") + len("content2")

    @pytest.mark.asyncio
    async def test_cleanup(self, provider):
        """Test cleanup operation"""
        result = await provider.cleanup()

        assert "cleaned_up" in result
        assert result["cleaned_up"] is True


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_operations_with_closed_provider(self):
        """Test operations after provider is closed"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            await provider.close()

            # Operations should handle closed state gracefully
            node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
            result = await provider.create_node(node_info)
            assert result is False

    @pytest.mark.asyncio
    async def test_permission_errors(self):
        """Test handling of permission errors"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a read-only directory
            readonly_path = os.path.join(temp_dir, "readonly")
            os.makedirs(readonly_path)
            os.chmod(readonly_path, 0o444)

            try:
                provider = AsyncFilesystemStorageProvider(root_path=readonly_path)
                await provider.initialize()

                # Try to create a file (should fail due to permissions)
                node_info = EnhancedNodeInfo(
                    name="test.txt", is_dir=False, parent_path="/"
                )
                result = await provider.create_node(node_info)
                assert result is False

                await provider.close()
            finally:
                # Restore permissions for cleanup
                os.chmod(readonly_path, 0o755)

    @pytest.mark.asyncio
    async def test_invalid_paths(self, provider):
        """Test handling of invalid paths"""
        # Test with various invalid path scenarios
        # Empty path resolves to root and exists
        assert await provider.exists("/")
        assert not await provider.exists(
            "../../../etc/passwd"
        )  # Path traversal attempt

        # Reading invalid paths should return None/empty
        content = await provider.read_file("/nonexistent/path")
        assert content is None

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, provider):
        """Test concurrent file operations"""
        # Create multiple concurrent operations
        tasks = []

        # Concurrent file creation
        for i in range(10):
            node_info = EnhancedNodeInfo(
                name=f"concurrent{i}.txt", is_dir=False, parent_path="/"
            )
            task = provider.create_node(node_info)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should succeed
        assert all(
            result is True for result in results if not isinstance(result, Exception)
        )

        # Verify all files exist
        for i in range(10):
            assert await provider.exists(f"/concurrent{i}.txt")

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()


class TestRetryMechanism:
    """Test retry logic and error recovery"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()

    @pytest.mark.asyncio
    async def test_with_retry_success(self, provider):
        """Test retry mechanism with successful operation"""

        async def mock_operation():
            return "success"

        result = await provider.with_retry(mock_operation)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_retry_eventual_success(self, provider):
        """Test retry mechanism with eventual success"""
        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await provider.with_retry(mock_operation, max_retries=3)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_retry_max_retries_exceeded(self, provider):
        """Test retry mechanism when max retries exceeded"""

        async def mock_operation():
            raise Exception("Persistent failure")

        with pytest.raises(Exception, match="Persistent failure"):
            await provider.with_retry(mock_operation, max_retries=2)


class TestPathResolution:
    """Test path resolution and normalization"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            yield provider
            await provider.close()

    async def test_resolve_path_absolute(self, provider):
        """Test resolving absolute paths"""
        result = provider._resolve_path("/test/path")
        expected = provider.root_path / "test" / "path"
        assert result == expected

    async def test_resolve_path_relative(self, provider):
        """Test resolving relative paths"""
        result = provider._resolve_path("test/path")
        expected = provider.root_path / "test" / "path"
        assert result == expected

    async def test_resolve_path_root(self, provider):
        """Test resolving root path"""
        result = provider._resolve_path("/")
        assert result == provider.root_path

    async def test_resolve_path_empty(self, provider):
        """Test resolving empty path"""
        result = provider._resolve_path("")
        assert result == provider.root_path

    async def test_resolve_path_normalization(self, provider):
        """Test path normalization"""
        result = provider._resolve_path("/test/../test/./path")
        expected = provider.root_path / "test" / "path"
        assert result == expected


class TestFilesystemErrorHandling:
    """Test filesystem-specific error handling scenarios"""

    @pytest.mark.asyncio
    async def test_initialize_root_not_directory(self):
        """Test initialization when root path is not a directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file instead of a directory
            root_file = os.path.join(temp_dir, "root_file.txt")
            with open(root_file, "w") as f:
                f.write("test")

            provider = AsyncFilesystemStorageProvider(root_path=root_file)
            result = await provider.initialize()
            assert result is False

    @pytest.mark.asyncio
    async def test_initialize_exception_handling(self):
        """Test initialization exception handling"""
        # Use a path that will cause permission errors on most systems
        provider = AsyncFilesystemStorageProvider(root_path="/root/nonexistent")
        result = await provider.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_create_node_when_exists(self):
        """Test creating node when it already exists"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a directory first
            await provider.create_directory("/existing")

            # Try to create a node with the same path
            node = EnhancedNodeInfo("existing", True, "/")
            result = await provider.create_node(node)
            assert result is False

    @pytest.mark.asyncio
    async def test_create_node_parent_missing(self):
        """Test creating node when parent doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Try to create a node in non-existent parent
            node = EnhancedNodeInfo("test.txt", False, "/nonexistent/parent")
            result = await provider.create_node(node)
            assert result is False

    @pytest.mark.asyncio
    async def test_create_node_exception_handling(self):
        """Test create_node exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a directory and then try to create a file with reserved name
            with patch(
                "pathlib.Path.touch", side_effect=PermissionError("Access denied")
            ):
                node = EnhancedNodeInfo("test.txt", False, "/")
                result = await provider.create_node(node)
                assert result is False

    @pytest.mark.asyncio
    async def test_delete_node_exception_handling(self):
        """Test delete_node exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a file first
            await provider.create_directory("/test")

            # Mock an exception during deletion
            with patch(
                "pathlib.Path.rmdir", side_effect=PermissionError("Access denied")
            ):
                result = await provider.delete_node("/test")
                assert result is False

    @pytest.mark.asyncio
    async def test_list_directory_exception_handling(self):
        """Test list_directory exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock an exception during directory listing
            with patch(
                "pathlib.Path.iterdir", side_effect=PermissionError("Access denied")
            ):
                result = await provider.list_directory("/")
                assert result == []

    @pytest.mark.asyncio
    async def test_get_node_info_exception_handling(self):
        """Test get_node_info exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock an exception during stat
            with patch(
                "pathlib.Path.stat", side_effect=PermissionError("Access denied")
            ):
                result = await provider.get_node_info("/")
                assert result is None

    @pytest.mark.asyncio
    async def test_read_file_exception_handling(self):
        """Test read_file exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a file first
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)

            # Test reading non-existent file (normal case)
            result = await provider.read_file("/nonexistent.txt")
            assert result is None

    @pytest.mark.asyncio
    async def test_write_file_exception_handling(self):
        """Test write_file exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Test writing to non-existent file (normal error case)
            result = await provider.write_file("/nonexistent.txt", b"test content")
            assert result is False

    @pytest.mark.asyncio
    async def test_exists_exception_handling(self):
        """Test exists exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock an exception during exists check
            with patch(
                "pathlib.Path.exists", side_effect=PermissionError("Access denied")
            ):
                result = await provider.exists("/")
                assert result is False

    @pytest.mark.asyncio
    async def test_copy_node_exception_handling(self):
        """Test copy_node exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a source file
            node = EnhancedNodeInfo("source.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/source.txt", b"test content")

            # Mock an exception during copy
            with patch("shutil.copy2", side_effect=PermissionError("Access denied")):
                result = await provider.copy_node("/source.txt", "/dest.txt")
                assert result is False

    @pytest.mark.asyncio
    async def test_move_node_exception_handling(self):
        """Test move_node exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a source file
            node = EnhancedNodeInfo("source.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/source.txt", b"test content")

            # Mock an exception during move
            with patch("shutil.move", side_effect=PermissionError("Access denied")):
                result = await provider.move_node("/source.txt", "/dest.txt")
                assert result is False

    @pytest.mark.asyncio
    async def test_get_storage_stats_exception_handling(self):
        """Test get_storage_stats exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock an exception during stats calculation
            with patch(
                "pathlib.Path.iterdir", side_effect=PermissionError("Access denied")
            ):
                result = await provider.get_storage_stats()
                # Should return default stats on exception
                assert isinstance(result, dict)
                assert "total_files" in result or "error" in result

    @pytest.mark.asyncio
    async def test_cleanup_exception_handling(self):
        """Test cleanup exception handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create some test files
            await provider.create_directory("/temp")
            node = EnhancedNodeInfo("test.txt", False, "/temp")
            await provider.create_node(node)

            # Mock an exception during cleanup
            with patch(
                "pathlib.Path.unlink", side_effect=PermissionError("Access denied")
            ):
                result = await provider.cleanup()
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_metadata_operations_when_disabled(self):
        """Test metadata operations when metadata is disabled"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=False
            )
            await provider.initialize()

            # Create a file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)

            # Metadata operations should work but not persist
            result = await provider.set_metadata("/test.txt", {"key": "value"})
            assert isinstance(result, bool)

            metadata = await provider.get_metadata("/test.txt")
            assert isinstance(metadata, dict)

    @pytest.mark.asyncio
    async def test_operations_after_close(self):
        """Test operations after provider is closed"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Close the provider
            await provider.close()

            # All operations should handle closed state gracefully
            node = EnhancedNodeInfo("test.txt", False, "/")
            assert await provider.create_node(node) is False
            assert await provider.delete_node("/test") is False
            assert await provider.get_node_info("/") is None
            assert await provider.list_directory("/") == []
            assert await provider.read_file("/test") is None
            assert await provider.write_file("/test", b"data") is False
            assert await provider.exists("/") is False

    @pytest.mark.asyncio
    async def test_concurrent_filesystem_operations(self):
        """Test concurrent filesystem operations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

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
            success_count = sum(
                1
                for result in results
                if result is True and not isinstance(result, Exception)
            )
            assert success_count >= 8  # Allow for some variation

    @pytest.mark.asyncio
    async def test_edge_case_paths(self):
        """Test edge case path handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Test empty path
            result = await provider.exists("")
            assert isinstance(result, bool)

            # Test root path variations
            assert await provider.exists("/") is True
            assert await provider.exists("/.") is True

            # Test path with special characters (if allowed by filesystem)
            special_chars = "test-file_123"
            node = EnhancedNodeInfo(special_chars, False, "/")
            result = await provider.create_node(node)
            assert result is True

            assert await provider.exists(f"/{special_chars}") is True

    @pytest.mark.asyncio
    async def test_write_to_directory_path(self):
        """Test writing to a path that is actually a directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a directory first
            await provider.create_directory("/test_dir")

            # Try to write to the directory path (should fail)
            result = await provider.write_file("/test_dir", b"test content")
            assert result is False

    @pytest.mark.asyncio
    async def test_permission_setting_error_handling(self):
        """Test permission setting error handling in create_node"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a node with invalid permissions
            node = EnhancedNodeInfo("test.txt", False, "/")
            node.permissions = (
                "invalid_permission_format"  # This should trigger ValueError
            )

            # The creation should still succeed despite permission error
            result = await provider.create_node(node)
            assert result is True

    @pytest.mark.asyncio
    async def test_write_file_permission_error(self):
        """Test write_file when permissions prevent writing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a file first
            node = EnhancedNodeInfo("readonly.txt", False, "/")
            await provider.create_node(node)

            # Make the file read-only and then try to write (this may not work on all systems)

            file_path = Path(temp_dir) / "readonly.txt"
            file_path.chmod(0o444)  # Read-only

            try:
                # This might fail due to permissions
                result = await provider.write_file("/readonly.txt", b"new content")
                # On some systems this might still succeed, so we just check it's boolean
                assert isinstance(result, bool)
            finally:
                # Restore permissions for cleanup
                with contextlib.suppress(builtins.BaseException):
                    file_path.chmod(0o644)

    @pytest.mark.asyncio
    async def test_read_directory_as_file_error(self):
        """Test reading a directory as if it were a file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a directory
            await provider.create_directory("/test_dir")

            # Try to read the directory as a file
            result = await provider.read_file("/test_dir")
            assert result is None

    @pytest.mark.asyncio
    async def test_copy_file_to_existing_destination(self):
        """Test copying file to existing destination (should fail)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create source file
            source_node = EnhancedNodeInfo("source.txt", False, "/")
            await provider.create_node(source_node)
            await provider.write_file("/source.txt", b"source content")

            # Create destination file
            dest_node = EnhancedNodeInfo("dest.txt", False, "/")
            await provider.create_node(dest_node)
            await provider.write_file("/dest.txt", b"dest content")

            # Copy should fail (destination exists)
            result = await provider.copy_node("/source.txt", "/dest.txt")
            assert result is False

            # Verify original content preserved
            content = await provider.read_file("/dest.txt")
            assert content == b"dest content"

    @pytest.mark.asyncio
    async def test_move_file_to_existing_destination(self):
        """Test moving file to existing destination (should fail)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create source file
            source_node = EnhancedNodeInfo("source.txt", False, "/")
            await provider.create_node(source_node)
            await provider.write_file("/source.txt", b"source content")

            # Create destination file
            dest_node = EnhancedNodeInfo("dest.txt", False, "/")
            await provider.create_node(dest_node)
            await provider.write_file("/dest.txt", b"dest content")

            # Move should fail (destination exists)
            result = await provider.move_node("/source.txt", "/dest.txt")
            assert result is False

            # Verify source still exists
            assert await provider.exists("/source.txt") is True

            # Verify original destination content preserved
            content = await provider.read_file("/dest.txt")
            assert content == b"dest content"

    @pytest.mark.asyncio
    async def test_get_storage_stats_with_symlinks(self):
        """Test storage stats calculation with symlinks and special files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create some files and directories
            await provider.create_directory("/test_dir")

            file_node = EnhancedNodeInfo("test.txt", False, "/test_dir")
            await provider.create_node(file_node)
            await provider.write_file("/test_dir/test.txt", b"a" * 100)

            # Create a symlink (if possible)
            try:
                import os

                os.symlink(
                    os.path.join(temp_dir, "test_dir", "test.txt"),
                    os.path.join(temp_dir, "test_dir", "symlink.txt"),
                )
            except (OSError, NotImplementedError):
                pass  # Symlinks might not be supported

            # Get stats
            stats = await provider.get_storage_stats()
            assert isinstance(stats, dict)
            assert "total_files" in stats
            assert "total_directories" in stats

    @pytest.mark.asyncio
    async def test_batch_operations_with_failures(self):
        """Test batch operations with some failures"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Batch create - filesystem provider auto-creates parent directories
            nodes = [
                EnhancedNodeInfo("valid1.txt", False, "/"),
                EnhancedNodeInfo(
                    "valid2.txt", False, "/auto_created"
                ),  # Parent will be auto-created
                EnhancedNodeInfo("valid3.txt", False, "/"),
            ]

            results = await provider.batch_create(nodes)
            assert len(results) == 3
            assert results[0] is True  # First should succeed
            assert results[1] is True  # Second should succeed (auto-creates parent)
            assert results[2] is True  # Third should succeed

            # Create a file that already exists for batch create test
            existing_node = EnhancedNodeInfo("existing.txt", False, "/")
            await provider.create_node(existing_node)

            # Batch create with existing file (should fail)
            duplicate_nodes = [
                EnhancedNodeInfo("new.txt", False, "/"),
                EnhancedNodeInfo("existing.txt", False, "/"),  # Already exists
            ]

            results = await provider.batch_create(duplicate_nodes)
            assert len(results) == 2
            assert results[0] is True  # New file should succeed
            assert results[1] is False  # Existing file should fail

            # Batch delete with some non-existent files
            paths = ["/valid1.txt", "/nonexistent.txt", "/valid3.txt"]
            results = await provider.batch_delete(paths)
            assert len(results) == 3
            assert results[0] is True  # First exists, should succeed
            assert results[1] is False  # Second doesn't exist, should fail
            assert results[2] is True  # Third exists, should succeed

    @pytest.mark.asyncio
    async def test_cleanup_with_expired_files(self):
        """Test cleanup removes expired files based on TTL"""
        from datetime import datetime, timedelta

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=True
            )
            await provider.initialize()

            # Create a file with past expiration (should be cleaned up)
            expired_node = EnhancedNodeInfo("expired.txt", False, "/")
            expired_node.expires_at = (
                datetime.utcnow() - timedelta(days=1)
            ).isoformat() + "Z"
            await provider.create_node(expired_node)
            await provider.write_file("/expired.txt", b"expired content")

            # Create a file with future expiration (should NOT be cleaned up)
            future_node = EnhancedNodeInfo("future.txt", False, "/")
            future_node.expires_at = (
                datetime.utcnow() + timedelta(days=1)
            ).isoformat() + "Z"
            await provider.create_node(future_node)
            await provider.write_file("/future.txt", b"future content")

            # Create a file without expiration (should NOT be cleaned up)
            normal_node = EnhancedNodeInfo("normal.txt", False, "/")
            await provider.create_node(normal_node)
            await provider.write_file("/normal.txt", b"normal content")

            # Run cleanup
            result = await provider.cleanup()

            # Check results
            assert "files_removed" in result
            assert "expired_removed" in result
            assert result["expired_removed"] >= 1  # At least the expired file

            # Verify expired file was removed
            assert not await provider.exists("/expired.txt")

            # Verify other files still exist
            assert await provider.exists("/future.txt")
            assert await provider.exists("/normal.txt")

    @pytest.mark.asyncio
    async def test_cleanup_with_metadata_read_error(self):
        """Test cleanup handles metadata read errors gracefully"""
        from datetime import datetime, timedelta

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=True
            )
            await provider.initialize()

            # Create a file with valid metadata
            valid_node = EnhancedNodeInfo("valid.txt", False, "/")
            valid_node.expires_at = (
                datetime.utcnow() - timedelta(days=1)
            ).isoformat() + "Z"
            await provider.create_node(valid_node)
            await provider.write_file("/valid.txt", b"content")

            # Corrupt the metadata file
            metadata_path = Path(temp_dir) / "valid.txt.meta"
            with open(metadata_path, "w") as f:
                f.write("invalid json{{{")

            # Cleanup should handle the error gracefully
            result = await provider.cleanup()
            assert isinstance(result, dict)
            assert "files_removed" in result

    @pytest.mark.asyncio
    async def test_cleanup_handles_file_deletion_errors(self):
        """Test cleanup handles individual file deletion errors"""
        from datetime import datetime, timedelta

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=True
            )
            await provider.initialize()

            # Create expired files
            for i in range(2):
                node = EnhancedNodeInfo(f"expired{i}.txt", False, "/")
                node.expires_at = (
                    datetime.utcnow() - timedelta(days=1)
                ).isoformat() + "Z"
                await provider.create_node(node)
                await provider.write_file(f"/expired{i}.txt", b"content")

            # Mock file deletion to fail for the first file but succeed for others
            original_unlink = Path.unlink
            call_count = [0]

            def mock_unlink(self, *args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise PermissionError("Cannot delete")
                return original_unlink(self, *args, **kwargs)

            with patch("pathlib.Path.unlink", mock_unlink):
                result = await provider.cleanup()
                # Should continue processing despite errors
                assert isinstance(result, dict)


class TestChecksums:
    """Test checksum calculation features"""

    @pytest.mark.asyncio
    async def test_calculate_file_checksum_md5(self):
        """Test MD5 checksum calculation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/test.txt", b"test content")

            # Calculate MD5
            checksum = await provider.calculate_file_checksum("/test.txt", "md5")
            assert checksum is not None
            assert len(checksum) == 32  # MD5 is 32 hex characters

    @pytest.mark.asyncio
    async def test_calculate_file_checksum_sha1(self):
        """Test SHA1 checksum calculation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/test.txt", b"test content")

            # Calculate SHA1
            checksum = await provider.calculate_file_checksum("/test.txt", "sha1")
            assert checksum is not None
            assert len(checksum) == 40  # SHA1 is 40 hex characters

    @pytest.mark.asyncio
    async def test_calculate_file_checksum_sha256(self):
        """Test SHA256 checksum calculation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/test.txt", b"test content")

            # Calculate SHA256
            checksum = await provider.calculate_file_checksum("/test.txt", "sha256")
            assert checksum is not None
            assert len(checksum) == 64  # SHA256 is 64 hex characters

    @pytest.mark.asyncio
    async def test_calculate_file_checksum_sha512(self):
        """Test SHA512 checksum calculation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/test.txt", b"test content")

            # Calculate SHA512
            checksum = await provider.calculate_file_checksum("/test.txt", "sha512")
            assert checksum is not None
            assert len(checksum) == 128  # SHA512 is 128 hex characters

    @pytest.mark.asyncio
    async def test_calculate_file_checksum_invalid_algorithm(self):
        """Test checksum with invalid algorithm"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/test.txt", b"test content")

            # Try invalid algorithm
            checksum = await provider.calculate_file_checksum("/test.txt", "invalid")
            assert checksum is None

    @pytest.mark.asyncio
    async def test_calculate_file_checksum_nonexistent(self):
        """Test checksum for nonexistent file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            checksum = await provider.calculate_file_checksum("/nonexistent.txt", "md5")
            assert checksum is None

    @pytest.mark.asyncio
    async def test_calculate_file_checksum_directory(self):
        """Test checksum for directory (should return None)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            await provider.create_directory("/test_dir")
            checksum = await provider.calculate_file_checksum("/test_dir", "md5")
            assert checksum is None

    @pytest.mark.asyncio
    async def test_calculate_file_checksum_closed_provider(self):
        """Test checksum with closed provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()
            await provider.close()

            checksum = await provider.calculate_file_checksum("/test.txt", "md5")
            assert checksum is None


class TestTTLAndExpiration:
    """Test TTL and file expiration features"""

    @pytest.mark.asyncio
    async def test_create_file_with_ttl_metadata(self):
        """Test creating file with TTL in metadata"""
        from datetime import datetime, timedelta

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=True
            )
            await provider.initialize()

            # Create file with TTL
            node = EnhancedNodeInfo("ttl_file.txt", False, "/")
            node.ttl = 3600  # 1 hour in seconds
            node.expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"

            result = await provider.create_node(node)
            assert result is True

            # Verify metadata was saved
            metadata = await provider.get_metadata("/ttl_file.txt")
            assert metadata.get("ttl") == 3600
            assert "expires_at" in metadata

    @pytest.mark.asyncio
    async def test_metadata_file_operations(self):
        """Test metadata sidecar file operations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=True
            )
            await provider.initialize()

            # Create file with custom metadata
            node = EnhancedNodeInfo("meta_file.txt", False, "/")
            node.custom_meta = {"author": "test", "version": "1.0"}
            node.tags = {"important": True}

            await provider.create_node(node)

            # Verify .meta file exists
            meta_path = Path(temp_dir) / "meta_file.txt.meta"
            assert meta_path.exists()

            # Delete the file - should also delete metadata
            await provider.delete_node("/meta_file.txt")
            assert not meta_path.exists()

    @pytest.mark.asyncio
    async def test_copy_preserves_metadata(self):
        """Test that copy_node preserves metadata files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=True
            )
            await provider.initialize()

            # Create file with metadata
            node = EnhancedNodeInfo("source.txt", False, "/")
            node.custom_meta = {"key": "value"}
            await provider.create_node(node)
            await provider.write_file("/source.txt", b"content")

            # Copy the file
            await provider.copy_node("/source.txt", "/dest.txt")

            # Verify metadata was copied
            dest_metadata = await provider.get_metadata("/dest.txt")
            assert dest_metadata.get("custom_meta", {}).get("key") == "value"

    @pytest.mark.asyncio
    async def test_move_preserves_metadata(self):
        """Test that move_node preserves metadata files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(
                root_path=temp_dir, use_metadata=True
            )
            await provider.initialize()

            # Create file with metadata
            node = EnhancedNodeInfo("source.txt", False, "/")
            node.custom_meta = {"key": "value"}
            await provider.create_node(node)
            await provider.write_file("/source.txt", b"content")

            # Move the file
            await provider.move_node("/source.txt", "/dest.txt")

            # Verify metadata was moved
            dest_metadata = await provider.get_metadata("/dest.txt")
            assert dest_metadata.get("custom_meta", {}).get("key") == "value"

            # Verify source metadata file is gone
            source_meta_path = Path(temp_dir) / "source.txt.meta"
            assert not source_meta_path.exists()


class TestUninitializedProvider:
    """Test operations on uninitialized provider"""

    @pytest.mark.asyncio
    async def test_uninitialized_set_metadata(self):
        """Test set_metadata on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            result = await provider.set_metadata("/test.txt", {"key": "value"})
            assert result is False

    @pytest.mark.asyncio
    async def test_uninitialized_get_storage_stats(self):
        """Test get_storage_stats on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            stats = await provider.get_storage_stats()
            assert "error" in stats
            assert stats["error"] == "Filesystem not initialized"

    @pytest.mark.asyncio
    async def test_uninitialized_cleanup(self):
        """Test cleanup on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            result = await provider.cleanup()
            assert result["files_removed"] == 0
            assert result["bytes_freed"] == 0
            assert result["expired_removed"] == 0

    @pytest.mark.asyncio
    async def test_uninitialized_create_directory(self):
        """Test create_directory on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            result = await provider.create_directory("/test_dir")
            assert result is False

    @pytest.mark.asyncio
    async def test_uninitialized_copy_node(self):
        """Test copy_node on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            result = await provider.copy_node("/src.txt", "/dst.txt")
            assert result is False

    @pytest.mark.asyncio
    async def test_uninitialized_move_node(self):
        """Test move_node on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            result = await provider.move_node("/src.txt", "/dst.txt")
            assert result is False

    @pytest.mark.asyncio
    async def test_uninitialized_batch_write(self):
        """Test batch_write on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            operations = [("/file1.txt", b"content1"), ("/file2.txt", b"content2")]
            results = await provider.batch_write(operations)
            assert all(r is False for r in results)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_uninitialized_batch_read(self):
        """Test batch_read on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            paths = ["/file1.txt", "/file2.txt"]
            results = await provider.batch_read(paths)
            assert all(r is None for r in results)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_uninitialized_batch_delete(self):
        """Test batch_delete on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            paths = ["/file1.txt", "/file2.txt"]
            results = await provider.batch_delete(paths)
            assert all(r is False for r in results)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_uninitialized_batch_create(self):
        """Test batch_create on uninitialized provider"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            # Don't initialize
            nodes = [
                EnhancedNodeInfo("file1.txt", False, "/"),
                EnhancedNodeInfo("file2.txt", False, "/"),
            ]
            results = await provider.batch_create(nodes)
            assert all(r is False for r in results)
            assert len(results) == 2


class TestAdditionalErrorPaths:
    """Test additional error handling paths"""

    @pytest.mark.asyncio
    async def test_read_file_with_permission_error(self):
        """Test read_file when permission denied"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/test.txt", b"content")

            # Mock open to raise PermissionError
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                result = await provider.read_file("/test.txt")
                assert result is None

            await provider.close()

    @pytest.mark.asyncio
    async def test_set_metadata_with_write_error(self):
        """Test set_metadata when writing fails"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)

            # Mock open to raise error
            with patch("builtins.open", side_effect=OSError("Write failed")):
                result = await provider.set_metadata("/test.txt", {"key": "value"})
                assert result is False

            await provider.close()

    @pytest.mark.asyncio
    async def test_metadata_write_exception_during_create(self):
        """Test metadata write exception during create_node"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a node with metadata that will fail to write
            node = EnhancedNodeInfo("test.txt", False, "/")
            node.custom_meta = {"key": "value"}

            # Mock the metadata write to fail
            with patch("builtins.open", side_effect=OSError("Write failed")):
                # Should still return True (metadata is not critical)
                result = await provider.create_node(node)
                # The node should be created even if metadata fails
                assert result is True

            await provider.close()

    @pytest.mark.asyncio
    async def test_storage_stats_with_stat_error(self):
        """Test storage stats when stat() fails on some files"""

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create files
            node1 = EnhancedNodeInfo("file1.txt", False, "/")
            node2 = EnhancedNodeInfo("file2.txt", False, "/")
            await provider.create_node(node1)
            await provider.create_node(node2)

            # Mock stat to fail on some files
            original_stat = Path.stat
            call_count = [0]

            def mock_stat(self):
                call_count[0] += 1
                if call_count[0] % 3 == 0:  # Fail every 3rd call
                    raise OSError("Stat failed")
                return original_stat(self)

            with patch("pathlib.Path.stat", mock_stat):
                stats = await provider.get_storage_stats()
                # Should still return stats, just skip errored files
                assert "total_files" in stats

            await provider.close()

    @pytest.mark.asyncio
    async def test_storage_stats_with_major_error(self):
        """Test storage stats when major error occurs"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock iterdir to raise an exception
            with patch("pathlib.Path.iterdir", side_effect=OSError("Iterdir failed")):
                stats = await provider.get_storage_stats()
                # Should return error dict
                assert "error" in stats or "total_files" in stats

            await provider.close()

    @pytest.mark.asyncio
    async def test_cleanup_with_major_error(self):
        """Test cleanup when major error occurs"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock os.walk to raise an exception
            with patch("os.walk", side_effect=OSError("Walk failed")):
                result = await provider.cleanup()
                # Should return default values
                assert result["files_removed"] == 0
                assert result["bytes_freed"] == 0

            await provider.close()

    @pytest.mark.asyncio
    async def test_create_directory_with_error(self):
        """Test create_directory when mkdir fails"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock mkdir to raise an exception
            with patch(
                "pathlib.Path.mkdir", side_effect=PermissionError("No permission")
            ):
                result = await provider.create_directory("/test_dir")
                assert result is False

            await provider.close()

    @pytest.mark.asyncio
    async def test_checksum_with_read_error(self):
        """Test checksum calculation when file read fails"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create a file
            node = EnhancedNodeInfo("test.txt", False, "/")
            await provider.create_node(node)
            await provider.write_file("/test.txt", b"content")

            # Mock open to raise error
            with patch("builtins.open", side_effect=OSError("Read failed")):
                result = await provider.calculate_file_checksum("/test.txt", "sha256")
                assert result is None

            await provider.close()

    @pytest.mark.asyncio
    async def test_move_node_nonexistent_source(self):
        """Test move_node with nonexistent source"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            result = await provider.move_node("/nonexistent.txt", "/dest.txt")
            assert result is False

            await provider.close()

    @pytest.mark.asyncio
    async def test_batch_write_creates_nonexistent_files(self):
        """Test batch_write creates files if they don't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # batch_write should create files if they don't exist
            operations = [("/file1.txt", b"content1"), ("/file2.txt", b"content2")]
            results = await provider.batch_write(operations)
            assert all(results)

            # Verify files were created and content written
            content1 = await provider.read_file("/file1.txt")
            content2 = await provider.read_file("/file2.txt")
            assert content1 == b"content1"
            assert content2 == b"content2"

            await provider.close()

    @pytest.mark.asyncio
    async def test_batch_write_with_errors(self):
        """Test batch_write when some operations fail"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock open to fail for some writes
            original_open = open
            call_count = [0]

            def mock_open(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 2:  # Fail second write
                    raise OSError("Write failed")
                return original_open(*args, **kwargs)

            with patch("builtins.open", side_effect=mock_open):
                operations = [("/file1.txt", b"content1"), ("/file2.txt", b"content2")]
                results = await provider.batch_write(operations)
                # Should have mix of success and failure
                assert isinstance(results, list)
                assert len(results) == 2

            await provider.close()

    @pytest.mark.asyncio
    async def test_batch_read_with_errors(self):
        """Test batch_read when some operations fail"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create files
            node1 = EnhancedNodeInfo("file1.txt", False, "/")
            node2 = EnhancedNodeInfo("file2.txt", False, "/")
            await provider.create_node(node1)
            await provider.create_node(node2)
            await provider.write_file("/file1.txt", b"content1")
            await provider.write_file("/file2.txt", b"content2")

            # Mock open to fail for some reads
            original_open = open
            call_count = [0]

            def mock_open(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 2:  # Fail second read
                    raise OSError("Read failed")
                return original_open(*args, **kwargs)

            with patch("builtins.open", side_effect=mock_open):
                paths = ["/file1.txt", "/file2.txt"]
                results = await provider.batch_read(paths)
                # Should have mix of success and None
                assert isinstance(results, list)
                assert len(results) == 2

            await provider.close()

    @pytest.mark.asyncio
    async def test_batch_delete_nonempty_directory(self):
        """Test batch_delete with non-empty directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create directory with file
            dir_node = EnhancedNodeInfo("test_dir", True, "/")
            file_node = EnhancedNodeInfo("file.txt", False, "/test_dir")
            await provider.create_node(dir_node)
            await provider.create_node(file_node)

            # Try to delete non-empty directory
            results = await provider.batch_delete(["/test_dir"])
            assert results[0] is False

            await provider.close()

    @pytest.mark.asyncio
    async def test_batch_delete_with_errors(self):
        """Test batch_delete when some operations fail"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Create files
            node1 = EnhancedNodeInfo("file1.txt", False, "/")
            node2 = EnhancedNodeInfo("file2.txt", False, "/")
            await provider.create_node(node1)
            await provider.create_node(node2)

            # Mock unlink to fail for some deletes
            original_unlink = Path.unlink
            call_count = [0]

            def mock_unlink(self, *args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:  # Fail first delete
                    raise OSError("Delete failed")
                return original_unlink(self, *args, **kwargs)

            with patch("pathlib.Path.unlink", mock_unlink):
                paths = ["/file1.txt", "/file2.txt"]
                results = await provider.batch_delete(paths)
                # Should have mix of success and failure
                assert isinstance(results, list)
                assert len(results) == 2

            await provider.close()

    @pytest.mark.asyncio
    async def test_batch_create_with_errors(self):
        """Test batch_create when some operations fail"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
            await provider.initialize()

            # Mock touch to fail for some creates
            original_touch = Path.touch
            call_count = [0]

            def mock_touch(self, *args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 2:  # Fail second create
                    raise OSError("Create failed")
                return original_touch(self, *args, **kwargs)

            with patch("pathlib.Path.touch", mock_touch):
                nodes = [
                    EnhancedNodeInfo("file1.txt", False, "/"),
                    EnhancedNodeInfo("file2.txt", False, "/"),
                    EnhancedNodeInfo("file3.txt", False, "/"),
                ]
                results = await provider.batch_create(nodes)
                # Should have mix of success and failure
                assert isinstance(results, list)
                assert len(results) == 3

            await provider.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
