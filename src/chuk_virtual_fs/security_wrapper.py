"""
chuk_virtual_fs/security_wrapper.py - Security wrapper for storage providers
"""

import logging
import posixpath
import re
from datetime import UTC, datetime
from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust level as needed
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


class SecurityWrapper(AsyncStorageProvider):
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
        provider: AsyncStorageProvider,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB default max file size
        max_total_size: int = 100 * 1024 * 1024,  # 100MB default total quota
        read_only: bool = False,
        allowed_paths: list[str] | None = None,
        denied_paths: list[str] | None = None,
        denied_patterns: list[str | re.Pattern] | None = None,
        max_path_depth: int = 10,
        max_files: int = 1000,
        setup_allowed_paths: bool = True,
    ):
        """
        Initialize the security wrapper.
        """
        # Validate and fallback for numeric configurations
        if max_file_size <= 0:
            logger.warning(
                "Invalid max_file_size (%s); defaulting to 10MB", max_file_size
            )
            max_file_size = 10 * 1024 * 1024
        if max_total_size <= 0:
            logger.warning(
                "Invalid max_total_size (%s); defaulting to 100MB", max_total_size
            )
            max_total_size = 100 * 1024 * 1024
        if max_path_depth <= 0:
            logger.warning(
                "Invalid max_path_depth (%s); defaulting to 10", max_path_depth
            )
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
        self.denied_patterns: list[re.Pattern] = []
        default_patterns = [
            r"\.\.",  # Path traversal pattern
            r"^\.hidden",  # Hidden files starting with .hidden
            r"^\.",  # All hidden files
            r".*\.(exe|sh|bat|cmd)$",  # Executable files
        ]
        pattern_list = denied_patterns or default_patterns
        failed_patterns = 0
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
                    failed_patterns += 1
            # Note: else clause removed as unreachable - all cases covered above

        # Warn if no patterns were successfully compiled
        if not self.denied_patterns:
            logger.warning(
                "No valid denied patterns compiled - security may be compromised. "
                "All %d pattern(s) failed to compile.",
                failed_patterns,
            )

        self.max_path_depth = max_path_depth
        self.max_files = max_files
        self._violation_log: list[dict[str, Any]] = []

        # Optional: Track current directory from provider if available.
        if hasattr(provider, "current_directory_path"):
            self.current_directory_path = provider.current_directory_path

        # Mark setup flag for allowed path checks
        self._in_setup = False
        self.setup_allowed_paths = setup_allowed_paths

    def _normalize_path(self, path: str | None) -> str:
        """Normalize and return a valid path; defaults to root if invalid."""
        if not path:
            return "/"
        try:
            return posixpath.normpath(path)
        except Exception:
            return "/"

    async def setup_allowed_paths_async(self) -> None:
        """
        Create allowed paths to ensure they exist before applying restrictions.
        This should be called after initialization if setup_allowed_paths was True.

        This method temporarily disables security checks to create the allowed paths.
        """
        if not self.setup_allowed_paths or self.allowed_paths == ["/"]:
            return

        original_read_only = self.read_only
        self.read_only = False
        self._in_setup = True

        try:
            # Create each allowed path if it doesn't exist
            for path in self.allowed_paths:
                if path != "/" and not await self.provider.exists(path):
                    # Create directory node for allowed path
                    from chuk_virtual_fs.node_info import EnhancedNodeInfo

                    parts = path.strip("/").split("/")
                    parent = "/" if len(parts) == 1 else "/".join(parts[:-1])
                    name = parts[-1]

                    node_info = EnhancedNodeInfo(
                        name=name, is_dir=True, parent_path=parent, permissions="755"
                    )
                    await self.provider.create_node(node_info)
                    logger.info(f"Created allowed path: {path}")
        except Exception as e:
            logger.warning(f"Error setting up allowed paths: {e}")
        finally:
            self.read_only = original_read_only
            self._in_setup = False

    def _log_violation(self, operation: str, path: str, reason: str) -> None:
        """Log a security violation using the logging module."""
        violation = {
            "operation": operation,
            "path": path,
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._violation_log.append(violation)
        logger.error(
            "Security violation: %s (op: %s, path: %s)", reason, operation, path
        )

    def get_violation_log(self) -> list[dict[str, Any]]:
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
            logger.warning(
                "Failed to match pattern '%s' with '%s': %s", pattern.pattern, string, e
            )
            return False

    def _matches_denied_patterns(self, basename: str) -> bool:
        """Return True if the basename matches any denied patterns."""
        return any(
            self._safe_pattern_match(pattern, basename)
            for pattern in self.denied_patterns
        )

    def _check_allowed_paths(self, path: str) -> bool:
        """Return True if the normalized path is in the allowed paths list."""
        if self.allowed_paths == ["/"]:
            return True
        return any(
            path == allowed or path.startswith(allowed + "/")
            for allowed in self.allowed_paths
        )

    def _check_denied_paths(self, path: str) -> bool:
        """Return True if the normalized path is in the denied paths list."""
        return any(
            path == denied or path.startswith(denied + "/")
            for denied in self.denied_paths
        )

    def _is_path_allowed(self, path: str | None, operation: str) -> bool:
        """
        Check if a path is allowed based on security rules.
        """
        if getattr(self, "_in_setup", False):
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
            self._log_violation(
                operation,
                norm_path,
                f"Path depth exceeds maximum ({path_depth} > {self.max_path_depth})",
            )
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

    async def initialize(self) -> bool:
        """Initialize the underlying provider."""
        return await self.provider.initialize()

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node with security checks."""
        path = node_info.get_path()
        if not self._is_path_allowed(path, "create_node"):
            return False

        # Enforce file count limits for files only.
        if not node_info.is_dir:
            stats = await self.get_storage_stats()
            if stats.get("file_count", 0) >= self.max_files:
                self._log_violation(
                    "create_node",
                    path,
                    f"File count exceeds maximum ({self.max_files})",
                )
                return False

        return await self.provider.create_node(node_info)

    async def delete_node(self, path: str) -> bool:
        """Delete a node with security checks."""
        if not self._is_path_allowed(path, "delete_node"):
            return False
        return await self.provider.delete_node(path)

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get node information with security checks."""
        if not self._is_path_allowed(path, "get_node_info"):
            return None
        return await self.provider.get_node_info(path)

    async def list_directory(self, path: str) -> list[str]:
        """List directory contents with security checks."""
        if not self._is_path_allowed(path, "list_directory"):
            return []
        return await self.provider.list_directory(path)

    async def write_file(self, path: str, content: bytes) -> bool:
        """Write content to a file with security checks."""
        if not self._is_path_allowed(path, "write_file"):
            return False

        content_size = len(content)
        if content_size > self.max_file_size:
            self._log_violation(
                "write_file",
                path,
                f"File size exceeds maximum ({content_size} > {self.max_file_size} bytes)",
            )
            return False

        stats = await self.get_storage_stats()
        current_size = stats.get("total_size_bytes", 0)
        current_content = await self.read_file(path)
        current_file_size = len(current_content) if current_content else 0
        new_total_size = current_size - current_file_size + content_size

        if new_total_size > self.max_total_size:
            self._log_violation(
                "write_file",
                path,
                f"Total storage quota exceeded ({new_total_size} > {self.max_total_size} bytes)",
            )
            return False

        return await self.provider.write_file(path, content)

    async def read_file(self, path: str) -> bytes | None:
        """Read file content with security checks."""
        if not self._is_path_allowed(path, "read_file"):
            return None
        return await self.provider.read_file(path)

    async def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics, including security-related stats."""
        stats = await self.provider.get_storage_stats()
        stats.update(
            {
                "max_file_size": self.max_file_size,
                "max_total_size": self.max_total_size,
                "max_files": self.max_files,
                "read_only": self.read_only,
                "allowed_paths": self.allowed_paths,
                "security_violations": len(self._violation_log),
            }
        )
        return stats

    async def cleanup(self) -> dict[str, Any]:
        """Perform cleanup operations."""
        return await self.provider.cleanup()

    async def close(self) -> None:
        """Close the wrapped provider."""
        return await self.provider.close()

    # Required async methods from AsyncStorageProvider

    async def exists(self, path: str) -> bool:
        """Check if a path exists with security checks."""
        if not self._is_path_allowed(path, "exists"):
            return False
        return await self.provider.exists(path)

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a node with security checks."""
        if not self._is_path_allowed(path, "get_metadata"):
            return {}
        return await self.provider.get_metadata(path)

    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set metadata for a node with security checks."""
        if not self._is_path_allowed(path, "set_metadata"):
            return False
        return await self.provider.set_metadata(path, metadata)

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the underlying provider."""
        return getattr(self.provider, name)
