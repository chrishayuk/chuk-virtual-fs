"""
chuk_virtual_fs/providers/async_memory.py - Async in-memory storage provider
"""

from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider


class AsyncMemoryStorageProvider(AsyncStorageProvider):
    """
    Async in-memory storage provider with enhanced features
    """

    def __init__(self, session_id: str | None = None, sandbox_id: str | None = None):
        super().__init__()
        self.nodes: dict[str, EnhancedNodeInfo] = {}
        self.file_contents: dict[str, bytes] = {}
        self.session_id = session_id
        self.sandbox_id = sandbox_id or "default"
        self._initialized = False
        self._stats = {"reads": 0, "writes": 0, "deletes": 0, "creates": 0}

    async def initialize(self) -> bool:
        """Initialize the storage provider"""
        async with self._lock:
            # Create root node if it doesn't exist
            if "/" not in self.nodes:
                root_info = EnhancedNodeInfo(
                    name="",
                    is_dir=True,
                    parent_path="",
                    session_id=self.session_id,
                    sandbox_id=self.sandbox_id,
                )
                self.nodes["/"] = root_info
            self._initialized = True
            return True

    async def close(self) -> None:
        """Close and cleanup provider resources"""
        async with self._lock:
            self._closed = True
            # Optional: Clear memory
            # self.nodes.clear()
            # self.file_contents.clear()

    async def exists(self, path: str) -> bool:
        """Check if a path exists"""
        async with self._lock:
            return path in self.nodes

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node"""
        if self._closed:
            raise RuntimeError("Provider is closed")

        async with self._lock:
            path = node_info.get_path()

            # Check if already exists
            if path in self.nodes:
                return False

            # Check parent exists
            parent_path = node_info.parent_path
            if parent_path != "/" and parent_path not in self.nodes:
                return False

            # Ensure parent is a directory
            if parent_path != "/" and not self.nodes[parent_path].is_dir:
                return False

            # Set session and sandbox info
            node_info.session_id = node_info.session_id or self.session_id
            node_info.sandbox_id = node_info.sandbox_id or self.sandbox_id
            node_info.provider = "async_memory"

            # Store node
            self.nodes[path] = node_info

            # Initialize empty content for files
            if not node_info.is_dir:
                self.file_contents[path] = b""

            self._stats["creates"] += 1
            return True

    async def delete_node(self, path: str) -> bool:
        """Delete a node"""
        if self._closed:
            raise RuntimeError("Provider is closed")

        async with self._lock:
            if path not in self.nodes:
                return False

            if path == "/":
                return False  # Can't delete root

            node = self.nodes[path]

            # If directory, check if empty
            if node.is_dir:
                # Check for children
                for other_path in self.nodes:
                    if other_path != path and other_path.startswith(path + "/"):
                        return False  # Directory not empty

            # Delete node
            del self.nodes[path]

            # Delete content if file
            if not node.is_dir and path in self.file_contents:
                del self.file_contents[path]

            self._stats["deletes"] += 1
            return True

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get information about a node"""
        async with self._lock:
            node = self.nodes.get(path)
            if node:
                node.update_accessed()
                self._stats["reads"] += 1
            return node

    async def list_directory(self, path: str) -> list[str]:
        """List contents of a directory"""
        async with self._lock:
            if path not in self.nodes:
                return []

            node = self.nodes[path]
            if not node.is_dir:
                return []

            # Find direct children
            children = []
            path_with_slash = path if path.endswith("/") else path + "/"
            if path == "/":
                path_with_slash = "/"

            for node_path in self.nodes:
                if node_path == path:
                    continue

                # Check if direct child
                if path == "/":
                    if "/" not in node_path[1:] and node_path != "/":
                        children.append(node_path[1:])
                else:
                    if node_path.startswith(path_with_slash):
                        relative = node_path[len(path_with_slash) :]
                        if relative and "/" not in relative:
                            children.append(relative)

            return sorted(children)

    async def write_file(self, path: str, content: bytes) -> bool:
        """Write content to a file"""
        if self._closed:
            raise RuntimeError("Provider is closed")

        async with self._lock:
            if path not in self.nodes:
                return False

            node = self.nodes[path]
            if node.is_dir:
                return False

            # Store content
            self.file_contents[path] = content

            # Update metadata
            node.calculate_checksums(content)
            node.update_modified()
            node.size = len(content)

            self._stats["writes"] += 1
            return True

    async def read_file(self, path: str) -> bytes | None:
        """Read content from a file"""
        async with self._lock:
            if path not in self.nodes:
                return None

            node = self.nodes[path]
            if node.is_dir:
                return None

            node.update_accessed()
            self._stats["reads"] += 1
            return self.file_contents.get(path, b"")

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get enhanced metadata for a node"""
        async with self._lock:
            node = self.nodes.get(path)
            if not node:
                return {}

            metadata = node.to_dict()

            # Add provider-specific metadata
            metadata["provider"] = "async_memory"
            metadata["stats"] = {
                "total_nodes": len(self.nodes),
                "total_files": sum(1 for n in self.nodes.values() if not n.is_dir),
                "total_dirs": sum(1 for n in self.nodes.values() if n.is_dir),
            }

            return metadata

    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set custom metadata for a node"""
        async with self._lock:
            if path not in self.nodes:
                return False

            node = self.nodes[path]

            # Store metadata directly in custom_meta for consistency
            if not hasattr(node, "custom_meta") or node.custom_meta is None:
                node.custom_meta = {}

            # Store all metadata in custom_meta
            for key, value in metadata.items():
                if key not in ["custom_meta", "tags"]:
                    node.custom_meta[key] = value

            # Handle custom_meta if provided
            if "custom_meta" in metadata:
                node.custom_meta.update(metadata["custom_meta"])

            # Handle tags specially
            if "tags" in metadata:
                if isinstance(metadata["tags"], list):
                    node.tags = metadata["tags"]  # type: ignore[assignment]
                elif hasattr(node.tags, "update"):
                    node.tags.update(metadata["tags"])
                else:
                    node.tags = metadata["tags"]

            # Update allowed fields on the node directly
            allowed_fields = ["mime_type", "ttl", "owner", "group", "permissions"]
            for field in allowed_fields:
                if field in metadata:
                    setattr(node, field, metadata[field])

            node.update_modified()

            if node.ttl:
                node.calculate_expiry()

            return True

    async def get_storage_stats(self) -> dict:
        """Get storage statistics"""
        async with self._lock:
            total_size = sum(len(content) for content in self.file_contents.values())

            expired_count = sum(1 for node in self.nodes.values() if node.is_expired())

            return {
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "file_count": sum(1 for n in self.nodes.values() if not n.is_dir),
                "directory_count": sum(1 for n in self.nodes.values() if n.is_dir),
                "total_nodes": len(self.nodes),
                "expired_nodes": expired_count,
                "operations": self._stats.copy(),
                "session_id": self.session_id,
                "sandbox_id": self.sandbox_id,
            }

    async def cleanup(self) -> dict:
        """Perform cleanup operations"""
        async with self._lock:
            # Remove expired nodes
            expired_paths = [
                path for path, node in self.nodes.items() if node.is_expired()
            ]

            bytes_freed = 0
            for path in expired_paths:
                if path in self.file_contents:
                    bytes_freed += len(self.file_contents[path])
                    del self.file_contents[path]
                del self.nodes[path]

            # Clean up /tmp directory if it exists
            tmp_paths = [path for path in self.nodes if path.startswith("/tmp/")]  # nosec B108 - Virtual FS path

            for path in tmp_paths:
                if path in self.file_contents:
                    bytes_freed += len(self.file_contents[path])
                    del self.file_contents[path]
                if path in self.nodes:
                    del self.nodes[path]

            return {
                "bytes_freed": bytes_freed,
                "files_removed": len(expired_paths) + len(tmp_paths),
                "expired_removed": len(expired_paths),
                "tmp_removed": len(tmp_paths),
            }

    # Session-based operations

    async def list_by_session(self, session_id: str) -> list[str]:
        """List all nodes belonging to a session"""
        async with self._lock:
            return [
                path
                for path, node in self.nodes.items()
                if node.session_id == session_id
            ]

    async def delete_session(self, session_id: str) -> int:
        """Delete all nodes belonging to a session"""
        async with self._lock:
            session_paths = [
                path
                for path, node in self.nodes.items()
                if node.session_id == session_id
            ]

            for path in session_paths:
                if path in self.file_contents:
                    del self.file_contents[path]
                del self.nodes[path]

            return len(session_paths)

    # Additional methods for feature parity with S3 provider

    async def create_directory(
        self, path: str, mode: int = 0o755, owner_id: int = 1000, group_id: int = 1000
    ) -> bool:
        """Create a directory with proper parent creation"""
        if self._closed:
            raise RuntimeError("Provider is closed")

        async with self._lock:
            # Normalize path
            if path.endswith("/"):
                path = path.rstrip("/")

            # Check if already exists
            if path in self.nodes:
                return True  # Already exists

            # Create parent directories if needed
            path_parts = path.strip("/").split("/")
            current_path = ""

            for part in path_parts:
                parent_path = current_path
                current_path = (
                    f"/{part}" if not current_path else f"{current_path}/{part}"
                )

                if current_path not in self.nodes:
                    node_info = EnhancedNodeInfo(
                        name=part,
                        is_dir=True,
                        parent_path=parent_path or "/",
                        permissions=str(mode),
                        owner=str(owner_id),
                        group=str(group_id),
                        session_id=self.session_id,
                        sandbox_id=self.sandbox_id,
                        provider="async_memory",
                    )
                    self.nodes[current_path] = node_info
                    self._stats["creates"] += 1

            return True

    async def copy_node(self, src_path: str, dst_path: str) -> bool:
        """Copy a node to a new location"""
        if self._closed:
            raise RuntimeError("Provider is closed")

        # First, collect what needs to be copied
        async with self._lock:
            if src_path not in self.nodes:
                return False

            src_node = self.nodes[src_path]

            # Create a deep copy of the node
            import copy

            dst_node = copy.deepcopy(src_node)

            # Update path information
            dst_node.name = dst_path.split("/")[-1]
            dst_node.parent_path = "/".join(dst_path.split("/")[:-1]) or "/"

            # Check if destination parent exists
            if dst_node.parent_path != "/" and dst_node.parent_path not in self.nodes:
                return False

            # Store the copy
            self.nodes[dst_path] = dst_node

            # Copy file contents if it's a file
            if not src_node.is_dir and src_path in self.file_contents:
                self.file_contents[dst_path] = self.file_contents[src_path][
                    :
                ]  # Copy bytes

            # Collect children to copy if it's a directory
            children_to_copy = []
            if src_node.is_dir:
                src_with_slash = src_path if src_path.endswith("/") else src_path + "/"
                for node_path in list(self.nodes.keys()):
                    if node_path != src_path and node_path.startswith(src_with_slash):
                        relative_path = node_path[len(src_with_slash) :]
                        new_path = f"{dst_path}/{relative_path}"
                        children_to_copy.append((node_path, new_path))

        # Copy children outside the lock to avoid deadlock
        for child_src, child_dst in children_to_copy:
            await self.copy_node(child_src, child_dst)

        return True

    async def move_node(self, src_path: str, dst_path: str) -> bool:
        """Move a node to a new location"""
        if await self.copy_node(src_path, dst_path):
            return await self.delete_node(src_path)
        return False

    async def batch_write(self, operations: list[tuple[str, bytes]]) -> list[bool]:
        """Write multiple files in batch"""
        results = []
        for path, content in operations:
            # Create node if it doesn't exist
            if path not in self.nodes:
                node_info = EnhancedNodeInfo(
                    name=path.split("/")[-1],
                    is_dir=False,
                    parent_path="/".join(path.split("/")[:-1]) or "/",
                    session_id=self.session_id,
                    sandbox_id=self.sandbox_id,
                    provider="async_memory",
                )
                await self.create_node(node_info)

            result = await self.write_file(path, content)
            results.append(result)
        return results

    async def batch_read(self, paths: list[str]) -> list[bytes | None]:
        """Read multiple files in batch"""
        results = []
        for path in paths:
            content = await self.read_file(path)
            results.append(content)
        return results

    async def batch_delete(self, paths: list[str]) -> list[bool]:
        """Delete multiple nodes in batch"""
        results = []
        for path in paths:
            result = await self.delete_node(path)
            results.append(result)
        return results

    async def batch_create(self, nodes: list[EnhancedNodeInfo]) -> list[bool]:
        """Create multiple nodes in batch"""
        results = []
        for node in nodes:
            result = await self.create_node(node)
            results.append(result)
        return results

    async def calculate_file_checksum(
        self, path: str, algorithm: str = "sha256"
    ) -> str | None:
        """Calculate checksum for a file by path"""
        async with self._lock:
            if path not in self.nodes:
                return None

            node = self.nodes[path]
            if node.is_dir:
                return None

            content = self.file_contents.get(path, b"")

            import hashlib

            if algorithm == "md5":
                return hashlib.md5(content, usedforsecurity=False).hexdigest()  # nosec B324
            elif algorithm == "sha256":
                return hashlib.sha256(content).hexdigest()
            elif algorithm == "sha512":
                return hashlib.sha512(content).hexdigest()
            else:
                return None


# Backwards compatibility alias
MemoryStorageProvider = AsyncMemoryStorageProvider
