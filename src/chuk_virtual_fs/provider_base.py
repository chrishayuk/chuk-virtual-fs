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

    def __init__(self):
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

    async def with_retry(self, func, *args, max_retries: int = None, **kwargs):
        """Execute function with retry logic"""
        max_retries = max_retries or self._retry_max
        last_exception = None

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = self._retry_delay * (2**attempt)  # Exponential backoff
                    await asyncio.sleep(delay)
                    continue

        raise last_exception

    # Context manager support

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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


# Backwards compatibility alias
StorageProvider = AsyncStorageProvider
