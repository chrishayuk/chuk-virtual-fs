"""
chuk_virtual_fs/providers/e2b.py - Async E2B-based storage provider
"""

import asyncio
import builtins
import contextlib
import hashlib
import posixpath
import time
from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider


class E2BStorageProvider(AsyncStorageProvider):
    """
    Async E2B Sandbox storage provider

    Uses asyncio.to_thread() to run E2B operations asynchronously.
    Requires e2b_code_interpreter package: pip install e2b-code-interpreter
    """

    def __init__(
        self,
        sandbox_id: str | None = None,
        root_dir: str = "/home/user",
        auto_create_root: bool = True,
        timeout: int = 300,  # 5 minutes default
        **sandbox_kwargs: Any,
    ):
        """
        Initialize the E2B Sandbox storage provider

        Args:
            sandbox_id: Optional ID of an existing sandbox to connect to
            root_dir: Root directory in the sandbox (default: /home/user)
            auto_create_root: Whether to automatically create the root directory
            timeout: Sandbox timeout in seconds (default: 300)
            **sandbox_kwargs: Additional arguments to pass to Sandbox constructor
        """
        super().__init__()
        self._closed = False
        self.root_dir = root_dir
        self.sandbox: Any = None  # Type depends on e2b_code_interpreter package
        self.sandbox_id = sandbox_id
        self.auto_create_root = auto_create_root
        self.timeout = timeout
        self.sandbox_kwargs = sandbox_kwargs

        # Cache for node information to reduce API calls
        self.node_cache: dict[str, EnhancedNodeInfo] = {}
        self.cache_ttl = 30  # seconds
        self.cache_timestamps: dict[str, float] = {}

        # Track statistics locally to reduce API calls
        self._stats = {
            "total_size_bytes": 0,
            "file_count": 0,
            "directory_count": 1,  # Start with root directory
        }

    def _get_sandbox_path(self, path: str) -> str:
        """Convert virtual filesystem path to sandbox path"""
        if path == "/":
            return self.root_dir

        # Remove leading slash for joining with root_dir
        clean_path = path[1:] if path.startswith("/") else path
        return posixpath.join(self.root_dir, clean_path)

    def _check_cache(self, path: str) -> EnhancedNodeInfo | None:
        """Check if node info is in cache and still valid"""
        now = time.time()
        if (
            path in self.node_cache
            and now - self.cache_timestamps.get(path, 0) < self.cache_ttl
        ):
            cached: EnhancedNodeInfo = self.node_cache[path]
            return cached
        return None

    def _update_cache(self, path: str, node_info: EnhancedNodeInfo) -> None:
        """Update node info in cache"""
        self.node_cache[path] = node_info
        self.cache_timestamps[path] = time.time()

    async def initialize(self) -> bool:
        """Initialize the E2B provider (async)"""
        return await asyncio.to_thread(self._sync_initialize)

    def _sync_initialize(self) -> bool:
        """Initialize the E2B Sandbox provider"""
        try:
            from e2b_code_interpreter import Sandbox  # type: ignore[import-untyped]

            # Connect to existing sandbox or create a new one
            if self.sandbox_id:
                # Connect to the existing sandbox
                try:
                    self.sandbox = Sandbox.connect(self.sandbox_id)
                    print(
                        f"Successfully connected to existing sandbox: {self.sandbox_id}"
                    )
                except Exception as e:
                    print(f"Error connecting to sandbox {self.sandbox_id}: {e}")
                    print("Creating a new sandbox instead...")
                    self.sandbox = Sandbox(timeout=self.timeout, **self.sandbox_kwargs)
            else:
                # Create a new sandbox
                self.sandbox = Sandbox(timeout=self.timeout, **self.sandbox_kwargs)

            # Store the sandbox ID
            if self.sandbox:  # Type guard for mypy
                self.sandbox_id = self.sandbox.sandbox_id

                # Ensure the root directory exists if auto_create_root is True
                if self.auto_create_root:
                    # Check if root directory exists
                    try:
                        self.sandbox.files.list(self.root_dir)
                    except Exception:
                        # Directory doesn't exist, create it
                        self.sandbox.commands.run(f"mkdir -p {self.root_dir}")

            # Create root node info
            root_info = EnhancedNodeInfo("", True)
            self._update_cache("/", root_info)

            return True
        except ImportError:
            print(
                "Error: e2b_code_interpreter package is required for E2B storage provider"
            )
            return False
        except Exception as e:
            print(f"Error initializing E2B sandbox: {e}")
            return False

    async def close(self) -> None:
        """Close the E2B provider and cleanup"""
        await asyncio.to_thread(self._sync_close)

    def _sync_close(self) -> None:
        """Close the sandbox"""
        if self.sandbox:
            with contextlib.suppress(builtins.BaseException):
                self.sandbox.close()
            self.sandbox = None
        self.node_cache.clear()
        self.cache_timestamps.clear()
        self._closed = True

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node (async)"""
        return await asyncio.to_thread(self._sync_create_node, node_info)

    def _sync_create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node (file or directory)"""
        if not self.sandbox:
            return False

        try:
            path = node_info.get_path()
            sandbox_path = self._get_sandbox_path(path)

            # Check if the node already exists
            if self._sync_get_node_info(path):
                return False

            # Ensure parent directory exists
            parent_path = posixpath.dirname(path)
            if parent_path != path and not self._sync_get_node_info(parent_path):
                return False

            # Create the node
            if node_info.is_dir:
                # Create directory
                result = self.sandbox.commands.run(f"mkdir -p {sandbox_path}")
                if result.exit_code != 0:
                    return False

                # Update stats
                self._stats["directory_count"] += 1
            else:
                # Create empty file
                result = self.sandbox.commands.run(f"touch {sandbox_path}")
                if result.exit_code != 0:
                    return False

                # Update stats
                self._stats["file_count"] += 1

            # Add to cache
            self._update_cache(path, node_info)

            return True
        except Exception as e:
            print(f"Error creating node: {e}")
            return False

    async def delete_node(self, path: str) -> bool:
        """Delete a node (async)"""
        return await asyncio.to_thread(self._sync_delete_node, path)

    def _sync_delete_node(self, path: str) -> bool:
        """Delete a node"""
        if not self.sandbox:
            return False

        try:
            # Check if node exists
            node_info = self._sync_get_node_info(path)
            if not node_info:
                return False

            sandbox_path = self._get_sandbox_path(path)

            # Check if directory is empty (if it's a directory)
            if node_info.is_dir:
                result = self.sandbox.commands.run(f"ls -A {sandbox_path}")
                if result.exit_code == 0 and result.stdout.strip():
                    # Directory not empty
                    return False

                # Delete the directory
                result = self.sandbox.commands.run(f"rmdir {sandbox_path}")
                if result.exit_code != 0:
                    return False

                # Update stats
                self._stats["directory_count"] -= 1
            else:
                # Get file size before deleting
                try:
                    content = self._sync_read_file(path)
                    file_size = len(content) if content else 0
                except Exception:
                    file_size = 0

                # Delete the file
                result = self.sandbox.commands.run(f"rm {sandbox_path}")
                if result.exit_code != 0:
                    return False

                # Update stats
                self._stats["file_count"] -= 1
                self._stats["total_size_bytes"] -= file_size

            # Remove from cache
            if path in self.node_cache:
                del self.node_cache[path]
                del self.cache_timestamps[path]

            return True
        except Exception as e:
            print(f"Error deleting node: {e}")
            return False

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get node info (async)"""
        return await asyncio.to_thread(self._sync_get_node_info, path)

    def _sync_get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get information about a node"""
        if not self.sandbox:
            return None

        # Normalize path
        if not path:
            path = "/"
        elif path != "/" and path.endswith("/"):
            path = path[:-1]

        # Check cache first
        cached = self._check_cache(path)
        if cached:
            return cached

        try:
            sandbox_path = self._get_sandbox_path(path)

            # Check if path exists and get its type
            result = self.sandbox.commands.run(
                f"stat -c '%F' {sandbox_path} 2>/dev/null || echo 'not_found'"
            )
            if result.exit_code != 0 or "not_found" in result.stdout:
                return None

            # Determine if it's a directory or file
            is_dir = "directory" in result.stdout.strip()

            # Get parent path and name
            parent_path = posixpath.dirname(path)
            name = posixpath.basename(path) or ""

            # Create node info
            node_info = EnhancedNodeInfo(name, is_dir, parent_path)

            # Get modification time and size
            result = self.sandbox.commands.run(f"stat -c '%Y %s' {sandbox_path}")
            if result.exit_code == 0:
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    mtime = int(parts[0])
                    file_size = int(parts[1])
                    node_info.modified_at = time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime)
                    )
                    # Set size for files only
                    if not is_dir:
                        node_info.size = file_size

            # Update cache
            self._update_cache(path, node_info)

            return node_info
        except Exception as e:
            print(f"Error getting node info: {e}")
            return None

    async def list_directory(self, path: str) -> list[str]:
        """List directory contents (async)"""
        return await asyncio.to_thread(self._sync_list_directory, path)

    def _sync_list_directory(self, path: str) -> list[str]:
        """List contents of a directory"""
        if not self.sandbox:
            return []

        # Normalize path
        if not path:
            path = "/"
        elif path != "/" and path.endswith("/"):
            path = path[:-1]

        try:
            # Check if the path exists and is a directory
            node_info = self._sync_get_node_info(path)
            if not node_info or not node_info.is_dir:
                return []

            sandbox_path = self._get_sandbox_path(path)

            # List directory contents
            result = self.sandbox.commands.run(f"ls -A {sandbox_path}")
            if result.exit_code != 0:
                return []

            # Split the output into lines and filter empty lines
            items = [line.strip() for line in result.stdout.split("\n") if line.strip()]

            return items
        except Exception as e:
            print(f"Error listing directory: {e}")
            return []

    async def write_file(self, path: str, content: bytes) -> bool:
        """Write file content (async)"""
        return await asyncio.to_thread(self._sync_write_file, path, content)

    def _sync_write_file(self, path: str, content: bytes) -> bool:
        """Write content to a file"""
        if not self.sandbox:
            return False

        try:
            # Check if path exists and is a file
            node_info = self._sync_get_node_info(path)

            # Get the old size if file exists
            old_size = 0
            if node_info:
                if node_info.is_dir:
                    return False

                try:
                    old_content = self._sync_read_file(path)
                    old_size = len(old_content) if old_content else 0
                except Exception:
                    old_size = 0
            else:
                # File doesn't exist, create parent directories
                parent_path = posixpath.dirname(path)
                if parent_path and parent_path != "/":
                    parent_info = self._sync_get_node_info(parent_path)
                    if not parent_info:
                        # Create parent directory
                        parent_parts = parent_path.strip("/").split("/")
                        current_path = ""
                        for part in parent_parts:
                            if not part:
                                continue
                            current_path = f"{current_path}/{part}"
                            if not self._sync_get_node_info(current_path):
                                parent_node_info = EnhancedNodeInfo(
                                    part, True, posixpath.dirname(current_path)
                                )
                                if not self._sync_create_node(parent_node_info):
                                    return False
                    elif not parent_info.is_dir:
                        return False

                # Create the file
                file_name = posixpath.basename(path)
                file_node_info = EnhancedNodeInfo(file_name, False, parent_path)
                if not self._sync_create_node(file_node_info):
                    return False

            # Calculate new size
            content_size = len(content)

            # Write the content to the file
            sandbox_path = self._get_sandbox_path(path)

            # Write to a temporary file first to handle special characters
            temp_path = f"{self.root_dir}/.tmp_write_{time.time()}"
            # Convert bytes to string for E2B
            content_str = (
                content.decode("utf-8") if isinstance(content, bytes) else content
            )
            self.sandbox.files.write(temp_path, content_str)

            # Move the temporary file to the destination
            result = self.sandbox.commands.run(f"mv {temp_path} {sandbox_path}")
            if result.exit_code != 0:
                return False

            # Update stats
            self._stats["total_size_bytes"] = (
                self._stats["total_size_bytes"] - old_size + content_size
            )

            # Invalidate cache to force fresh fetch with correct size on next get_node_info
            if path in self.node_cache:
                del self.node_cache[path]
                del self.cache_timestamps[path]

            return True
        except Exception as e:
            print(f"Error writing file: {e}")
            return False

    async def read_file(self, path: str) -> bytes | None:
        """Read file content (async)"""
        return await asyncio.to_thread(self._sync_read_file, path)

    def _sync_read_file(self, path: str) -> bytes | None:
        """Read content from a file"""
        if not self.sandbox:
            return None

        try:
            # Check if path exists and is a file
            node_info = self._sync_get_node_info(path)
            if not node_info or node_info.is_dir:
                return None

            sandbox_path = self._get_sandbox_path(path)

            # Read the file content
            content: Any = self.sandbox.files.read(sandbox_path)

            # Convert to bytes if string
            if isinstance(content, str):
                content = content.encode("utf-8")

            return content  # type: ignore[no-any-return]
        except Exception as e:
            print(f"Error reading file: {e}")
            return None

    async def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics (async)"""
        return await asyncio.to_thread(self._sync_get_storage_stats)

    def _sync_get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics"""
        if not self.sandbox:
            return {"error": "Sandbox not initialized"}

        # Update directory count with a direct check if possible
        try:
            result = self.sandbox.commands.run(f"find {self.root_dir} -type d | wc -l")
            if result.exit_code == 0:
                self._stats["directory_count"] = int(result.stdout.strip())

            # Update file count
            result = self.sandbox.commands.run(f"find {self.root_dir} -type f | wc -l")
            if result.exit_code == 0:
                self._stats["file_count"] = int(result.stdout.strip())

            # Update total size
            result = self.sandbox.commands.run(f"du -sb {self.root_dir} | cut -f1")
            if result.exit_code == 0:
                self._stats["total_size_bytes"] = int(result.stdout.strip())
        except Exception:  # nosec B110 - Intentional: fallback to cached stats on command failure
            # Fallback to stored stats if commands fail
            pass

        # Return the stats with additional information
        stats: dict[str, Any] = self._stats.copy()
        # Rename for consistency with other providers
        stats["total_size"] = stats.pop("total_size_bytes")
        stats["total_files"] = stats.pop("file_count")
        stats["total_directories"] = stats.pop("directory_count")

        # Additional computed stats
        stats["total_size_mb"] = stats["total_size"] / (1024 * 1024)
        stats["node_count"] = stats["total_files"] + stats["total_directories"]
        stats["sandbox_id"] = self.sandbox_id
        stats["root_dir"] = self.root_dir

        return stats

    async def cleanup(self) -> dict[str, Any]:
        """Cleanup resources (async)"""
        return await asyncio.to_thread(self._sync_cleanup)

    def _sync_cleanup(self) -> dict[str, Any]:
        """Perform cleanup operations"""
        if not self.sandbox:
            return {"error": "Sandbox not initialized"}

        try:
            # Get initial stats
            self._stats["total_size_bytes"]
            self._stats["file_count"]

            # Clean up temporary files
            tmp_dir = f"{self.root_dir}/tmp"  # nosec B108 - Virtual FS path, not system temp

            # Create tmp directory if it doesn't exist
            self.sandbox.commands.run(f"mkdir -p {tmp_dir}")

            # Remove all files in the tmp directory
            self.sandbox.commands.run(f"find {tmp_dir} -type f -delete")

            # Calculate changes (stats are recalculated dynamically)
            # Note: stats are recalculated fresh in get_storage_stats()
            bytes_freed = 0  # Would need fresh stats calculation
            files_removed = 0  # Would need fresh stats calculation

            return {
                "cleaned_up": True,
                "bytes_freed": bytes_freed,
                "files_removed": files_removed,
                "expired_removed": 0,  # E2B doesn't have TTL expiration
                "sandbox_id": self.sandbox_id,
            }
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return {"error": str(e)}

    # Enhanced async methods

    async def calculate_checksum(self, content: bytes) -> str:
        """Calculate SHA256 checksum of content (overrides base class)"""
        return hashlib.sha256(content).hexdigest()

    async def copy_node(self, source: str, destination: str) -> bool:
        """Copy a node from source to destination"""
        return await asyncio.to_thread(self._sync_copy_node, source, destination)

    def _sync_copy_node(self, source: str, destination: str) -> bool:
        """Copy a node from source to destination (sync)"""
        if not self.sandbox:
            return False

        try:
            # Get source node info
            source_info = self._sync_get_node_info(source)
            if not source_info:
                return False

            # Get sandbox paths
            src_sandbox_path = self._get_sandbox_path(source)
            dest_sandbox_path = self._get_sandbox_path(destination)

            if source_info.is_dir:
                # Copy directory recursively
                result = self.sandbox.commands.run(
                    f"cp -r {src_sandbox_path} {dest_sandbox_path}"
                )
                if result.exit_code != 0:
                    return False

                # Update cache and stats
                dest_parent = posixpath.dirname(destination)
                dest_name = posixpath.basename(destination)
                dest_info = EnhancedNodeInfo(dest_name, True, dest_parent)
                self._update_cache(destination, dest_info)
                self._stats["directory_count"] += 1
            else:
                # Copy file
                result = self.sandbox.commands.run(
                    f"cp {src_sandbox_path} {dest_sandbox_path}"
                )
                if result.exit_code != 0:
                    return False

                # Update cache and stats
                dest_parent = posixpath.dirname(destination)
                dest_name = posixpath.basename(destination)
                dest_info = EnhancedNodeInfo(dest_name, False, dest_parent)

                # Copy file size info
                try:
                    content = self._sync_read_file(source)
                    if content:
                        dest_info.size = len(content)
                        self._stats["total_size_bytes"] += len(content)
                        self._stats["file_count"] += 1
                except Exception:  # nosec B110 - Intentional: file size calc is not critical
                    pass

                self._update_cache(destination, dest_info)

            return True

        except Exception as e:
            print(f"Error copying node: {e}")
            return False

    async def move_node(self, source: str, destination: str) -> bool:
        """Move a node from source to destination"""
        return await asyncio.to_thread(self._sync_move_node, source, destination)

    def _sync_move_node(self, source: str, destination: str) -> bool:
        """Move a node from source to destination (sync)"""
        if not self.sandbox:
            return False

        try:
            # Get source node info
            source_info = self._sync_get_node_info(source)
            if not source_info:
                return False

            # Get sandbox paths
            src_sandbox_path = self._get_sandbox_path(source)
            dest_sandbox_path = self._get_sandbox_path(destination)

            # Move using mv command
            result = self.sandbox.commands.run(
                f"mv {src_sandbox_path} {dest_sandbox_path}"
            )
            if result.exit_code != 0:
                return False

            # Update cache
            dest_parent = posixpath.dirname(destination)
            dest_name = posixpath.basename(destination)
            dest_info = EnhancedNodeInfo(dest_name, source_info.is_dir, dest_parent)
            dest_info.size = source_info.size
            self._update_cache(destination, dest_info)

            # Remove source from cache
            if source in self.node_cache:
                del self.node_cache[source]
                del self.cache_timestamps[source]

            return True

        except Exception as e:
            print(f"Error moving node: {e}")
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

    async def stream_write(
        self,
        path: str,
        stream: Any,
        chunk_size: int = 8192,
        progress_callback: Any = None,
    ) -> bool:
        """
        Write content to a file from an async stream with progress tracking and atomic safety.

        Uses E2B sandbox for atomic write operations.
        """
        return await asyncio.to_thread(
            self._sync_stream_write, path, stream, chunk_size, progress_callback
        )

    def _sync_stream_write(
        self, path: str, stream: Any, chunk_size: int, progress_callback: Any
    ) -> bool:
        """Synchronous stream write with atomic safety"""
        if not self.sandbox:
            return False

        try:
            # Create a unique temp file in E2B sandbox
            temp_path = f"{self.root_dir}/.tmp_stream_{time.time()}"
            sandbox_temp_path = temp_path

            # Collect chunks and track progress
            chunks = []
            total_bytes = 0

            # We need to consume the async generator in a sync context
            # This is a workaround for E2B's synchronous file operations
            import inspect

            if inspect.isasyncgen(stream):
                # Convert async generator to list of chunks
                loop = asyncio.new_event_loop()
                try:

                    async def collect_chunks() -> None:
                        nonlocal total_bytes
                        async for chunk in stream:
                            chunks.append(chunk)
                            total_bytes += len(chunk)

                            # Report progress
                            if progress_callback:
                                if asyncio.iscoroutinefunction(progress_callback):
                                    await progress_callback(total_bytes, -1)
                                else:
                                    progress_callback(total_bytes, -1)

                    loop.run_until_complete(collect_chunks())
                finally:
                    loop.close()
            else:
                # Regular iterator
                for chunk in stream:
                    chunks.append(chunk)
                    total_bytes += len(chunk)

                    if progress_callback:
                        progress_callback(total_bytes, -1)

            # Combine all chunks
            content = b"".join(chunks)

            # Write to temp file
            content_str = (
                content.decode("utf-8") if isinstance(content, bytes) else content
            )
            self.sandbox.files.write(sandbox_temp_path, content_str)

            # Get the final sandbox path
            sandbox_path = self._get_sandbox_path(path)

            # Atomic move from temp to final location
            result = self.sandbox.commands.run(f"mv {sandbox_temp_path} {sandbox_path}")
            if result.exit_code != 0:
                # Clean up temp file on failure
                self.sandbox.commands.run(f"rm -f {sandbox_temp_path}")
                return False

            # Update stats
            self._stats["total_size_bytes"] += total_bytes

            # Invalidate cache to force fresh fetch on next get_node_info
            if path in self.node_cache:
                del self.node_cache[path]
                del self.cache_timestamps[path]

            return True

        except Exception as e:
            print(f"Error in stream write: {e}")
            # Attempt cleanup
            with contextlib.suppress(BaseException):
                self.sandbox.commands.run(f"rm -f {sandbox_temp_path}")
            return False

    # Required async methods from AsyncStorageProvider

    async def exists(self, path: str) -> bool:
        """Check if a path exists (async)"""
        return await asyncio.to_thread(self._sync_exists, path)

    def _sync_exists(self, path: str) -> bool:
        """Check if a path exists"""
        # Empty string should return False
        if not path:
            return False
        return self._sync_get_node_info(path) is not None

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a node (async)"""
        return await asyncio.to_thread(self._sync_get_metadata, path)

    def _sync_get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a node"""
        node_info = self._sync_get_node_info(path)
        if not node_info:
            return {}

        result = {
            "name": node_info.name,
            "is_dir": node_info.is_dir,
            "size": node_info.size,
            "created_at": node_info.created_at,
            "modified_at": node_info.modified_at,
            "accessed_at": node_info.accessed_at,
            "mime_type": node_info.mime_type,
            "permissions": node_info.permissions,
            "custom_meta": node_info.custom_meta or {},
            "tags": node_info.tags or {},
        }

        # Include custom metadata at top level
        if node_info.custom_meta:
            result.update(node_info.custom_meta)

        return result

    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set metadata for a node (async)"""
        return await asyncio.to_thread(self._sync_set_metadata, path, metadata)

    def _sync_set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set metadata for a node"""
        node_info = self._sync_get_node_info(path)
        if not node_info:
            return False

        # Update node info with new metadata
        if not hasattr(node_info, "custom_meta"):
            node_info.custom_meta = {}

        # Store metadata directly
        node_info.custom_meta.update(metadata)

        if "permissions" in metadata:
            node_info.permissions = metadata["permissions"]

        # Update timestamps
        node_info.update_modified()

        # Update cache
        self._update_cache(path, node_info)
        return True
