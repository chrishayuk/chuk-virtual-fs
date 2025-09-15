"""
chuk_virtual_fs/providers/filesystem.py - Local filesystem storage provider

Provides access to the local filesystem using async operations.
Perfect for development, testing, and applications that need direct filesystem access.
"""

import asyncio
import hashlib
import json
import os
import posixpath
import shutil
import stat
import time
from pathlib import Path
from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider


class AsyncFilesystemStorageProvider(AsyncStorageProvider):
    """Async filesystem storage provider
    
    Provides virtual filesystem operations on the local filesystem.
    All operations are thread-safe and use asyncio.to_thread for I/O.
    """

    def __init__(self, root_path: str = None, create_root: bool = True, use_metadata: bool = True):
        super().__init__()
        self.root_path = Path(root_path) if root_path else Path.cwd() / "virtual_fs"
        self.create_root = create_root
        self.use_metadata = use_metadata
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the filesystem provider"""
        return await asyncio.to_thread(self._sync_initialize)

    def _sync_initialize(self) -> bool:
        """Synchronous initialization"""
        try:
            if self.create_root and not self.root_path.exists():
                self.root_path.mkdir(parents=True, exist_ok=True)
            
            if not self.root_path.exists():
                print(f"Error: Root path {self.root_path} does not exist")
                return False
            
            if not self.root_path.is_dir():
                print(f"Error: Root path {self.root_path} is not a directory")
                return False
            
            self._initialized = True
            return True
        except Exception as e:
            print(f"Error initializing filesystem storage: {e}")
            return False

    async def close(self) -> None:
        """Close the filesystem provider"""
        self._initialized = False
        self._closed = True

    def _resolve_path(self, path: str) -> Path:
        """Resolve virtual path to actual filesystem path"""
        # Normalize the path
        if not path:
            path = "/"
        elif not path.startswith("/"):
            path = "/" + path
        
        # Normalize using posixpath to handle .. and . patterns
        normalized_path = posixpath.normpath(path)
        
        # Remove leading slash and join with root
        relative_path = normalized_path.lstrip("/")
        if not relative_path:
            return self.root_path
        
        return self.root_path / relative_path

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node (file or directory)"""
        return await asyncio.to_thread(self._sync_create_node, node_info)

    def _sync_create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node (sync)"""
        if not self._initialized:
            return False

        try:
            fs_path = self._resolve_path(node_info.get_path())
            
            # Check if already exists
            if fs_path.exists():
                return False
            
            # Ensure parent directory exists
            parent_path = fs_path.parent
            if not parent_path.exists():
                return False
            
            if node_info.is_dir:
                fs_path.mkdir()
            else:
                fs_path.touch()
                
            # Set metadata if provided
            self._set_filesystem_metadata(fs_path, node_info)
            return True
            
        except Exception as e:
            print(f"Error creating node: {e}")
            return False

    def _set_filesystem_metadata(self, fs_path: Path, node_info: EnhancedNodeInfo):
        """Set filesystem metadata from node info"""
        try:
            # Set permissions if provided
            if hasattr(node_info, 'permissions') and node_info.permissions:
                try:
                    mode = int(node_info.permissions, 8)
                    fs_path.chmod(mode)
                except (ValueError, OSError):
                    pass
            
            # Store extended metadata in xattrs or sidecar file
            metadata = {
                'custom_meta': node_info.custom_meta or {},
                'tags': node_info.tags or {},
                'session_id': node_info.session_id,
                'sandbox_id': node_info.sandbox_id,
                'ttl': node_info.ttl,
                'expires_at': node_info.expires_at,
                'provider': 'filesystem'
            }
            
            # Store in sidecar file
            metadata_path = fs_path.with_suffix(fs_path.suffix + '.meta')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
                
        except Exception as e:
            # Metadata setting is not critical
            pass

    def _get_filesystem_metadata(self, fs_path: Path) -> dict:
        """Get filesystem metadata"""
        try:
            metadata_path = fs_path.with_suffix(fs_path.suffix + '.meta')
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    async def delete_node(self, path: str) -> bool:
        """Delete a node"""
        return await asyncio.to_thread(self._sync_delete_node, path)

    def _sync_delete_node(self, path: str) -> bool:
        """Delete a node (sync)"""
        if not self._initialized:
            return False

        try:
            fs_path = self._resolve_path(path)
            
            if not fs_path.exists():
                return False
            
            if fs_path.is_dir():
                # Check if directory is empty
                if any(fs_path.iterdir()):
                    return False
                fs_path.rmdir()
            else:
                fs_path.unlink()
            
            # Remove metadata file if it exists
            metadata_path = fs_path.with_suffix(fs_path.suffix + '.meta')
            if metadata_path.exists():
                metadata_path.unlink()
            
            return True
            
        except Exception as e:
            print(f"Error deleting node: {e}")
            return False

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get information about a node"""
        return await asyncio.to_thread(self._sync_get_node_info, path)

    def _sync_get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get information about a node (sync)"""
        if not self._initialized:
            return None

        try:
            fs_path = self._resolve_path(path)
            
            if not fs_path.exists():
                return None
            
            stat_info = fs_path.stat()
            is_dir = fs_path.is_dir()
            
            # Get extended metadata
            metadata = self._get_filesystem_metadata(fs_path)
            
            # Create node info
            node_info = EnhancedNodeInfo(
                name=fs_path.name or "/",
                is_dir=is_dir,
                parent_path=str(fs_path.parent.relative_to(self.root_path)) if fs_path != self.root_path else "",
                size=stat_info.st_size if not is_dir else 0,
                created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat_info.st_ctime)),
                modified_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat_info.st_mtime)),
                accessed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat_info.st_atime)),
                permissions=oct(stat_info.st_mode)[-3:],
                custom_meta=metadata,  # Store all metadata as custom_meta
                tags=metadata.get('tags', {}),
                session_id=metadata.get('session_id'),
                sandbox_id=metadata.get('sandbox_id'),
                ttl=metadata.get('ttl'),
                expires_at=metadata.get('expires_at')
            )
            
            # Set MIME type
            node_info.set_mime_type(fs_path.name)
            
            return node_info
            
        except Exception as e:
            print(f"Error getting node info: {e}")
            return None

    async def list_directory(self, path: str) -> list[str]:
        """List contents of a directory"""
        return await asyncio.to_thread(self._sync_list_directory, path)

    def _sync_list_directory(self, path: str) -> list[str]:
        """List contents of a directory (sync)"""
        if not self._initialized:
            return []

        try:
            fs_path = self._resolve_path(path)
            
            if not fs_path.exists() or not fs_path.is_dir():
                return []
            
            items = []
            for item in fs_path.iterdir():
                # Skip metadata files
                if item.name.endswith('.meta'):
                    continue
                items.append(item.name)
            
            return sorted(items)
            
        except Exception as e:
            print(f"Error listing directory: {e}")
            return []

    async def write_file(self, path: str, content: bytes) -> bool:
        """Write content to a file"""
        return await asyncio.to_thread(self._sync_write_file, path, content)

    def _sync_write_file(self, path: str, content: bytes) -> bool:
        """Write content to a file (sync)"""
        if not self._initialized:
            return False

        try:
            fs_path = self._resolve_path(path)
            
            # Check if path exists and is not a directory
            if not fs_path.exists():
                return False  # File must be created first with create_node
                
            if fs_path.is_dir():
                return False
            
            # Write content
            with open(fs_path, 'wb') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            print(f"Error writing file: {e}")
            return False

    async def read_file(self, path: str) -> bytes | None:
        """Read content from a file"""
        return await asyncio.to_thread(self._sync_read_file, path)

    def _sync_read_file(self, path: str) -> bytes | None:
        """Read content from a file (sync)"""
        if not self._initialized:
            return None

        try:
            fs_path = self._resolve_path(path)
            
            if not fs_path.exists() or fs_path.is_dir():
                return None
            
            with open(fs_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            print(f"Error reading file: {e}")
            return None

    async def exists(self, path: str) -> bool:
        """Check if a path exists"""
        return await asyncio.to_thread(self._sync_exists, path)

    def _sync_exists(self, path: str) -> bool:
        """Check if a path exists (sync)"""
        if not self._initialized:
            return False

        try:
            fs_path = self._resolve_path(path)
            return fs_path.exists()
        except Exception as e:
            print(f"Error checking existence: {e}")
            return False

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get enhanced metadata for a node"""
        return await asyncio.to_thread(self._sync_get_metadata, path)

    def _sync_get_metadata(self, path: str) -> dict[str, Any]:
        """Get enhanced metadata for a node (sync)"""
        # If metadata is disabled, return empty dict
        if not self.use_metadata:
            return {}
            
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
        """Set custom metadata for a node"""
        return await asyncio.to_thread(self._sync_set_metadata, path, metadata)

    def _sync_set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set custom metadata for a node (sync)"""
        if not self._initialized:
            return False

        # If metadata is disabled, just return True (no-op)
        if not self.use_metadata:
            return True

        try:
            fs_path = self._resolve_path(path)
            
            if not fs_path.exists():
                return False
            
            # Get existing metadata
            existing_metadata = self._get_filesystem_metadata(fs_path)
            
            # Update with new metadata (store directly at top level)
            existing_metadata.update(metadata)
            
            # Save back to sidecar file
            metadata_path = fs_path.with_suffix(fs_path.suffix + '.meta')
            with open(metadata_path, 'w') as f:
                json.dump(existing_metadata, f)
            
            return True
            
        except Exception as e:
            print(f"Error setting metadata: {e}")
            return False

    async def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics"""
        return await asyncio.to_thread(self._sync_get_storage_stats)

    def _sync_get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics (sync)"""
        if not self._initialized:
            return {"error": "Filesystem not initialized"}

        try:
            total_size = 0
            file_count = 0
            directory_count = 0
            
            def count_items(path):
                nonlocal total_size, file_count, directory_count
                try:
                    for item in path.iterdir():
                        if item.is_file():
                            # Skip metadata files
                            if item.name.endswith('.meta'):
                                continue
                            try:
                                total_size += item.stat().st_size
                                file_count += 1
                            except OSError:
                                pass
                        elif item.is_dir():
                            directory_count += 1
                            count_items(item)  # Recursively count subdirectories
                except OSError:
                    pass
            
            count_items(self.root_path)
            
            return {
                "total_size": total_size,
                "total_files": file_count,
                "total_directories": directory_count,
                "root_path": str(self.root_path)
            }
            
        except Exception as e:
            print(f"Error getting storage stats: {e}")
            return {"error": str(e)}

    async def cleanup(self) -> dict[str, Any]:
        """Perform cleanup operations"""
        return await asyncio.to_thread(self._sync_cleanup)

    def _sync_cleanup(self) -> dict[str, Any]:
        """Perform cleanup operations (sync)"""
        files_removed = 0
        bytes_freed = 0
        expired_removed = 0
        
        if not self._initialized:
            return {
                "files_removed": files_removed,
                "bytes_freed": bytes_freed,
                "expired_removed": expired_removed
            }

        try:
            # Clean up expired files based on TTL
            current_time = time.time()
            
            for root, dirs, files in os.walk(self.root_path):
                for file in files:
                    if file.endswith('.meta'):
                        continue
                        
                    file_path = Path(root) / file
                    metadata = self._get_filesystem_metadata(file_path)
                    
                    # Check if file is expired
                    if metadata.get('expires_at'):
                        try:
                            from datetime import datetime
                            expires_at = datetime.fromisoformat(metadata['expires_at'].replace('Z', '+00:00'))
                            if datetime.utcnow() > expires_at.replace(tzinfo=None):
                                size = file_path.stat().st_size
                                file_path.unlink()
                                
                                # Remove metadata file
                                metadata_path = file_path.with_suffix(file_path.suffix + '.meta')
                                if metadata_path.exists():
                                    metadata_path.unlink()
                                
                                files_removed += 1
                                bytes_freed += size
                                expired_removed += 1
                        except Exception:
                            pass
            
            return {
                "cleaned_up": True,
                "files_removed": files_removed,
                "bytes_freed": bytes_freed,
                "expired_removed": expired_removed
            }
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return {
                "files_removed": files_removed,
                "bytes_freed": bytes_freed,
                "expired_removed": expired_removed
            }

    # Enhanced features for parity with other providers

    async def create_directory(self, path: str, mode: int = 0o755, owner_id: int = 1000, group_id: int = 1000) -> bool:
        """Create a directory with parent directories if needed"""
        return await asyncio.to_thread(self._sync_create_directory, path, mode, owner_id, group_id)

    def _sync_create_directory(self, path: str, mode: int, owner_id: int, group_id: int) -> bool:
        """Create a directory (sync)"""
        if not self._initialized:
            return False

        try:
            fs_path = self._resolve_path(path)
            
            # Create parent directories if needed
            fs_path.mkdir(parents=True, exist_ok=True)
            
            # Set permissions
            try:
                fs_path.chmod(mode)
            except OSError:
                pass
            
            return True
            
        except Exception as e:
            print(f"Error creating directory: {e}")
            return False

    async def calculate_checksum(self, content: bytes) -> str:
        """Calculate SHA256 checksum of content (overrides base class)"""
        return hashlib.sha256(content).hexdigest()

    async def calculate_file_checksum(self, path: str, algorithm: str = "sha256") -> str | None:
        """Calculate checksum for a file"""
        return await asyncio.to_thread(self._sync_calculate_checksum, path, algorithm)

    def _sync_calculate_checksum(self, path: str, algorithm: str) -> str | None:
        """Calculate checksum for a file (sync)"""
        if not self._initialized:
            return None

        try:
            fs_path = self._resolve_path(path)
            
            if not fs_path.exists() or fs_path.is_dir():
                return None
            
            hash_obj = None
            if algorithm.lower() == "md5":
                hash_obj = hashlib.md5()
            elif algorithm.lower() == "sha1":
                hash_obj = hashlib.sha1()
            elif algorithm.lower() == "sha256":
                hash_obj = hashlib.sha256()
            elif algorithm.lower() == "sha512":
                hash_obj = hashlib.sha512()
            else:
                return None
            
            with open(fs_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            print(f"Error calculating checksum: {e}")
            return None

    async def copy_node(self, src_path: str, dst_path: str) -> bool:
        """Copy a node (file or directory) to another location"""
        return await asyncio.to_thread(self._sync_copy_node, src_path, dst_path)

    def _sync_copy_node(self, src_path: str, dst_path: str) -> bool:
        """Copy a node (sync)"""
        if not self._initialized:
            return False

        try:
            src_fs_path = self._resolve_path(src_path)
            dst_fs_path = self._resolve_path(dst_path)
            
            if not src_fs_path.exists():
                return False
            
            if dst_fs_path.exists():
                return False
            
            # Ensure parent directory exists
            dst_fs_path.parent.mkdir(parents=True, exist_ok=True)
            
            if src_fs_path.is_dir():
                shutil.copytree(src_fs_path, dst_fs_path)
            else:
                shutil.copy2(src_fs_path, dst_fs_path)
            
            # Copy metadata file if it exists
            src_metadata_path = src_fs_path.with_suffix(src_fs_path.suffix + '.meta')
            if src_metadata_path.exists():
                dst_metadata_path = dst_fs_path.with_suffix(dst_fs_path.suffix + '.meta')
                shutil.copy2(src_metadata_path, dst_metadata_path)
            
            return True
            
        except Exception as e:
            print(f"Error copying node: {e}")
            return False

    async def move_node(self, src_path: str, dst_path: str) -> bool:
        """Move a node to another location"""
        return await asyncio.to_thread(self._sync_move_node, src_path, dst_path)

    def _sync_move_node(self, src_path: str, dst_path: str) -> bool:
        """Move a node (sync)"""
        if not self._initialized:
            return False

        try:
            src_fs_path = self._resolve_path(src_path)
            dst_fs_path = self._resolve_path(dst_path)
            
            if not src_fs_path.exists():
                return False
            
            if dst_fs_path.exists():
                return False
            
            # Ensure parent directory exists
            dst_fs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the file/directory
            shutil.move(str(src_fs_path), str(dst_fs_path))
            
            # Move metadata file if it exists
            src_metadata_path = src_fs_path.with_suffix(src_fs_path.suffix + '.meta')
            if src_metadata_path.exists():
                dst_metadata_path = dst_fs_path.with_suffix(dst_fs_path.suffix + '.meta')
                shutil.move(str(src_metadata_path), str(dst_metadata_path))
            
            return True
            
        except Exception as e:
            print(f"Error moving node: {e}")
            return False

    # Batch operations for performance

    async def batch_write(self, operations: list[tuple[str, bytes]]) -> list[bool]:
        """Write multiple files in batch"""
        return await asyncio.to_thread(self._sync_batch_write, operations)

    def _sync_batch_write(self, operations: list[tuple[str, bytes]]) -> list[bool]:
        """Write multiple files in batch (sync)"""
        if not self._initialized:
            return [False] * len(operations)

        results = []
        for path, content in operations:
            try:
                fs_path = self._resolve_path(path)
                
                # Ensure parent directory exists
                fs_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Create node if it doesn't exist
                if not fs_path.exists():
                    fs_path.touch()
                
                # Write content
                with open(fs_path, 'wb') as f:
                    f.write(content)
                
                results.append(True)
            except Exception as e:
                print(f"Error in batch write for {path}: {e}")
                results.append(False)
        
        return results

    async def batch_read(self, paths: list[str]) -> list[bytes | None]:
        """Read multiple files in batch"""
        return await asyncio.to_thread(self._sync_batch_read, paths)

    def _sync_batch_read(self, paths: list[str]) -> list[bytes | None]:
        """Read multiple files in batch (sync)"""
        if not self._initialized:
            return [None] * len(paths)

        results = []
        for path in paths:
            try:
                fs_path = self._resolve_path(path)
                
                if fs_path.exists() and not fs_path.is_dir():
                    with open(fs_path, 'rb') as f:
                        results.append(f.read())
                else:
                    results.append(None)
            except Exception as e:
                print(f"Error in batch read for {path}: {e}")
                results.append(None)
        
        return results

    async def batch_delete(self, paths: list[str]) -> list[bool]:
        """Delete multiple nodes in batch"""
        return await asyncio.to_thread(self._sync_batch_delete, paths)

    def _sync_batch_delete(self, paths: list[str]) -> list[bool]:
        """Delete multiple nodes in batch (sync)"""
        if not self._initialized:
            return [False] * len(paths)

        results = []
        for path in paths:
            try:
                fs_path = self._resolve_path(path)
                
                if not fs_path.exists():
                    results.append(False)
                    continue
                
                if fs_path.is_dir():
                    # Check if directory is empty
                    if any(fs_path.iterdir()):
                        results.append(False)
                        continue
                    fs_path.rmdir()
                else:
                    fs_path.unlink()
                
                # Remove metadata file if it exists
                metadata_path = fs_path.with_suffix(fs_path.suffix + '.meta')
                if metadata_path.exists():
                    metadata_path.unlink()
                
                results.append(True)
            except Exception as e:
                print(f"Error in batch delete for {path}: {e}")
                results.append(False)
        
        return results

    async def batch_create(self, nodes: list[EnhancedNodeInfo]) -> list[bool]:
        """Create multiple nodes in batch"""
        return await asyncio.to_thread(self._sync_batch_create, nodes)

    def _sync_batch_create(self, nodes: list[EnhancedNodeInfo]) -> list[bool]:
        """Create multiple nodes in batch (sync)"""
        if not self._initialized:
            return [False] * len(nodes)

        results = []
        for node_info in nodes:
            try:
                fs_path = self._resolve_path(node_info.get_path())
                
                # Check if already exists
                if fs_path.exists():
                    results.append(False)
                    continue
                
                # Ensure parent directory exists
                fs_path.parent.mkdir(parents=True, exist_ok=True)
                
                if node_info.is_dir:
                    fs_path.mkdir()
                else:
                    fs_path.touch()
                
                # Set metadata
                self._set_filesystem_metadata(fs_path, node_info)
                results.append(True)
                
            except Exception as e:
                print(f"Error in batch create for {node_info.get_path()}: {e}")
                results.append(False)
        
        return results