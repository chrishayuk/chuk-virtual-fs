"""
Tests for batch_operations.py
"""

import pytest

from chuk_virtual_fs.batch_operations import (
    BatchOperation,
    BatchOperationType,
    BatchProcessor,
    BatchResult,
)
from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider


@pytest.fixture
async def provider():
    """Create a memory storage provider"""
    provider = AsyncMemoryStorageProvider()
    await provider.initialize()
    yield provider
    await provider.close()


@pytest.fixture
def batch_processor(provider):
    """Create a batch processor"""
    return BatchProcessor(provider, max_concurrent=5, chunk_size=10)


class TestBatchOperations:
    """Test batch operation classes"""

    def test_batch_operation_creation(self):
        """Test creating batch operations"""
        op = BatchOperation(
            operation_type=BatchOperationType.CREATE,
            path="/test.txt",
            data=b"content",
        )
        assert op.operation_type == BatchOperationType.CREATE
        assert op.path == "/test.txt"
        assert op.data == b"content"

    def test_batch_result_creation(self):
        """Test creating batch results"""
        op = BatchOperation(operation_type=BatchOperationType.READ, path="/test.txt")
        result = BatchResult(success=True, operation=op, result=b"data")
        assert result.success
        assert result.operation == op
        assert result.result == b"data"


class TestBatchProcessor:
    """Test BatchProcessor"""

    @pytest.mark.asyncio
    async def test_batch_processor_initialization(self, provider):
        """Test batch processor initialization"""
        processor = BatchProcessor(
            provider, max_concurrent=10, chunk_size=50, retry_handler=None
        )
        assert processor.provider == provider
        assert processor.max_concurrent == 10
        assert processor.chunk_size == 50
        assert processor.retry_handler is not None
        assert processor.stats["total_operations"] == 0

    @pytest.mark.asyncio
    async def test_execute_batch_stop_on_error(self, batch_processor):
        """Test execute_batch with stop_on_error"""
        # Create operations where one will fail
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.CREATE,
                path="/file1.txt",
                data=EnhancedNodeInfo(name="file1.txt", is_dir=False, parent_path="/"),
            ),
            BatchOperation(
                operation_type=BatchOperationType.DELETE, path="/nonexistent.txt"
            ),
            BatchOperation(
                operation_type=BatchOperationType.CREATE,
                path="/file3.txt",
                data=EnhancedNodeInfo(name="file3.txt", is_dir=False, parent_path="/"),
            ),
        ]

        results = await batch_processor.execute_batch(operations, stop_on_error=True)

        # Should have some results (may stop early on error)
        assert len(results) >= 1
        assert batch_processor.stats["total_operations"] >= 1

    @pytest.mark.asyncio
    async def test_execute_batch_exception_handling(self, batch_processor):
        """Test exception handling in batch execution"""
        # Create an operation that will cause an exception
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.CREATE,
                path="/test.txt",
                data="invalid_data",  # Should be EnhancedNodeInfo
            )
        ]

        results = await batch_processor.execute_batch(operations)

        assert len(results) == 1
        assert not results[0].success
        assert results[0].error is not None

    @pytest.mark.asyncio
    async def test_batch_copy_files(self, provider, batch_processor):
        """Test batch copy operations"""
        # Create source files first
        await provider.create_node(
            EnhancedNodeInfo(name="source1.txt", is_dir=False, parent_path="/")
        )
        await provider.write_file("/source1.txt", b"content1")

        await provider.create_node(
            EnhancedNodeInfo(name="source2.txt", is_dir=False, parent_path="/")
        )
        await provider.write_file("/source2.txt", b"content2")

        # Batch copy
        copy_specs = [
            ("/source1.txt", "/dest1.txt"),
            ("/source2.txt", "/dest2.txt"),
        ]

        results = await batch_processor.batch_copy_files(copy_specs)

        assert len(results) == 2
        assert all(r.success for r in results)

        # Verify copies exist
        assert await provider.exists("/dest1.txt")
        assert await provider.exists("/dest2.txt")

    @pytest.mark.asyncio
    async def test_batch_move_files(self, provider, batch_processor):
        """Test batch move operations"""
        # Create source files
        await provider.create_node(
            EnhancedNodeInfo(name="move1.txt", is_dir=False, parent_path="/")
        )
        await provider.write_file("/move1.txt", b"content1")

        await provider.create_node(
            EnhancedNodeInfo(name="move2.txt", is_dir=False, parent_path="/")
        )
        await provider.write_file("/move2.txt", b"content2")

        # Batch move
        move_specs = [
            ("/move1.txt", "/moved1.txt"),
            ("/move2.txt", "/moved2.txt"),
        ]

        results = await batch_processor.batch_move_files(move_specs)

        assert len(results) == 2
        assert all(r.success for r in results)

        # Verify moves
        assert await provider.exists("/moved1.txt")
        assert await provider.exists("/moved2.txt")

    @pytest.mark.asyncio
    async def test_batch_write_files(self, provider, batch_processor):
        """Test batch_write_files method"""
        # Create files first
        await provider.create_node(
            EnhancedNodeInfo(name="write1.txt", is_dir=False, parent_path="/")
        )
        await provider.create_node(
            EnhancedNodeInfo(name="write2.txt", is_dir=False, parent_path="/")
        )

        # Batch write
        file_data = {
            "/write1.txt": b"new content 1",
            "/write2.txt": b"new content 2",
        }

        results = await batch_processor.batch_write_files(file_data)

        assert len(results) == 2
        assert all(r.success for r in results)

        # Verify content
        content1 = await provider.read_file("/write1.txt")
        assert content1 == b"new content 1"

    @pytest.mark.asyncio
    async def test_batch_update_metadata(self, provider, batch_processor):
        """Test batch metadata updates"""
        # Create files
        await provider.create_node(
            EnhancedNodeInfo(name="meta1.txt", is_dir=False, parent_path="/")
        )
        await provider.write_file("/meta1.txt", b"content")

        await provider.create_node(
            EnhancedNodeInfo(name="meta2.txt", is_dir=False, parent_path="/")
        )
        await provider.write_file("/meta2.txt", b"content")

        # Update metadata
        metadata_updates = {
            "/meta1.txt": {"owner": "user1", "tags": {"env": "prod"}},
            "/meta2.txt": {"owner": "user2", "tags": {"env": "dev"}},
        }

        results = await batch_processor.batch_update_metadata(metadata_updates)

        assert len(results) == 2
        assert all(r.success for r in results)

        # Verify metadata
        meta1 = await provider.get_metadata("/meta1.txt")
        assert meta1["owner"] == "user1"

    @pytest.mark.asyncio
    async def test_batch_create_with_metadata(self, batch_processor):
        """Test batch_create_files with metadata"""
        file_specs = [
            {
                "path": "/test1.txt",
                "content": b"content1",
                "metadata": {"owner": "testuser", "mime_type": "text/plain"},
            },
            {
                "path": "/test2.txt",
                "content": b"content2",
                "metadata": {"owner": "admin"},
            },
        ]

        results = await batch_processor.batch_create_files(file_specs)

        # Each file creates 2 operations (create + write)
        assert len(results) == 4
        assert batch_processor.stats["total_operations"] == 4

    @pytest.mark.asyncio
    async def test_get_stats(self, batch_processor):
        """Test get_stats with calculations"""
        # Execute some operations to populate stats
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.CREATE,
                path="/stat_test.txt",
                data=EnhancedNodeInfo(
                    name="stat_test.txt", is_dir=False, parent_path="/"
                ),
            )
        ]

        await batch_processor.execute_batch(operations)

        stats = batch_processor.get_stats()

        assert "total_operations" in stats
        assert "successful_operations" in stats
        assert "failed_operations" in stats
        assert "average_duration_ms" in stats
        assert "success_rate" in stats
        assert stats["total_operations"] > 0
        assert stats["success_rate"] >= 0

    @pytest.mark.asyncio
    async def test_reset_stats(self, batch_processor):
        """Test reset_stats method"""
        # Execute operation to populate stats
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.CREATE,
                path="/reset_test.txt",
                data=EnhancedNodeInfo(
                    name="reset_test.txt", is_dir=False, parent_path="/"
                ),
            )
        ]

        await batch_processor.execute_batch(operations)
        assert batch_processor.stats["total_operations"] > 0

        # Reset
        batch_processor.reset_stats()

        assert batch_processor.stats["total_operations"] == 0
        assert batch_processor.stats["successful_operations"] == 0
        assert batch_processor.stats["failed_operations"] == 0

    @pytest.mark.asyncio
    async def test_unknown_operation_type(self, batch_processor):
        """Test handling of unknown operation type"""

        # Create a simple object with a value that doesn't match any operation type
        class FakeOperationType:
            def __init__(self):
                self.value = "unknown_operation"

            def __eq__(self, other):
                return False  # Never equal to any BatchOperationType

            def __repr__(self):
                return f"FakeOperationType({self.value})"

        operation = BatchOperation(operation_type=FakeOperationType(), path="/test.txt")

        # This should raise ValueError for unknown operation type
        with pytest.raises(ValueError, match="Unknown operation type"):
            await batch_processor._perform_operation(operation)

    @pytest.mark.asyncio
    async def test_get_metadata_operation(self, provider, batch_processor):
        """Test METADATA operation for getting metadata"""
        # Create a file
        await provider.create_node(
            EnhancedNodeInfo(name="getmeta.txt", is_dir=False, parent_path="/")
        )
        await provider.write_file("/getmeta.txt", b"content")

        # Get metadata via batch operation (data=None means get)
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.METADATA,
                path="/getmeta.txt",
                data=None,  # None means get metadata
            )
        ]

        results = await batch_processor.execute_batch(operations)

        assert len(results) == 1
        assert results[0].success
        assert results[0].result is not None
        assert "name" in results[0].result

    @pytest.mark.asyncio
    async def test_large_batch_chunking(self, provider, batch_processor):
        """Test that large batches are properly chunked"""
        # Set small chunk size
        batch_processor.chunk_size = 5

        # Create 20 operations (should be split into 4 chunks)
        operations = []
        for i in range(20):
            operations.append(
                BatchOperation(
                    operation_type=BatchOperationType.CREATE,
                    path=f"/chunk_test_{i}.txt",
                    data=EnhancedNodeInfo(
                        name=f"chunk_test_{i}.txt", is_dir=False, parent_path="/"
                    ),
                )
            )

        results = await batch_processor.execute_batch(operations)

        assert len(results) == 20
        assert batch_processor.stats["total_operations"] == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
