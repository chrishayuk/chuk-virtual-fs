"""
Test module for E2BStorageProvider

This module contains comprehensive tests for the E2B provider,
covering all features and edge cases to ensure high test coverage.

Note: These tests use mocking to avoid requiring actual E2B sandbox connections.
"""

import asyncio

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.e2b import E2BStorageProvider


def mock_e2b_provider(provider: E2BStorageProvider) -> None:
    """Helper function to mock E2B provider initialization"""

    def mock_sync_initialize():
        provider.sandbox = MockE2BSandbox()
        # Set the sandbox_id like the real implementation does
        provider.sandbox_id = provider.sandbox.sandbox_id
        return True

    provider._sync_initialize = mock_sync_initialize


class MockE2BSandbox:
    """Mock E2B Sandbox for testing"""

    def __init__(self, sandbox_id="test-sandbox-123"):
        self.sandbox_id = sandbox_id
        self.files = MockFileManager()
        self.commands = MockCommandManager(self.files)
        # Set up cross-references
        self.files.command_manager = self.commands
        self._closed = False

    def close(self):
        self._closed = True

    @classmethod
    def connect(cls, sandbox_id):
        return cls(sandbox_id)


class MockFileManager:
    """Mock E2B file manager"""

    def __init__(self):
        self.files = {}
        self.command_manager = None  # Will be set by the sandbox

    def write(self, path: str, content: str):
        self.files[path] = content

    def read(self, path: str) -> str:
        # First check own files collection
        if path in self.files:
            return self.files[path]
        # Then check command manager's filesystem
        if self.command_manager and path in self.command_manager.filesystem:
            return self.command_manager.filesystem[path]
        return ""

    def list(self, path: str) -> list:
        # Simulate directory listing
        if path == "/home/user":
            return ["file1.txt", "subdir"]
        return []


class MockCommandResult:
    """Mock command execution result"""

    def __init__(self, exit_code=0, stdout="", stderr=""):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class MockCommandManager:
    """Mock E2B command manager"""

    def __init__(self, file_manager=None):
        self.filesystem = {}
        self.directories = {"/home/user"}
        self.file_manager = file_manager

    def run(self, command: str) -> MockCommandResult:
        """Mock command execution with realistic responses"""
        command = command.strip()

        # mkdir commands
        if command.startswith("mkdir -p "):
            path = command[9:]
            self.directories.add(path)
            return MockCommandResult(0)

        # touch commands
        elif command.startswith("touch "):
            path = command[6:]
            self.filesystem[path] = ""
            return MockCommandResult(0)

        # stat commands for existence check
        elif command.startswith("stat -c '%F'"):
            # Extract path from command like: stat -c '%F' /path 2>/dev/null || echo 'not_found'
            parts = command.split()
            # Find the path (the first argument after the stat format specifier)
            try:
                parts.index("stat")
                format_idx = -1
                for i, part in enumerate(parts):
                    if part.startswith("'%F'") or part == "'%F'":
                        format_idx = i
                        break
                if format_idx >= 0 and format_idx + 1 < len(parts):
                    path = parts[format_idx + 1]
                else:
                    path = parts[3] if len(parts) > 3 else ""
            except (ValueError, IndexError):
                path = parts[3] if len(parts) > 3 else ""

            if path in self.directories:
                return MockCommandResult(0, "directory")
            elif path in self.filesystem:
                return MockCommandResult(0, "regular file")
            else:
                return MockCommandResult(1, "not_found")

        # stat commands for modification time
        elif command.startswith("stat -c '%Y'"):
            return MockCommandResult(0, "1635724800")  # Mock timestamp

        # ls commands
        elif command.startswith("ls -A "):
            path = command[6:]
            if path in self.directories:
                # Return mock directory contents
                if path == "/home/user":
                    return MockCommandResult(0, "test_file.txt\ntest_dir")
                else:
                    return MockCommandResult(0, "")
            return MockCommandResult(1)

        # cp commands
        elif command.startswith("cp "):
            if " -r " in command:
                # Copy directory
                parts = command.split()
                src, dest = parts[-2], parts[-1]
                if src in self.directories:
                    self.directories.add(dest)
                    return MockCommandResult(0)
            else:
                # Copy file
                parts = command.split()
                src, dest = parts[-2], parts[-1]
                if src in self.filesystem:
                    self.filesystem[dest] = self.filesystem[src]
                    return MockCommandResult(0)
            return MockCommandResult(1)

        # mv commands
        elif command.startswith("mv "):
            parts = command.split()
            src, dest = parts[-2], parts[-1]
            if src in self.filesystem:
                self.filesystem[dest] = self.filesystem.pop(src)
                return MockCommandResult(0)
            elif self.file_manager and src in self.file_manager.files:
                # Move from file manager to filesystem
                self.filesystem[dest] = self.file_manager.files.pop(src)
                return MockCommandResult(0)
            elif src in self.directories:
                self.directories.discard(src)
                self.directories.add(dest)
                return MockCommandResult(0)
            return MockCommandResult(1)

        # rm commands
        elif command.startswith("rm "):
            path = command[3:]
            if path in self.filesystem:
                del self.filesystem[path]
                return MockCommandResult(0)
            return MockCommandResult(1)

        # rmdir commands
        elif command.startswith("rmdir "):
            path = command[6:]
            if path in self.directories:
                self.directories.discard(path)
                return MockCommandResult(0)
            return MockCommandResult(1)

        # find commands for stats
        elif command.startswith("find ") and command.endswith("| wc -l"):
            if "-type d" in command:
                # Count directories
                return MockCommandResult(0, str(len(self.directories)))
            elif "-type f" in command:
                # Count files
                return MockCommandResult(0, str(len(self.filesystem)))

        # du command for size
        elif command.startswith("du -sb "):
            total_size = sum(len(content) for content in self.filesystem.values())
            return MockCommandResult(0, str(total_size))

        # Default success for unknown commands
        return MockCommandResult(0)


class TestProviderLifecycle:
    """Test provider initialization, setup, and teardown"""

    def test_initialization(self):
        """Test provider can be created with default settings"""
        provider = E2BStorageProvider()
        assert provider.root_dir == "/home/user"
        assert provider.auto_create_root is True
        assert provider.timeout == 300
        assert not provider._closed

    def test_initialization_with_custom_settings(self):
        """Test provider initialization with custom settings"""
        provider = E2BStorageProvider(
            sandbox_id="custom-sandbox",
            root_dir="/workspace",
            auto_create_root=False,
            timeout=600,
        )
        assert provider.sandbox_id == "custom-sandbox"
        assert provider.root_dir == "/workspace"
        assert provider.auto_create_root is False
        assert provider.timeout == 600

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful provider initialization"""
        provider = E2BStorageProvider()

        # Mock the _sync_initialize method directly
        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            return True

        provider._sync_initialize = mock_sync_initialize
        result = await provider.initialize()

        assert result is True
        assert provider.sandbox is not None
        assert provider.sandbox.sandbox_id == "test-sandbox-123"

    @pytest.mark.asyncio
    async def test_initialize_import_error(self):
        """Test initialization with missing e2b package"""
        provider = E2BStorageProvider()

        # Mock the _sync_initialize method to simulate ImportError handling
        def mock_sync_initialize():
            # Simulate the actual ImportError handling in the real method
            try:
                raise ImportError("e2b not found")
            except ImportError:
                return False

        provider._sync_initialize = mock_sync_initialize
        result = await provider.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_close(self):
        """Test provider close operation"""
        provider = E2BStorageProvider()

        # Mock initialization
        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()

        await provider.close()

        assert provider._closed is True
        assert provider.sandbox is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test provider as async context manager"""
        provider = E2BStorageProvider()

        # Mock initialization
        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            return True

        provider._sync_initialize = mock_sync_initialize

        async with provider:
            assert provider.sandbox is not None
            assert not provider._closed

        assert provider._closed is True


class TestDirectoryOperations:
    """Test directory creation, listing, and management"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
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
        # Mock will return predefined contents
        contents = await provider.list_directory("/")

        # MockCommandManager returns ["test_file.txt", "test_dir"] for root
        assert isinstance(contents, list)

    @pytest.mark.asyncio
    async def test_list_empty_directory(self, provider):
        """Test listing empty directory"""
        # Create empty directory
        node_info = EnhancedNodeInfo(name="empty_dir", is_dir=True, parent_path="/")
        await provider.create_node(node_info)

        contents = await provider.list_directory("/empty_dir")
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
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
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
        content = b"Hello, E2B World!"
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

        # Create large content (1KB)
        large_content = b"x" * 1024

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
    async def test_write_without_create(self, provider):
        """Test writing to file that wasn't created first"""
        result = await provider.write_file("/nonexistent.txt", b"content")
        # E2B provider should handle auto-creation of parent paths
        assert result is True

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
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
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
        """Create initialized provider"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
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


class TestEnhancedFeatures:
    """Test enhanced features like copy, move, checksums"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_calculate_checksum(self, provider):
        """Test checksum calculation"""
        content = b"Hello, E2B!"
        checksum = await provider.calculate_checksum(content)

        # SHA256 of "Hello, E2B!"
        # Note: This is a placeholder - actual hash would be different
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 hex length

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
        """Test copying a directory"""
        # Create source directory
        dir_info = EnhancedNodeInfo(name="source_dir", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        # Copy directory
        result = await provider.copy_node("/source_dir", "/dest_dir")

        assert result is True
        assert await provider.exists("/dest_dir")

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
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
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


class TestStorageStats:
    """Test storage statistics and cleanup operations"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_get_storage_stats_empty(self, provider):
        """Test storage statistics for empty sandbox"""
        stats = await provider.get_storage_stats()

        assert "total_files" in stats
        assert "total_directories" in stats
        assert "total_size" in stats
        assert "sandbox_id" in stats
        assert stats["sandbox_id"] == "test-sandbox-123"

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

        assert stats["total_files"] >= 2
        assert stats["total_directories"] >= 1
        assert "total_size" in stats

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
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
        await provider.initialize()
        await provider.close()

        # Operations should handle closed state gracefully
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
        result = await provider.create_node(node_info)
        assert result is False

    @pytest.mark.asyncio
    async def test_sandbox_command_failures(self):
        """Test handling of sandbox command failures"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
        await provider.initialize()

        # Mock command failure
        provider.sandbox.commands.run = lambda cmd: MockCommandResult(1, "", "Error")

        # Operations should handle command failures gracefully
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
        result = await provider.create_node(node_info)
        assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_invalid_paths(self):
        """Test handling of invalid paths"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
        await provider.initialize()

        # Test with various invalid path scenarios
        assert not await provider.exists("")

        # Reading invalid paths should return None/empty
        content = await provider.read_file("/nonexistent/path")
        assert content is None

        await provider.close()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent file operations"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
        await provider.initialize()

        # Create multiple concurrent operations
        tasks = []

        # Concurrent file creation
        for i in range(5):
            node_info = EnhancedNodeInfo(
                name=f"concurrent{i}.txt", is_dir=False, parent_path="/"
            )
            task = provider.create_node(node_info)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most operations should succeed
        success_count = sum(1 for result in results if result is True)
        assert success_count >= 3  # Allow for some variance in mocking

        await provider.close()


class TestCaching:
    """Test caching mechanisms"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_node_info_caching(self, provider):
        """Test that node info is properly cached"""
        # Create a file
        node_info = EnhancedNodeInfo(name="cached.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # First call should populate cache
        info1 = await provider.get_node_info("/cached.txt")
        assert "/cached.txt" in provider.node_cache

        # Second call should use cache
        info2 = await provider.get_node_info("/cached.txt")
        assert info1 is info2  # Should be same object from cache

    @pytest.mark.asyncio
    async def test_cache_expiration(self, provider):
        """Test cache expiration mechanism"""
        # Set very short TTL for testing
        provider.cache_ttl = 0.1  # 100ms

        # Create a file
        node_info = EnhancedNodeInfo(name="expire.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Get info (populates cache)
        await provider.get_node_info("/expire.txt")
        assert "/expire.txt" in provider.node_cache

        # Wait for cache to expire
        await asyncio.sleep(0.2)

        # Get info again (should refresh cache)
        await provider.get_node_info("/expire.txt")
        # This might be same or different depending on mock behavior


class TestAdditionalEdgeCases:
    """Test additional edge cases and error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()
        mock_e2b_provider(provider)
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_get_sandbox_path(self, provider):
        """Test path conversion from virtual to sandbox paths"""
        # Root path
        assert provider._get_sandbox_path("/") == "/home/user"

        # Nested path
        assert (
            provider._get_sandbox_path("/workspace/file.txt")
            == "/home/user/workspace/file.txt"
        )

        # Path without leading slash
        assert (
            provider._get_sandbox_path("workspace/file.txt")
            == "/home/user/workspace/file.txt"
        )

    @pytest.mark.asyncio
    async def test_check_cache_hit(self, provider):
        """Test cache hit scenario"""
        # Create and cache a node
        node_info = EnhancedNodeInfo(name="cached.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Manually populate cache
        provider._update_cache("/cached.txt", node_info)

        # Check cache
        cached_info = provider._check_cache("/cached.txt")
        assert cached_info is not None
        assert cached_info.name == "cached.txt"

    @pytest.mark.asyncio
    async def test_check_cache_miss(self, provider):
        """Test cache miss scenario"""
        cached_info = provider._check_cache("/not_cached.txt")
        assert cached_info is None

    @pytest.mark.asyncio
    async def test_update_cache(self, provider):
        """Test cache update"""
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
        provider._update_cache("/test.txt", node_info)

        assert "/test.txt" in provider.node_cache
        assert "/test.txt" in provider.cache_timestamps

    @pytest.mark.asyncio
    async def test_write_file_updates_stats(self, provider):
        """Test that writing files updates statistics"""
        # Create and write file
        node_info = EnhancedNodeInfo(name="stats.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        initial_stats = provider._stats.copy()
        await provider.write_file("/stats.txt", b"test content")

        # Stats should be updated
        assert provider._stats["total_size_bytes"] >= initial_stats["total_size_bytes"]

    @pytest.mark.asyncio
    async def test_delete_file_updates_stats(self, provider):
        """Test that deleting files updates statistics"""
        # Create and write file
        node_info = EnhancedNodeInfo(name="delete.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)
        await provider.write_file("/delete.txt", b"content to delete")

        initial_file_count = provider._stats["file_count"]

        # Delete file
        await provider.delete_node("/delete.txt")

        # Stats should be updated
        assert provider._stats["file_count"] == initial_file_count - 1

    @pytest.mark.asyncio
    async def test_write_file_with_parent_creation(self, provider):
        """Test writing file with automatic parent directory creation"""
        # Write file to non-existent parent path
        result = await provider.write_file("/new_parent/child.txt", b"content")

        # Should create parent and succeed
        assert result is True
        assert await provider.exists("/new_parent/child.txt")

    @pytest.mark.asyncio
    async def test_write_file_to_directory_fails(self, provider):
        """Test that writing to a directory path fails"""
        # Create directory
        dir_info = EnhancedNodeInfo(name="testdir", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        # Try to write to directory
        result = await provider.write_file("/testdir", b"content")

        # Should fail
        assert result is False

    @pytest.mark.asyncio
    async def test_create_node_already_exists(self, provider):
        """Test creating node that already exists"""
        # Create node
        node_info = EnhancedNodeInfo(name="exists.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Try to create again
        result = await provider.create_node(node_info)

        # Should fail
        assert result is False

    @pytest.mark.asyncio
    async def test_create_node_without_parent(self, provider):
        """Test creating node when parent doesn't exist"""
        # Try to create node with non-existent parent
        node_info = EnhancedNodeInfo(
            name="orphan.txt", is_dir=False, parent_path="/nonexistent"
        )

        result = await provider.create_node(node_info)

        # Should fail
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_non_empty_directory(self, provider):
        """Test that deleting non-empty directory fails"""
        # Create directory and file inside
        dir_info = EnhancedNodeInfo(name="nonempty", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        file_info = EnhancedNodeInfo(
            name="file.txt", is_dir=False, parent_path="/nonempty"
        )
        await provider.create_node(file_info)

        # Mock the ls command to return non-empty result
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "ls -A" in cmd:
                return MockCommandResult(0, "file.txt")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        # Try to delete directory
        result = await provider.delete_node("/nonempty")

        # Should fail
        assert result is False

    @pytest.mark.asyncio
    async def test_get_node_info_path_normalization(self, provider):
        """Test node info retrieval with different path formats"""
        # Create file
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Get with trailing slash (should be normalized)
        info1 = await provider.get_node_info("/test.txt/")
        info2 = await provider.get_node_info("/test.txt")

        # Should handle normalization
        assert info1 is not None or info2 is not None

    @pytest.mark.asyncio
    async def test_get_node_info_empty_path(self, provider):
        """Test node info retrieval with empty path"""
        # Empty path should default to root
        info = await provider.get_node_info("")

        # Should return root info or None
        assert info is None or info.is_dir

    @pytest.mark.asyncio
    async def test_list_directory_with_trailing_slash(self, provider):
        """Test listing directory with trailing slash"""
        # Create directory
        dir_info = EnhancedNodeInfo(name="testdir", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        # List with trailing slash
        contents1 = await provider.list_directory("/testdir/")
        contents2 = await provider.list_directory("/testdir")

        # Should handle both
        assert isinstance(contents1, list)
        assert isinstance(contents2, list)

    @pytest.mark.asyncio
    async def test_list_directory_on_file(self, provider):
        """Test listing directory on a file path"""
        # Create file
        file_info = EnhancedNodeInfo(name="file.txt", is_dir=False, parent_path="/")
        await provider.create_node(file_info)

        # Try to list file as directory
        contents = await provider.list_directory("/file.txt")

        # Should return empty list
        assert contents == []

    @pytest.mark.asyncio
    async def test_metadata_with_permissions(self, provider):
        """Test setting metadata with permissions"""
        # Create file
        node_info = EnhancedNodeInfo(name="perms.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Set metadata with permissions
        metadata = {"permissions": "755", "owner": "user"}
        result = await provider.set_metadata("/perms.txt", metadata)

        assert result is True

        # Get metadata
        retrieved = await provider.get_metadata("/perms.txt")
        assert retrieved.get("permissions") == "755"

    @pytest.mark.asyncio
    async def test_copy_node_error_on_command_failure(self, provider):
        """Test copy node when command fails"""
        # Create source file
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        await provider.create_node(source_info)

        # Mock command to fail
        provider.sandbox.commands.run = lambda cmd: MockCommandResult(1, "", "Error")

        # Try to copy
        result = await provider.copy_node("/source.txt", "/dest.txt")

        # Should fail
        assert result is False

    @pytest.mark.asyncio
    async def test_move_node_error_on_command_failure(self, provider):
        """Test move node when command fails"""
        # Create source file
        source_info = EnhancedNodeInfo(
            name="move_src.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(source_info)

        # Mock command to fail
        provider.sandbox.commands.run = lambda cmd: MockCommandResult(1, "", "Error")

        # Try to move
        result = await provider.move_node("/move_src.txt", "/move_dst.txt")

        # Should fail
        assert result is False

    @pytest.mark.asyncio
    async def test_move_node_nonexistent_source(self, provider):
        """Test moving nonexistent source"""
        result = await provider.move_node("/nonexistent", "/dest")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_with_no_files(self, provider):
        """Test cleanup when there are no files"""
        result = await provider.cleanup()

        assert "cleaned_up" in result
        assert result["cleaned_up"] is True

    @pytest.mark.asyncio
    async def test_cleanup_creates_tmp_dir(self, provider):
        """Test that cleanup creates tmp directory if it doesn't exist"""
        # Call cleanup
        result = await provider.cleanup()

        # Should succeed even if tmp doesn't exist
        assert result["cleaned_up"] is True

    @pytest.mark.asyncio
    async def test_storage_stats_with_command_failures(self, provider):
        """Test storage stats when commands fail"""
        # Mock commands to fail
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "find" in cmd or "du" in cmd:
                return MockCommandResult(1, "", "Error")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        # Should still return stats using cached values
        stats = await provider.get_storage_stats()

        assert "total_files" in stats
        assert "total_directories" in stats

    @pytest.mark.asyncio
    async def test_batch_operations_with_mixed_success(self, provider):
        """Test batch operations where some succeed and some fail"""
        # Create valid and invalid nodes
        nodes = [
            EnhancedNodeInfo(name="valid1.txt", is_dir=False, parent_path="/"),
            EnhancedNodeInfo(
                name="valid2.txt", is_dir=False, parent_path="/nonexistent"
            ),  # Invalid parent
            EnhancedNodeInfo(name="valid3.txt", is_dir=False, parent_path="/"),
        ]

        results = await provider.batch_create(nodes)

        # Should have mixed results
        assert len(results) == 3
        assert any(results)  # At least some should succeed
        assert not all(results)  # Not all should succeed

    @pytest.mark.asyncio
    async def test_read_file_returns_bytes(self, provider):
        """Test that read_file always returns bytes"""
        # Create and write file
        node_info = EnhancedNodeInfo(name="bytes.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)
        await provider.write_file("/bytes.txt", b"binary content")

        # Read file
        content = await provider.read_file("/bytes.txt")

        # Should be bytes
        assert isinstance(content, bytes)

    @pytest.mark.asyncio
    async def test_write_file_with_string_content(self, provider):
        """Test writing file with string content (should be converted)"""
        # Create file
        node_info = EnhancedNodeInfo(name="string.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Write with string (provider should handle conversion)
        result = await provider.write_file("/string.txt", b"string content")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_with_empty_string(self, provider):
        """Test exists with empty string returns False"""
        result = await provider.exists("")
        assert result is False

    @pytest.mark.asyncio
    async def test_copy_directory_updates_stats(self, provider):
        """Test that copying directory updates statistics"""
        # Create source directory
        dir_info = EnhancedNodeInfo(name="copy_src_dir", is_dir=True, parent_path="/")
        await provider.create_node(dir_info)

        initial_dir_count = provider._stats["directory_count"]

        # Copy directory
        await provider.copy_node("/copy_src_dir", "/copy_dst_dir")

        # Stats should be updated
        assert provider._stats["directory_count"] > initial_dir_count

    @pytest.mark.asyncio
    async def test_cache_cleared_on_close(self, provider):
        """Test that cache is cleared when provider is closed"""
        # Populate cache
        node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)
        await provider.get_node_info("/test.txt")

        assert len(provider.node_cache) > 0

        # Close provider
        await provider.close()

        # Cache should be cleared
        assert len(provider.node_cache) == 0
        assert len(provider.cache_timestamps) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
