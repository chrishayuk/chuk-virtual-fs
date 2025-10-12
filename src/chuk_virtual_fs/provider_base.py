"""
chuk_virtual_fs/async_provider_base.py - Async base class for storage providers
"""

import asyncio
import hashlib
from abc import ABC, abstractmethod
from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo


class AsyncStorageProvider(ABC):
    """Abstract async base class for filesystem storage providers"""

    def __init__(self) -> None:
        self._closed = False
        self._lock = asyncio.Lock()
        self._retry_max = 3
        self._retry_delay = 1.0

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the storage provider"""

    @abstractmethod
    async def close(self) -> None:
        """Close and cleanup provider resources"""

    @abstractmethod
    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node (file or directory)"""

    @abstractmethod
    async def delete_node(self, path: str) -> bool:
        """Delete a node"""

    @abstractmethod
    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get information about a node"""

    @abstractmethod
    async def list_directory(self, path: str) -> list[str]:
        """List contents of a directory"""

    @abstractmethod
    async def write_file(self, path: str, content: bytes) -> bool:
        """Write content to a file"""

    @abstractmethod
    async def read_file(self, path: str) -> bytes | None:
        """Read content from a file"""

    @abstractmethod
    async def get_storage_stats(self) -> dict:
        """Get storage statistics"""

    @abstractmethod
    async def cleanup(self) -> dict:
        """Perform cleanup operations"""

    # Enhanced async methods

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a path exists"""

    @abstractmethod
    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get enhanced metadata for a node"""

    @abstractmethod
    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set custom metadata for a node"""

    async def calculate_checksum(self, content: bytes) -> str:
        """Calculate SHA256 checksum of content"""
        return hashlib.sha256(content).hexdigest()

    async def copy_node(self, source: str, destination: str) -> bool:
        """Copy a node from source to destination"""
        node_info = await self.get_node_info(source)
        if not node_info:
            return False

        if not node_info.is_dir:
            content = await self.read_file(source)
            if content is None:
                return False

            dest_info = EnhancedNodeInfo(
                name=destination.split("/")[-1],
                is_dir=False,
                parent_path="/".join(destination.split("/")[:-1]) or "/",
            )

            if not await self.create_node(dest_info):
                return False

            return await self.write_file(destination, content)
        else:
            # Handle directory copy
            dest_info = EnhancedNodeInfo(
                name=destination.split("/")[-1],
                is_dir=True,
                parent_path="/".join(destination.split("/")[:-1]) or "/",
            )

            if not await self.create_node(dest_info):
                return False

            # Copy contents recursively
            items = await self.list_directory(source)
            for item in items:
                src_path = f"{source}/{item}".replace("//", "/")
                dest_path = f"{destination}/{item}".replace("//", "/")
                await self.copy_node(src_path, dest_path)

            return True

    async def move_node(self, source: str, destination: str) -> bool:
        """Move a node from source to destination"""
        if await self.copy_node(source, destination):
            return await self.delete_node(source)
        return False

    # Batch operations

    async def batch_create(self, nodes: list[EnhancedNodeInfo]) -> list[bool]:
        """Create multiple nodes in batch"""
        tasks = [self.create_node(node) for node in nodes]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def batch_delete(self, paths: list[str]) -> list[bool]:
        """Delete multiple nodes in batch"""
        tasks = [self.delete_node(path) for path in paths]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def batch_read(self, paths: list[str]) -> list[bytes | None]:
        """Read multiple files in batch"""
        tasks = [self.read_file(path) for path in paths]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def batch_write(self, operations: list[tuple[str, bytes]]) -> list[bool]:
        """Write multiple files in batch"""
        tasks = [self.write_file(path, content) for path, content in operations]
        return await asyncio.gather(*tasks, return_exceptions=False)

    # Retry mechanism

    async def with_retry(
        self, func: Any, *args: Any, max_retries: int | None = None, **kwargs: Any
    ) -> Any:
        """Execute function with retry logic"""
        max_retries = max_retries or self._retry_max
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = self._retry_delay * (2**attempt)  # Exponential backoff
                    await asyncio.sleep(delay)
                    continue

        if last_exception:
            raise last_exception
        raise Exception("Retry failed with unknown error")

    # Context manager support

    async def __aenter__(self) -> "AsyncStorageProvider":
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Async context manager exit"""
        await self.close()
        return False

    # Presigned URL support (optional, provider-specific)

    async def generate_presigned_url(
        self, path: str, operation: str = "GET", expires_in: int = 3600
    ) -> str | None:
        """Generate a presigned URL for the given path (provider-specific)"""
        return None

    async def generate_presigned_upload_url(
        self, path: str, expires_in: int = 3600
    ) -> tuple[str, str] | None:
        """Generate a presigned URL for uploading (provider-specific)"""
        return None

    # Streaming operations

    async def stream_write(
        self,
        path: str,
        stream: Any,
        chunk_size: int = 8192,
        progress_callback: Any = None,
    ) -> bool:
        """
        Write content to a file from an async stream with atomic safety

        Args:
            path: Path to write to
            stream: AsyncIterator[bytes] or AsyncIterable[bytes]
            chunk_size: Size of chunks to buffer
            progress_callback: Optional callback function(bytes_written, total_bytes)
                             Called after each chunk. total_bytes is -1 if unknown.

        Returns:
            True if successful

        Note:
            Default implementation uses atomic write pattern:
            1. Writes to temporary file (path.tmp)
            2. Moves to final location on success
            3. Cleans up temp file on failure

            This prevents corruption if write fails midway.
            Providers should override for provider-specific optimizations.
        """
        # Use temp file for atomic writes
        temp_path = f"{path}.tmp"

        try:
            chunks = []
            total_bytes = 0

            # Collect chunks with progress reporting
            async for chunk in stream:
                chunks.append(chunk)
                total_bytes += len(chunk)

                # Report progress if callback provided
                if progress_callback:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(total_bytes, -1)
                    else:
                        progress_callback(total_bytes, -1)

            content = b"".join(chunks)

            # Create temp file node if it doesn't exist
            if not await self.exists(temp_path):
                from chuk_virtual_fs.node_info import EnhancedNodeInfo

                temp_node = EnhancedNodeInfo(
                    name=f"{path.split('/')[-1]}.tmp",
                    is_dir=False,
                    parent_path="/".join(path.split("/")[:-1]) or "/",
                )
                await self.create_node(temp_node)

            # Write to temp file
            success = await self.write_file(temp_path, content)
            if not success:
                # Cleanup temp file
                await self.delete_node(temp_path)
                return False

            # Atomically move temp to final location
            # If target exists, delete it first
            if await self.exists(path):
                await self.delete_node(path)

            # Create final node if it doesn't exist
            if not await self.exists(path):
                from chuk_virtual_fs.node_info import EnhancedNodeInfo

                final_node = EnhancedNodeInfo(
                    name=path.split("/")[-1],
                    is_dir=False,
                    parent_path="/".join(path.split("/")[:-1]) or "/",
                )
                await self.create_node(final_node)

            # Move temp to final (atomic on most providers)
            move_success = await self.move_node(temp_path, path)

            if not move_success:
                # If move failed, try copy + delete
                content_temp = await self.read_file(temp_path)
                if content_temp:
                    await self.write_file(path, content_temp)
                    await self.delete_node(temp_path)
                    return True
                return False

            return True

        except Exception as e:
            # Cleanup temp file on any error
            if await self.exists(temp_path):
                await self.delete_node(temp_path)
            raise e

    async def stream_read(self, path: str, chunk_size: int = 8192) -> Any:
        """
        Read content from a file as an async stream

        Args:
            path: Path to read from
            chunk_size: Size of chunks to yield

        Yields:
            bytes: Chunks of file content

        Note:
            Default implementation reads entire file then yields chunks.
            Providers should override for true streaming support.
        """
        content = await self.read_file(path)
        if content is None:
            return

        # Yield content in chunks
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]


# Backwards compatibility alias
StorageProvider = AsyncStorageProvider
