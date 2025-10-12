"""
chuk_virtual_fs/batch_operations.py - Batch operations for efficient bulk processing
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.retry_handler import RetryHandler

logger = logging.getLogger(__name__)


class BatchOperationType(Enum):
    """Types of batch operations"""

    CREATE = "create"
    DELETE = "delete"
    READ = "read"
    WRITE = "write"
    COPY = "copy"
    MOVE = "move"
    METADATA = "metadata"


@dataclass
class BatchOperation:
    """Single operation in a batch"""

    operation_type: BatchOperationType
    path: str
    data: Any | None = None
    metadata: dict[str, Any] | None = None
    destination: str | None = None  # For copy/move operations


@dataclass
class BatchResult:
    """Result of a batch operation"""

    success: bool
    operation: BatchOperation
    result: Any | None = None
    error: str | None = None
    duration_ms: float = 0.0


class BatchProcessor:
    """
    Handles batch operations for virtual filesystem
    """

    def __init__(
        self,
        provider: Any,
        max_concurrent: int = 10,
        chunk_size: int = 100,
        retry_handler: RetryHandler | None = None,
    ):
        """
        Initialize batch processor

        Args:
            provider: Storage provider instance
            max_concurrent: Maximum concurrent operations
            chunk_size: Size of chunks for processing
            retry_handler: Optional retry handler
        """
        self.provider = provider
        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.retry_handler = retry_handler or RetryHandler()
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Statistics
        self.stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "total_duration_ms": 0.0,
        }

    async def execute_batch(
        self, operations: list[BatchOperation], stop_on_error: bool = False
    ) -> list[BatchResult]:
        """
        Execute a batch of operations

        Args:
            operations: List of operations to execute
            stop_on_error: Whether to stop on first error

        Returns:
            List of batch results
        """
        results = []

        # Process in chunks
        for i in range(0, len(operations), self.chunk_size):
            chunk = operations[i : i + self.chunk_size]
            chunk_results = await self._process_chunk(chunk, stop_on_error)
            results.extend(chunk_results)

            # Check if we should stop
            if stop_on_error and any(not r.success for r in chunk_results):
                break

        # Update statistics
        self.stats["total_operations"] += len(results)
        self.stats["successful_operations"] += sum(1 for r in results if r.success)
        self.stats["failed_operations"] += sum(1 for r in results if not r.success)
        self.stats["total_duration_ms"] += sum(r.duration_ms for r in results)

        return results

    async def _process_chunk(
        self, chunk: list[BatchOperation], stop_on_error: bool
    ) -> list[BatchResult]:
        """Process a chunk of operations concurrently"""
        tasks: list[asyncio.Task[BatchResult]] = []

        for operation in chunk:
            if stop_on_error and tasks:
                # Check if any previous task failed
                done, _ = await asyncio.wait(tasks, timeout=0)
                if any(not task.result().success for task in done if task.done()):
                    break

            task = asyncio.create_task(self._execute_operation(operation))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to BatchResult
        processed_results: list[BatchResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    BatchResult(success=False, operation=chunk[i], error=str(result))
                )
            else:
                processed_results.append(result)  # type: ignore[arg-type]

        return processed_results

    async def _execute_operation(self, operation: BatchOperation) -> BatchResult:
        """Execute a single operation with retry logic"""
        async with self.semaphore:
            start_time = asyncio.get_event_loop().time()

            try:
                result = await self.retry_handler.execute_async(
                    self._perform_operation, operation
                )

                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                return BatchResult(
                    success=True,
                    operation=operation,
                    result=result,
                    duration_ms=duration_ms,
                )

            except Exception as e:
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                logger.error(
                    f"Batch operation failed: {operation.operation_type} on {operation.path}: {e}"
                )

                return BatchResult(
                    success=False,
                    operation=operation,
                    error=str(e),
                    duration_ms=duration_ms,
                )

    async def _perform_operation(self, operation: BatchOperation) -> Any:
        """Perform the actual operation"""
        op_type = operation.operation_type

        if op_type == BatchOperationType.CREATE:
            return await self.provider.create_node(operation.data)

        elif op_type == BatchOperationType.DELETE:
            return await self.provider.delete_node(operation.path)

        elif op_type == BatchOperationType.READ:
            return await self.provider.read_file(operation.path)

        elif op_type == BatchOperationType.WRITE:
            return await self.provider.write_file(operation.path, operation.data)

        elif op_type == BatchOperationType.COPY:
            return await self.provider.copy_node(operation.path, operation.destination)

        elif op_type == BatchOperationType.MOVE:
            return await self.provider.move_node(operation.path, operation.destination)

        elif op_type == BatchOperationType.METADATA:
            if operation.data:
                return await self.provider.set_metadata(operation.path, operation.data)
            else:
                return await self.provider.get_metadata(operation.path)

        else:
            raise ValueError(f"Unknown operation type: {op_type}")

    # Convenience methods for common batch operations

    async def batch_create_files(
        self, file_specs: list[dict[str, Any]]
    ) -> list[BatchResult]:
        """
        Create multiple files in batch

        Args:
            file_specs: List of file specifications with 'path', 'content', and optional 'metadata'

        Returns:
            List of batch results
        """
        operations = []

        for spec in file_specs:
            # Create node info
            path = spec["path"]
            name = path.split("/")[-1]
            parent = "/".join(path.split("/")[:-1]) or "/"

            node_info = EnhancedNodeInfo(name=name, is_dir=False, parent_path=parent)

            # Set metadata if provided
            if "metadata" in spec:
                for key, value in spec["metadata"].items():
                    if hasattr(node_info, key):
                        setattr(node_info, key, value)

            # Create the node first
            operations.append(
                BatchOperation(
                    operation_type=BatchOperationType.CREATE, path=path, data=node_info
                )
            )

            # Then write content
            if "content" in spec:
                operations.append(
                    BatchOperation(
                        operation_type=BatchOperationType.WRITE,
                        path=path,
                        data=spec["content"],
                    )
                )

        return await self.execute_batch(operations)

    async def batch_delete_paths(self, paths: list[str]) -> list[BatchResult]:
        """Delete multiple paths in batch"""
        operations = [
            BatchOperation(operation_type=BatchOperationType.DELETE, path=path)
            for path in paths
        ]
        return await self.execute_batch(operations)

    async def batch_read_files(self, paths: list[str]) -> dict[str, bytes]:
        """
        Read multiple files in batch

        Returns:
            Dictionary mapping paths to file contents
        """
        operations = [
            BatchOperation(operation_type=BatchOperationType.READ, path=path)
            for path in paths
        ]

        results = await self.execute_batch(operations)

        return {
            r.operation.path: r.result
            for r in results
            if r.success and r.result is not None
        }

    async def batch_write_files(self, file_data: dict[str, bytes]) -> list[BatchResult]:
        """
        Write multiple files in batch

        Args:
            file_data: Dictionary mapping paths to file contents
        """
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.WRITE, path=path, data=content
            )
            for path, content in file_data.items()
        ]
        return await self.execute_batch(operations)

    async def batch_copy_files(
        self, copy_specs: list[tuple[str, str]]
    ) -> list[BatchResult]:
        """
        Copy multiple files in batch

        Args:
            copy_specs: List of (source, destination) tuples
        """
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.COPY,
                path=source,
                destination=destination,
            )
            for source, destination in copy_specs
        ]
        return await self.execute_batch(operations)

    async def batch_move_files(
        self, move_specs: list[tuple[str, str]]
    ) -> list[BatchResult]:
        """
        Move multiple files in batch

        Args:
            move_specs: List of (source, destination) tuples
        """
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.MOVE,
                path=source,
                destination=destination,
            )
            for source, destination in move_specs
        ]
        return await self.execute_batch(operations)

    async def batch_update_metadata(
        self, metadata_updates: dict[str, dict[str, Any]]
    ) -> list[BatchResult]:
        """
        Update metadata for multiple files

        Args:
            metadata_updates: Dictionary mapping paths to metadata updates
        """
        operations = [
            BatchOperation(
                operation_type=BatchOperationType.METADATA, path=path, data=metadata
            )
            for path, metadata in metadata_updates.items()
        ]
        return await self.execute_batch(operations)

    def get_stats(self) -> dict[str, Any]:
        """Get batch processing statistics"""
        stats = self.stats.copy()
        if stats["total_operations"] > 0:
            stats["average_duration_ms"] = (
                stats["total_duration_ms"] / stats["total_operations"]
            )
            stats["success_rate"] = (
                stats["successful_operations"] / stats["total_operations"]
            )
        return stats

    def reset_stats(self) -> None:
        """Reset statistics"""
        self.stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "total_duration_ms": 0.0,
        }
