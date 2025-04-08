"""
chuk_virtual_fs/providers/e2b.py - E2B-based storage provider
"""
import os
import time
import json
import posixpath
from typing import Dict, List, Optional, Any, Union
from chuk_virtual_fs.provider_base import StorageProvider
from chuk_virtual_fs.node_info import FSNodeInfo


class E2BStorageProvider(StorageProvider):
    """
    E2B Sandbox storage provider
    
    Interfaces with E2B Code Interpreter's sandbox environment
    to provide filesystem operations within a remote sandbox.
    
    Requires e2b_code_interpreter package: pip install e2b-code-interpreter
    """
    
    def __init__(
        self, 
        sandbox_id: Optional[str] = None,
        root_dir: str = "/home/user",
        auto_create_root: bool = True,
        timeout: int = 300,  # 5 minutes default
        **sandbox_kwargs
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
        self.root_dir = root_dir
        self.sandbox = None
        self.sandbox_id = sandbox_id
        self.auto_create_root = auto_create_root
        self.timeout = timeout
        self.sandbox_kwargs = sandbox_kwargs
        
        # Cache for node information to reduce API calls
        self.node_cache = {}
        self.cache_ttl = 30  # seconds
        self.cache_timestamps = {}
        
        # Track statistics locally to reduce API calls
        self._stats = {
            "total_size_bytes": 0,
            "file_count": 0,
            "directory_count": 1,  # Start with root directory
        }
        
    def _get_sandbox_path(self, path: str) -> str:
        """Convert virtual filesystem path to sandbox path"""
        if path == '/':
            return self.root_dir
            
        # Remove leading slash for joining with root_dir
        clean_path = path[1:] if path.startswith('/') else path
        return posixpath.join(self.root_dir, clean_path)
        
    def _check_cache(self, path: str) -> Optional[FSNodeInfo]:
        """Check if node info is in cache and still valid"""
        now = time.time()
        if path in self.node_cache and now - self.cache_timestamps.get(path, 0) < self.cache_ttl:
            return self.node_cache[path]
        return None
        
    def _update_cache(self, path: str, node_info: FSNodeInfo) -> None:
        """Update node info in cache"""
        self.node_cache[path] = node_info
        self.cache_timestamps[path] = time.time()
    
    def initialize(self) -> bool:
        """Initialize the E2B Sandbox provider"""
        try:
            from e2b_code_interpreter import Sandbox
            
            # Connect to existing sandbox or create a new one
            if self.sandbox_id:
                # Connect to the existing sandbox
                try:
                    self.sandbox = Sandbox.connect(self.sandbox_id)
                    print(f"Successfully connected to existing sandbox: {self.sandbox_id}")
                except Exception as e:
                    print(f"Error connecting to sandbox {self.sandbox_id}: {e}")
                    print("Creating a new sandbox instead...")
                    self.sandbox = Sandbox(timeout=self.timeout, **self.sandbox_kwargs)
            else:
                # Create a new sandbox
                self.sandbox = Sandbox(timeout=self.timeout, **self.sandbox_kwargs)
            
            # Store the sandbox ID
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
            root_info = FSNodeInfo("", True)
            self._update_cache("/", root_info)
            
            return True
        except ImportError:
            print("Error: e2b_code_interpreter package is required for E2B storage provider")
            return False
        except Exception as e:
            print(f"Error initializing E2B sandbox: {e}")
            return False
    
    def create_node(self, node_info: FSNodeInfo) -> bool:
        """Create a new node (file or directory)"""
        if not self.sandbox:
            return False
            
        try:
            path = node_info.get_path()
            sandbox_path = self._get_sandbox_path(path)
            
            # Check if the node already exists
            if self.get_node_info(path):
                return False
                
            # Ensure parent directory exists
            parent_path = posixpath.dirname(path)
            if parent_path != path and not self.get_node_info(parent_path):
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
    
    def delete_node(self, path: str) -> bool:
        """Delete a node"""
        if not self.sandbox:
            return False
            
        try:
            # Check if node exists
            node_info = self.get_node_info(path)
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
                    content = self.read_file(path)
                    file_size = len(content.encode('utf-8')) if content else 0
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
    
    def get_node_info(self, path: str) -> Optional[FSNodeInfo]:
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
            result = self.sandbox.commands.run(f"stat -c '%F' {sandbox_path} 2>/dev/null || echo 'not_found'")
            if result.exit_code != 0 or 'not_found' in result.stdout:
                return None
                
            # Determine if it's a directory or file
            is_dir = 'directory' in result.stdout.strip()
            
            # Get parent path and name
            parent_path = posixpath.dirname(path)
            name = posixpath.basename(path) or ""
            
            # Create node info
            node_info = FSNodeInfo(name, is_dir, parent_path)
            
            # Get modification time
            result = self.sandbox.commands.run(f"stat -c '%Y' {sandbox_path}")
            if result.exit_code == 0:
                mtime = int(result.stdout.strip())
                node_info.modified_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
            
            # Update cache
            self._update_cache(path, node_info)
            
            return node_info
        except Exception as e:
            print(f"Error getting node info: {e}")
            return None
    
    def list_directory(self, path: str) -> List[str]:
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
            node_info = self.get_node_info(path)
            if not node_info or not node_info.is_dir:
                return []
                
            sandbox_path = self._get_sandbox_path(path)
            
            # List directory contents
            result = self.sandbox.commands.run(f"ls -A {sandbox_path}")
            if result.exit_code != 0:
                return []
                
            # Split the output into lines and filter empty lines
            items = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            
            return items
        except Exception as e:
            print(f"Error listing directory: {e}")
            return []
    
    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file"""
        if not self.sandbox:
            return False
            
        try:
            # Check if path exists and is a file
            node_info = self.get_node_info(path)
            
            # Get the old size if file exists
            old_size = 0
            if node_info:
                if node_info.is_dir:
                    return False
                
                try:
                    old_content = self.read_file(path)
                    old_size = len(old_content.encode('utf-8')) if old_content else 0
                except Exception:
                    old_size = 0
            else:
                # File doesn't exist, create parent directories
                parent_path = posixpath.dirname(path)
                if parent_path and parent_path != "/":
                    parent_info = self.get_node_info(parent_path)
                    if not parent_info:
                        # Create parent directory
                        parent_parts = parent_path.strip('/').split('/')
                        current_path = ""
                        for part in parent_parts:
                            if not part:
                                continue
                            current_path = f"{current_path}/{part}"
                            if not self.get_node_info(current_path):
                                parent_node_info = FSNodeInfo(part, True, posixpath.dirname(current_path))
                                if not self.create_node(parent_node_info):
                                    return False
                    elif not parent_info.is_dir:
                        return False
                
                # Create the file
                file_name = posixpath.basename(path)
                file_node_info = FSNodeInfo(file_name, False, parent_path)
                if not self.create_node(file_node_info):
                    return False
            
            # Calculate new size
            content_size = len(content.encode('utf-8'))
            
            # Write the content to the file
            sandbox_path = self._get_sandbox_path(path)
            
            # Write to a temporary file first to handle special characters
            temp_path = f"{self.root_dir}/.tmp_write_{time.time()}"
            self.sandbox.files.write(temp_path, content)
            
            # Move the temporary file to the destination
            result = self.sandbox.commands.run(f"mv {temp_path} {sandbox_path}")
            if result.exit_code != 0:
                return False
            
            # Update stats
            self._stats["total_size_bytes"] = self._stats["total_size_bytes"] - old_size + content_size
            
            # Update node info in cache
            if path in self.node_cache:
                self.node_cache[path].modified_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.cache_timestamps[path] = time.time()
            
            return True
        except Exception as e:
            print(f"Error writing file: {e}")
            return False
    
    def read_file(self, path: str) -> Optional[str]:
        """Read content from a file"""
        if not self.sandbox:
            return None
            
        try:
            # Check if path exists and is a file
            node_info = self.get_node_info(path)
            if not node_info or node_info.is_dir:
                return None
                
            sandbox_path = self._get_sandbox_path(path)
            
            # Read the file content
            content = self.sandbox.files.read(sandbox_path)
            
            # If content is bytes, decode to string
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')
                
            return content
        except Exception as e:
            print(f"Error reading file: {e}")
            return None
    
    def get_storage_stats(self) -> Dict:
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
        except Exception:
            # Fallback to stored stats if commands fail
            pass
            
        # Return the stats with additional information
        stats = self._stats.copy()
        stats["total_size_mb"] = stats["total_size_bytes"] / (1024 * 1024)
        stats["node_count"] = stats["file_count"] + stats["directory_count"]
        stats["sandbox_id"] = self.sandbox_id
        stats["root_dir"] = self.root_dir
        
        return stats
    
    def cleanup(self) -> Dict:
        """Perform cleanup operations"""
        if not self.sandbox:
            return {"error": "Sandbox not initialized"}
            
        try:
            # Get initial stats
            size_before = self._stats["total_size_bytes"]
            files_before = self._stats["file_count"]
            
            # Clean up temporary files
            tmp_dir = f"{self.root_dir}/tmp"
            
            # Create tmp directory if it doesn't exist
            self.sandbox.commands.run(f"mkdir -p {tmp_dir}")
            
            # Remove all files in the tmp directory
            result = self.sandbox.commands.run(f"find {tmp_dir} -type f -delete")
            
            # Get updated stats
            self.get_storage_stats()
            
            # Calculate changes
            bytes_freed = size_before - self._stats["total_size_bytes"]
            files_removed = files_before - self._stats["file_count"]
            
            return {
                "bytes_freed": bytes_freed,
                "files_removed": files_removed,
                "sandbox_id": self.sandbox_id
            }
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return {"error": str(e)}
    
    def close(self) -> bool:
        """Close the sandbox connection"""
        if self.sandbox:
            try:
                # No explicit close method in E2B API, but we can clear our reference
                self.sandbox = None
                return True
            except Exception as e:
                print(f"Error closing sandbox: {e}")
                return False
        return True