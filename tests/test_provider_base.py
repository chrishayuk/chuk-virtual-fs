"""
Comprehensive pytest test suite for provider_base.py
"""

from unittest.mock import AsyncMock

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider


class ConcreteProvider(AsyncStorageProvider):
    """Concrete implementation of AsyncStorageProvider for testing"""

    def __init__(self):
        super().__init__()
        self.initialized = False
        self.nodes = {}  # path -> (node_info, content)

    async def initialize(self) -> bool:
        self.initialized = True
        return True

    async def close(self) -> None:
        self.initialized = False

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        path = f"{node_info.parent_path}/{node_info.name}".replace("//", "/")
        if path in self.nodes:
            return False
        self.nodes[path] = (node_info, b"" if not node_info.is_dir else None)
        return True

    async def delete_node(self, path: str) -> bool:
        if path in self.nodes:
            del self.nodes[path]
            return True
        return False

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        if path in self.nodes:
            return self.nodes[path][0]
        return None

    async def list_directory(self, path: str) -> list[str]:
        items = []
        for node_path in self.nodes:
            if node_path.startswith(path + "/"):
                # Get immediate children only
                relative = node_path[len(path) + 1 :]
                if "/" not in relative:
                    items.append(relative)
        return items

    async def write_file(self, path: str, content: bytes) -> bool:
        if path in self.nodes:
            node_info = self.nodes[path][0]
            if not node_info.is_dir:
                self.nodes[path] = (node_info, content)
                return True
        return False

    async def read_file(self, path: str) -> bytes | None:
        if path in self.nodes:
            node_info, content = self.nodes[path]
            if not node_info.is_dir:
                return content
        return None

    async def get_storage_stats(self) -> dict:
        return {"nodes": len(self.nodes)}

    async def cleanup(self) -> dict:
        return {"cleaned": 0}

    async def exists(self, path: str) -> bool:
        return path in self.nodes

    async def get_metadata(self, path: str) -> dict:
        return {}

    async def set_metadata(self, path: str, metadata: dict) -> bool:
        return True


@pytest.fixture
def provider():
    """Create a concrete provider instance for testing"""
    return ConcreteProvider()


class TestCalculateChecksum:
    """Test calculate_checksum method"""

    @pytest.mark.asyncio
    async def test_calculate_checksum_empty_content(self, provider):
        """Test checksum calculation for empty content"""
        checksum = await provider.calculate_checksum(b"")
        # SHA256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert checksum == expected

    @pytest.mark.asyncio
    async def test_calculate_checksum_simple_content(self, provider):
        """Test checksum calculation for simple content"""
        checksum = await provider.calculate_checksum(b"Hello World")
        # SHA256 of "Hello World"
        expected = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
        assert checksum == expected

    @pytest.mark.asyncio
    async def test_calculate_checksum_binary_content(self, provider):
        """Test checksum calculation for binary content"""
        binary_data = b"\x00\x01\x02\x03\x04\xff\xfe"
        checksum = await provider.calculate_checksum(binary_data)
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 is 64 hex characters


class TestCopyNode:
    """Test copy_node method"""

    @pytest.mark.asyncio
    async def test_copy_file_success(self, provider):
        """Test successful file copy"""
        await provider.initialize()

        # Create source file
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        await provider.create_node(source_info)
        await provider.write_file("/source.txt", b"test content")

        # Copy file
        result = await provider.copy_node("/source.txt", "/dest.txt")

        assert result is True
        # Verify destination exists
        dest_info = await provider.get_node_info("/dest.txt")
        assert dest_info is not None
        assert dest_info.name == "dest.txt"
        # Verify content was copied
        content = await provider.read_file("/dest.txt")
        assert content == b"test content"

    @pytest.mark.asyncio
    async def test_copy_file_source_not_found(self, provider):
        """Test copy when source file doesn't exist - covers line 84"""
        await provider.initialize()

        # Try to copy non-existent file
        result = await provider.copy_node("/nonexistent.txt", "/dest.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_file_read_failure(self, provider):
        """Test copy when read_file returns None - covers line 89"""
        await provider.initialize()

        # Create a provider with mocked read_file that returns None
        provider.read_file = AsyncMock(return_value=None)
        provider.get_node_info = AsyncMock(
            return_value=EnhancedNodeInfo(
                name="source.txt", is_dir=False, parent_path="/"
            )
        )

        result = await provider.copy_node("/source.txt", "/dest.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_file_create_failure(self, provider):
        """Test copy when create_node fails - covers line 98"""
        await provider.initialize()

        # Mock to return valid node info and content, but fail on create
        provider.get_node_info = AsyncMock(
            return_value=EnhancedNodeInfo(
                name="source.txt", is_dir=False, parent_path="/"
            )
        )
        provider.read_file = AsyncMock(return_value=b"content")
        provider.create_node = AsyncMock(return_value=False)

        result = await provider.copy_node("/source.txt", "/dest.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_directory_empty(self, provider):
        """Test copying empty directory - covers lines 103-119"""
        await provider.initialize()

        # Create source directory
        source_info = EnhancedNodeInfo(name="source_dir", is_dir=True, parent_path="/")
        await provider.create_node(source_info)

        # Copy directory
        result = await provider.copy_node("/source_dir", "/dest_dir")

        assert result is True
        # Verify destination directory exists
        dest_info = await provider.get_node_info("/dest_dir")
        assert dest_info is not None
        assert dest_info.is_dir is True

    @pytest.mark.asyncio
    async def test_copy_directory_with_files(self, provider):
        """Test copying directory with files - covers lines 103-119"""
        await provider.initialize()

        # Create source directory with files
        source_info = EnhancedNodeInfo(name="source_dir", is_dir=True, parent_path="/")
        await provider.create_node(source_info)

        file1_info = EnhancedNodeInfo(
            name="file1.txt", is_dir=False, parent_path="/source_dir"
        )
        await provider.create_node(file1_info)
        await provider.write_file("/source_dir/file1.txt", b"content1")

        file2_info = EnhancedNodeInfo(
            name="file2.txt", is_dir=False, parent_path="/source_dir"
        )
        await provider.create_node(file2_info)
        await provider.write_file("/source_dir/file2.txt", b"content2")

        # Copy directory
        result = await provider.copy_node("/source_dir", "/dest_dir")

        assert result is True
        # Verify destination directory and files exist
        dest_info = await provider.get_node_info("/dest_dir")
        assert dest_info is not None

        dest_file1 = await provider.read_file("/dest_dir/file1.txt")
        assert dest_file1 == b"content1"

        dest_file2 = await provider.read_file("/dest_dir/file2.txt")
        assert dest_file2 == b"content2"

    @pytest.mark.asyncio
    async def test_copy_directory_nested(self, provider):
        """Test copying nested directories - covers lines 103-119"""
        await provider.initialize()

        # Create nested directory structure
        source_dir = EnhancedNodeInfo(name="source", is_dir=True, parent_path="/")
        await provider.create_node(source_dir)

        sub_dir = EnhancedNodeInfo(name="subdir", is_dir=True, parent_path="/source")
        await provider.create_node(sub_dir)

        file_info = EnhancedNodeInfo(
            name="file.txt", is_dir=False, parent_path="/source/subdir"
        )
        await provider.create_node(file_info)
        await provider.write_file("/source/subdir/file.txt", b"nested content")

        # Copy directory
        result = await provider.copy_node("/source", "/dest")

        assert result is True
        # Verify nested structure was copied
        nested_content = await provider.read_file("/dest/subdir/file.txt")
        assert nested_content == b"nested content"

    @pytest.mark.asyncio
    async def test_copy_directory_create_failure(self, provider):
        """Test copy when creating destination directory fails - covers lines 103-119"""
        await provider.initialize()

        # Mock to return valid directory info but fail on create
        provider.get_node_info = AsyncMock(
            return_value=EnhancedNodeInfo(
                name="source_dir", is_dir=True, parent_path="/"
            )
        )
        provider.create_node = AsyncMock(return_value=False)

        result = await provider.copy_node("/source_dir", "/dest_dir")

        assert result is False


class TestMoveNode:
    """Test move_node method"""

    @pytest.mark.asyncio
    async def test_move_file_success(self, provider):
        """Test successful file move"""
        await provider.initialize()

        # Create source file
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        await provider.create_node(source_info)
        await provider.write_file("/source.txt", b"test content")

        # Move file
        result = await provider.move_node("/source.txt", "/dest.txt")

        assert result is True
        # Verify source is deleted
        source_exists = await provider.exists("/source.txt")
        assert source_exists is False
        # Verify destination exists
        dest_content = await provider.read_file("/dest.txt")
        assert dest_content == b"test content"

    @pytest.mark.asyncio
    async def test_move_file_copy_failure(self, provider):
        """Test move when copy fails - covers line 125"""
        await provider.initialize()

        # Try to move non-existent file
        result = await provider.move_node("/nonexistent.txt", "/dest.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_move_directory_success(self, provider):
        """Test successful directory move"""
        await provider.initialize()

        # Create source directory with file
        source_dir = EnhancedNodeInfo(name="source_dir", is_dir=True, parent_path="/")
        await provider.create_node(source_dir)

        file_info = EnhancedNodeInfo(
            name="file.txt", is_dir=False, parent_path="/source_dir"
        )
        await provider.create_node(file_info)
        await provider.write_file("/source_dir/file.txt", b"content")

        # Move directory
        result = await provider.move_node("/source_dir", "/dest_dir")

        assert result is True
        # Verify source is deleted
        source_exists = await provider.exists("/source_dir")
        assert source_exists is False
        # Verify destination exists
        dest_content = await provider.read_file("/dest_dir/file.txt")
        assert dest_content == b"content"


class TestPresignedUrls:
    """Test presigned URL methods"""

    @pytest.mark.asyncio
    async def test_generate_presigned_url_default(self, provider):
        """Test generate_presigned_url returns None by default"""
        result = await provider.generate_presigned_url("/test.txt")
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_presigned_url_with_params(self, provider):
        """Test generate_presigned_url with custom parameters"""
        result = await provider.generate_presigned_url(
            "/test.txt", operation="PUT", expires_in=7200
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_presigned_upload_url_default(self, provider):
        """Test generate_presigned_upload_url returns None - covers line 192"""
        result = await provider.generate_presigned_upload_url("/test.txt")
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_presigned_upload_url_with_expiry(self, provider):
        """Test generate_presigned_upload_url with custom expiry - covers line 192"""
        result = await provider.generate_presigned_upload_url(
            "/test.txt", expires_in=7200
        )
        assert result is None


class TestBatchOperations:
    """Test batch operation methods"""

    @pytest.mark.asyncio
    async def test_batch_create_multiple_nodes(self, provider):
        """Test batch creation of multiple nodes"""
        await provider.initialize()

        nodes = [
            EnhancedNodeInfo(name="file1.txt", is_dir=False, parent_path="/"),
            EnhancedNodeInfo(name="file2.txt", is_dir=False, parent_path="/"),
            EnhancedNodeInfo(name="dir1", is_dir=True, parent_path="/"),
        ]

        results = await provider.batch_create(nodes)

        assert len(results) == 3
        assert all(results)

    @pytest.mark.asyncio
    async def test_batch_delete_multiple_nodes(self, provider):
        """Test batch deletion of multiple nodes"""
        await provider.initialize()

        # Create nodes first
        nodes = [
            EnhancedNodeInfo(name="file1.txt", is_dir=False, parent_path="/"),
            EnhancedNodeInfo(name="file2.txt", is_dir=False, parent_path="/"),
        ]
        await provider.batch_create(nodes)

        # Delete them
        results = await provider.batch_delete(["/file1.txt", "/file2.txt"])

        assert len(results) == 2
        assert all(results)

    @pytest.mark.asyncio
    async def test_batch_read_multiple_files(self, provider):
        """Test batch reading of multiple files"""
        await provider.initialize()

        # Create and write files
        for i in range(3):
            node_info = EnhancedNodeInfo(
                name=f"file{i}.txt", is_dir=False, parent_path="/"
            )
            await provider.create_node(node_info)
            await provider.write_file(f"/file{i}.txt", f"content{i}".encode())

        # Batch read
        results = await provider.batch_read(["/file0.txt", "/file1.txt", "/file2.txt"])

        assert len(results) == 3
        assert results[0] == b"content0"
        assert results[1] == b"content1"
        assert results[2] == b"content2"

    @pytest.mark.asyncio
    async def test_batch_write_multiple_files(self, provider):
        """Test batch writing to multiple files"""
        await provider.initialize()

        # Create files first
        for i in range(3):
            node_info = EnhancedNodeInfo(
                name=f"file{i}.txt", is_dir=False, parent_path="/"
            )
            await provider.create_node(node_info)

        # Batch write
        operations = [
            ("/file0.txt", b"content0"),
            ("/file1.txt", b"content1"),
            ("/file2.txt", b"content2"),
        ]
        results = await provider.batch_write(operations)

        assert len(results) == 3
        assert all(results)


class TestRetryMechanism:
    """Test with_retry method"""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self, provider):
        """Test retry succeeds on first attempt"""

        async def success_func():
            return "success"

        result = await provider.with_retry(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self, provider):
        """Test retry succeeds after some failures"""
        attempts = []

        async def fail_twice_then_succeed():
            attempts.append(1)
            if len(attempts) < 3:
                raise Exception("Temporary failure")
            return "success"

        # Set very short retry delay for testing
        provider._retry_delay = 0.01

        result = await provider.with_retry(fail_twice_then_succeed)
        assert result == "success"
        assert len(attempts) == 3

    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self, provider):
        """Test retry raises exception after all attempts fail"""

        async def always_fail():
            raise ValueError("Always fails")

        # Set very short retry delay for testing
        provider._retry_delay = 0.01

        with pytest.raises(ValueError, match="Always fails"):
            await provider.with_retry(always_fail, max_retries=2)

    @pytest.mark.asyncio
    async def test_retry_with_custom_max_retries(self, provider):
        """Test retry with custom max_retries parameter"""
        attempts = []

        async def count_attempts():
            attempts.append(1)
            raise Exception("Fail")

        provider._retry_delay = 0.01

        with pytest.raises(Exception):  # noqa: B017
            await provider.with_retry(count_attempts, max_retries=5)

        assert len(attempts) == 5


class TestContextManager:
    """Test async context manager support"""

    @pytest.mark.asyncio
    async def test_context_manager_initialization(self, provider):
        """Test context manager calls initialize"""
        assert provider.initialized is False

        async with provider as p:
            assert p.initialized is True

        assert provider.initialized is False

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self, provider):
        """Test context manager calls close on exit"""
        async with provider:
            assert provider.initialized is True

        # After exit, close should have been called
        assert provider.initialized is False

    @pytest.mark.asyncio
    async def test_context_manager_exception_handling(self, provider):
        """Test context manager closes even on exception"""
        with pytest.raises(ValueError):
            async with provider:
                assert provider.initialized is True
                raise ValueError("Test exception")

        # Should still close despite exception
        assert provider.initialized is False


class TestBackwardsCompatibility:
    """Test backwards compatibility"""

    def test_storage_provider_alias(self):
        """Test that StorageProvider is an alias for AsyncStorageProvider"""
        from chuk_virtual_fs.provider_base import AsyncStorageProvider, StorageProvider

        assert StorageProvider is AsyncStorageProvider


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
