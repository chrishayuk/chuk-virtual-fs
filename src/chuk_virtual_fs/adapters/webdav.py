"""
WebDAV adapter for chuk-virtual-fs.

Exposes a VirtualFileSystem via WebDAV protocol, allowing it to be mounted
in Finder (macOS), File Explorer (Windows), or any WebDAV client.

No kernel extensions or system modifications required!
"""

import io
import logging
import mimetypes
import os
import threading
import time
from typing import TYPE_CHECKING, Any, Optional

from wsgidav import wsgidav_app
from wsgidav.dav_provider import DAVCollection, DAVNonCollection, DAVProvider

if TYPE_CHECKING:
    from cheroot.wsgi import Server

# These will be imported lazily to avoid circular import
DAVError = None
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404

from chuk_virtual_fs import SyncVirtualFileSystem

logger = logging.getLogger(__name__)


def _get_dav_error() -> type:
    """Lazy import of DAVError to avoid circular import."""
    global DAVError
    if DAVError is None:
        from wsgidav.dav_error import DAVError as _DAVError

        DAVError = _DAVError
    return DAVError  # type: ignore[no-any-return]


class VFSResource(DAVNonCollection):
    """Represents a file in the VFS."""

    def __init__(self, path: str, vfs: SyncVirtualFileSystem, environ: dict):
        super().__init__(path, environ)
        self.vfs = vfs
        self.vfs_path = path

    def get_content_length(self) -> int | None:
        """Return file size."""
        try:
            return self.vfs.get_size(self.vfs_path)
        except Exception:
            return None

    def get_content_type(self) -> str:
        """Return MIME type."""
        mime_type, _ = mimetypes.guess_type(self.vfs_path)
        return mime_type or "application/octet-stream"

    def get_creation_date(self) -> float | None:
        """Return creation timestamp."""
        try:
            info = self.vfs.get_node_info(self.vfs_path)
            if info and hasattr(info, "created_at"):
                # Ensure we return a float timestamp
                ts = info.created_at
                return float(ts) if ts is not None else time.time()
        except Exception:
            pass
        return time.time()

    def get_display_name(self) -> str:
        """Return display name."""
        return os.path.basename(self.vfs_path)

    def get_etag(self) -> str:
        """Return entity tag."""
        try:
            info = self.vfs.get_node_info(self.vfs_path)
            if info and hasattr(info, "modified_at"):
                ts = info.modified_at
                if ts is not None:
                    return f'"{int(float(ts))}-{self.get_content_length()}"'
        except Exception:
            pass
        return f'"{int(time.time())}-{self.get_content_length()}"'

    def get_last_modified(self) -> float | None:
        """Return last modified timestamp."""
        try:
            info = self.vfs.get_node_info(self.vfs_path)
            if info and hasattr(info, "modified_at"):
                # Ensure we return a float timestamp
                ts = info.modified_at
                return float(ts) if ts is not None else time.time()
        except Exception:
            pass
        return time.time()

    def get_content(self) -> io.BytesIO:
        """Return file content as stream."""
        try:
            content = self.vfs.read_file(self.vfs_path)
            content_bytes: bytes
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            elif content is None:
                content_bytes = b""
            else:
                content_bytes = content
            return io.BytesIO(content_bytes)
        except Exception as e:
            logger.error(f"Error reading file {self.vfs_path}: {e}")
            DAVErrorClass = _get_dav_error()
            raise DAVErrorClass(HTTP_NOT_FOUND, f"File not found: {self.vfs_path}")

    def begin_write(self, content_type: str | None = None) -> io.BytesIO:
        """Begin writing to file."""
        return io.BytesIO()

    def end_write(self, with_errors: bool) -> None:
        """Complete write operation."""
        if not with_errors and hasattr(self, "_write_buffer"):
            content = self._write_buffer.getvalue()
            try:
                self.vfs.write_file(self.vfs_path, content.decode("utf-8"))
            except UnicodeDecodeError:
                # Binary content
                self.vfs.write_file(self.vfs_path, content)

    def support_ranges(self) -> bool:
        """Whether this resource supports range requests."""
        return True

    def support_etag(self) -> bool:
        """Whether this resource supports ETags."""
        return True


class VFSCollection(DAVCollection):
    """Represents a directory in the VFS."""

    def __init__(self, path: str, vfs: SyncVirtualFileSystem, environ: dict):
        super().__init__(path, environ)
        self.vfs = vfs
        self.vfs_path = path

    def get_member_names(self) -> list[str]:
        """Return list of member names."""
        try:
            return self.vfs.ls(self.vfs_path)
        except Exception as e:
            logger.error(f"Error listing directory {self.vfs_path}: {e}")
            return []

    def get_member(self, name: str) -> Optional["VFSResource | VFSCollection"]:
        """Return a member by name."""
        member_path = os.path.join(self.vfs_path, name)
        try:
            if self.vfs.is_dir(member_path):
                return VFSCollection(member_path, self.vfs, self.environ)
            elif self.vfs.is_file(member_path):
                return VFSResource(member_path, self.vfs, self.environ)
        except Exception as e:
            logger.error(f"Error getting member {member_path}: {e}")
        return None

    def create_empty_resource(self, name: str) -> "VFSResource":
        """Create a new empty file."""
        member_path = os.path.join(self.vfs_path, name)
        try:
            self.vfs.touch(member_path)
            return VFSResource(member_path, self.vfs, self.environ)
        except Exception as e:
            logger.error(f"Error creating file {member_path}: {e}")
            DAVErrorClass = _get_dav_error()
            raise DAVErrorClass(HTTP_FORBIDDEN, f"Cannot create file: {name}")

    def create_collection(self, name: str) -> "VFSCollection":
        """Create a new directory."""
        member_path = os.path.join(self.vfs_path, name)
        try:
            self.vfs.mkdir(member_path)
            return VFSCollection(member_path, self.vfs, self.environ)
        except Exception as e:
            logger.error(f"Error creating directory {member_path}: {e}")
            DAVErrorClass = _get_dav_error()
            raise DAVErrorClass(HTTP_FORBIDDEN, f"Cannot create directory: {name}")

    def delete(self) -> None:
        """Delete this directory."""
        try:
            self.vfs.rmdir(self.vfs_path)
        except Exception as e:
            logger.error(f"Error deleting directory {self.vfs_path}: {e}")
            DAVErrorClass = _get_dav_error()
            raise DAVErrorClass(HTTP_FORBIDDEN, "Cannot delete directory")

    def get_display_name(self) -> str:
        """Return display name."""
        return os.path.basename(self.vfs_path) or "/"

    def get_creation_date(self) -> float | None:
        """Return creation timestamp."""
        try:
            info = self.vfs.get_node_info(self.vfs_path)
            if info and hasattr(info, "created_at"):
                # Ensure we return a float timestamp
                ts = info.created_at
                return float(ts) if ts is not None else time.time()
        except Exception:
            pass
        return time.time()

    def get_last_modified(self) -> float | None:
        """Return last modified timestamp."""
        try:
            info = self.vfs.get_node_info(self.vfs_path)
            if info and hasattr(info, "modified_at"):
                # Ensure we return a float timestamp
                ts = info.modified_at
                return float(ts) if ts is not None else time.time()
        except Exception:
            pass
        return time.time()


class WebDAVProvider(DAVProvider):
    """WebDAV provider that exposes a VirtualFileSystem."""

    def __init__(self, vfs: SyncVirtualFileSystem, readonly: bool = False):
        """
        Initialize WebDAV provider.

        Args:
            vfs: The VirtualFileSystem to expose
            readonly: If True, only allow read operations
        """
        super().__init__()
        self.vfs = vfs
        self.readonly = readonly

    def get_resource_inst(
        self, path: str, environ: dict
    ) -> Optional["VFSResource | VFSCollection"]:
        """
        Return a DAVResource object for the given path.

        Args:
            path: WebDAV path (e.g., "/docs/file.txt")
            environ: WSGI environment dict

        Returns:
            VFSResource, VFSCollection, or None if not found
        """
        # Normalize path
        vfs_path = path if path else "/"

        try:
            # Check if path exists
            if not self.vfs.exists(vfs_path):
                return None

            # Return appropriate resource type
            if self.vfs.is_dir(vfs_path):
                return VFSCollection(vfs_path, self.vfs, environ)
            elif self.vfs.is_file(vfs_path):
                return VFSResource(vfs_path, self.vfs, environ)
        except Exception as e:
            logger.error(f"Error getting resource for {vfs_path}: {e}")

        return None

    def is_readonly(self) -> bool:
        """Return True if this provider is read-only."""
        return self.readonly


class WebDAVAdapter:
    """
    WebDAV server adapter for VirtualFileSystem.

    Exposes a VFS via WebDAV protocol, allowing it to be mounted as a network
    drive without requiring kernel extensions.

    Example:
        >>> from chuk_virtual_fs import SyncVirtualFileSystem
        >>> from chuk_virtual_fs.adapters import WebDAVAdapter
        >>>
        >>> vfs = SyncVirtualFileSystem()
        >>> vfs.write_file("/test.txt", "Hello World")
        >>>
        >>> # Start WebDAV server
        >>> adapter = WebDAVAdapter(vfs, host="127.0.0.1", port=8080)
        >>> adapter.start()  # Blocking
        >>>
        >>> # Or run in background
        >>> adapter.start_background()
        >>> # Access at http://127.0.0.1:8080
        >>> adapter.stop()
    """

    def __init__(
        self,
        vfs: SyncVirtualFileSystem,
        host: str = "127.0.0.1",
        port: int = 8080,
        readonly: bool = False,
        **kwargs: Any,
    ):
        """
        Initialize WebDAV adapter.

        Args:
            vfs: VirtualFileSystem to expose
            host: Host to bind to (default: 127.0.0.1)
            port: Port to bind to (default: 8080)
            readonly: If True, only allow read operations
            **kwargs: Additional WsgiDAV configuration options
        """
        self.vfs = vfs
        self.host = host
        self.port = port
        self.readonly = readonly

        # Create WebDAV provider
        provider = WebDAVProvider(vfs, readonly=readonly)

        # Build WsgiDAV configuration
        config = {
            "host": host,
            "port": port,
            "provider_mapping": {"/": provider},
            "verbose": kwargs.get("verbose", 1),
            "logging": {
                "enable_loggers": kwargs.get("enable_loggers", []),
            },
            "simple_dc": {"user_mapping": {"*": True}},  # Allow anonymous access
        }

        # Merge additional kwargs
        config.update(kwargs)

        # Create WSGI application
        self.app = wsgidav_app.WsgiDAVApp(config)
        self._server: Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """
        Start WebDAV server (blocking).

        This will block until the server is stopped via Ctrl+C or stop().
        """
        from cheroot import wsgi

        logger.info(f"Starting WebDAV server at http://{self.host}:{self.port}")
        self._server = wsgi.Server((self.host, self.port), self.app)

        try:
            self._server.start()
        except KeyboardInterrupt:
            logger.info("WebDAV server stopped by user")
            self._server.stop()

    def start_background(self) -> None:
        """
        Start WebDAV server in background thread.

        Use stop() to terminate the server.
        """
        if self._thread and self._thread.is_alive():
            logger.warning("WebDAV server already running")
            return

        from cheroot import wsgi

        logger.info(
            f"Starting WebDAV server in background at http://{self.host}:{self.port}"
        )
        self._server = wsgi.Server((self.host, self.port), self.app)

        # Start server in daemon thread
        self._thread = threading.Thread(target=self._server.start, daemon=True)
        self._thread.start()

        # Give server time to start
        time.sleep(0.5)
        logger.info(f"WebDAV server ready at http://{self.host}:{self.port}")

    def stop(self) -> None:
        """Stop WebDAV server."""
        if self._server:
            logger.info("Stopping WebDAV server")
            self._server.stop()
            self._server = None
            self._thread = None

    @property
    def url(self) -> str:
        """Get the WebDAV server URL."""
        return f"http://{self.host}:{self.port}"

    def __enter__(self) -> "WebDAVAdapter":
        """Context manager entry."""
        self.start_background()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()
