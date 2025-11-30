"""
tests/providers/test_google_drive_provider.py - Tests for Google Drive storage provider

Uses mocking to avoid requiring actual Google Drive credentials.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.google_drive import GoogleDriveProvider

# Check if Google Drive dependencies are available
try:
    import google.auth.transport.requests  # noqa: F401
    import google.oauth2.credentials  # noqa: F401
    import googleapiclient.discovery  # noqa: F401
    import googleapiclient.errors  # noqa: F401
    import googleapiclient.http  # noqa: F401

    GOOGLE_DRIVE_DEPS_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_DEPS_AVAILABLE = False

# Skip all tests if Google Drive dependencies not available
pytestmark = pytest.mark.skipif(
    not GOOGLE_DRIVE_DEPS_AVAILABLE,
    reason="Google Drive dependencies not installed. Install with: pip install chuk-virtual-fs[google_drive]",
)

# Mock Google Drive API responses
MOCK_ROOT_FOLDER_ID = "mock_root_folder_id_123"
MOCK_FILE_ID = "mock_file_id_456"
MOCK_FOLDER_ID = "mock_folder_id_789"


@pytest.fixture
def mock_credentials():
    """Create mock Google OAuth2 credentials."""
    creds = MagicMock()
    creds.token = "mock_token"
    creds.refresh_token = "mock_refresh_token"
    creds.expired = False
    creds.valid = True
    return creds


@pytest.fixture
def mock_drive_service():
    """Create mock Google Drive service."""
    service = MagicMock()

    # Mock files() API
    files_api = MagicMock()
    service.files.return_value = files_api

    return service


@pytest.fixture
async def provider(mock_credentials, mock_drive_service):
    """Create GoogleDriveProvider with mocked dependencies."""

    with patch("googleapiclient.discovery.build") as mock_build:
        mock_build.return_value = mock_drive_service

        prov = GoogleDriveProvider(
            credentials=mock_credentials,
            root_folder="CHUK_TEST",
            cache_ttl=60,
        )

        # Mock the root folder creation/retrieval
        with patch.object(prov, "_get_or_create_root_folder") as mock_root:
            mock_root.return_value = MOCK_ROOT_FOLDER_ID
            await prov.initialize()

        yield prov
        await prov.close()


@pytest.mark.asyncio
async def test_initialize(mock_credentials):
    """Test provider initialization."""
    mock_service = MagicMock()

    # Mock list() for finding existing root folder
    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "files": [{"id": MOCK_ROOT_FOLDER_ID, "name": "CHUK_TEST"}]
    }
    mock_service.files().list.return_value = mock_list

    with patch("googleapiclient.discovery.build") as mock_build:
        mock_build.return_value = mock_service

        provider = GoogleDriveProvider(credentials=mock_credentials)

        # Mock asyncio.to_thread to execute sync
        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.initialize()

        assert result is True
        assert provider.service is not None
        assert provider._root_folder_id == MOCK_ROOT_FOLDER_ID


@pytest.mark.asyncio
async def test_initialize_creates_root_folder(mock_credentials):
    """Test that initialization creates root folder if it doesn't exist."""
    mock_service = MagicMock()

    # Mock list() - no existing folder found
    mock_list = MagicMock()
    mock_list.execute.return_value = {"files": []}
    mock_service.files().list.return_value = mock_list

    # Mock create() - creates new folder
    mock_create = MagicMock()
    mock_create.execute.return_value = {"id": MOCK_ROOT_FOLDER_ID}
    mock_service.files().create.return_value = mock_create

    with patch("googleapiclient.discovery.build") as mock_build:
        mock_build.return_value = mock_service

        provider = GoogleDriveProvider(
            credentials=mock_credentials, root_folder="CHUK_TEST"
        )

        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.initialize()

        assert result is True
        assert provider._root_folder_id == MOCK_ROOT_FOLDER_ID

        # Verify create was called with correct parameters
        assert mock_service.files().create.called


@pytest.mark.asyncio
async def test_normalize_path(provider):
    """Test path normalization."""
    assert provider._normalize_path("/") == "/"
    assert provider._normalize_path("/test") == "/test"
    assert provider._normalize_path("test") == "/test"
    assert provider._normalize_path("/test/") == "/test"
    assert provider._normalize_path("/test/file.txt") == "/test/file.txt"


@pytest.mark.asyncio
async def test_split_path(provider):
    """Test path splitting."""
    assert provider._split_path("/") == []
    assert provider._split_path("/test") == ["test"]
    assert provider._split_path("/test/file.txt") == ["test", "file.txt"]
    assert provider._split_path("/a/b/c/d") == ["a", "b", "c", "d"]


@pytest.mark.asyncio
async def test_get_file_id_by_path_root(provider):
    """Test getting file ID for root path."""
    file_id = await provider._get_file_id_by_path("/")
    assert file_id == MOCK_ROOT_FOLDER_ID


@pytest.mark.asyncio
async def test_get_file_id_by_path_cached(provider):
    """Test that file ID lookups use cache."""
    # Pre-populate cache
    provider._path_cache["/test"] = (MOCK_FILE_ID, asyncio.get_event_loop().time())

    file_id = await provider._get_file_id_by_path("/test")
    assert file_id == MOCK_FILE_ID
    assert provider._stats["cache_hits"] == 1
    assert provider._stats["cache_misses"] == 0


@pytest.mark.asyncio
async def test_get_file_id_by_path_walk(provider):
    """Test walking path to find file ID."""
    # Mock service responses for path walking
    mock_service = provider.service

    # Mock finding "test" folder
    mock_list_test = MagicMock()
    mock_list_test.execute.return_value = {
        "files": [{"id": MOCK_FOLDER_ID, "name": "test"}]
    }

    # Mock finding "file.txt"
    mock_list_file = MagicMock()
    mock_list_file.execute.return_value = {
        "files": [{"id": MOCK_FILE_ID, "name": "file.txt"}]
    }

    mock_service.files().list.side_effect = [mock_list_test, mock_list_file]

    with patch(
        "asyncio.to_thread", side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)
    ):
        file_id = await provider._get_file_id_by_path("/test/file.txt")

    assert file_id == MOCK_FILE_ID
    assert "/test/file.txt" in provider._path_cache


@pytest.mark.asyncio
async def test_create_node_directory(provider):
    """Test creating a directory node."""
    mock_service = provider.service

    # Mock path lookups: parent exists, node doesn't exist yet
    with patch.object(
        provider,
        "_get_file_id_by_path",
        side_effect=[
            MOCK_ROOT_FOLDER_ID,  # First call: parent path "/" exists
            None,  # Second call: node "/test_folder" doesn't exist yet
        ],
    ):
        # Mock create response
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": MOCK_FOLDER_ID}
        mock_service.files().create.return_value = mock_create

        node_info = EnhancedNodeInfo(
            name="test_folder",
            is_dir=True,
            parent_path="/",
        )

        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.create_node(node_info)

        assert result is True
        assert provider._stats["creates"] == 1

        # Verify create was called with folder MIME type
        call_args = mock_service.files().create.call_args
        assert call_args is not None
        body = call_args[1]["body"]
        assert body["mimeType"] == GoogleDriveProvider.FOLDER_MIME_TYPE


@pytest.mark.asyncio
async def test_create_node_file_with_metadata(provider):
    """Test creating a file node with custom metadata."""
    mock_service = provider.service

    # Mock path lookups: parent exists, node doesn't exist yet
    with patch.object(
        provider,
        "_get_file_id_by_path",
        side_effect=[
            MOCK_ROOT_FOLDER_ID,  # First call: parent path "/" exists
            None,  # Second call: node "/test.txt" doesn't exist yet
        ],
    ):
        # Mock create response
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": MOCK_FILE_ID}
        mock_service.files().create.return_value = mock_create

        node_info = EnhancedNodeInfo(
            name="test.txt",
            is_dir=False,
            parent_path="/",
            session_id="session_123",
            sandbox_id="sandbox_456",
            custom_meta={"key": "value"},
            tags={"env": "test"},
            ttl=3600,
        )

        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.create_node(node_info)

        assert result is True

        # Verify appProperties were set
        call_args = mock_service.files().create.call_args
        body = call_args[1]["body"]
        assert "appProperties" in body
        app_props = body["appProperties"]
        assert app_props["session_id"] == "session_123"
        assert app_props["sandbox_id"] == "sandbox_456"
        assert json.loads(app_props["custom_meta"]) == {"key": "value"}
        assert json.loads(app_props["tags"]) == {"env": "test"}
        assert app_props["ttl"] == "3600"


@pytest.mark.asyncio
async def test_delete_node(provider):
    """Test deleting a node."""
    mock_service = provider.service

    # Mock finding the file
    provider._path_cache["/test.txt"] = (MOCK_FILE_ID, asyncio.get_event_loop().time())

    # Mock delete response
    mock_delete = MagicMock()
    mock_delete.execute.return_value = {}
    mock_service.files().delete.return_value = mock_delete

    with patch(
        "asyncio.to_thread", side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)
    ):
        result = await provider.delete_node("/test.txt")

    assert result is True
    assert provider._stats["deletes"] == 1
    assert "/test.txt" not in provider._path_cache


@pytest.mark.asyncio
async def test_delete_root_fails(provider):
    """Test that deleting root path fails."""
    result = await provider.delete_node("/")
    assert result is False


@pytest.mark.asyncio
async def test_get_node_info(provider):
    """Test getting node information."""
    mock_service = provider.service

    # Mock finding the file
    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "files": [{"id": MOCK_FILE_ID, "name": "test.txt"}]
    }
    mock_service.files().list.return_value = mock_list

    # Mock get metadata
    mock_get = MagicMock()
    mock_get.execute.return_value = {
        "id": MOCK_FILE_ID,
        "name": "test.txt",
        "mimeType": "text/plain",
        "size": "100",
        "createdTime": "2024-01-01T00:00:00.000Z",
        "modifiedTime": "2024-01-01T00:00:00.000Z",
        "md5Checksum": "abc123",
        "parents": [MOCK_ROOT_FOLDER_ID],
        "appProperties": {
            "session_id": "session_123",
            "custom_meta": json.dumps({"key": "value"}),
        },
    }
    mock_service.files().get.return_value = mock_get

    with patch(
        "asyncio.to_thread", side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)
    ):
        node_info = await provider.get_node_info("/test.txt")

    assert node_info is not None
    assert node_info.name == "test.txt"
    assert node_info.size == 100
    assert node_info.md5 == "abc123"
    assert node_info.session_id == "session_123"
    assert node_info.custom_meta == {"key": "value"}


@pytest.mark.asyncio
async def test_get_node_info_cached(provider):
    """Test that node info lookups use cache."""
    # Pre-populate cache
    mock_node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/")
    provider._node_cache[MOCK_FILE_ID] = (
        mock_node_info,
        asyncio.get_event_loop().time(),
    )
    provider._path_cache["/test.txt"] = (MOCK_FILE_ID, asyncio.get_event_loop().time())

    node_info = await provider.get_node_info("/test.txt")

    assert node_info is not None
    assert node_info.name == "test.txt"
    assert provider._stats["cache_hits"] >= 1


@pytest.mark.asyncio
async def test_list_directory(provider):
    """Test listing directory contents."""
    mock_service = provider.service

    # Pre-populate cache for folder
    provider._path_cache["/test"] = (MOCK_FOLDER_ID, asyncio.get_event_loop().time())

    # Mock list response
    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "files": [
            {"name": "a.txt"},
            {"name": "b.txt"},
            {"name": "subfolder"},
        ]
    }
    mock_service.files().list.return_value = mock_list

    with patch(
        "asyncio.to_thread", side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)
    ):
        children = await provider.list_directory("/test")

    assert len(children) == 3
    assert "a.txt" in children
    assert "b.txt" in children
    assert "subfolder" in children


@pytest.mark.asyncio
async def test_write_file_new(provider):
    """Test writing content to a new file."""
    mock_service = provider.service

    # Mock file doesn't exist, then parent folder exists
    with patch.object(
        provider,
        "_get_file_id_by_path",
        side_effect=[
            None,  # First call: file doesn't exist
            MOCK_ROOT_FOLDER_ID,  # Second call: parent folder exists
        ],
    ):
        # Mock create response
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": MOCK_FILE_ID}
        mock_service.files().create.return_value = mock_create

        content = b"Hello, World!"

        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.write_file("/test.txt", content)

        assert result is True
        assert provider._stats["writes"] == 1


@pytest.mark.asyncio
async def test_write_file_update(provider):
    """Test updating existing file content."""
    mock_service = provider.service

    # Mock file exists
    provider._get_file_id_by_path = AsyncMock(return_value=MOCK_FILE_ID)

    # Mock update response
    mock_update = MagicMock()
    mock_update.execute.return_value = {}
    mock_service.files().update.return_value = mock_update

    content = b"Updated content"

    with patch(
        "asyncio.to_thread", side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)
    ):
        result = await provider.write_file("/test.txt", content)

    assert result is True
    assert provider._stats["writes"] == 1


@pytest.mark.asyncio
async def test_read_file(provider):
    """Test reading file content."""

    # Mock file exists
    provider._get_file_id_by_path = AsyncMock(return_value=MOCK_FILE_ID)

    # Mock download
    content = b"File content here"

    # Create a mock service request
    mock_request = MagicMock()
    provider.service.files().get_media = MagicMock(return_value=mock_request)

    # Create a mock downloader with proper next_chunk behavior
    class MockDownloader:
        def __init__(self, buffer, request):
            self.buffer = buffer
            self.buffer.write(content)
            self.called = False

        def next_chunk(self):
            if not self.called:
                self.called = True
                return (None, True)  # (status, done=True)
            return (None, True)

    # Patch MediaIoBaseDownload to use our mock
    provider.MediaIoBaseDownload = MockDownloader

    read_content = await provider.read_file("/test.txt")

    assert read_content == content
    assert provider._stats["reads"] == 1


@pytest.mark.asyncio
async def test_exists(provider):
    """Test checking if path exists."""
    # File exists
    provider._get_file_id_by_path = AsyncMock(return_value=MOCK_FILE_ID)
    assert await provider.exists("/test.txt") is True

    # File doesn't exist
    provider._get_file_id_by_path = AsyncMock(return_value=None)
    assert await provider.exists("/nonexistent.txt") is False


@pytest.mark.asyncio
async def test_get_metadata(provider):
    """Test getting custom metadata."""
    mock_node_info = EnhancedNodeInfo(
        name="test.txt",
        is_dir=False,
        parent_path="/",
        custom_meta={"key": "value", "number": 42},
    )

    # Mock get_node_info
    with patch.object(provider, "get_node_info", return_value=mock_node_info):
        metadata = await provider.get_metadata("/test.txt")

    assert metadata == {"key": "value", "number": 42}


@pytest.mark.asyncio
async def test_set_metadata(provider):
    """Test setting custom metadata."""
    mock_service = provider.service

    # Mock file exists
    provider._get_file_id_by_path = AsyncMock(return_value=MOCK_FILE_ID)

    # Mock update response
    mock_update = MagicMock()
    mock_update.execute.return_value = {}
    mock_service.files().update.return_value = mock_update

    metadata = {"key": "value", "number": 42}

    with patch(
        "asyncio.to_thread", side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)
    ):
        result = await provider.set_metadata("/test.txt", metadata)

    assert result is True

    # Verify update was called with metadata
    call_args = mock_service.files().update.call_args
    body = call_args[1]["body"]
    assert "appProperties" in body
    assert json.loads(body["appProperties"]["custom_meta"]) == metadata


@pytest.mark.asyncio
async def test_get_storage_stats(provider):
    """Test getting storage statistics."""
    stats = await provider.get_storage_stats()

    assert "provider" in stats
    assert stats["provider"] == "google_drive"
    assert "root_folder" in stats
    assert "operations" in stats
    assert "cache" in stats

    operations = stats["operations"]
    assert "reads" in operations
    assert "writes" in operations
    assert "creates" in operations
    assert "deletes" in operations
    assert "api_calls" in operations

    cache = stats["cache"]
    assert "hits" in cache
    assert "misses" in cache


@pytest.mark.asyncio
async def test_cleanup(provider):
    """Test cleanup operation."""
    # Pre-populate caches
    provider._path_cache["/test"] = (MOCK_FILE_ID, 0)
    provider._node_cache[MOCK_FILE_ID] = (MagicMock(), 0)

    result = await provider.cleanup()

    assert "cache_cleared" in result
    assert result["cache_cleared"] is True
    assert len(provider._path_cache) == 0
    assert len(provider._node_cache) == 0


@pytest.mark.asyncio
async def test_credentials_from_dict():
    """Test initializing provider with credentials dict."""
    creds_dict = {
        "token": "mock_token",
        "refresh_token": "mock_refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client.apps.googleusercontent.com",
        "client_secret": "secret",
        "scopes": ["https://www.googleapis.com/auth/drive.file"],
    }

    mock_drive_service = MagicMock()

    with (
        patch(
            "google.oauth2.credentials.Credentials.from_authorized_user_info"
        ) as mock_from_dict,
        patch("googleapiclient.discovery.build", return_value=mock_drive_service),
        patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ),
    ):
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_from_dict.return_value = mock_creds

        provider = GoogleDriveProvider(credentials=creds_dict, root_folder="TEST")

        # Mock root folder creation
        with patch.object(
            provider, "_get_or_create_root_folder", return_value="root_id"
        ):
            await provider.initialize()

        assert provider.credentials == mock_creds
        mock_from_dict.assert_called_once_with(creds_dict)


@pytest.mark.asyncio
async def test_drive_metadata_to_node_info(provider):
    """Test converting Drive metadata to EnhancedNodeInfo."""
    metadata = {
        "id": MOCK_FILE_ID,
        "name": "test.txt",
        "mimeType": "text/plain",
        "size": "1024",
        "createdTime": "2024-01-01T00:00:00.000Z",
        "modifiedTime": "2024-01-02T00:00:00.000Z",
        "md5Checksum": "abc123def456",
        "parents": [MOCK_ROOT_FOLDER_ID],
        "appProperties": {
            "session_id": "session_123",
            "sandbox_id": "sandbox_456",
            "custom_meta": json.dumps({"env": "test"}),
            "tags": json.dumps({"type": "document"}),
            "ttl": "3600",
        },
    }

    node_info = provider._drive_metadata_to_node_info(metadata, "/test.txt")

    assert node_info.name == "test.txt"
    assert node_info.is_dir is False
    assert node_info.size == 1024
    assert node_info.mime_type == "text/plain"
    assert node_info.md5 == "abc123def456"
    assert node_info.session_id == "session_123"
    assert node_info.sandbox_id == "sandbox_456"
    assert node_info.custom_meta == {"env": "test"}
    assert node_info.tags == {"type": "document"}
    assert node_info.ttl == 3600
    assert node_info.provider == "google_drive"


@pytest.mark.asyncio
async def test_drive_metadata_folder_to_node_info(provider):
    """Test converting Drive folder metadata to EnhancedNodeInfo."""
    metadata = {
        "id": MOCK_FOLDER_ID,
        "name": "documents",
        "mimeType": GoogleDriveProvider.FOLDER_MIME_TYPE,
        "createdTime": "2024-01-01T00:00:00.000Z",
        "modifiedTime": "2024-01-02T00:00:00.000Z",
        "parents": [MOCK_ROOT_FOLDER_ID],
        "appProperties": {},
    }

    node_info = provider._drive_metadata_to_node_info(metadata, "/documents")

    assert node_info.name == "documents"
    assert node_info.is_dir is True
    assert node_info.size == 0
    assert node_info.mime_type == GoogleDriveProvider.FOLDER_MIME_TYPE


@pytest.mark.asyncio
async def test_initialize_with_expired_credentials(mock_drive_service):
    """Test initialize with expired credentials that need refresh."""
    creds = MagicMock()
    creds.token = "old_token"
    creds.refresh_token = "refresh_token"
    creds.expired = True
    creds.valid = False

    provider = GoogleDriveProvider(credentials=creds, root_folder="TEST")

    # Mock the build and root folder creation
    with (
        patch(
            "googleapiclient.discovery.build",
            return_value=mock_drive_service,
        ),
        patch.object(provider, "_get_or_create_root_folder", return_value="root_id"),
        patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ),
    ):
        success = await provider.initialize()

    assert success is True
    # Verify refresh was called
    assert creds.refresh.called


@pytest.mark.asyncio
async def test_initialize_failure():
    """Test initialize failure handling."""
    creds = MagicMock()
    creds.expired = False

    provider = GoogleDriveProvider(credentials=creds, root_folder="TEST")

    # Mock build to raise an exception
    with (
        patch(
            "googleapiclient.discovery.build",
            side_effect=Exception("API Error"),
        ),
        patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ),
    ):
        success = await provider.initialize()

    assert success is False


@pytest.mark.asyncio
async def test_create_node_already_exists(provider):
    """Test creating a node that already exists."""

    # Mock that node already exists
    with patch.object(
        provider,
        "_get_file_id_by_path",
        side_effect=[
            MOCK_ROOT_FOLDER_ID,  # Parent exists
            MOCK_FILE_ID,  # Node already exists
        ],
    ):
        node_info = EnhancedNodeInfo(
            name="existing.txt",
            is_dir=False,
            parent_path="/",
        )

        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.create_node(node_info)

        # Should return False for already existing node
        assert result is False


@pytest.mark.asyncio
async def test_create_node_parent_not_found(provider):
    """Test creating a node when parent doesn't exist."""
    # Mock that parent doesn't exist
    with patch.object(provider, "_get_file_id_by_path", return_value=None):
        node_info = EnhancedNodeInfo(
            name="test.txt",
            is_dir=False,
            parent_path="/nonexistent",
        )

        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.create_node(node_info)

        # Should return False when parent not found
        assert result is False


@pytest.mark.asyncio
async def test_delete_node_not_found(provider):
    """Test deleting a node that doesn't exist."""
    # Mock that file doesn't exist
    with patch.object(provider, "_get_file_id_by_path", return_value=None):
        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.delete_node("/nonexistent.txt")

        assert result is False


@pytest.mark.asyncio
async def test_get_node_info_not_found(provider):
    """Test getting node info for non-existent file."""
    # Mock that file doesn't exist
    with patch.object(provider, "_get_file_id_by_path", return_value=None):
        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.get_node_info("/nonexistent.txt")

        assert result is None


@pytest.mark.asyncio
async def test_list_directory_not_found(provider):
    """Test listing a directory that doesn't exist."""
    # Mock that directory doesn't exist
    with patch.object(provider, "_get_file_id_by_path", return_value=None):
        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.list_directory("/nonexistent")

        assert result == []


@pytest.mark.asyncio
async def test_read_file_not_found(provider):
    """Test reading a file that doesn't exist."""
    # Mock that file doesn't exist
    with patch.object(provider, "_get_file_id_by_path", return_value=None):
        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.read_file("/nonexistent.txt")

        assert result is None


@pytest.mark.asyncio
async def test_write_file_parent_not_found(provider):
    """Test writing a file when parent directory doesn't exist."""
    # Mock that file doesn't exist, and parent also doesn't exist
    with patch.object(
        provider,
        "_get_file_id_by_path",
        side_effect=[
            None,  # File doesn't exist
            None,  # Parent doesn't exist either
        ],
    ):
        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.write_file("/nonexistent/test.txt", b"content")

        assert result is False


@pytest.mark.asyncio
async def test_set_metadata_file_not_found(provider):
    """Test setting metadata on non-existent file."""
    # Mock that file doesn't exist
    with patch.object(provider, "_get_file_id_by_path", return_value=None):
        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.set_metadata("/nonexistent.txt", {"key": "value"})

        assert result is False


@pytest.mark.asyncio
async def test_get_metadata_file_not_found(provider):
    """Test getting metadata from non-existent file."""
    # Mock that file doesn't exist
    with patch.object(provider, "_get_file_id_by_path", return_value=None):
        with patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ):
            result = await provider.get_metadata("/nonexistent.txt")

        assert result == {}


@pytest.mark.asyncio
async def test_get_file_id_by_path_not_found(provider):
    """Test getting file ID for a path that doesn't exist in Drive."""
    mock_service = provider.service

    # Mock list response with no files found
    mock_list = MagicMock()
    mock_list.execute.return_value = {"files": []}
    mock_service.files().list.return_value = mock_list

    # Clear cache to force actual lookup
    provider._path_cache.clear()

    with patch(
        "asyncio.to_thread", side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)
    ):
        result = await provider._get_file_id_by_path("/nonexistent/path")

    assert result is None


@pytest.mark.asyncio
async def test_drive_metadata_to_node_info_minimal(provider):
    """Test converting minimal Drive metadata to NodeInfo."""
    metadata = {
        "id": MOCK_FILE_ID,
        "name": "minimal.txt",
        "mimeType": "text/plain",
        "parents": [MOCK_ROOT_FOLDER_ID],
    }

    node_info = provider._drive_metadata_to_node_info(metadata, "/minimal.txt")

    assert node_info.name == "minimal.txt"
    assert node_info.is_dir is False
    assert node_info.size == 0  # Default when not provided
    assert node_info.mime_type == "text/plain"
    assert node_info.session_id is None
    assert node_info.sandbox_id == "default"  # Provider has default sandbox_id


@pytest.mark.asyncio
async def test_close(provider):
    """Test close() method."""
    # Close should complete without error
    await provider.close()

    # Should be able to close multiple times
    await provider.close()


@pytest.mark.asyncio
async def test_exists_true(provider):
    """Test exists() when file does exist."""
    # Mock that file exists
    with (
        patch.object(provider, "_get_file_id_by_path", return_value=MOCK_FILE_ID),
        patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ),
    ):
        result = await provider.exists("/test.txt")

    assert result is True


@pytest.mark.asyncio
async def test_exists_false(provider):
    """Test exists() when file doesn't exist."""
    # Mock that file doesn't exist
    with (
        patch.object(provider, "_get_file_id_by_path", return_value=None),
        patch(
            "asyncio.to_thread",
            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs),
        ),
    ):
        result = await provider.exists("/nonexistent.txt")

    assert result is False
