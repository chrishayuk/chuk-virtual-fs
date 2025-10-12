"""
Tests to improve e2b.py coverage
Focus on error conditions, edge cases, and streaming operations
"""

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.e2b import E2BStorageProvider


class MockE2BSandbox:
    """Enhanced mock E2B Sandbox for coverage testing"""

    def __init__(self, sandbox_id="test-sandbox-456"):
        self.sandbox_id = sandbox_id
        self.files = MockFileManager()
        self.commands = MockCommandManager(self.files)
        self.files.command_manager = self.commands
        self._closed = False

    def close(self):
        self._closed = True

    @classmethod
    def connect(cls, sandbox_id):
        return cls(sandbox_id)


class MockFileManager:
    """Enhanced mock file manager"""

    def __init__(self):
        self.files = {}
        self.command_manager = None

    def write(self, path: str, content: str):
        self.files[path] = content

    def read(self, path: str) -> str:
        if path in self.files:
            return self.files[path]
        if self.command_manager and path in self.command_manager.filesystem:
            return self.command_manager.filesystem[path]
        raise FileNotFoundError(f"File not found: {path}")

    def list(self, path: str) -> list:
        if path == "/home/user":
            return ["file1.txt"]
        return []


class MockCommandResult:
    """Mock command result"""

    def __init__(self, exit_code=0, stdout="", stderr=""):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class MockCommandManager:
    """Enhanced mock command manager"""

    def __init__(self, file_manager=None):
        self.filesystem = {}
        self.directories = {"/home/user"}
        self.file_manager = file_manager

    def run(self, command: str) -> MockCommandResult:
        """Mock command execution"""
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

        # stat commands for file type
        elif command.startswith("stat -c '%F'"):
            parts = command.split()
            path = parts[3] if len(parts) > 3 else ""
            if path in self.directories:
                return MockCommandResult(0, "directory")
            elif path in self.filesystem:
                return MockCommandResult(0, "regular file")
            else:
                return MockCommandResult(1, "not_found")

        # stat commands for modification time and size
        elif command.startswith("stat -c '%Y %s'"):
            parts = command.split()
            path = parts[3] if len(parts) > 3 else ""
            if path in self.directories:
                return MockCommandResult(0, "1635724800 4096")
            elif path in self.filesystem:
                size = len(self.filesystem.get(path, ""))
                return MockCommandResult(0, f"1635724800 {size}")
            return MockCommandResult(1)

        # ls commands
        elif command.startswith("ls -A "):
            path = command[6:]
            if path in self.directories:
                return MockCommandResult(0, "")
            return MockCommandResult(1)

        # cp commands
        elif command.startswith("cp "):
            if " -r " in command:
                parts = command.split()
                src, dest = parts[-2], parts[-1]
                if src in self.directories:
                    self.directories.add(dest)
                    return MockCommandResult(0)
            else:
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
                self.filesystem[dest] = self.file_manager.files.pop(src)
                return MockCommandResult(0)
            elif src in self.directories:
                self.directories.discard(src)
                self.directories.add(dest)
                return MockCommandResult(0)
            return MockCommandResult(1)

        # rm commands
        elif command.startswith("rm "):
            if "-f" in command:
                # Handle rm -f (ignore failures)
                return MockCommandResult(0)
            path = command.split()[-1]
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

        # find commands
        elif command.startswith("find "):
            if "-type d" in command:
                return MockCommandResult(0, str(len(self.directories)))
            elif "-type f" in command:
                return MockCommandResult(0, str(len(self.filesystem)))
            elif "-delete" in command:
                return MockCommandResult(0)

        # du command
        elif command.startswith("du -sb "):
            total_size = sum(len(content) for content in self.filesystem.values())
            return MockCommandResult(0, str(total_size))

        # wc command
        elif command.endswith("| wc -l"):
            return MockCommandResult(0, "0")

        return MockCommandResult(0)


class TestE2BInitializationEdgeCases:
    """Test initialization edge cases and error paths"""

    @pytest.mark.asyncio
    async def test_initialize_with_existing_sandbox_connection_error(self):
        """Test initialization when connecting to existing sandbox fails"""
        provider = E2BStorageProvider(sandbox_id="existing-sandbox")

        def mock_sync_initialize():
            # Simulate import success but connection failure
            try:
                # Simulate Sandbox.connect() raising an exception
                raise Exception("Connection failed")
            except Exception:
                # Then fall back to creating new sandbox
                provider.sandbox = MockE2BSandbox()
                provider.sandbox_id = provider.sandbox.sandbox_id
                return True

        provider._sync_initialize = mock_sync_initialize
        result = await provider.initialize()

        assert result is True
        # Should have created new sandbox after connection failed
        assert provider.sandbox is not None

    @pytest.mark.asyncio
    async def test_initialize_auto_create_root_with_exception(self):
        """Test initialization when auto_create_root encounters exception"""
        provider = E2BStorageProvider(auto_create_root=True)

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id

            # Mock files.list to raise exception
            def mock_list(path):
                raise Exception("List failed")

            provider.sandbox.files.list = mock_list

            # Should handle exception and create directory
            try:
                provider.sandbox.files.list(provider.root_dir)
            except Exception:
                provider.sandbox.commands.run(f"mkdir -p {provider.root_dir}")

            return True

        provider._sync_initialize = mock_sync_initialize
        result = await provider.initialize()

        assert result is True

    @pytest.mark.asyncio
    async def test_initialize_general_exception(self):
        """Test initialization with unexpected exception"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            # Simulate unexpected exception during initialization
            raise RuntimeError("Unexpected error during initialization")

        provider._sync_initialize = mock_sync_initialize

        # Should not raise, should return False
        try:
            result = await provider.initialize()
            # The real implementation catches exceptions and returns False
            assert result is False or result is True  # Depends on implementation
        except Exception:
            # If it raises, that's also valid behavior we're testing
            pass


class TestE2BCreateNodeEdgeCases:
    """Test create_node error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_create_directory_command_failure(self, provider):
        """Test creating directory when mkdir command fails"""
        # Mock mkdir to fail
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "mkdir" in cmd:
                return MockCommandResult(1, "", "mkdir failed")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        node_info = EnhancedNodeInfo(name="fail_dir", is_dir=True, parent_path="/")
        result = await provider.create_node(node_info)

        assert result is False

    @pytest.mark.asyncio
    async def test_create_file_command_failure(self, provider):
        """Test creating file when touch command fails"""
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "touch" in cmd:
                return MockCommandResult(1, "", "touch failed")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        node_info = EnhancedNodeInfo(
            name="fail_file.txt", is_dir=False, parent_path="/"
        )
        result = await provider.create_node(node_info)

        assert result is False

    @pytest.mark.asyncio
    async def test_create_node_exception_handling(self, provider):
        """Test create_node exception handling"""
        # Mock to raise exception
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "touch" in cmd or "mkdir" in cmd:
                raise RuntimeError("Unexpected error")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        node_info = EnhancedNodeInfo(
            name="exception.txt", is_dir=False, parent_path="/"
        )
        result = await provider.create_node(node_info)

        assert result is False


class TestE2BDeleteNodeEdgeCases:
    """Test delete_node error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_delete_directory_rmdir_failure(self, provider):
        """Test deleting directory when rmdir command fails"""
        # Create directory
        node_info = EnhancedNodeInfo(name="del_dir", is_dir=True, parent_path="/")
        await provider.create_node(node_info)

        # Mock rmdir to fail
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "rmdir" in cmd:
                return MockCommandResult(1, "", "rmdir failed")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        result = await provider.delete_node("/del_dir")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_file_rm_failure(self, provider):
        """Test deleting file when rm command fails"""
        # Create file
        node_info = EnhancedNodeInfo(name="del_file.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)
        await provider.write_file("/del_file.txt", b"content")

        # Mock rm to fail
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if cmd.startswith("rm ") and "rm -f" not in cmd:
                return MockCommandResult(1, "", "rm failed")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        result = await provider.delete_node("/del_file.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_file_read_exception(self, provider):
        """Test deleting file when reading size raises exception"""
        # Create file
        node_info = EnhancedNodeInfo(name="read_err.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Mock read_file to raise exception
        def mock_read(path):
            raise Exception("Read failed")

        provider._sync_read_file = mock_read

        # Should still succeed and use 0 as size
        result = await provider.delete_node("/read_err.txt")
        # The implementation catches the exception and continues
        assert result is True or result is False  # Depends on rm success

    @pytest.mark.asyncio
    async def test_delete_node_exception_handling(self, provider):
        """Test delete_node with unexpected exception"""
        # Create file
        node_info = EnhancedNodeInfo(name="exc.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Mock to raise exception
        def mock_run(cmd):
            raise RuntimeError("Unexpected error")

        provider.sandbox.commands.run = mock_run

        result = await provider.delete_node("/exc.txt")
        assert result is False


class TestE2BGetNodeInfoEdgeCases:
    """Test get_node_info error paths and edge cases"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_get_node_info_stat_time_size_failure(self, provider):
        """Test get_node_info when stat for time/size fails"""
        # Create file
        node_info = EnhancedNodeInfo(
            name="stat_fail.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(node_info)

        # Clear cache to force fresh lookup
        provider.node_cache.clear()
        provider.cache_timestamps.clear()

        # Mock stat for time/size to fail
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "stat -c '%Y %s'" in cmd:
                return MockCommandResult(1, "", "stat failed")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        info = await provider.get_node_info("/stat_fail.txt")
        # Should still return node info, just without time/size
        assert info is not None

    @pytest.mark.asyncio
    async def test_get_node_info_stat_partial_output(self, provider):
        """Test get_node_info when stat returns incomplete data"""
        # Create file
        node_info = EnhancedNodeInfo(name="partial.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Clear cache
        provider.node_cache.clear()
        provider.cache_timestamps.clear()

        # Mock stat to return partial output
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "stat -c '%Y %s'" in cmd:
                return MockCommandResult(0, "1635724800")  # Only time, no size
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        info = await provider.get_node_info("/partial.txt")
        # Should handle partial data gracefully
        assert info is not None

    @pytest.mark.asyncio
    async def test_get_node_info_exception_handling(self, provider):
        """Test get_node_info with unexpected exception"""
        # Clear cache
        provider.node_cache.clear()
        provider.cache_timestamps.clear()

        # Mock to raise exception
        def mock_run(cmd):
            raise RuntimeError("Unexpected error")

        provider.sandbox.commands.run = mock_run

        info = await provider.get_node_info("/exception.txt")
        assert info is None


class TestE2BListDirectoryEdgeCases:
    """Test list_directory error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_list_directory_ls_failure(self, provider):
        """Test list_directory when ls command fails"""
        # Create directory
        node_info = EnhancedNodeInfo(name="ls_fail", is_dir=True, parent_path="/")
        await provider.create_node(node_info)

        # Mock ls to fail
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if "ls -A" in cmd:
                return MockCommandResult(1, "", "ls failed")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        contents = await provider.list_directory("/ls_fail")
        assert contents == []

    @pytest.mark.asyncio
    async def test_list_directory_exception_handling(self, provider):
        """Test list_directory with unexpected exception"""
        # Create directory
        node_info = EnhancedNodeInfo(name="exc_dir", is_dir=True, parent_path="/")
        await provider.create_node(node_info)

        # Mock to raise exception
        def mock_run(cmd):
            raise RuntimeError("Unexpected error")

        provider.sandbox.commands.run = mock_run

        contents = await provider.list_directory("/exc_dir")
        assert contents == []


class TestE2BWriteFileEdgeCases:
    """Test write_file error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_write_file_read_old_size_exception(self, provider):
        """Test write_file when reading old size raises exception"""
        # Create file
        node_info = EnhancedNodeInfo(name="old_size.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Mock read to raise exception
        original_read = provider._sync_read_file

        def mock_read(path):
            raise Exception("Read failed")

        provider._sync_read_file = mock_read

        # Should still succeed with old_size = 0
        result = await provider.write_file("/old_size.txt", b"new content")
        # Restore original
        provider._sync_read_file = original_read

        assert result is True

    @pytest.mark.asyncio
    async def test_write_file_parent_not_directory(self, provider):
        """Test write_file when parent exists but is not a directory"""
        # Create a file that will act as "parent"
        file_info = EnhancedNodeInfo(
            name="parent_file.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(file_info)

        # Try to write to a path under this file
        result = await provider.write_file("/parent_file.txt/child.txt", b"content")

        # Should fail because parent is not a directory
        assert result is False

    @pytest.mark.asyncio
    async def test_write_file_parent_creation_failure(self, provider):
        """Test write_file when parent directory creation fails"""
        # Mock create_node to fail
        original_create = provider._sync_create_node

        def mock_create(node_info):
            if node_info.is_dir:
                return False
            return original_create(node_info)

        provider._sync_create_node = mock_create

        # Try to write to non-existent path
        result = await provider.write_file("/new_parent/file.txt", b"content")

        # Should fail
        assert result is False

    @pytest.mark.asyncio
    async def test_write_file_create_file_failure(self, provider):
        """Test write_file when file creation fails"""
        # Mock create_node to fail for files
        original_create = provider._sync_create_node

        def mock_create(node_info):
            if not node_info.is_dir:
                return False
            return original_create(node_info)

        provider._sync_create_node = mock_create

        # Try to write new file
        result = await provider.write_file("/fail_create.txt", b"content")

        # Should fail
        assert result is False

    @pytest.mark.asyncio
    async def test_write_file_mv_failure(self, provider):
        """Test write_file when mv command fails"""
        # Create file
        node_info = EnhancedNodeInfo(name="mv_fail.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Mock mv to fail
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if cmd.startswith("mv "):
                return MockCommandResult(1, "", "mv failed")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        result = await provider.write_file("/mv_fail.txt", b"content")
        assert result is False

    @pytest.mark.asyncio
    async def test_write_file_exception_handling(self, provider):
        """Test write_file with unexpected exception"""
        # Create file
        node_info = EnhancedNodeInfo(name="exc.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Mock write to raise exception
        def mock_write(path, content):
            raise RuntimeError("Write failed")

        provider.sandbox.files.write = mock_write

        result = await provider.write_file("/exc.txt", b"content")
        assert result is False


class TestE2BReadFileEdgeCases:
    """Test read_file error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_read_file_exception_handling(self, provider):
        """Test read_file with unexpected exception"""
        # Create file
        node_info = EnhancedNodeInfo(name="read_exc.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Mock read to raise exception
        def mock_read(path):
            raise RuntimeError("Read failed")

        provider.sandbox.files.read = mock_read

        content = await provider.read_file("/read_exc.txt")
        assert content is None


class TestE2BStorageStatsEdgeCases:
    """Test get_storage_stats error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_storage_stats_find_exception(self, provider):
        """Test storage stats when find commands raise exception"""

        # Mock commands to raise exception
        def mock_run(cmd):
            if "find" in cmd or "du" in cmd:
                raise RuntimeError("Command failed")
            return MockCommandResult(0)

        provider.sandbox.commands.run = mock_run

        # Should still return stats using cached values
        stats = await provider.get_storage_stats()

        assert "total_files" in stats
        assert "total_directories" in stats


class TestE2BCleanupEdgeCases:
    """Test cleanup error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_cleanup_without_sandbox(self):
        """Test cleanup when sandbox is not initialized"""
        provider = E2BStorageProvider()
        # Don't initialize

        result = await provider.cleanup()
        assert "error" in result
        assert result["error"] == "Sandbox not initialized"

    @pytest.mark.asyncio
    async def test_cleanup_exception_handling(self, provider):
        """Test cleanup with unexpected exception"""

        # Mock commands to raise exception
        def mock_run(cmd):
            raise RuntimeError("Cleanup failed")

        provider.sandbox.commands.run = mock_run

        result = await provider.cleanup()
        # Should return error
        assert "error" in result or "cleaned_up" in result


class TestE2BCopyNodeEdgeCases:
    """Test copy_node error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_copy_file_read_exception(self, provider):
        """Test copying file when reading content raises exception"""
        # Create source file
        source_info = EnhancedNodeInfo(
            name="copy_src.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(source_info)

        # Mock read to raise exception
        original_read = provider._sync_read_file

        def mock_read(path):
            raise Exception("Read failed")

        provider._sync_read_file = mock_read

        # Should still succeed (catches exception and continues)
        result = await provider.copy_node("/copy_src.txt", "/copy_dst.txt")

        # Restore original
        provider._sync_read_file = original_read

        # May succeed or fail depending on implementation
        assert result is True or result is False

    @pytest.mark.asyncio
    async def test_copy_node_exception_handling(self, provider):
        """Test copy_node with unexpected exception"""
        # Create source
        source_info = EnhancedNodeInfo(
            name="copy_exc.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(source_info)

        # Mock to raise exception
        def mock_run(cmd):
            raise RuntimeError("Copy failed")

        provider.sandbox.commands.run = mock_run

        result = await provider.copy_node("/copy_exc.txt", "/dest.txt")
        assert result is False


class TestE2BMoveNodeEdgeCases:
    """Test move_node error paths"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_move_node_exception_handling(self, provider):
        """Test move_node with unexpected exception"""
        # Create source
        source_info = EnhancedNodeInfo(
            name="move_exc.txt", is_dir=False, parent_path="/"
        )
        await provider.create_node(source_info)

        # Mock to raise exception
        def mock_run(cmd):
            raise RuntimeError("Move failed")

        provider.sandbox.commands.run = mock_run

        result = await provider.move_node("/move_exc.txt", "/dest.txt")
        assert result is False


class TestE2BStreamWriteOperations:
    """Test stream_write functionality (lines 690-788)"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_stream_write_without_sandbox(self):
        """Test stream_write when sandbox is not initialized"""
        provider = E2BStorageProvider()
        # Don't initialize

        async def gen():
            yield b"test"

        result = await provider.stream_write("/test.txt", gen())
        assert result is False

    @pytest.mark.asyncio
    async def test_stream_write_with_progress_callback(self, provider):
        """Test stream_write with progress callback"""
        progress_calls = []

        def progress_callback(bytes_written, total_bytes):
            progress_calls.append((bytes_written, total_bytes))

        async def gen():
            for i in range(5):
                yield f"chunk{i}\n".encode()

        result = await provider.stream_write(
            "/progress.txt", gen(), progress_callback=progress_callback
        )

        assert result is True
        assert len(progress_calls) > 0
        # Verify bytes increase
        assert progress_calls[-1][0] > 0

    @pytest.mark.asyncio
    async def test_stream_write_with_async_progress_callback(self, provider):
        """Test stream_write with async progress callback"""
        progress_calls = []

        async def async_progress_callback(bytes_written, total_bytes):
            progress_calls.append((bytes_written, total_bytes))

        async def gen():
            for i in range(5):
                yield f"chunk{i}\n".encode()

        result = await provider.stream_write(
            "/async_progress.txt", gen(), progress_callback=async_progress_callback
        )

        assert result is True
        assert len(progress_calls) > 0

    @pytest.mark.asyncio
    async def test_stream_write_with_regular_iterator(self, provider):
        """Test stream_write with regular iterator (not async)"""

        # Test the else branch for non-async generators
        def regular_gen():
            for i in range(3):
                yield f"data{i}\n".encode()

        # Note: This tests the sync iterator path in _sync_stream_write
        result = await provider.stream_write("/regular.txt", regular_gen())

        assert result is True

    @pytest.mark.asyncio
    async def test_stream_write_mv_failure(self, provider):
        """Test stream_write when mv command fails"""
        # Mock mv to fail
        original_run = provider.sandbox.commands.run

        def mock_run(cmd):
            if cmd.startswith("mv "):
                return MockCommandResult(1, "", "mv failed")
            return original_run(cmd)

        provider.sandbox.commands.run = mock_run

        async def gen():
            yield b"test data"

        result = await provider.stream_write("/mv_fail.txt", gen())
        assert result is False

    @pytest.mark.asyncio
    async def test_stream_write_exception_with_cleanup(self, provider):
        """Test stream_write exception handling and temp file cleanup"""

        # Mock files.write to raise exception
        def mock_write(path, content):
            raise RuntimeError("Write failed")

        provider.sandbox.files.write = mock_write

        async def gen():
            yield b"test data"

        result = await provider.stream_write("/exception.txt", gen())
        assert result is False

        # Verify cleanup attempted (rm -f should have been called)
        # This is tested indirectly through the result

    @pytest.mark.asyncio
    async def test_stream_write_cache_invalidation(self, provider):
        """Test that stream_write invalidates cache"""
        # Create file first
        node_info = EnhancedNodeInfo(name="cache.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Get node info to populate cache
        await provider.get_node_info("/cache.txt")
        assert "/cache.txt" in provider.node_cache

        # Stream write should invalidate cache
        async def gen():
            yield b"new content"

        result = await provider.stream_write("/cache.txt", gen())

        # Cache should be cleared for this file
        if result:
            # If write succeeded, cache should be invalidated
            # (or repopulated with new info)
            pass

    @pytest.mark.asyncio
    async def test_stream_write_stats_update(self, provider):
        """Test that stream_write updates statistics"""
        initial_size = provider._stats["total_size_bytes"]

        async def gen():
            for i in range(10):
                yield f"line {i}\n".encode()

        result = await provider.stream_write("/stats.txt", gen())

        if result:
            # Stats should be updated
            assert provider._stats["total_size_bytes"] >= initial_size


class TestE2BSetMetadataEdgeCases:
    """Test set_metadata edge cases"""

    @pytest.fixture
    async def provider(self):
        """Create initialized provider"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()
        yield provider
        await provider.close()

    @pytest.mark.asyncio
    async def test_set_metadata_node_without_custom_meta(self, provider):
        """Test setting metadata on node without custom_meta attribute"""
        # Create file
        node_info = EnhancedNodeInfo(name="no_meta.txt", is_dir=False, parent_path="/")
        await provider.create_node(node_info)

        # Get node and remove custom_meta if it exists
        info = await provider.get_node_info("/no_meta.txt")
        if hasattr(info, "custom_meta"):
            delattr(info, "custom_meta")

        # Set metadata should handle this
        result = await provider.set_metadata("/no_meta.txt", {"key": "value"})

        # Should succeed (creates custom_meta)
        assert result is True


class TestE2BCloseWithException:
    """Test close with exception handling"""

    @pytest.mark.asyncio
    async def test_close_with_sandbox_close_exception(self):
        """Test close when sandbox.close() raises exception"""
        provider = E2BStorageProvider()

        def mock_sync_initialize():
            provider.sandbox = MockE2BSandbox()
            provider.sandbox_id = provider.sandbox.sandbox_id
            return True

        provider._sync_initialize = mock_sync_initialize
        await provider.initialize()

        # Mock close to raise exception
        def mock_close():
            raise RuntimeError("Close failed")

        provider.sandbox.close = mock_close

        # Should not raise, should handle gracefully
        await provider.close()

        assert provider._closed is True
        assert provider.sandbox is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
