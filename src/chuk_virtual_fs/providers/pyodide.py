"""
chuk_virtual_fs/providers/pyodide.py - Async Pyodide-native Storage Provider
"""

import asyncio
import os
import time
from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider


class PyodideStorageProvider(AsyncStorageProvider):
    """
    Pyodide-native implementation of storage provider
    Uses Pyodide's file system capabilities with fallback mechanisms
    """

    def __init__(self, base_path: str = "/home/pyodide"):
        """
        Initialize Pyodide storage provider

        Args:
            base_path: Base directory for file operations
        """
        super().__init__()
        self.base_path = base_path
        self._total_size = 0

    async def initialize(self) -> bool:
        """Initialize the provider (async)"""
        return await asyncio.to_thread(self._sync_initialize)

    def _sync_initialize(self) -> bool:
        """Initialize the storage provider"""
        try:
            # Ensure base path exists
            os.makedirs(self.base_path, exist_ok=True)

            # Create essential subdirectories
            for subdir in ["bin", "home", "tmp", "etc"]:
                os.makedirs(os.path.join(self.base_path, subdir), exist_ok=True)

            # Initialize some default files
            motd_path = os.path.join(self.base_path, "etc", "motd")
            if not os.path.exists(motd_path):
                with open(motd_path, "w") as f:
                    f.write("Welcome to PyodideShell - A Pyodide-native Filesystem!\n")

            return True
        except Exception as e:
            print(f"Filesystem initialization error: {e}")
            return False

    async def close(self) -> None:
        """Close the provider"""
        # Nothing to close for Pyodide

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a node (async)"""
        return await asyncio.to_thread(self._sync_create_node, node_info)

    def _sync_create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node (file or directory)"""
        full_path = os.path.join(self.base_path, node_info.get_path().lstrip("/"))

        try:
            if node_info.is_dir:
                os.makedirs(full_path, exist_ok=True)
            else:
                # Ensure parent directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                # Create an empty file
                open(full_path, "a").close()

            return True
        except Exception as e:
            print(f"Error creating node {full_path}: {e}")
            return False

    async def delete_node(self, path: str) -> bool:
        """Delete a node (async)"""
        return await asyncio.to_thread(self._sync_delete_node, path)

    def _sync_delete_node(self, path: str) -> bool:
        """Delete a node"""
        full_path = os.path.join(self.base_path, path.lstrip("/"))

        try:
            # Check if directory and not empty
            if os.path.isdir(full_path):
                # Ensure directory is empty before removing
                if os.listdir(full_path):
                    return False
                os.rmdir(full_path)
            else:
                os.remove(full_path)

            return True
        except Exception as e:
            print(f"Error deleting node {full_path}: {e}")
            return False

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get node info (async)"""
        return await asyncio.to_thread(self._sync_get_node_info, path)

    def _sync_get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get information about a node"""
        full_path = os.path.join(self.base_path, path.lstrip("/"))

        try:
            if not os.path.exists(full_path):
                return None

            # Get file/dir name
            name = os.path.basename(full_path) or "/"

            # Create node info
            node_info = EnhancedNodeInfo(
                name, is_dir=os.path.isdir(full_path), parent_path=os.path.dirname(path)
            )

            # Add additional metadata
            stat = os.stat(full_path)
            node_info.created_at = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_ctime)
            )
            node_info.modified_at = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)
            )

            return node_info
        except Exception:
            return None

    async def list_directory(self, path: str) -> list[str]:
        """List directory (async)"""
        return await asyncio.to_thread(self._sync_list_directory, path)

    def _sync_list_directory(self, path: str) -> list[str]:
        """List contents of a directory"""
        full_path = os.path.join(self.base_path, path.lstrip("/"))

        try:
            # Validate it's a directory
            if not os.path.isdir(full_path):
                return []

            # List contents, excluding hidden files
            return [item for item in os.listdir(full_path) if not item.startswith(".")]
        except Exception:
            return []

    async def write_file(self, path: str, content: bytes) -> bool:
        """Write file (async)"""
        return await asyncio.to_thread(self._sync_write_file, path, content)

    def _sync_write_file(self, path: str, content: bytes) -> bool:
        """Write content to a file"""
        full_path = os.path.join(self.base_path, path.lstrip("/"))

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "wb") as f:
                f.write(content)

            # Update total size tracking
            self._total_size += len(content)

            return True
        except Exception as e:
            print(f"Error writing file {full_path}: {e}")
            return False

    async def read_file(self, path: str) -> bytes | None:
        """Read file (async)"""
        return await asyncio.to_thread(self._sync_read_file, path)

    def _sync_read_file(self, path: str) -> bytes | None:
        """Read content from a file"""
        full_path = os.path.join(self.base_path, path.lstrip("/"))

        try:
            with open(full_path, "rb") as f:
                return f.read()
        except Exception:
            return None

    async def get_storage_stats(self) -> dict:
        """Get storage stats (async)"""
        return await asyncio.to_thread(self._sync_get_storage_stats)

    def _sync_get_storage_stats(self) -> dict:
        """Get storage statistics"""
        try:
            # Walk through the entire filesystem to get stats
            total_size = 0
            file_count = 0
            dir_count = 0

            for root, dirs, files in os.walk(self.base_path):
                dir_count += len(dirs)
                file_count += len(files)

                # Calculate size of files
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)

            return {
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "file_count": file_count,
                "directory_count": dir_count,
                "node_count": file_count + dir_count,
            }
        except Exception as e:
            print(f"Error getting storage stats: {e}")
            return {
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "file_count": 0,
                "directory_count": 0,
                "node_count": 0,
            }

    async def cleanup(self) -> dict:
        """Cleanup (async)"""
        return await asyncio.to_thread(self._sync_cleanup)

    def _sync_cleanup(self) -> dict:
        """Perform cleanup operations"""
        try:
            # Focus on cleaning up temporary files
            tmp_path = os.path.join(self.base_path, "tmp")

            size_before = self._total_size
            removed = 0

            for root, _, files in os.walk(tmp_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        removed += 1
                        self._total_size -= file_size
                    except Exception:
                        pass

            return {
                "bytes_freed": size_before - self._total_size,
                "files_removed": removed,
            }
        except Exception as e:
            print(f"Cleanup error: {e}")
            return {"bytes_freed": 0, "files_removed": 0}

    # Required async methods from AsyncStorageProvider

    async def exists(self, path: str) -> bool:
        """Check if a path exists (async)"""
        return await asyncio.to_thread(self._sync_exists, path)

    def _sync_exists(self, path: str) -> bool:
        """Check if a path exists"""
        full_path = os.path.join(self.base_path, path.lstrip("/"))
        return os.path.exists(full_path)

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a node (async)"""
        return await asyncio.to_thread(self._sync_get_metadata, path)

    def _sync_get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a node"""
        node_info = self._sync_get_node_info(path)
        if not node_info:
            return {}

        return {
            "name": node_info.name,
            "is_dir": node_info.is_dir,
            "size": node_info.size,
            "created_at": node_info.created_at,
            "modified_at": node_info.modified_at,
            "accessed_at": node_info.accessed_at,
            "mime_type": node_info.mime_type,
            "permissions": node_info.permissions,
            "custom_metadata": node_info.custom_metadata or {},
        }

    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set metadata for a node (async)"""
        return await asyncio.to_thread(self._sync_set_metadata, path, metadata)

    def _sync_set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set metadata for a node"""
        # Pyodide filesystem doesn't support extended attributes
        # We could store metadata in a sidecar file if needed
        # For now, return True to indicate success
        return True
