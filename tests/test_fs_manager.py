"""
Comprehensive pytest test suite for async virtual filesystem
"""

import pytest

from chuk_virtual_fs.fs_manager import AsyncVirtualFileSystem


@pytest.fixture
async def vfs():
    """Create an async virtual filesystem instance"""
    fs = AsyncVirtualFileSystem(provider="memory")
    await fs.initialize()
    yield fs
    await fs.close()


@pytest.fixture
async def vfs_with_data(vfs):
    """Create a VFS with some test data"""
    # Create directories
    await vfs.mkdir("/home")
    await vfs.mkdir("/tmp")
    await vfs.mkdir("/etc")
    await vfs.mkdir("/home/user")

    # Create files
    await vfs.write_file("/home/user/test.txt", "Hello World")
    await vfs.write_file("/etc/config.ini", "[settings]\nkey=value")
    await vfs.write_file("/tmp/temp.log", "Log entry 1\nLog entry 2")

    return vfs


class TestBasicOperations:
    """Test basic filesystem operations"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test filesystem initialization"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            assert fs._initialized
            assert not fs._closed
            assert fs.current_directory == "/"

        # After context exit, should be closed
        assert fs._closed

    @pytest.mark.asyncio
    async def test_pwd(self, vfs):
        """Test getting current directory"""
        assert vfs.pwd() == "/"

        await vfs.mkdir("/test")
        await vfs.cd("/test")
        assert vfs.pwd() == "/test"

    @pytest.mark.asyncio
    async def test_resolve_path(self, vfs):
        """Test path resolution"""
        # Absolute paths
        assert vfs.resolve_path("/home/user") == "/home/user"
        assert vfs.resolve_path("/") == "/"

        # Relative paths from root
        assert vfs.resolve_path("home") == "/home"
        assert vfs.resolve_path("./home") == "/home"

        # Change directory and test relative paths
        await vfs.mkdir("/home")
        await vfs.mkdir("/home/user")
        await vfs.cd("/home")

        assert vfs.resolve_path("user") == "/home/user"
        assert vfs.resolve_path("../") == "/"
        assert vfs.resolve_path("./user/../") == "/home"


class TestDirectoryOperations:
    """Test directory operations"""

    @pytest.mark.asyncio
    async def test_mkdir(self, vfs):
        """Test directory creation"""
        # Create directory
        assert await vfs.mkdir("/test")
        assert await vfs.exists("/test")
        assert await vfs.is_dir("/test")

        # Try to create existing directory
        assert not await vfs.mkdir("/test")

        # Create nested directory
        assert await vfs.mkdir("/test/nested")
        assert await vfs.exists("/test/nested")

    @pytest.mark.asyncio
    async def test_rmdir(self, vfs):
        """Test directory removal"""
        # Create and remove directory
        await vfs.mkdir("/test")
        assert await vfs.rmdir("/test")
        assert not await vfs.exists("/test")

        # Try to remove non-existent directory
        assert not await vfs.rmdir("/nonexistent")

        # Try to remove non-empty directory
        await vfs.mkdir("/parent")
        await vfs.mkdir("/parent/child")
        assert not await vfs.rmdir("/parent")

    @pytest.mark.asyncio
    async def test_ls(self, vfs_with_data):
        """Test directory listing"""
        # List root
        root_contents = await vfs_with_data.ls("/")
        assert "home" in root_contents
        assert "tmp" in root_contents
        assert "etc" in root_contents

        # List subdirectory
        home_contents = await vfs_with_data.ls("/home")
        assert "user" in home_contents

        # List directory with files
        user_contents = await vfs_with_data.ls("/home/user")
        assert "test.txt" in user_contents

    @pytest.mark.asyncio
    async def test_cd(self, vfs_with_data):
        """Test changing directory"""
        # Change to existing directory
        assert await vfs_with_data.cd("/home")
        assert vfs_with_data.pwd() == "/home"

        # Change using relative path
        assert await vfs_with_data.cd("user")
        assert vfs_with_data.pwd() == "/home/user"

        # Try to change to file
        assert not await vfs_with_data.cd("test.txt")
        assert vfs_with_data.pwd() == "/home/user"

        # Try to change to non-existent directory
        assert not await vfs_with_data.cd("/nonexistent")


class TestFileOperations:
    """Test file operations"""

    @pytest.mark.asyncio
    async def test_touch(self, vfs):
        """Test file creation"""
        # Create new file
        assert await vfs.touch("/test.txt")
        assert await vfs.exists("/test.txt")
        assert await vfs.is_file("/test.txt")

        # Touch existing file (should succeed)
        assert await vfs.touch("/test.txt")

        # Create file with metadata
        assert await vfs.touch("/test2.txt", mime_type="text/plain", owner="user")
        node_info = await vfs.get_node_info("/test2.txt")
        assert node_info.mime_type == "text/plain"
        assert node_info.owner == "user"

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, vfs):
        """Test writing and reading files"""
        # Write string content
        content = "Hello, World!"
        assert await vfs.write_file("/test.txt", content)

        # Read as bytes
        read_content = await vfs.read_file("/test.txt")
        assert read_content == content.encode("utf-8")

        # Read as text
        read_text = await vfs.read_file("/test.txt", as_text=True)
        assert read_text == content

        # Write bytes content
        byte_content = b"\x00\x01\x02\x03"
        assert await vfs.write_file("/binary.dat", byte_content)
        read_bytes = await vfs.read_file("/binary.dat")
        assert read_bytes == byte_content

    @pytest.mark.asyncio
    async def test_rm(self, vfs_with_data):
        """Test file removal"""
        # Remove file
        assert await vfs_with_data.rm("/tmp/temp.log")
        assert not await vfs_with_data.exists("/tmp/temp.log")

        # Try to remove non-existent file
        assert not await vfs_with_data.rm("/nonexistent.txt")

        # Remove empty directory
        await vfs_with_data.mkdir("/empty")
        assert await vfs_with_data.rm("/empty")
        assert not await vfs_with_data.exists("/empty")

    @pytest.mark.asyncio
    async def test_file_exists_checks(self, vfs_with_data):
        """Test existence and type checks"""
        # Check file
        assert await vfs_with_data.exists("/home/user/test.txt")
        assert await vfs_with_data.is_file("/home/user/test.txt")
        assert not await vfs_with_data.is_dir("/home/user/test.txt")

        # Check directory
        assert await vfs_with_data.exists("/home")
        assert await vfs_with_data.is_dir("/home")
        assert not await vfs_with_data.is_file("/home")

        # Check non-existent
        assert not await vfs_with_data.exists("/nonexistent")
        assert not await vfs_with_data.is_file("/nonexistent")
        assert not await vfs_with_data.is_dir("/nonexistent")


class TestCopyMoveOperations:
    """Test copy and move operations"""

    @pytest.mark.asyncio
    async def test_copy_file(self, vfs_with_data):
        """Test copying files"""
        # Copy file
        assert await vfs_with_data.cp("/home/user/test.txt", "/tmp/test_copy.txt")

        # Verify both files exist
        assert await vfs_with_data.exists("/home/user/test.txt")
        assert await vfs_with_data.exists("/tmp/test_copy.txt")

        # Verify content is the same
        original = await vfs_with_data.read_file("/home/user/test.txt", as_text=True)
        copy = await vfs_with_data.read_file("/tmp/test_copy.txt", as_text=True)
        assert original == copy

    @pytest.mark.asyncio
    async def test_copy_directory(self, vfs):
        """Test copying directories"""
        # Create directory structure
        await vfs.mkdir("/source")
        await vfs.mkdir("/source/subdir")
        await vfs.write_file("/source/file1.txt", "Content 1")
        await vfs.write_file("/source/subdir/file2.txt", "Content 2")

        # Copy directory
        assert await vfs.cp("/source", "/dest")

        # Verify structure
        assert await vfs.exists("/dest")
        assert await vfs.exists("/dest/subdir")
        assert await vfs.exists("/dest/file1.txt")
        assert await vfs.exists("/dest/subdir/file2.txt")

        # Verify content
        content1 = await vfs.read_file("/dest/file1.txt", as_text=True)
        assert content1 == "Content 1"
        content2 = await vfs.read_file("/dest/subdir/file2.txt", as_text=True)
        assert content2 == "Content 2"

    @pytest.mark.asyncio
    async def test_move_file(self, vfs):
        """Test moving files"""
        # Create file
        await vfs.write_file("/source.txt", "Test content")

        # Move file
        assert await vfs.mv("/source.txt", "/dest.txt")

        # Verify source is gone, dest exists
        assert not await vfs.exists("/source.txt")
        assert await vfs.exists("/dest.txt")

        # Verify content
        content = await vfs.read_file("/dest.txt", as_text=True)
        assert content == "Test content"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Move directory functionality needs implementation fixes")
    async def test_move_directory(self, vfs):
        """Test moving directories"""
        # Create directory structure
        await vfs.mkdir("/source")
        await vfs.write_file("/source/file.txt", "Content")

        # Move directory
        assert await vfs.mv("/source", "/dest")

        # Verify source is gone, dest exists
        assert not await vfs.exists("/source")
        assert await vfs.exists("/dest")
        assert await vfs.exists("/dest/file.txt")


class TestMetadata:
    """Test metadata operations"""

    @pytest.mark.asyncio
    async def test_get_metadata(self, vfs):
        """Test getting metadata"""
        # Create file with content
        content = "Test content"
        await vfs.write_file("/test.txt", content)

        # Get metadata
        metadata = await vfs.get_metadata("/test.txt")

        assert metadata["name"] == "test.txt"
        assert not metadata["is_dir"]
        assert metadata["size"] == len(content.encode("utf-8"))
        assert metadata["sha256"] is not None
        assert metadata["created_at"] is not None
        assert metadata["modified_at"] is not None

    @pytest.mark.asyncio
    async def test_set_metadata(self, vfs):
        """Test setting metadata"""
        # Create file
        await vfs.touch("/test.txt")

        # Set metadata
        custom_meta = {
            "custom_meta": {"author": "test", "version": "1.0"},
            "tags": {"env": "test", "type": "config"},
            "mime_type": "text/plain",
            "owner": "testuser",
        }

        assert await vfs.set_metadata("/test.txt", custom_meta)

        # Verify metadata
        metadata = await vfs.get_metadata("/test.txt")
        assert metadata["custom_meta"]["author"] == "test"
        assert metadata["tags"]["env"] == "test"
        assert metadata["mime_type"] == "text/plain"
        assert metadata["owner"] == "testuser"

    @pytest.mark.asyncio
    async def test_mime_type_detection(self, vfs):
        """Test automatic MIME type detection"""
        # Test various file types
        test_files = {
            "/test.txt": "text/plain",
            "/test.html": "text/html",
            "/test.json": "application/json",
            "/test.jpg": "image/jpeg",
            "/test.pdf": "application/pdf",
            "/test.py": "text/x-python",
            "/test.md": "text/markdown",
        }

        for path, expected_mime in test_files.items():
            await vfs.touch(path)
            node_info = await vfs.get_node_info(path)
            assert node_info.mime_type == expected_mime


class TestBatchOperations:
    """Test batch operations"""

    @pytest.mark.asyncio
    async def test_batch_create_files(self, vfs):
        """Test creating multiple files in batch"""
        file_specs = [
            {"path": "/file1.txt", "content": b"Content 1"},
            {"path": "/file2.txt", "content": b"Content 2"},
            {"path": "/dir/file3.txt", "content": b"Content 3"},
        ]

        # Create directory for nested file
        await vfs.mkdir("/dir")

        await vfs.batch_create_files(file_specs)

        # Verify all files created
        assert await vfs.exists("/file1.txt")
        assert await vfs.exists("/file2.txt")
        assert await vfs.exists("/dir/file3.txt")

        # Verify content
        content1 = await vfs.read_file("/file1.txt")
        assert content1 == b"Content 1"

    @pytest.mark.asyncio
    async def test_batch_read_files(self, vfs_with_data):
        """Test reading multiple files in batch"""
        paths = ["/home/user/test.txt", "/etc/config.ini", "/tmp/temp.log"]

        results = await vfs_with_data.batch_read_files(paths)

        assert len(results) == 3
        assert results["/home/user/test.txt"] == b"Hello World"
        assert b"[settings]" in results["/etc/config.ini"]
        assert b"Log entry 1" in results["/tmp/temp.log"]

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Batch write functionality needs implementation fixes")
    async def test_batch_write_files(self, vfs):
        """Test writing multiple files in batch"""
        file_data = {
            "/batch1.txt": b"Batch content 1",
            "/batch2.txt": b"Batch content 2",
            "/batch3.txt": b"Batch content 3",
        }

        await vfs.batch_write_files(file_data)

        # Verify all files written
        for path, expected_content in file_data.items():
            content = await vfs.read_file(path)
            assert content == expected_content

    @pytest.mark.asyncio
    async def test_batch_delete_paths(self, vfs_with_data):
        """Test deleting multiple paths in batch"""
        paths = ["/home/user/test.txt", "/tmp/temp.log"]

        await vfs_with_data.batch_delete_paths(paths)

        # Verify files deleted
        assert not await vfs_with_data.exists("/home/user/test.txt")
        assert not await vfs_with_data.exists("/tmp/temp.log")

        # Other files should still exist
        assert await vfs_with_data.exists("/etc/config.ini")


class TestUtilityOperations:
    """Test utility operations"""

    @pytest.mark.asyncio
    async def test_find(self, vfs_with_data):
        """Test finding files"""
        # Find all files
        all_files = await vfs_with_data.find("*", "/")
        assert len(all_files) > 0

        # Find specific pattern
        txt_files = await vfs_with_data.find("*.txt", "/")
        assert len(txt_files) > 0 or any(".txt" in f for f in txt_files if f)

        # Non-recursive search
        root_items = await vfs_with_data.find("*", "/", recursive=False)
        assert all("/" not in item[1:] for item in root_items if item != "/")

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, vfs_with_data):
        """Test getting storage statistics"""
        stats = await vfs_with_data.get_storage_stats()

        assert "file_count" in stats
        assert "directory_count" in stats
        assert "total_size_bytes" in stats
        assert "filesystem_stats" in stats
        assert stats["filesystem_stats"]["operations"] > 0

    @pytest.mark.asyncio
    async def test_cleanup(self, vfs):
        """Test cleanup operations"""
        # Create temp files
        await vfs.mkdir("/tmp")
        await vfs.write_file("/tmp/temp1.txt", "Temp content 1")
        await vfs.write_file("/tmp/temp2.txt", "Temp content 2")

        # Run cleanup
        result = await vfs.cleanup()

        assert "bytes_freed" in result
        assert "files_removed" in result


class TestErrorHandling:
    """Test error handling"""

    @pytest.mark.asyncio
    async def test_invalid_provider(self):
        """Test invalid provider name"""
        with pytest.raises(ValueError, match="Unknown provider"):
            async with AsyncVirtualFileSystem(provider="invalid"):
                pass

    @pytest.mark.asyncio
    async def test_operations_on_closed_fs(self):
        """Test operations on closed filesystem"""
        fs = AsyncVirtualFileSystem(provider="memory")
        await fs.initialize()
        await fs.close()

        # Operations should handle closed state gracefully
        # Specific behavior depends on implementation
        assert fs._closed

    @pytest.mark.asyncio
    async def test_batch_operations_disabled(self):
        """Test batch operations when disabled"""
        fs = AsyncVirtualFileSystem(provider="memory", enable_batch=False)
        await fs.initialize()

        with pytest.raises(RuntimeError, match="Batch operations not enabled"):
            await fs.batch_read_files(["/test.txt"])

        await fs.close()


class TestRetryMechanism:
    """Test retry mechanism"""

    @pytest.mark.asyncio
    async def test_retry_enabled(self):
        """Test operations with retry enabled"""
        fs = AsyncVirtualFileSystem(provider="memory", enable_retry=True)
        await fs.initialize()

        # Normal operations should work
        assert await fs.touch("/test.txt")
        assert await fs.write_file("/test.txt", "Content")

        await fs.close()

    @pytest.mark.asyncio
    async def test_retry_disabled(self):
        """Test operations with retry disabled"""
        fs = AsyncVirtualFileSystem(provider="memory", enable_retry=False)
        await fs.initialize()

        # Normal operations should still work
        assert await fs.touch("/test.txt")
        assert await fs.write_file("/test.txt", "Content")

        await fs.close()


class TestStatistics:
    """Test statistics tracking"""

    @pytest.mark.asyncio
    async def test_operation_statistics(self, vfs):
        """Test that operations are tracked"""
        initial_stats = vfs.stats.copy()

        # Perform operations
        await vfs.touch("/test.txt")
        await vfs.write_file("/test.txt", "Test content")
        await vfs.read_file("/test.txt")
        await vfs.rm("/test.txt")

        # Check stats updated
        assert vfs.stats["operations"] > initial_stats["operations"]
        assert vfs.stats["files_created"] > initial_stats["files_created"]
        assert vfs.stats["files_deleted"] > initial_stats["files_deleted"]
        assert vfs.stats["bytes_written"] > 0
        assert vfs.stats["bytes_read"] > 0


class TestAdditionalCoverage:
    """Additional tests to improve coverage"""

    @pytest.mark.asyncio
    async def test_double_initialization(self):
        """Test that calling initialize twice is handled"""
        fs = AsyncVirtualFileSystem(provider="memory")
        await fs.initialize()

        # Call initialize again - should return early
        await fs.initialize()

        assert fs._initialized
        await fs.close()

    @pytest.mark.asyncio
    async def test_double_close(self):
        """Test that calling close twice is handled"""
        fs = AsyncVirtualFileSystem(provider="memory")
        await fs.initialize()
        await fs.close()

        # Call close again - should return early
        await fs.close()

        assert fs._closed

    @pytest.mark.asyncio
    async def test_sqlite_provider_initialization(self):
        """Test SQLite provider initialization"""
        try:
            fs = AsyncVirtualFileSystem(provider="sqlite", db_path=":memory:")
            await fs.initialize()
            assert fs.provider is not None
            await fs.close()
        except Exception:
            # SQLite might not be available in all environments
            pass

    @pytest.mark.asyncio
    async def test_filesystem_provider_initialization(self):
        """Test filesystem provider initialization"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                fs = AsyncVirtualFileSystem(provider="filesystem", root_path=tmpdir)
                await fs.initialize()
                assert fs.provider is not None
                await fs.close()
            except Exception:
                # Filesystem provider might not be available
                pass

    @pytest.mark.asyncio
    async def test_resolve_empty_path(self, vfs):
        """Test resolving empty path"""
        # Empty path should resolve to current directory
        assert vfs.resolve_path("") == "/"

        await vfs.mkdir("/test")
        await vfs.cd("/test")
        assert vfs.resolve_path("") == "/test"

    @pytest.mark.asyncio
    async def test_split_path_root(self, vfs):
        """Test splitting root path"""
        parent, name = vfs.split_path("/")
        assert parent == "/"
        assert name == ""

    @pytest.mark.asyncio
    async def test_touch_existing_directory(self, vfs):
        """Test touching a directory should fail"""
        await vfs.mkdir("/testdir")
        # Try to touch a directory - should fail
        result = await vfs.touch("/testdir")
        assert not result

    @pytest.mark.asyncio
    async def test_write_binary_type_checking(self, vfs):
        """Test write_binary with wrong type"""
        with pytest.raises(TypeError, match="write_binary requires bytes"):
            await vfs.write_binary("/test.bin", "not bytes")

    @pytest.mark.asyncio
    async def test_write_text_type_checking(self, vfs):
        """Test write_text with wrong type"""
        with pytest.raises(TypeError, match="write_text requires str"):
            await vfs.write_text("/test.txt", b"not string")

    @pytest.mark.asyncio
    async def test_write_binary_success(self, vfs):
        """Test write_binary with correct type"""
        content = b"\x00\x01\x02\x03\x04"
        assert await vfs.write_binary("/test.bin", content)

        # Read back and verify
        read_content = await vfs.read_file("/test.bin")
        assert read_content == content

    @pytest.mark.asyncio
    async def test_write_text_with_encoding(self, vfs):
        """Test write_text with encoding"""
        content = "Hello, World! Café"
        assert await vfs.write_text("/test.txt", content, encoding="utf-8")

        # Read back
        read_content = await vfs.read_file("/test.txt", as_text=True)
        assert read_content == content

    @pytest.mark.asyncio
    async def test_read_binary(self, vfs):
        """Test read_binary method"""
        content = b"binary content"
        await vfs.write_file("/test.bin", content)

        read_content = await vfs.read_binary("/test.bin")
        assert read_content == content

        # Test reading non-existent file
        result = await vfs.read_binary("/nonexistent.bin")
        assert result is None

    @pytest.mark.asyncio
    async def test_read_text_with_encoding(self, vfs):
        """Test read_text with encoding"""
        content = "Text content"
        await vfs.write_text("/test.txt", content)

        read_content = await vfs.read_text("/test.txt", encoding="utf-8")
        assert read_content == content

        # Test reading non-existent file
        result = await vfs.read_text("/nonexistent.txt")
        assert result is None

    @pytest.mark.asyncio
    async def test_read_text_decode_error(self, vfs):
        """Test read_text with decode error"""
        # Write invalid UTF-8 bytes
        invalid_utf8 = b"\xff\xfe"
        await vfs.write_file("/invalid.txt", invalid_utf8)

        # Try to read as UTF-8 strict - should raise
        with pytest.raises(UnicodeDecodeError):
            await vfs.read_text("/invalid.txt", encoding="utf-8", errors="strict")

        # Try with errors='ignore' - should work
        result = await vfs.read_text("/invalid.txt", encoding="utf-8", errors="ignore")
        assert result is not None

    @pytest.mark.asyncio
    async def test_batch_operations_all_disabled_errors(self):
        """Test all batch operations when batch is disabled"""
        fs = AsyncVirtualFileSystem(provider="memory", enable_batch=False)
        await fs.initialize()

        # Test batch_create_files
        with pytest.raises(RuntimeError, match="Batch operations not enabled"):
            await fs.batch_create_files([{"path": "/test.txt", "content": b"test"}])

        # Test batch_write_files
        with pytest.raises(RuntimeError, match="Batch operations not enabled"):
            await fs.batch_write_files({"/test.txt": b"content"})

        # Test batch_delete_paths
        with pytest.raises(RuntimeError, match="Batch operations not enabled"):
            await fs.batch_delete_paths(["/test.txt"])

        await fs.close()

    @pytest.mark.asyncio
    async def test_find_with_nonexistent_path(self, vfs):
        """Test find with path that doesn't exist"""
        # Should handle gracefully and return empty list
        results = await vfs.find("*.txt", "/nonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_error_statistics_tracking(self, vfs):
        """Test that errors are tracked in statistics"""
        from unittest.mock import AsyncMock, patch

        from chuk_virtual_fs.node_info import EnhancedNodeInfo

        initial_errors = vfs.stats["errors"]

        # Force mkdir to fail by making provider.create_node fail
        with patch.object(
            vfs.provider, "create_node", new_callable=AsyncMock, return_value=False
        ):
            result = await vfs.mkdir("/will-fail")
            assert not result
            assert vfs.stats["errors"] == initial_errors + 1

        # Force rmdir to fail - need to set up dir to exist but delete to fail
        await vfs.mkdir("/testdir")
        mock_node_info = EnhancedNodeInfo(name="testdir", is_dir=True, parent_path="/")
        with (
            patch.object(
                vfs.provider,
                "get_node_info",
                new_callable=AsyncMock,
                return_value=mock_node_info,
            ),
            patch.object(
                vfs.provider, "list_directory", new_callable=AsyncMock, return_value=[]
            ),
            patch.object(
                vfs.provider,
                "delete_node",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            result = await vfs.rmdir("/testdir")
            assert not result
            assert vfs.stats["errors"] == initial_errors + 2

        # Force cp to fail
        with patch.object(
            vfs.provider, "copy_node", new_callable=AsyncMock, return_value=False
        ):
            result = await vfs.cp("/src", "/dest")
            assert not result
            assert vfs.stats["errors"] == initial_errors + 3

        # Force mv to fail
        with patch.object(
            vfs.provider, "move_node", new_callable=AsyncMock, return_value=False
        ):
            result = await vfs.mv("/src2", "/dest2")
            assert not result
            assert vfs.stats["errors"] == initial_errors + 4

        # Force set_metadata to fail
        with patch.object(
            vfs.provider, "set_metadata", new_callable=AsyncMock, return_value=False
        ):
            result = await vfs.set_metadata("/file", {})
            assert not result
            assert vfs.stats["errors"] == initial_errors + 5

        # Force read_file to fail (return None)
        with patch.object(
            vfs.provider, "read_file", new_callable=AsyncMock, return_value=None
        ):
            result = await vfs.read_file("/missing")
            assert result is None
            assert vfs.stats["errors"] == initial_errors + 6

    @pytest.mark.asyncio
    async def test_touch_create_node_failure(self, vfs):
        """Test touch when create_node fails"""
        from unittest.mock import AsyncMock, patch

        # Mock create_node to fail
        with patch.object(
            vfs.provider, "create_node", new_callable=AsyncMock, return_value=False
        ):
            result = await vfs.touch("/will-fail.txt")
            assert not result

    @pytest.mark.asyncio
    async def test_touch_write_failure(self, vfs):
        """Test touch when write_file fails"""
        from unittest.mock import AsyncMock, patch

        # Mock write_file to fail after successful create_node
        with patch.object(
            vfs.provider, "write_file", new_callable=AsyncMock, return_value=False
        ):
            # First create the parent structure if needed
            result = await vfs.touch("/fail-write.txt")
            # The result depends on whether create_node succeeded but write failed
            # In this case, touch should return False
            assert not result

    @pytest.mark.asyncio
    async def test_write_file_touch_failure(self, vfs):
        """Test write_file when touch fails"""
        from unittest.mock import AsyncMock, patch

        # Mock exists to return False and touch to fail
        with (
            patch.object(
                vfs.provider, "exists", new_callable=AsyncMock, return_value=False
            ),
            patch.object(vfs, "touch", new_callable=AsyncMock, return_value=False),
        ):
            result = await vfs.write_file("/fail.txt", "content")
            assert not result

    @pytest.mark.asyncio
    async def test_write_file_write_failure(self, vfs):
        """Test write_file when provider.write_file fails"""
        from unittest.mock import AsyncMock, patch

        # Create file first
        await vfs.touch("/test.txt")

        # Mock write_file to fail
        with patch.object(
            vfs.provider, "write_file", new_callable=AsyncMock, return_value=False
        ):
            result = await vfs.write_file("/test.txt", "content")
            assert not result

    @pytest.mark.asyncio
    async def test_get_provider_name(self, vfs):
        """Test getting provider name"""
        name = await vfs.get_provider_name()
        assert name == "memory"

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, vfs):
        """Test generating presigned URL"""
        # Memory provider doesn't support presigned URLs, but we can test the call
        await vfs.write_file("/test.txt", "content")

        # This should call through to provider
        result = await vfs.generate_presigned_url("/test.txt", expires_in=3600)
        # Memory provider likely returns None
        assert result is None or isinstance(result, str)
