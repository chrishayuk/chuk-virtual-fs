"""
Test Provider Consistency
==========================
This test suite ensures all storage providers (Memory, SQLite, S3, E2B, Pyodide)
implement the same interface consistently and return compatible results.
"""

import asyncio
import shutil
import tempfile

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider
from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider
from chuk_virtual_fs.providers.pyodide import PyodideStorageProvider
from chuk_virtual_fs.providers.sqlite import SqliteStorageProvider


def get_test_providers():
    """Get list of providers to test for consistency"""
    providers = []

    # Memory provider
    providers.append(("memory", AsyncMemoryStorageProvider))

    # SQLite provider (in-memory)
    providers.append(("sqlite", lambda: SqliteStorageProvider(":memory:")))

    # Pyodide provider (with temp directory)
    temp_dir = tempfile.mkdtemp(prefix="pyodide_test_")
    providers.append(("pyodide", lambda: PyodideStorageProvider(base_path=temp_dir)))

    # Note: S3 and E2B providers require external services, so we'll test their interface only

    return providers


class TestProviderConsistency:
    """Test that all providers implement the same interface consistently"""

    @pytest.fixture(params=get_test_providers(), ids=lambda x: x[0])
    async def provider(self, request):
        """Fixture that provides each provider for testing"""
        name, provider_class = request.param

        # Create provider instance
        provider = provider_class() if callable(provider_class) else provider_class()

        # Initialize provider
        await provider.initialize()

        yield name, provider

        # Cleanup
        await provider.close()

        # Additional cleanup for pyodide
        if name == "pyodide" and hasattr(provider, "base_path"):
            shutil.rmtree(provider.base_path, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_basic_file_operations(self, provider):
        """Test basic file operations are consistent across providers"""
        name, prov = provider

        # Create a file
        file_node = EnhancedNodeInfo("test_file.txt", False, "/")
        result = await prov.create_node(file_node)
        assert result is True, f"{name}: Failed to create file"

        # Check file exists
        exists = await prov.exists("/test_file.txt")
        assert exists is True, f"{name}: File should exist"

        # Write content
        content = b"Test content for consistency"
        write_result = await prov.write_file("/test_file.txt", content)
        assert write_result is True, f"{name}: Failed to write file"

        # Read content
        read_content = await prov.read_file("/test_file.txt")
        assert read_content == content, f"{name}: Content mismatch"

        # Get node info
        info = await prov.get_node_info("/test_file.txt")
        assert info is not None, f"{name}: Failed to get node info"
        assert info.name == "test_file.txt", f"{name}: Name mismatch"
        assert info.is_dir is False, f"{name}: Should be a file"

        # Delete file
        delete_result = await prov.delete_node("/test_file.txt")
        assert delete_result is True, f"{name}: Failed to delete file"

        # Check file doesn't exist
        exists_after = await prov.exists("/test_file.txt")
        assert exists_after is False, f"{name}: File should not exist after deletion"

    @pytest.mark.asyncio
    async def test_directory_operations(self, provider):
        """Test directory operations are consistent across providers"""
        name, prov = provider

        # Create a directory
        dir_node = EnhancedNodeInfo("test_dir", True, "/")
        result = await prov.create_node(dir_node)
        assert result is True, f"{name}: Failed to create directory"

        # Check directory exists
        exists = await prov.exists("/test_dir")
        assert exists is True, f"{name}: Directory should exist"

        # Create file in directory
        file_node = EnhancedNodeInfo("nested_file.txt", False, "/test_dir")
        result = await prov.create_node(file_node)
        assert result is True, f"{name}: Failed to create nested file"

        # List directory
        contents = await prov.list_directory("/test_dir")
        assert "nested_file.txt" in contents, f"{name}: Nested file not in listing"

        # Get directory info
        info = await prov.get_node_info("/test_dir")
        assert info is not None, f"{name}: Failed to get directory info"
        assert info.name == "test_dir", f"{name}: Directory name mismatch"
        assert info.is_dir is True, f"{name}: Should be a directory"

        # Delete nested file first
        await prov.delete_node("/test_dir/nested_file.txt")

        # Delete directory
        delete_result = await prov.delete_node("/test_dir")
        assert delete_result is True, f"{name}: Failed to delete directory"

    @pytest.mark.asyncio
    async def test_error_handling(self, provider):
        """Test error handling is consistent across providers"""
        name, prov = provider

        # Read non-existent file
        content = await prov.read_file("/non_existent.txt")
        assert content is None, f"{name}: Should return None for non-existent file"

        # Delete non-existent file
        result = await prov.delete_node("/non_existent.txt")
        assert result is False, f"{name}: Should return False for non-existent delete"

        # Get info for non-existent file
        info = await prov.get_node_info("/non_existent.txt")
        assert info is None, f"{name}: Should return None for non-existent node info"

        # List non-existent directory
        contents = await prov.list_directory("/non_existent_dir")
        assert contents == [], (
            f"{name}: Should return empty list for non-existent directory"
        )

        # Check non-existent path exists
        exists = await prov.exists("/non_existent.txt")
        assert exists is False, f"{name}: Non-existent path should return False"

    @pytest.mark.asyncio
    async def test_metadata_operations(self, provider):
        """Test metadata operations are consistent across providers"""
        name, prov = provider

        # Create a file
        file_node = EnhancedNodeInfo("meta_test.txt", False, "/")
        await prov.create_node(file_node)

        # Set metadata
        metadata = {
            "author": "test_user",
            "version": "1.0",
            "tags": ["test", "consistency"],
        }
        result = await prov.set_metadata("/meta_test.txt", metadata)
        assert result is True, f"{name}: Failed to set metadata"

        # Get metadata
        retrieved = await prov.get_metadata("/meta_test.txt")
        assert retrieved is not None, f"{name}: Failed to get metadata"

        # Check if metadata is stored (may be in different formats)
        # Some providers store in custom_meta, others directly
        author = retrieved.get("author") or retrieved.get("custom_meta", {}).get(
            "author"
        )
        version = retrieved.get("version") or retrieved.get("custom_meta", {}).get(
            "version"
        )
        retrieved.get("tags") or retrieved.get("custom_meta", {}).get("tags")

        assert author == "test_user", f"{name}: Author metadata mismatch"
        assert version == "1.0", f"{name}: Version metadata mismatch"

        # Cleanup
        await prov.delete_node("/meta_test.txt")

    @pytest.mark.asyncio
    async def test_batch_operations(self, provider):
        """Test batch operations are consistent across providers"""
        name, prov = provider

        # Batch create
        nodes = [EnhancedNodeInfo(f"batch{i}.txt", False, "/") for i in range(3)]
        create_results = await prov.batch_create(nodes)
        assert len(create_results) == 3, f"{name}: Batch create result count mismatch"
        assert all(create_results), f"{name}: Some batch creates failed"

        # Batch write
        operations = [(f"/batch{i}.txt", f"content{i}".encode()) for i in range(3)]
        write_results = await prov.batch_write(operations)
        assert len(write_results) == 3, f"{name}: Batch write result count mismatch"
        assert all(write_results), f"{name}: Some batch writes failed"

        # Batch read
        paths = [f"/batch{i}.txt" for i in range(3)]
        read_results = await prov.batch_read(paths)
        assert len(read_results) == 3, f"{name}: Batch read result count mismatch"
        assert all(r is not None for r in read_results), (
            f"{name}: Some batch reads failed"
        )

        # Verify content
        for i, content in enumerate(read_results):
            expected = f"content{i}".encode()
            assert content == expected, (
                f"{name}: Batch read content mismatch at index {i}"
            )

        # Batch delete
        delete_results = await prov.batch_delete(paths)
        assert len(delete_results) == 3, f"{name}: Batch delete result count mismatch"
        assert all(delete_results), f"{name}: Some batch deletes failed"

    @pytest.mark.asyncio
    async def test_storage_stats_format(self, provider):
        """Test storage stats return consistent format across providers"""
        name, prov = provider

        # Create some test data
        for i in range(2):
            node = EnhancedNodeInfo(f"stats_test{i}.txt", False, "/")
            await prov.create_node(node)
            await prov.write_file(f"/stats_test{i}.txt", b"test content")

        # Get storage stats
        stats = await prov.get_storage_stats()
        assert isinstance(stats, dict), f"{name}: Stats should be a dictionary"

        # Check for common keys (providers may use different names)
        has_size = any(
            k in stats for k in ["total_size", "total_size_bytes", "total_bytes"]
        )
        has_files = any(k in stats for k in ["total_files", "file_count", "files"])
        has_dirs = any(
            k in stats for k in ["total_directories", "directory_count", "directories"]
        )

        assert has_size, f"{name}: Stats missing size information"
        assert has_files, f"{name}: Stats missing file count"
        assert has_dirs, f"{name}: Stats missing directory count"

        # Cleanup
        for i in range(2):
            await prov.delete_node(f"/stats_test{i}.txt")

    @pytest.mark.asyncio
    async def test_copy_move_operations(self, provider):
        """Test copy and move operations where supported"""
        name, prov = provider

        # Create source file
        source_node = EnhancedNodeInfo("source.txt", False, "/")
        await prov.create_node(source_node)
        await prov.write_file("/source.txt", b"source content")

        # Test copy if supported
        if hasattr(prov, "copy_node"):
            copy_result = await prov.copy_node("/source.txt", "/copy.txt")
            if copy_result:  # Some providers may not support copy
                assert await prov.exists("/source.txt"), (
                    f"{name}: Source should still exist after copy"
                )
                assert await prov.exists("/copy.txt"), f"{name}: Copy should exist"

                copy_content = await prov.read_file("/copy.txt")
                assert copy_content == b"source content", (
                    f"{name}: Copy content mismatch"
                )

                await prov.delete_node("/copy.txt")

        # Test move if supported
        if hasattr(prov, "move_node"):
            # Create another source for move
            move_source = EnhancedNodeInfo("move_source.txt", False, "/")
            await prov.create_node(move_source)
            await prov.write_file("/move_source.txt", b"move content")

            move_result = await prov.move_node("/move_source.txt", "/moved.txt")
            if move_result:  # Some providers may not support move
                assert not await prov.exists("/move_source.txt"), (
                    f"{name}: Source should not exist after move"
                )
                assert await prov.exists("/moved.txt"), (
                    f"{name}: Moved file should exist"
                )

                moved_content = await prov.read_file("/moved.txt")
                assert moved_content == b"move content", (
                    f"{name}: Moved content mismatch"
                )

                await prov.delete_node("/moved.txt")

        # Cleanup
        await prov.delete_node("/source.txt")

    @pytest.mark.asyncio
    async def test_cleanup_operation(self, provider):
        """Test cleanup operation returns consistent format"""
        name, prov = provider

        # Create some temporary files
        for i in range(2):
            node = EnhancedNodeInfo(f"cleanup_test{i}.txt", False, "/")
            await prov.create_node(node)
            await prov.write_file(f"/cleanup_test{i}.txt", b"cleanup content")

        # Perform cleanup
        result = await prov.cleanup()
        assert isinstance(result, dict), f"{name}: Cleanup should return a dictionary"

        # Check for common keys (providers may use different formats)
        has_status = any(k in result for k in ["cleaned_up", "success", "status"])
        has_metrics = any(
            k in result for k in ["files_removed", "bytes_freed", "items_removed"]
        )

        assert has_status or has_metrics, (
            f"{name}: Cleanup result missing status or metrics"
        )

        # Cleanup test files
        for i in range(2):
            try:
                await prov.delete_node(f"/cleanup_test{i}.txt")
            except:
                pass  # Files may have been cleaned up


class TestProviderInterfaces:
    """Test that all providers implement required interface methods"""

    def test_all_providers_inherit_from_base(self):
        """Test all providers inherit from AsyncStorageProvider"""
        from chuk_virtual_fs.providers.e2b import E2BStorageProvider
        from chuk_virtual_fs.providers.filesystem import AsyncFilesystemStorageProvider
        from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider
        from chuk_virtual_fs.providers.pyodide import PyodideStorageProvider
        from chuk_virtual_fs.providers.s3 import S3StorageProvider
        from chuk_virtual_fs.providers.sqlite import SqliteStorageProvider

        providers = [
            AsyncMemoryStorageProvider,
            SqliteStorageProvider,
            S3StorageProvider,
            E2BStorageProvider,
            PyodideStorageProvider,
            AsyncFilesystemStorageProvider,
        ]

        for provider_class in providers:
            assert issubclass(provider_class, AsyncStorageProvider), (
                f"{provider_class.__name__} should inherit from AsyncStorageProvider"
            )

    def test_required_methods_present(self):
        """Test all providers have required methods"""
        from chuk_virtual_fs.providers.e2b import E2BStorageProvider
        from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider
        from chuk_virtual_fs.providers.pyodide import PyodideStorageProvider
        from chuk_virtual_fs.providers.s3 import S3StorageProvider
        from chuk_virtual_fs.providers.sqlite import SqliteStorageProvider

        required_methods = [
            "initialize",
            "close",
            "create_node",
            "delete_node",
            "get_node_info",
            "list_directory",
            "write_file",
            "read_file",
            "exists",
            "get_metadata",
            "set_metadata",
            "get_storage_stats",
            "cleanup",
            "batch_create",
            "batch_delete",
            "batch_read",
            "batch_write",
        ]

        providers = [
            AsyncMemoryStorageProvider,
            SqliteStorageProvider,
            S3StorageProvider,
            E2BStorageProvider,
            PyodideStorageProvider,
        ]

        for provider_class in providers:
            for method in required_methods:
                assert hasattr(provider_class, method), (
                    f"{provider_class.__name__} missing required method: {method}"
                )

                # Check method is async
                method_obj = getattr(provider_class, method)
                if not method.startswith("_"):  # Skip private methods
                    assert asyncio.iscoroutinefunction(method_obj), (
                        f"{provider_class.__name__}.{method} should be async"
                    )

    def test_method_signatures_match(self):
        """Test that method signatures are consistent across providers"""
        import inspect

        from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider
        from chuk_virtual_fs.providers.sqlite import SqliteStorageProvider

        # Use memory provider as reference
        reference = AsyncMemoryStorageProvider
        compare_to = SqliteStorageProvider

        methods_to_check = [
            "create_node",
            "delete_node",
            "write_file",
            "read_file",
            "get_node_info",
            "list_directory",
            "exists",
        ]

        for method_name in methods_to_check:
            ref_method = getattr(reference, method_name)
            comp_method = getattr(compare_to, method_name)

            ref_sig = inspect.signature(ref_method)
            comp_sig = inspect.signature(comp_method)

            # Check parameter names match (excluding self)
            ref_params = list(ref_sig.parameters.keys())[1:]  # Skip 'self'
            comp_params = list(comp_sig.parameters.keys())[1:]  # Skip 'self'

            assert ref_params == comp_params, (
                f"Parameter mismatch in {method_name}: {ref_params} vs {comp_params}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
