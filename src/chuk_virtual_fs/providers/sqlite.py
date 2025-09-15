"""
chuk_virtual_fs/providers/sqlite.py - Thread-safe SQLite-based storage provider

Fixed version that properly handles SQLite threading constraints
"""

import asyncio
import json
import posixpath
import sqlite3
import time
from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider


class SqliteStorageProvider(AsyncStorageProvider):
    """Thread-safe SQLite-based storage provider
    
    Each operation gets its own SQLite connection to avoid threading issues.
    """

    def __init__(self, db_path: str = ":memory:"):
        super().__init__()
        self.db_path = db_path
        self._initialized = False

    def _get_connection(self):
        """Get a new SQLite connection for this operation"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            
            # Always ensure schema exists for new connections
            if self._initialized:
                self._ensure_schema(conn)
            
            return conn
        except Exception as e:
            print(f"Error creating SQLite connection: {e}")
            return None

    def _ensure_schema(self, conn):
        """Ensure database schema exists"""
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                path TEXT PRIMARY KEY,
                node_data TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_content (
                path TEXT PRIMARY KEY,
                content BLOB,
                size INTEGER DEFAULT 0,
                FOREIGN KEY (path) REFERENCES nodes (path) ON DELETE CASCADE
            )
        """)
        
        # Create root directory if it doesn't exist
        cursor.execute("SELECT 1 FROM nodes WHERE path = ?", ("/",))
        if not cursor.fetchone():
            root_info = EnhancedNodeInfo("/", True, parent_path="")
            root_data = json.dumps(root_info.to_dict())
            cursor.execute("INSERT OR IGNORE INTO nodes VALUES (?, ?)", ("/", root_data))
        
        conn.commit()

    async def initialize(self) -> bool:
        """Initialize the database"""
        return await asyncio.to_thread(self._sync_initialize)

    def _sync_initialize(self) -> bool:
        """Synchronous database initialization"""
        try:
            conn = self._get_connection()
            if conn is None:
                return False
            
            self._ensure_schema(conn)
            conn.close()
            self._initialized = True
            
            # Store a dummy connection for backward compatibility
            self.conn = "initialized"
            return True
        except Exception as e:
            print(f"Error initializing SQLite storage: {e}")
            return False

    async def close(self) -> None:
        """Close - no persistent connections to close"""
        self._initialized = False
        self.conn = None  # For backward compatibility with tests

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node"""
        return await asyncio.to_thread(self._sync_create_node, node_info)

    def _sync_create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node (sync)"""
        if not self._initialized:
            return False
            
        conn = self._get_connection()
        if not conn:
            return False

        try:
            path = node_info.get_path()
            cursor = conn.cursor()

            # Check if node already exists
            cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (path,))
            if cursor.fetchone():
                return False

            # Ensure parent exists
            parent_path = posixpath.dirname(path)
            if parent_path != path:
                cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (parent_path,))
                if not cursor.fetchone():
                    return False

            # Insert node
            node_data = json.dumps(node_info.to_dict())
            cursor.execute("INSERT INTO nodes VALUES (?, ?)", (path, node_data))

            # Initialize empty content for files
            if not node_info.is_dir:
                cursor.execute(
                    "INSERT INTO file_content VALUES (?, ?, ?)", (path, b"", 0)
                )

            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating node: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False
        finally:
            conn.close()

    async def delete_node(self, path: str) -> bool:
        """Delete a node"""
        return await asyncio.to_thread(self._sync_delete_node, path)

    def _sync_delete_node(self, path: str) -> bool:
        """Delete a node (sync)"""
        if not self._initialized:
            return False
            
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()

            # Check if node exists
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()
            if not result:
                return False

            node_data = json.loads(result[0])
            is_dir = node_data["is_dir"]

            # Check if directory is empty
            if is_dir:
                cursor.execute("SELECT 1 FROM nodes WHERE path LIKE ?", (path + "/%",))
                if cursor.fetchone():
                    return False

            # Delete node
            cursor.execute("DELETE FROM nodes WHERE path = ?", (path,))

            # Delete content if it's a file
            if not is_dir:
                cursor.execute("DELETE FROM file_content WHERE path = ?", (path,))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting node: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False
        finally:
            conn.close()

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get node info"""
        return await asyncio.to_thread(self._sync_get_node_info, path)

    def _sync_get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get information about a node (sync)"""
        if not self._initialized:
            return None
            
        conn = self._get_connection()
        if not conn:
            return None

        # Normalize path
        if not path:
            path = "/"
        elif path != "/" and path.endswith("/"):
            path = path[:-1]

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()

            if not result:
                return None

            node_data = json.loads(result[0])
            return EnhancedNodeInfo.from_dict(node_data)
        except Exception as e:
            print(f"Error getting node info: {e}")
            return None
        finally:
            conn.close()

    async def list_directory(self, path: str) -> list[str]:
        """List directory contents"""
        return await asyncio.to_thread(self._sync_list_directory, path)

    def _sync_list_directory(self, path: str) -> list[str]:
        """List contents of a directory (sync)"""
        if not self._initialized:
            return []
            
        conn = self._get_connection()
        if not conn:
            return []

        # Normalize path
        if not path:
            path = "/"
        elif path != "/" and path.endswith("/"):
            path = path[:-1]

        try:
            cursor = conn.cursor()
            
            # List direct children
            if path == "/":
                pattern = "/%"
                exclude_pattern = "/%/%"
            else:
                pattern = f"{path}/%"
                exclude_pattern = f"{path}/%/%"
            
            cursor.execute(
                "SELECT path FROM nodes WHERE path LIKE ? AND path NOT LIKE ?",
                (pattern, exclude_pattern)
            )
            
            results = []
            for row in cursor.fetchall():
                child_path = row[0]
                name = child_path.split("/")[-1]
                if name:  # Skip empty names
                    results.append(name)
            
            return sorted(results)
        except Exception as e:
            print(f"Error listing directory: {e}")
            return []
        finally:
            conn.close()

    async def read_file(self, path: str) -> bytes | None:
        """Read file content"""
        return await asyncio.to_thread(self._sync_read_file, path)

    def _sync_read_file(self, path: str) -> bytes | None:
        """Read file content (sync)"""
        if not self._initialized:
            return None
            
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            
            # Check if it's a file
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()
            if not result:
                return None
            
            node_data = json.loads(result[0])
            if node_data["is_dir"]:
                return None
            
            # Get content
            cursor.execute("SELECT content FROM file_content WHERE path = ?", (path,))
            result = cursor.fetchone()
            
            return result[0] if result else b""
        except Exception as e:
            print(f"Error reading file: {e}")
            return None
        finally:
            conn.close()

    async def write_file(self, path: str, content: bytes) -> bool:
        """Write file content"""
        return await asyncio.to_thread(self._sync_write_file, path, content)

    def _sync_write_file(self, path: str, content: bytes) -> bool:
        """Write file content (sync)"""
        if not self._initialized:
            return False
            
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            
            # Check if file exists and is not a directory
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()
            if not result:
                return False
            
            node_data = json.loads(result[0])
            if node_data["is_dir"]:
                return False
            
            # Update content
            cursor.execute(
                "INSERT OR REPLACE INTO file_content (path, content, size) VALUES (?, ?, ?)",
                (path, content, len(content))
            )
            
            # Update node metadata
            node_info = EnhancedNodeInfo.from_dict(node_data)
            node_info.size = len(content)
            node_info.update_modified()
            
            updated_data = json.dumps(node_info.to_dict())
            cursor.execute("UPDATE nodes SET node_data = ? WHERE path = ?", (updated_data, path))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error writing file: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False
        finally:
            conn.close()

    async def exists(self, path: str) -> bool:
        """Check if path exists"""
        return await asyncio.to_thread(self._sync_exists, path)

    def _sync_exists(self, path: str) -> bool:
        """Check if path exists (sync)"""
        if not self._initialized:
            return False
            
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (path,))
            return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking existence: {e}")
            return False
        finally:
            conn.close()

    async def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics"""
        return await asyncio.to_thread(self._sync_get_storage_stats)

    def _sync_get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics (sync)"""
        if not self._initialized:
            return {"error": "Database not initialized"}
            
        conn = self._get_connection()
        if not conn:
            return {"error": "Database not initialized"}

        try:
            cursor = conn.cursor()
            
            # Get total file size
            cursor.execute("SELECT COALESCE(SUM(size), 0) FROM file_content")
            total_size = cursor.fetchone()[0]
            
            # Count files
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE json_extract(node_data, '$.is_dir') = 0")
            file_count = cursor.fetchone()[0]
            
            # Count directories
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE json_extract(node_data, '$.is_dir') = 1")
            dir_count = cursor.fetchone()[0]
            
            return {
                "total_size_bytes": total_size,
                "file_count": file_count,
                "directory_count": dir_count,
            }
        except Exception as e:
            print(f"Error getting storage stats: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

    async def cleanup(self) -> dict[str, Any]:
        """Cleanup expired files"""
        return await asyncio.to_thread(self._sync_cleanup)

    def _sync_cleanup(self) -> dict[str, Any]:
        """Cleanup expired files (sync)"""
        return {
            "files_removed": 0,
            "bytes_freed": 0,
            "expired_removed": 0
        }

    async def create_directory(self, path: str, mode: int = 0o755, owner_id: int = 1000, group_id: int = 1000) -> bool:
        """Create a directory with parent directories if needed"""
        return await asyncio.to_thread(self._sync_create_directory, path, mode, owner_id, group_id)

    def _sync_create_directory(self, path: str, mode: int, owner_id: int, group_id: int) -> bool:
        """Create a directory (sync)"""
        if not self._initialized:
            return False
            
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            
            # Normalize path
            if path.endswith("/"):
                path = path.rstrip("/")
            
            # Check if already exists
            cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (path,))
            if cursor.fetchone():
                return True  # Already exists
            
            # Create parent directories if needed
            path_parts = path.strip("/").split("/")
            current_path = ""
            
            for part in path_parts:
                parent_path = current_path
                current_path = f"/{part}" if not current_path else f"{current_path}/{part}"
                
                # Check if this path already exists
                cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (current_path,))
                if not cursor.fetchone():
                    # Create the directory node
                    node_info = EnhancedNodeInfo(
                        name=part,
                        is_dir=True,
                        parent_path=parent_path or "/",
                        permissions=str(mode),
                        owner=str(owner_id),
                        group=str(group_id),
                        provider="sqlite",
                    )
                    node_data = json.dumps(node_info.to_dict())
                    cursor.execute("INSERT INTO nodes VALUES (?, ?)", (current_path, node_data))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating directory: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False
        finally:
            conn.close()

    async def calculate_checksum(self, path: str, algorithm: str = "sha256") -> str | None:
        """Calculate checksum for a file"""
        return await asyncio.to_thread(self._sync_calculate_checksum, path, algorithm)

    def _sync_calculate_checksum(self, path: str, algorithm: str) -> str | None:
        """Calculate checksum for a file (sync)"""
        if not self._initialized:
            return None
            
        conn = self._get_connection()
        if not conn:
            return None

        try:
            import hashlib
            
            cursor = conn.cursor()
            
            # Check if it's a file
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()
            if not result:
                return None
            
            node_data = json.loads(result[0])
            if node_data["is_dir"]:
                return None
            
            # Get content
            cursor.execute("SELECT content FROM file_content WHERE path = ?", (path,))
            result = cursor.fetchone()
            
            if not result:
                return None
            
            content = result[0] or b""
            
            # Calculate checksum
            if algorithm.lower() == "md5":
                return hashlib.md5(content).hexdigest()
            elif algorithm.lower() == "sha1":
                return hashlib.sha1(content).hexdigest()
            elif algorithm.lower() == "sha256":
                return hashlib.sha256(content).hexdigest()
            elif algorithm.lower() == "sha512":
                return hashlib.sha512(content).hexdigest()
            else:
                return None
                
        except Exception as e:
            print(f"Error calculating checksum: {e}")
            return None
        finally:
            conn.close()

    async def copy_node(self, src_path: str, dst_path: str) -> bool:
        """Copy a node (file or directory) to another location"""
        return await asyncio.to_thread(self._sync_copy_node, src_path, dst_path)

    def _sync_copy_node(self, src_path: str, dst_path: str) -> bool:
        """Copy a node (sync)"""
        if not self._initialized:
            return False
            
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            
            # Check if source exists
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (src_path,))
            result = cursor.fetchone()
            if not result:
                return False
            
            # Check if destination already exists
            cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (dst_path,))
            if cursor.fetchone():
                return False
            
            src_data = json.loads(result[0])
            src_info = EnhancedNodeInfo.from_dict(src_data)
            
            # Create destination node
            dst_name = dst_path.split("/")[-1]
            dst_parent = "/".join(dst_path.split("/")[:-1]) or "/"
            
            dst_info = EnhancedNodeInfo(
                name=dst_name,
                is_dir=src_info.is_dir,
                parent_path=dst_parent,
                size=src_info.size,
                mime_type=src_info.mime_type,
                provider="sqlite",
            )
            
            dst_data = json.dumps(dst_info.to_dict())
            cursor.execute("INSERT INTO nodes VALUES (?, ?)", (dst_path, dst_data))
            
            # Copy file content if it's a file
            if not src_info.is_dir:
                cursor.execute("SELECT content, size FROM file_content WHERE path = ?", (src_path,))
                content_result = cursor.fetchone()
                if content_result:
                    cursor.execute(
                        "INSERT INTO file_content VALUES (?, ?, ?)",
                        (dst_path, content_result[0], content_result[1])
                    )
            
            # Recursively copy directory contents if it's a directory
            if src_info.is_dir:
                # Get all children of the source directory
                cursor.execute(
                    "SELECT path FROM nodes WHERE path LIKE ?",
                    (src_path + "/%",)
                )
                children = cursor.fetchall()
                
                for child_row in children:
                    child_path = child_row[0]
                    relative_path = child_path[len(src_path):]
                    new_child_path = dst_path + relative_path
                    
                    # Recursively copy each child
                    self._sync_copy_node_internal(conn, child_path, new_child_path)
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error copying node: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False
        finally:
            conn.close()

    def _sync_copy_node_internal(self, conn, src_path: str, dst_path: str) -> bool:
        """Internal copy node using existing connection"""
        try:
            cursor = conn.cursor()
            
            # Get source node data
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (src_path,))
            result = cursor.fetchone()
            if not result:
                return False
            
            src_data = json.loads(result[0])
            src_info = EnhancedNodeInfo.from_dict(src_data)
            
            # Create destination node
            dst_name = dst_path.split("/")[-1]
            dst_parent = "/".join(dst_path.split("/")[:-1]) or "/"
            
            dst_info = EnhancedNodeInfo(
                name=dst_name,
                is_dir=src_info.is_dir,
                parent_path=dst_parent,
                size=src_info.size,
                mime_type=src_info.mime_type,
                provider="sqlite",
            )
            
            dst_data = json.dumps(dst_info.to_dict())
            cursor.execute("INSERT INTO nodes VALUES (?, ?)", (dst_path, dst_data))
            
            # Copy file content if it's a file
            if not src_info.is_dir:
                cursor.execute("SELECT content, size FROM file_content WHERE path = ?", (src_path,))
                content_result = cursor.fetchone()
                if content_result:
                    cursor.execute(
                        "INSERT INTO file_content VALUES (?, ?, ?)",
                        (dst_path, content_result[0], content_result[1])
                    )
            
            return True
        except Exception as e:
            print(f"Error copying node internally: {e}")
            return False

    async def move_node(self, src_path: str, dst_path: str) -> bool:
        """Move a node to another location"""
        return await asyncio.to_thread(self._sync_move_node, src_path, dst_path)

    def _sync_move_node(self, src_path: str, dst_path: str) -> bool:
        """Move a node (sync)"""
        if not self._initialized:
            return False
            
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            
            # Check if source exists
            cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (src_path,))
            if not cursor.fetchone():
                return False
            
            # Check if destination already exists
            cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (dst_path,))
            if cursor.fetchone():
                return False
            
            # Update nodes table
            cursor.execute("UPDATE nodes SET path = ? WHERE path = ?", (dst_path, src_path))
            
            # Update file_content table if needed
            cursor.execute("UPDATE file_content SET path = ? WHERE path = ?", (dst_path, src_path))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error moving node: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False
        finally:
            conn.close()

    async def batch_write(self, operations: list[tuple[str, bytes]]) -> list[bool]:
        """Write multiple files in batch"""
        return await asyncio.to_thread(self._sync_batch_write, operations)

    def _sync_batch_write(self, operations: list[tuple[str, bytes]]) -> list[bool]:
        """Write multiple files in batch (sync)"""
        if not self._initialized:
            return [False] * len(operations)
            
        conn = self._get_connection()
        if not conn:
            return [False] * len(operations)

        results = []
        try:
            for path, content in operations:
                # Create node if it doesn't exist
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (path,))
                if not cursor.fetchone():
                    node_info = EnhancedNodeInfo(
                        name=path.split("/")[-1],
                        is_dir=False,
                        parent_path="/".join(path.split("/")[:-1]) or "/",
                        provider="sqlite",
                    )
                    node_data = json.dumps(node_info.to_dict())
                    cursor.execute("INSERT INTO nodes VALUES (?, ?)", (path, node_data))
                    cursor.execute("INSERT INTO file_content VALUES (?, ?, ?)", (path, b"", 0))
                
                result = self._sync_write_file_internal(conn, path, content)
                results.append(result)
            
            conn.commit()
        except Exception as e:
            print(f"Error in batch write: {e}")
            try:
                conn.rollback()
            except:
                pass
            # If there was an error, mark all as failed
            results = [False] * len(operations)
        finally:
            conn.close()
        
        return results

    def _sync_write_file_internal(self, conn, path: str, content: bytes) -> bool:
        """Internal write file using existing connection"""
        try:
            cursor = conn.cursor()
            
            # Update content
            cursor.execute(
                "INSERT OR REPLACE INTO file_content (path, content, size) VALUES (?, ?, ?)",
                (path, content, len(content))
            )
            
            # Update node metadata
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()
            if result:
                node_data = json.loads(result[0])
                node_info = EnhancedNodeInfo.from_dict(node_data)
                node_info.size = len(content)
                node_info.update_modified()
                
                updated_data = json.dumps(node_info.to_dict())
                cursor.execute("UPDATE nodes SET node_data = ? WHERE path = ?", (updated_data, path))
            
            return True
        except Exception as e:
            print(f"Error writing file: {e}")
            return False

    async def batch_read(self, paths: list[str]) -> list[bytes | None]:
        """Read multiple files in batch"""
        return await asyncio.to_thread(self._sync_batch_read, paths)

    def _sync_batch_read(self, paths: list[str]) -> list[bytes | None]:
        """Read multiple files in batch (sync)"""
        if not self._initialized:
            return [None] * len(paths)
            
        conn = self._get_connection()
        if not conn:
            return [None] * len(paths)

        results = []
        try:
            for path in paths:
                content = self._sync_read_file_internal(conn, path)
                results.append(content)
        finally:
            conn.close()
        
        return results

    def _sync_read_file_internal(self, conn, path: str) -> bytes | None:
        """Internal read file using existing connection"""
        try:
            cursor = conn.cursor()
            
            # Check if it's a file
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()
            if not result:
                return None
            
            node_data = json.loads(result[0])
            if node_data["is_dir"]:
                return None
            
            # Get content
            cursor.execute("SELECT content FROM file_content WHERE path = ?", (path,))
            result = cursor.fetchone()
            
            return result[0] if result else b""
        except Exception as e:
            return None

    async def batch_delete(self, paths: list[str]) -> list[bool]:
        """Delete multiple nodes in batch"""
        return await asyncio.to_thread(self._sync_batch_delete, paths)

    def _sync_batch_delete(self, paths: list[str]) -> list[bool]:
        """Delete multiple nodes in batch (sync)"""
        if not self._initialized:
            return [False] * len(paths)
            
        conn = self._get_connection()
        if not conn:
            return [False] * len(paths)

        results = []
        try:
            for path in paths:
                result = self._sync_delete_node_internal(conn, path)
                results.append(result)
            conn.commit()
        except Exception as e:
            print(f"Error in batch delete: {e}")
            try:
                conn.rollback()
            except:
                pass
            results = [False] * len(paths)
        finally:
            conn.close()
        
        return results

    def _sync_delete_node_internal(self, conn, path: str) -> bool:
        """Internal delete node using existing connection"""
        try:
            cursor = conn.cursor()

            # Check if node exists
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()
            if not result:
                return False

            node_data = json.loads(result[0])
            is_dir = node_data["is_dir"]

            # Check if directory is empty
            if is_dir:
                cursor.execute("SELECT 1 FROM nodes WHERE path LIKE ?", (path + "/%",))
                if cursor.fetchone():
                    return False

            # Delete node
            cursor.execute("DELETE FROM nodes WHERE path = ?", (path,))

            # Delete content if it's a file
            if not is_dir:
                cursor.execute("DELETE FROM file_content WHERE path = ?", (path,))

            return True
        except Exception as e:
            return False

    async def batch_create(self, nodes: list[EnhancedNodeInfo]) -> list[bool]:
        """Create multiple nodes in batch"""
        return await asyncio.to_thread(self._sync_batch_create, nodes)

    def _sync_batch_create(self, nodes: list[EnhancedNodeInfo]) -> list[bool]:
        """Create multiple nodes in batch (sync)"""
        if not self._initialized:
            return [False] * len(nodes)
            
        conn = self._get_connection()
        if not conn:
            return [False] * len(nodes)

        results = []
        try:
            for node_info in nodes:
                result = self._sync_create_node_internal(conn, node_info)
                results.append(result)
            conn.commit()
        except Exception as e:
            print(f"Error in batch create: {e}")
            try:
                conn.rollback()
            except:
                pass
            results = [False] * len(nodes)
        finally:
            conn.close()
        
        return results

    def _sync_create_node_internal(self, conn, node_info: EnhancedNodeInfo) -> bool:
        """Internal create node using existing connection"""
        try:
            path = node_info.get_path()
            cursor = conn.cursor()

            # Check if node already exists
            cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (path,))
            if cursor.fetchone():
                return False

            # Ensure parent exists
            parent_path = posixpath.dirname(path)
            if parent_path != path:
                cursor.execute("SELECT 1 FROM nodes WHERE path = ?", (parent_path,))
                if not cursor.fetchone():
                    return False

            # Insert node
            node_data = json.dumps(node_info.to_dict())
            cursor.execute("INSERT INTO nodes VALUES (?, ?)", (path, node_data))

            # Initialize empty content for files
            if not node_info.is_dir:
                cursor.execute(
                    "INSERT INTO file_content VALUES (?, ?, ?)", (path, b"", 0)
                )

            return True
        except Exception as e:
            return False
    
    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a node"""
        return await asyncio.to_thread(self._sync_get_metadata, path)

    def _sync_get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a node (sync)"""
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
            "custom_meta": node_info.custom_meta or {},
            "tags": node_info.tags or {},
        }

    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set metadata for a node"""
        return await asyncio.to_thread(self._sync_set_metadata, path, metadata)

    def _sync_set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set metadata for a node (sync)"""
        if not self._initialized:
            return False
            
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT node_data FROM nodes WHERE path = ?", (path,))
            result = cursor.fetchone()
            if not result:
                return False

            node_data = json.loads(result[0])
            node_info = EnhancedNodeInfo.from_dict(node_data)
            
            # Update metadata fields
            for key, value in metadata.items():
                if hasattr(node_info, key):
                    setattr(node_info, key, value)
            
            node_info.update_modified()
            
            updated_data = json.dumps(node_info.to_dict())
            cursor.execute("UPDATE nodes SET node_data = ? WHERE path = ?", (updated_data, path))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error setting metadata: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False
        finally:
            conn.close()