"""Tests for WebDAV adapter."""

from unittest.mock import Mock, patch

from chuk_virtual_fs.adapters.webdav import (
    WebDAVAdapter,
    WebDAVProvider,
    _get_dav_error,
)
from chuk_virtual_fs.sync_wrapper import SyncVirtualFileSystem


class TestGetDavError:
    """Test DAVError lazy import."""

    def test_get_dav_error(self):
        """Test lazy import of DAVError."""
        # This will import DAVError
        error_class = _get_dav_error()
        assert error_class is not None

        # Second call should return cached value
        error_class2 = _get_dav_error()
        assert error_class is error_class2


class TestWebDAVProvider:
    """Test WebDAVProvider."""

    def test_init(self):
        """Test provider initialization."""
        vfs = SyncVirtualFileSystem()
        provider = WebDAVProvider(vfs, readonly=False)
        assert provider.vfs == vfs
        assert provider.readonly is False

    def test_init_readonly(self):
        """Test provider initialization with readonly."""
        vfs = SyncVirtualFileSystem()
        provider = WebDAVProvider(vfs, readonly=True)
        assert provider.readonly is True

    def test_get_resource_inst_not_found(self):
        """Test getting resource for non-existent path."""
        vfs = SyncVirtualFileSystem()
        provider = WebDAVProvider(vfs)
        resource = provider.get_resource_inst("/nonexistent", {})
        assert resource is None

    def test_is_readonly(self):
        """Test checking if provider is readonly."""
        vfs = SyncVirtualFileSystem()
        provider = WebDAVProvider(vfs, readonly=True)
        assert provider.is_readonly() is True

        provider2 = WebDAVProvider(vfs, readonly=False)
        assert provider2.is_readonly() is False


class TestWebDAVAdapter:
    """Test WebDAVAdapter."""

    def test_init(self):
        """Test adapter initialization."""
        vfs = SyncVirtualFileSystem()
        adapter = WebDAVAdapter(vfs, host="127.0.0.1", port=8080)
        assert adapter.vfs == vfs
        assert adapter.host == "127.0.0.1"
        assert adapter.port == 8080
        assert adapter.readonly is False

    def test_init_with_options(self):
        """Test adapter initialization with options."""
        vfs = SyncVirtualFileSystem()
        adapter = WebDAVAdapter(
            vfs, host="localhost", port=9090, readonly=True, verbose=2
        )
        assert adapter.host == "localhost"
        assert adapter.port == 9090
        assert adapter.readonly is True

    def test_url_property(self):
        """Test getting adapter URL."""
        vfs = SyncVirtualFileSystem()
        adapter = WebDAVAdapter(vfs, host="127.0.0.1", port=8080)
        assert adapter.url == "http://127.0.0.1:8080"

    @patch("cheroot.wsgi.Server")
    def test_start_background(self, mock_server_class):
        """Test starting adapter in background."""
        vfs = SyncVirtualFileSystem()
        adapter = WebDAVAdapter(vfs)

        mock_server = Mock()
        mock_server_class.return_value = mock_server

        adapter.start_background()

        mock_server_class.assert_called_once()
        mock_server.start.assert_called_once()

    @patch("cheroot.wsgi.Server")
    def test_stop(self, mock_server_class):
        """Test stopping adapter."""
        vfs = SyncVirtualFileSystem()
        adapter = WebDAVAdapter(vfs)

        mock_server = Mock()
        mock_server_class.return_value = mock_server
        adapter.start_background()

        adapter.stop()
        mock_server.stop.assert_called_once()

    @patch("cheroot.wsgi.Server")
    def test_context_manager(self, mock_server_class):
        """Test using adapter as context manager."""
        vfs = SyncVirtualFileSystem()

        mock_server = Mock()
        mock_server_class.return_value = mock_server

        with WebDAVAdapter(vfs) as adapter:
            assert adapter is not None
            mock_server.start.assert_called_once()

        mock_server.stop.assert_called_once()
