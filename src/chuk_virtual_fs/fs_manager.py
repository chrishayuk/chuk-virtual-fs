"""
chuk_virtual_fs/fs_manager.py - Async virtual filesystem manager
"""

from __future__ import annotations

import logging
import posixpath
from typing import TYPE_CHECKING, Any

from chuk_virtual_fs.batch_operations import BatchProcessor
from chuk_virtual_fs.mount_manager import MountManager
from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.retry_handler import RetryHandler

if TYPE_CHECKING:
    from chuk_virtual_fs.provider_base import AsyncStorageProvider

logger = logging.getLogger(__name__)


class AsyncVirtualFileSystem:
    """
    Simplified async virtual filesystem manager focused on core file operations
    """

    def __init__(
        self,
        provider: str = "memory",
        enable_retry: bool = True,
        enable_batch: bool = True,
        enable_mounts: bool = True,
        max_concurrent: int = 10,
        **provider_kwargs: Any,
    ) -> None:
        """
        Initialize async virtual filesystem

        Args:
            provider: Storage provider name ("memory", "s3", "filesystem")
            enable_retry: Enable retry logic for operations
            enable_batch: Enable batch operations
            enable_mounts: Enable virtual mount support
            max_concurrent: Maximum concurrent operations for batch processing
            **provider_kwargs: Additional arguments for the provider
        """
        self.provider_name = provider
        self.provider_kwargs = provider_kwargs
        self.enable_retry = enable_retry
        self.enable_batch = enable_batch
        self.enable_mounts = enable_mounts
        self.max_concurrent = max_concurrent

        # Components
        self.provider: AsyncStorageProvider | None = None
        self.batch_processor: BatchProcessor | None = None
        self.retry_handler: RetryHandler | None = None
        self.mount_manager: MountManager | None = None

        # State
        self.current_directory = "/"
        self._initialized = False
        self._closed = False

        # Statistics
        self.stats = {
            "operations": 0,
            "errors": 0,
            "bytes_read": 0,
            "bytes_written": 0,
            "files_created": 0,
            "files_deleted": 0,
        }

    async def initialize(self) -> None:
        """Initialize the filesystem and components"""
        if self._initialized:
            return

        # Initialize provider
        await self._init_provider()

        # Initialize retry handler
        if self.enable_retry:
            self.retry_handler = RetryHandler(
                max_retries=3,
                base_delay=1.0,
                max_delay=30.0,
                exponential_base=2.0,
                jitter=True,
            )

        # Initialize batch processor
        if self.enable_batch:
            self.batch_processor = BatchProcessor(
                provider=self.provider,
                max_concurrent=self.max_concurrent,
                retry_handler=self.retry_handler,
            )

        # Initialize mount manager
        if self.enable_mounts:
            self.mount_manager = MountManager()

        self._initialized = True
        logger.info(
            f"Initialized AsyncVirtualFileSystem with {self.provider_name} provider"
        )

    async def _init_provider(self) -> None:
        """Initialize the storage provider"""
        if self.provider_name == "memory":
            from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider

            self.provider = AsyncMemoryStorageProvider(**self.provider_kwargs)
        elif self.provider_name == "s3":
            from chuk_virtual_fs.providers.s3 import S3StorageProvider

            self.provider = S3StorageProvider(**self.provider_kwargs)
        elif self.provider_name == "sqlite":
            from chuk_virtual_fs.providers.sqlite import SqliteStorageProvider

            self.provider = SqliteStorageProvider(**self.provider_kwargs)
        elif self.provider_name == "filesystem":
            from chuk_virtual_fs.providers.filesystem import (
                AsyncFilesystemStorageProvider,
            )

            self.provider = AsyncFilesystemStorageProvider(**self.provider_kwargs)
        else:
            raise ValueError(f"Unknown provider: {self.provider_name}")

        await self.provider.initialize()

    async def close(self) -> None:
        """Close and cleanup resources"""
        if self._closed:
            return

        if self.mount_manager:
            await self.mount_manager.close_all()

        if self.provider:
            await self.provider.close()

        self._closed = True
        logger.info("Closed AsyncVirtualFileSystem")

    async def __aenter__(self) -> AsyncVirtualFileSystem:
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Async context manager exit"""
        await self.close()
        return False

    # Mount management

    def _get_provider_for_path(self, path: str) -> tuple[AsyncStorageProvider, str]:
        """
        Get the appropriate provider for a given path

        Returns:
            Tuple of (provider, local_path) where local_path is translated for the provider
        """
        if self.mount_manager:
            result = self.mount_manager.get_provider(path)
            if result:
                return result

        # Fall back to default provider
        assert self.provider is not None, "Provider must be initialized"
        return (self.provider, path)

    async def mount(
        self,
        mount_point: str,
        provider: str,
        **provider_kwargs: Any,
    ) -> bool:
        """
        Mount a provider at a specific path

        Args:
            mount_point: Path where provider should be mounted (e.g., "/cloud")
            provider: Provider name ("s3", "filesystem", "memory")
            **provider_kwargs: Arguments for provider initialization

        Returns:
            True if mount successful

        Example:
            await fs.mount("/cloud", provider="s3", bucket_name="my-bucket")
            await fs.mount("/local", provider="filesystem", root_path="/tmp")
        """
        if not self.mount_manager:
            logger.error("Mount manager not enabled")
            return False

        return await self.mount_manager.mount(mount_point, provider, provider_kwargs)

    async def unmount(self, mount_point: str) -> bool:
        """
        Unmount a provider

        Args:
            mount_point: Path to unmount

        Returns:
            True if unmount successful
        """
        if not self.mount_manager:
            logger.error("Mount manager not enabled")
            return False

        return await self.mount_manager.unmount(mount_point)

    def list_mounts(self) -> list[dict[str, Any]]:
        """
        List all active mounts

        Returns:
            List of mount information dictionaries
        """
        if not self.mount_manager:
            return []

        return self.mount_manager.list_mounts()

    # Path utilities

    def resolve_path(self, path: str) -> str:
        """Resolve a path to its absolute form"""
        if not path:
            return self.current_directory

        if path.startswith("/"):
            # Absolute path
            return posixpath.normpath(path)
        else:
            # Relative path
            return posixpath.normpath(posixpath.join(self.current_directory, path))

    def split_path(self, path: str) -> tuple[str, str]:
        """Split path into parent and name"""
        path = self.resolve_path(path)
        if path == "/":
            return "/", ""
        parent, name = posixpath.split(path)
        return parent or "/", name

    # Core operations with retry support

    async def _execute(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute function with optional retry"""
        if self.retry_handler:
            return await self.retry_handler.execute_async(func, *args, **kwargs)
        else:
            return await func(*args, **kwargs)

    # Directory operations

    async def mkdir(self, path: str, **metadata: Any) -> bool:
        """Create a directory"""
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        # Check if already exists
        if await provider.exists(local_path):
            return False

        parent, name = self.split_path(local_path)

        node_info = EnhancedNodeInfo(
            name=name, is_dir=True, parent_path=parent, **metadata
        )

        result = await self._execute(provider.create_node, node_info)

        if result:
            self.stats["operations"] += 1
        else:
            self.stats["errors"] += 1

        return result

    async def rmdir(self, path: str) -> bool:
        """Remove an empty directory"""
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        # Check if exists and is directory
        node_info = await provider.get_node_info(local_path)
        if not node_info or not node_info.is_dir:
            return False

        # Check if empty
        contents = await provider.list_directory(local_path)
        if contents:
            return False

        result = await self._execute(provider.delete_node, local_path)

        if result:
            self.stats["operations"] += 1
        else:
            self.stats["errors"] += 1

        return result

    async def ls(self, path: str | None = None) -> list[str]:
        """List directory contents"""
        resolved_path = self.resolve_path(path) if path else self.current_directory

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        contents = await provider.list_directory(local_path)
        self.stats["operations"] += 1

        return contents

    async def cd(self, path: str) -> bool:
        """Change current directory"""
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        node_info = await provider.get_node_info(local_path)
        if not node_info or not node_info.is_dir:
            return False

        self.current_directory = resolved_path
        return True

    def pwd(self) -> str:
        """Get current working directory"""
        return self.current_directory

    # File operations

    async def touch(self, path: str, **metadata: Any) -> bool:
        """Create an empty file"""
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        # If file exists, update timestamp and return success
        if await provider.exists(local_path):
            node_info = await provider.get_node_info(local_path)
            if node_info and not node_info.is_dir:
                node_info.update_modified()
                return True
            return False

        parent, name = self.split_path(local_path)

        node_info = EnhancedNodeInfo(
            name=name, is_dir=False, parent_path=parent, **metadata
        )
        node_info.set_mime_type()

        if not await self._execute(provider.create_node, node_info):
            self.stats["errors"] += 1
            return False

        result = await self._execute(provider.write_file, local_path, b"")

        if result:
            self.stats["operations"] += 1
            self.stats["files_created"] += 1
        else:
            self.stats["errors"] += 1

        return result

    async def write_file(
        self, path: str, content: str | bytes, **metadata: Any
    ) -> bool:
        """Write content to a file (accepts both str and bytes)"""
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        # Convert string to bytes
        if isinstance(content, str):
            content = content.encode("utf-8")

        # Create file if it doesn't exist
        if not await provider.exists(local_path) and not await self.touch(
            resolved_path, **metadata
        ):
            return False

        result = await self._execute(provider.write_file, local_path, content)

        if result:
            self.stats["operations"] += 1
            self.stats["bytes_written"] += len(content)
        else:
            self.stats["errors"] += 1

        return result

    async def write_binary(self, path: str, content: bytes, **metadata: Any) -> bool:
        """
        Explicitly write binary content to a file

        Args:
            path: File path
            content: Binary content as bytes
            **metadata: Optional metadata for the file

        Returns:
            True if successful, False otherwise
        """
        if not isinstance(content, bytes):
            raise TypeError(
                "write_binary requires bytes, not str. Use write_text for strings."
            )

        return await self.write_file(path, content, **metadata)

    async def write_text(
        self, path: str, content: str, encoding: str = "utf-8", **metadata: Any
    ) -> bool:
        """
        Explicitly write text content to a file

        Args:
            path: File path
            content: Text content as string
            encoding: Text encoding (default: utf-8)
            **metadata: Optional metadata for the file

        Returns:
            True if successful, False otherwise
        """
        if not isinstance(content, str):
            raise TypeError(
                "write_text requires str, not bytes. Use write_binary for bytes."
            )

        binary_content = content.encode(encoding)
        return await self.write_file(path, binary_content, **metadata)

    async def read_file(self, path: str, as_text: bool = False) -> bytes | str | None:
        """Read content from a file (legacy method - prefer read_binary or read_text)"""
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        content = await self._execute(provider.read_file, local_path)

        if content is not None:
            self.stats["operations"] += 1
            self.stats["bytes_read"] += len(content)

            if as_text:
                content = content.decode("utf-8")
        else:
            self.stats["errors"] += 1

        return content

    async def read_binary(self, path: str) -> bytes | None:
        """
        Explicitly read binary content from a file

        Args:
            path: File path

        Returns:
            Binary content as bytes, or None if file doesn't exist
        """
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        content = await self._execute(provider.read_file, local_path)

        if content is not None:
            self.stats["operations"] += 1
            self.stats["bytes_read"] += len(content)
        else:
            self.stats["errors"] += 1

        return content

    async def read_text(
        self, path: str, encoding: str = "utf-8", errors: str = "strict"
    ) -> str | None:
        """
        Explicitly read text content from a file

        Args:
            path: File path
            encoding: Text encoding (default: utf-8)
            errors: How to handle decode errors ('strict', 'ignore', 'replace')

        Returns:
            Text content as string, or None if file doesn't exist
        """
        content = await self.read_binary(path)

        if content is None:
            return None

        try:
            return content.decode(encoding, errors=errors)
        except UnicodeDecodeError as e:
            self.stats["errors"] += 1
            raise e

    async def rm(self, path: str) -> bool:
        """Remove a file or empty directory"""
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        result = await self._execute(provider.delete_node, local_path)

        if result:
            self.stats["operations"] += 1
            self.stats["files_deleted"] += 1
        else:
            self.stats["errors"] += 1

        return result

    async def exists(self, path: str) -> bool:
        """Check if a path exists"""
        resolved_path = self.resolve_path(path)
        provider, local_path = self._get_provider_for_path(resolved_path)
        return await provider.exists(local_path)

    async def is_file(self, path: str) -> bool:
        """Check if path is a file"""
        resolved_path = self.resolve_path(path)
        provider, local_path = self._get_provider_for_path(resolved_path)
        node_info = await provider.get_node_info(local_path)
        return node_info is not None and not node_info.is_dir

    async def is_dir(self, path: str) -> bool:
        """Check if path is a directory"""
        resolved_path = self.resolve_path(path)
        provider, local_path = self._get_provider_for_path(resolved_path)
        node_info = await provider.get_node_info(local_path)
        return node_info is not None and node_info.is_dir

    # Copy and move operations

    async def cp(self, source: str, destination: str) -> bool:
        """Copy a file or directory"""
        src_path = self.resolve_path(source)
        dest_path = self.resolve_path(destination)

        # Get provider for source path
        provider, local_src = self._get_provider_for_path(src_path)

        result = await self._execute(provider.copy_node, local_src, dest_path)

        if result:
            self.stats["operations"] += 1
        else:
            self.stats["errors"] += 1

        return result

    async def mv(self, source: str, destination: str) -> bool:
        """Move a file or directory"""
        src_path = self.resolve_path(source)
        dest_path = self.resolve_path(destination)

        # Get provider for source path
        provider, local_src = self._get_provider_for_path(src_path)

        result = await self._execute(provider.move_node, local_src, dest_path)

        if result:
            self.stats["operations"] += 1
        else:
            self.stats["errors"] += 1

        return result

    # Metadata operations

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a file or directory"""
        resolved_path = self.resolve_path(path)
        provider, local_path = self._get_provider_for_path(resolved_path)
        metadata = await provider.get_metadata(local_path)
        self.stats["operations"] += 1
        return metadata

    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set metadata for a file or directory"""
        resolved_path = self.resolve_path(path)
        provider, local_path = self._get_provider_for_path(resolved_path)
        result = await provider.set_metadata(local_path, metadata)

        if result:
            self.stats["operations"] += 1
        else:
            self.stats["errors"] += 1

        return result

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get node information"""
        resolved_path = self.resolve_path(path)
        provider, local_path = self._get_provider_for_path(resolved_path)
        return await provider.get_node_info(local_path)

    # Batch operations

    async def batch_create_files(self, file_specs: list[dict[str, Any]]) -> list[Any]:
        """Create multiple files in batch"""
        if not self.batch_processor:
            raise RuntimeError("Batch operations not enabled")

        # Resolve paths
        for spec in file_specs:
            spec["path"] = self.resolve_path(spec["path"])

        results = await self.batch_processor.batch_create_files(file_specs)
        self.stats["operations"] += len(results)
        return results

    async def batch_read_files(self, paths: list[str]) -> dict[str, bytes]:
        """Read multiple files in batch"""
        if not self.batch_processor:
            raise RuntimeError("Batch operations not enabled")

        resolved_paths = [self.resolve_path(p) for p in paths]
        results = await self.batch_processor.batch_read_files(resolved_paths)
        self.stats["operations"] += len(results)
        return results

    async def batch_write_files(self, file_data: dict[str, bytes]) -> list[Any]:
        """Write multiple files in batch"""
        if not self.batch_processor:
            raise RuntimeError("Batch operations not enabled")

        resolved_data = {
            self.resolve_path(path): content for path, content in file_data.items()
        }
        results = await self.batch_processor.batch_write_files(resolved_data)
        self.stats["operations"] += len(results)
        return results

    async def batch_delete_paths(self, paths: list[str]) -> list[Any]:
        """Delete multiple paths in batch"""
        if not self.batch_processor:
            raise RuntimeError("Batch operations not enabled")

        resolved_paths = [self.resolve_path(p) for p in paths]
        results = await self.batch_processor.batch_delete_paths(resolved_paths)
        self.stats["operations"] += len(results)
        return results

    # Utility operations

    async def find(
        self, pattern: str = "*", path: str = "/", recursive: bool = True
    ) -> list[str]:
        """Find files matching a pattern"""
        import fnmatch

        assert self.provider is not None, "Provider must be initialized"

        results: list[str] = []

        async def search(current_path: str) -> None:
            try:
                assert self.provider is not None
                items = await self.provider.list_directory(current_path)
                for item in items:
                    item_path = posixpath.join(current_path, item)
                    node_info = await self.provider.get_node_info(item_path)

                    # Use fnmatch for glob pattern matching
                    if fnmatch.fnmatch(item, pattern) and (
                        node_info and not node_info.is_dir
                    ):  # Only include files, not directories
                        results.append(item_path)

                    if recursive and node_info and node_info.is_dir:
                        await search(item_path)
            except Exception:
                # Log but don't fail - directory might not exist
                pass

        start_path = self.resolve_path(path)
        await search(start_path)
        return results

    async def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics"""
        assert self.provider is not None, "Provider must be initialized"
        provider_stats = await self.provider.get_storage_stats()

        return {
            **provider_stats,
            "filesystem_stats": self.stats.copy(),
            "current_directory": self.current_directory,
            "provider": self.provider_name,
        }

    async def cleanup(self) -> dict[str, Any]:
        """Perform cleanup operations"""
        assert self.provider is not None, "Provider must be initialized"
        return await self.provider.cleanup()

    async def get_provider_name(self) -> str:
        """Get the name of the current storage provider"""
        return self.provider_name

    async def generate_presigned_url(
        self, path: str, expires_in: int = 3600
    ) -> str | None:
        """Generate a presigned URL if provider supports it"""
        resolved_path = self.resolve_path(path)
        provider, local_path = self._get_provider_for_path(resolved_path)
        return await provider.generate_presigned_url(local_path, expires_in=expires_in)

    # Streaming operations

    async def stream_write(
        self, path: str, stream: Any, chunk_size: int = 8192, **metadata: Any
    ) -> bool:
        """
        Write content to a file from an async stream

        Args:
            path: File path
            stream: AsyncIterator[bytes] or AsyncIterable[bytes]
            chunk_size: Size of chunks (provider-specific)
            **metadata: Optional metadata for the file

        Returns:
            True if successful, False otherwise

        Example:
            async def data_generator():
                for i in range(100):
                    yield f"chunk {i}\n".encode()

            await fs.stream_write("/large_file.txt", data_generator())
        """
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        # Create file if it doesn't exist
        if not await provider.exists(local_path) and not await self.touch(
            resolved_path, **metadata
        ):
            return False

        result = await self._execute(
            provider.stream_write, local_path, stream, chunk_size
        )

        if result:
            self.stats["operations"] += 1
            self.stats["files_created"] += 1
        else:
            self.stats["errors"] += 1

        return result

    async def stream_read(self, path: str, chunk_size: int = 8192) -> Any:
        """
        Read content from a file as an async stream

        Args:
            path: File path
            chunk_size: Size of chunks to yield

        Yields:
            bytes: Chunks of file content

        Example:
            async for chunk in fs.stream_read("/large_file.txt"):
                process(chunk)
        """
        resolved_path = self.resolve_path(path)

        # Get mount-aware provider
        provider, local_path = self._get_provider_for_path(resolved_path)

        self.stats["operations"] += 1

        async for chunk in provider.stream_read(local_path, chunk_size):
            self.stats["bytes_read"] += len(chunk)
            yield chunk


# Alias for backwards compatibility
VirtualFileSystem = AsyncVirtualFileSystem
