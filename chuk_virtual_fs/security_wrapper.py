"""
chuk_virtual_fs/security_wrapper.py - Security wrapper for storage providers
"""

import posixpath
import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union

from chuk_virtual_fs.provider_base import StorageProvider
from chuk_virtual_fs.node_info import FSNodeInfo

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust level as needed
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class SecurityWrapper(StorageProvider):
    """
    Security wrapper for storage providers to add sandboxing and resource limits.
    
    Provides:
    - File size limits
    - Total storage quota
    - Path traversal protection
    - Restricted paths and file types
    - Read-only mode
    """

    def __init__(
        self, 
        provider: StorageProvider,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB default max file size
        max_total_size: int = 100 * 1024 * 1024,  # 100MB default total quota
        read_only: bool = False,
        allowed_paths: Optional[List[str]] = None,
        denied_paths: Optional[List[str]] = None,
        denied_patterns: Optional[List[Union[str, re.Pattern]]] = None,
        max_path_depth: int = 10,
        max_files: int = 1000,
        setup_allowed_paths: bool = True
    ):
        """
        Initialize the security wrapper.
        """
        # Validate and fallback for numeric configurations
        if max_file_size <= 0:
            logger.warning("Invalid max_file_size (%s); defaulting to 10MB", max_file_size)
            max_file_size = 10 * 1024 * 1024
        if max_total_size <= 0:
            logger.warning("Invalid max_total_size (%s); defaulting to 100MB", max_total_size)
            max_total_size = 100 * 1024 * 1024
        if max_path_depth <= 0:
            logger.warning("Invalid max_path_depth (%s); defaulting to 10", max_path_depth)
            max_path_depth = 10
        if max_files <= 0:
            logger.warning("Invalid max_files (%s); defaulting to 1000", max_files)
            max_files = 1000

        self.provider = provider
        self.max_file_size = max_file_size
        self.max_total_size = max_total_size
        self.read_only = read_only
        self.allowed_paths = allowed_paths or ["/"]
        self.denied_paths = denied_paths or ["/etc/passwd", "/etc/shadow"]

        # Compile patterns defensively.
        self.denied_patterns: List[re.Pattern] = []
        default_patterns = [
            r"\.\.",        # Path traversal pattern
            r"^\.hidden",   # Hidden files starting with .hidden
            r"^\.",         # All hidden files
            r".*\.(exe|sh|bat|cmd)$"  # Executable files
        ]
        pattern_list = denied_patterns or default_patterns
        for pattern in pattern_list:
            if isinstance(pattern, re.Pattern):
                # Already compiled; use as is.
                self.denied_patterns.append(pattern)
            elif isinstance(pattern, str):
                try:
                    compiled_pattern = re.compile(pattern)
                    self.denied_patterns.append(compiled_pattern)
                except Exception as e:
                    logger.warning("Could not compile pattern '%s': %s", pattern, e)
            else:
                logger.warning("Unexpected type for denied pattern: %s", type(pattern))

        self.max_path_depth = max_path_depth
        self.max_files = max_files
        self._violation_log: List[Dict[str, Any]] = []

        # Optional: Track current directory from provider if available.
        if hasattr(provider, 'current_directory_path'):
            self.current_directory_path = provider.current_directory_path

        # Setup allowed paths if requested.
        if setup_allowed_paths:
            self._setup_allowed_paths()

    def _normalize_path(self, path: Optional[str]) -> str:
        """Normalize and return a valid path; defaults to root if invalid."""
        if not path:
            return "/"
        try:
            return posixpath.normpath(path)
        except Exception:
            return "/"

    def _setup_allowed_paths(self) -> None:
        """
        Create allowed paths to ensure they exist before applying restrictions.
        Temporarily disables security checks during setup.
        """
        original_read_only = self.read_only
        self.read_only = False
        self._in_setup = True

        try:
            for path in self.allowed_paths:
                if path == "/":
                    continue  # Root exists
                norm_path = self._normalize_path(path)
                if self.provider.get_node_info(norm_path):
                    continue

                components = norm_path.strip('/').split('/')
                current_path = ""
                for component in components:
                    if not component:
                        continue
                    parent_path = current_path or "/"
                    current_path = posixpath.join(parent_path, component)
                    if not self.provider.get_node_info(current_path):
                        node_info = FSNodeInfo(component, True, parent_path)
                        self.provider.create_node(node_info)
        finally:
            self.read_only = original_read_only
            self._in_setup = False

    def _log_violation(self, operation: str, path: str, reason: str) -> None:
        """Log a security violation using the logging module."""
        violation = {
            "operation": operation,
            "path": path,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._violation_log.append(violation)
        logger.error("Security violation: %s (op: %s, path: %s)", reason, operation, path)

    def get_violation_log(self) -> List[Dict[str, Any]]:
        """Return a copy of the security violation log."""
        return self._violation_log.copy()

    def clear_violations(self) -> None:
        """Clear the security violation log."""
        self._violation_log = []

    def _safe_pattern_match(self, pattern: re.Pattern, string: str) -> bool:
        """Safely match a regex pattern against a string."""
        try:
            return pattern.search(string) is not None
        except Exception as e:
            logger.warning("Failed to match pattern '%s' with '%s': %s", pattern.pattern, string, e)
            return False

    def _matches_denied_patterns(self, basename: str) -> bool:
        """Return True if the basename matches any denied patterns."""
        return any(self._safe_pattern_match(pattern, basename) for pattern in self.denied_patterns)

    def _check_allowed_paths(self, path: str) -> bool:
        """Return True if the normalized path is in the allowed paths list."""
        if self.allowed_paths == ["/"]:
            return True
        return any(path == allowed or path.startswith(allowed + '/') for allowed in self.allowed_paths)

    def _check_denied_paths(self, path: str) -> bool:
        """Return True if the normalized path is in the denied paths list."""
        return any(path == denied or path.startswith(denied + '/') for denied in self.denied_paths)

    def _is_path_allowed(self, path: Optional[str], operation: str) -> bool:
        """
        Check if a path is allowed based on security rules.
        """
        if getattr(self, '_in_setup', False):
            return True

        norm_path = self._normalize_path(path)

        # Allow root path for certain read operations.
        if norm_path == "/" and operation in ["get_node_info", "list_directory"]:
            return True

        if self.read_only and operation in ["create_node", "delete_node", "write_file"]:
            self._log_violation(operation, norm_path, "Filesystem is in read-only mode")
            return False

        # Enforce maximum path depth.
        path_depth = len([p for p in norm_path.split("/") if p])
        if path_depth > self.max_path_depth:
            self._log_violation(operation, norm_path, f"Path depth exceeds maximum ({path_depth} > {self.max_path_depth})")
            return False

        if not self._check_allowed_paths(norm_path):
            self._log_violation(operation, norm_path, "Path not in allowed paths list")
            return False

        if self._check_denied_paths(norm_path):
            self._log_violation(operation, norm_path, "Path in denied paths list")
            return False

        if self._matches_denied_patterns(posixpath.basename(norm_path)):
            self._log_violation(operation, norm_path, "Path matches denied pattern")
            return False

        return True

    def initialize(self) -> bool:
        """Initialize the underlying provider."""
        return self.provider.initialize()

    def create_node(self, node_info: FSNodeInfo) -> bool:
        """Create a new node with security checks."""
        path = node_info.get_path()
        if not self._is_path_allowed(path, "create_node"):
            return False

        # Enforce file count limits for files only.
        if not node_info.is_dir:
            stats = self.get_storage_stats()
            if stats.get("file_count", 0) >= self.max_files:
                self._log_violation("create_node", path, f"File count exceeds maximum ({self.max_files})")
                return False

        return self.provider.create_node(node_info)

    def delete_node(self, path: str) -> bool:
        """Delete a node with security checks."""
        if not self._is_path_allowed(path, "delete_node"):
            return False
        return self.provider.delete_node(path)

    def get_node_info(self, path: str) -> Optional[FSNodeInfo]:
        """Get node information with security checks."""
        if not self._is_path_allowed(path, "get_node_info"):
            return None
        return self.provider.get_node_info(path)

    def list_directory(self, path: str) -> List[str]:
        """List directory contents with security checks."""
        if not self._is_path_allowed(path, "list_directory"):
            return []
        return self.provider.list_directory(path)

    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file with security checks."""
        if not self._is_path_allowed(path, "write_file"):
            return False

        content_size = len(content.encode('utf-8'))
        if content_size > self.max_file_size:
            self._log_violation("write_file", path, f"File size exceeds maximum ({content_size} > {self.max_file_size} bytes)")
            return False

        stats = self.get_storage_stats()
        current_size = stats.get("total_size_bytes", 0)
        current_content = self.read_file(path)
        current_file_size = len(current_content.encode('utf-8')) if current_content else 0
        new_total_size = current_size - current_file_size + content_size

        if new_total_size > self.max_total_size:
            self._log_violation("write_file", path, f"Total storage quota exceeded ({new_total_size} > {self.max_total_size} bytes)")
            return False

        return self.provider.write_file(path, content)

    def read_file(self, path: str) -> Optional[str]:
        """Read file content with security checks."""
        if not self._is_path_allowed(path, "read_file"):
            return None
        return self.provider.read_file(path)

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics, including security-related stats."""
        stats = self.provider.get_storage_stats()
        stats.update({
            "max_file_size": self.max_file_size,
            "max_total_size": self.max_total_size,
            "max_files": self.max_files,
            "read_only": self.read_only,
            "allowed_paths": self.allowed_paths,
            "security_violations": len(self._violation_log)
        })
        return stats

    def cleanup(self) -> Dict[str, Any]:
        """Perform cleanup operations."""
        return self.provider.cleanup()

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the underlying provider."""
        return getattr(self.provider, name)
