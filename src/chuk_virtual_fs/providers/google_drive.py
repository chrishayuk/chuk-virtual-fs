"""Google Drive storage provider for chuk-virtual-fs.

Stores files in user's Google Drive under CHUK/ folder.
Requires Google OAuth2 credentials.
"""

import asyncio
import contextlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider


class GoogleDriveProvider(AsyncStorageProvider):
    """Google Drive storage provider.

    Stores files in user's Google Drive under /CHUK/ directory.
    Uses Google Drive API v3 for all operations.

    Features:
    - User owns data (stored in their Google Drive)
    - Natural discoverability (visible in Drive UI)
    - Built-in sharing (use Drive's share features)
    - No infrastructure cost for provider

    Directory Structure:
        /CHUK/                          # Root CHUK folder
        /CHUK/stage/                    # chuk-mcp-stage scenes
        /CHUK/stage/scene-123/          # Individual scene
        /CHUK/stage/scene-123/scene.json
        /CHUK/artifacts/                # chuk-artifacts workspaces

    Metadata Storage:
        - File metadata stored in Drive's properties (key-value pairs)
        - Custom metadata in 'appProperties' (app-specific)
        - Tags stored as JSON in appProperties['tags']
    """

    # Google Drive folder MIME type
    FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

    # CHUK root folder name in Drive
    CHUK_ROOT_FOLDER = "CHUK"

    def __init__(
        self,
        credentials: Credentials | dict | None = None,
        root_folder: str = "CHUK",
        cache_ttl: int = 60,
        session_id: str | None = None,
        sandbox_id: str | None = None,
    ):
        """Initialize Google Drive provider.

        Args:
            credentials: Google OAuth2 credentials (Credentials object or dict)
            root_folder: Name of root folder in Drive (default: "CHUK")
            cache_ttl: Cache TTL in seconds (default: 60)
            session_id: Optional session ID for tracking
            sandbox_id: Optional sandbox ID for namespacing
        """
        super().__init__()
        self.root_folder = root_folder
        self.cache_ttl = cache_ttl
        self.session_id = session_id
        self.sandbox_id = sandbox_id or "default"

        # Initialize credentials
        if isinstance(credentials, dict):
            self.credentials = Credentials.from_authorized_user_info(credentials)
        else:
            self.credentials = credentials

        # Google Drive service (initialized in initialize())
        self.service: Any = None

        # Cache: path -> (file_id, timestamp)
        self._path_cache: dict[str, tuple[str | None, float]] = {}

        # Cache: file_id -> EnhancedNodeInfo
        self._node_cache: dict[str, tuple[EnhancedNodeInfo, float]] = {}

        # Root folder ID (set in initialize())
        self._root_folder_id: str | None = None

        # Statistics
        self._stats = {
            "reads": 0,
            "writes": 0,
            "deletes": 0,
            "creates": 0,
            "api_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    async def initialize(self) -> bool:
        """Initialize Google Drive connection and create root folder.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Refresh credentials if needed
            if (
                self.credentials
                and self.credentials.expired
                and self.credentials.refresh_token
            ):
                await asyncio.to_thread(self.credentials.refresh, Request())

            # Build Drive service
            self.service = await asyncio.to_thread(
                build, "drive", "v3", credentials=self.credentials
            )

            # Get or create CHUK root folder
            self._root_folder_id = await self._get_or_create_root_folder()

            return True

        except Exception as e:
            print(f"Failed to initialize Google Drive provider: {e}")
            return False

    async def close(self) -> None:
        """Close Google Drive connection and cleanup resources."""
        self._path_cache.clear()
        self._node_cache.clear()
        self.service = None
        self._root_folder_id = None

    async def _get_or_create_root_folder(self) -> str:
        """Get or create the CHUK root folder in Drive.

        Returns:
            File ID of root folder
        """
        # Search for existing CHUK folder in root
        query = (
            f"name='{self.root_folder}' and "
            f"mimeType='{self.FOLDER_MIME_TYPE}' and "
            "'root' in parents and "
            "trashed=false"
        )

        try:
            results = await asyncio.to_thread(
                self.service.files()
                .list(q=query, spaces="drive", fields="files(id, name)")
                .execute
            )
            self._stats["api_calls"] += 1

            files = results.get("files", [])
            if files:
                return files[0]["id"]  # type: ignore[no-any-return]

            # Create root folder
            folder_metadata = {
                "name": self.root_folder,
                "mimeType": self.FOLDER_MIME_TYPE,
                "parents": ["root"],
            }

            folder = await asyncio.to_thread(
                self.service.files().create(body=folder_metadata, fields="id").execute
            )
            self._stats["api_calls"] += 1

            return folder["id"]  # type: ignore[no-any-return]

        except HttpError as e:
            raise RuntimeError(f"Failed to get/create root folder: {e}")

    def _normalize_path(self, path: str) -> str:
        """Normalize VFS path to standard format.

        Args:
            path: VFS path

        Returns:
            Normalized path (absolute, no trailing slash except root)
        """
        # Ensure absolute path
        if not path.startswith("/"):
            path = "/" + path

        # Remove trailing slash unless root
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        return path

    def _split_path(self, path: str) -> list[str]:
        """Split path into components.

        Args:
            path: Normalized VFS path

        Returns:
            List of path components (excluding root /)
        """
        path = self._normalize_path(path)
        if path == "/":
            return []
        return [p for p in path.split("/") if p]

    async def _get_file_id_by_path(self, path: str) -> str | None:
        """Get Google Drive file ID from VFS path.

        Uses caching to reduce API calls.

        Args:
            path: VFS path

        Returns:
            File ID or None if not found
        """
        path = self._normalize_path(path)

        # Check cache
        if path in self._path_cache:
            file_id, timestamp = self._path_cache[path]
            if (asyncio.get_event_loop().time() - timestamp) < self.cache_ttl:
                self._stats["cache_hits"] += 1
                return file_id
            else:
                # Cache expired
                del self._path_cache[path]

        self._stats["cache_misses"] += 1

        # Root path
        if path == "/":
            self._path_cache[path] = (
                self._root_folder_id,
                asyncio.get_event_loop().time(),
            )
            return self._root_folder_id

        # Walk path from root
        components = self._split_path(path)
        current_parent_id = self._root_folder_id

        for component in components:
            # Search for child in current parent
            query = (
                f"name='{component}' and "
                f"'{current_parent_id}' in parents and "
                "trashed=false"
            )

            try:
                results = await asyncio.to_thread(
                    self.service.files()
                    .list(q=query, spaces="drive", fields="files(id, name)")
                    .execute
                )
                self._stats["api_calls"] += 1

                files = results.get("files", [])
                if not files:
                    return None

                current_parent_id = files[0]["id"]

            except HttpError:
                return None

        # Cache the result
        self._path_cache[path] = (current_parent_id, asyncio.get_event_loop().time())
        return current_parent_id

    async def _get_file_metadata(self, file_id: str) -> dict | None:
        """Get file metadata from Drive.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata dict or None if not found
        """
        try:
            fields = (
                "id, name, mimeType, size, createdTime, modifiedTime, "
                "md5Checksum, parents, appProperties, properties"
            )

            metadata = await asyncio.to_thread(
                self.service.files().get(fileId=file_id, fields=fields).execute
            )
            self._stats["api_calls"] += 1

            return metadata  # type: ignore[no-any-return]

        except HttpError:
            return None

    def _drive_metadata_to_node_info(
        self, metadata: dict, path: str
    ) -> EnhancedNodeInfo:
        """Convert Drive metadata to EnhancedNodeInfo.

        Args:
            metadata: Drive file metadata
            path: VFS path

        Returns:
            EnhancedNodeInfo object
        """
        is_dir = metadata["mimeType"] == self.FOLDER_MIME_TYPE
        name = metadata["name"]
        parent_path = str(Path(path).parent) if path != "/" else "/"

        # Parse timestamps
        created_at = metadata.get("createdTime", datetime.now(UTC).isoformat())
        modified_at = metadata.get("modifiedTime", datetime.now(UTC).isoformat())

        # Get custom metadata from appProperties
        app_props = metadata.get("appProperties", {})
        custom_meta = {}
        tags = {}

        if "custom_meta" in app_props:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                custom_meta = json.loads(app_props["custom_meta"])

        if "tags" in app_props:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                tags = json.loads(app_props["tags"])

        # Session and sandbox from appProperties
        session_id = app_props.get("session_id", self.session_id)
        sandbox_id = app_props.get("sandbox_id", self.sandbox_id)

        # TTL from appProperties
        ttl = None
        if "ttl" in app_props:
            with contextlib.suppress(ValueError, TypeError):
                ttl = int(app_props["ttl"])

        node_info = EnhancedNodeInfo(
            name=name,
            is_dir=is_dir,
            parent_path=parent_path,
            size=int(metadata.get("size", 0)) if not is_dir else 0,
            mime_type=metadata.get("mimeType", "application/octet-stream"),
            md5=metadata.get("md5Checksum"),
            created_at=created_at,
            modified_at=modified_at,
            session_id=session_id,
            sandbox_id=sandbox_id,
            custom_meta=custom_meta,
            tags=tags,
            ttl=ttl,
            provider="google_drive",
        )

        return node_info

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a file or directory node.

        Args:
            node_info: Node information

        Returns:
            True if created successfully
        """
        async with self._lock:
            try:
                path = node_info.get_path()
                parent_path = node_info.parent_path

                # Get parent folder ID
                parent_id = await self._get_file_id_by_path(parent_path)
                if not parent_id:
                    print(f"Parent path not found: {parent_path}")
                    return False

                # Check if already exists
                existing_id = await self._get_file_id_by_path(path)
                if existing_id:
                    print(f"Node already exists: {path}")
                    return False

                # Prepare metadata
                file_metadata: dict[str, Any] = {
                    "name": node_info.name,
                    "parents": [parent_id],
                }

                if node_info.is_dir:
                    file_metadata["mimeType"] = self.FOLDER_MIME_TYPE

                # Add app properties (custom metadata)
                app_properties = {}
                if node_info.session_id:
                    app_properties["session_id"] = node_info.session_id
                if node_info.sandbox_id:
                    app_properties["sandbox_id"] = node_info.sandbox_id
                if node_info.custom_meta:
                    app_properties["custom_meta"] = json.dumps(node_info.custom_meta)
                if node_info.tags:
                    app_properties["tags"] = json.dumps(node_info.tags)
                if node_info.ttl:
                    app_properties["ttl"] = str(node_info.ttl)

                if app_properties:
                    file_metadata["appProperties"] = app_properties

                # Create node
                created_file = await asyncio.to_thread(
                    self.service.files().create(body=file_metadata, fields="id").execute
                )
                self._stats["api_calls"] += 1
                self._stats["creates"] += 1

                # Cache the new file ID
                file_id = created_file["id"]
                self._path_cache[path] = (file_id, asyncio.get_event_loop().time())

                return True

            except HttpError as e:
                print(f"Failed to create node {node_info.get_path()}: {e}")
                return False

    async def delete_node(self, path: str) -> bool:
        """Delete a file or directory node.

        Args:
            path: VFS path to delete

        Returns:
            True if deleted successfully
        """
        async with self._lock:
            try:
                path = self._normalize_path(path)

                # Can't delete root
                if path == "/":
                    return False

                # Get file ID
                file_id = await self._get_file_id_by_path(path)
                if not file_id:
                    return False

                # Delete (move to trash)
                await asyncio.to_thread(
                    self.service.files().delete(fileId=file_id).execute
                )
                self._stats["api_calls"] += 1
                self._stats["deletes"] += 1

                # Clear from cache
                if path in self._path_cache:
                    del self._path_cache[path]
                if file_id in self._node_cache:
                    del self._node_cache[file_id]

                return True

            except HttpError as e:
                print(f"Failed to delete node {path}: {e}")
                return False

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get node information.

        Args:
            path: VFS path

        Returns:
            EnhancedNodeInfo or None if not found
        """
        path = self._normalize_path(path)

        # Get file ID
        file_id = await self._get_file_id_by_path(path)
        if not file_id:
            return None

        # Check node cache
        if file_id in self._node_cache:
            node_info, timestamp = self._node_cache[file_id]
            if (asyncio.get_event_loop().time() - timestamp) < self.cache_ttl:
                self._stats["cache_hits"] += 1
                return node_info
            else:
                del self._node_cache[file_id]

        self._stats["cache_misses"] += 1

        # Get metadata from Drive
        metadata = await self._get_file_metadata(file_id)
        if not metadata:
            return None

        # Convert to NodeInfo
        node_info = self._drive_metadata_to_node_info(metadata, path)

        # Cache it
        self._node_cache[file_id] = (node_info, asyncio.get_event_loop().time())

        return node_info

    async def list_directory(self, path: str) -> list[str]:
        """List directory contents (direct children only).

        Args:
            path: VFS path to directory

        Returns:
            List of child names (sorted)
        """
        path = self._normalize_path(path)

        # Get folder ID
        folder_id = await self._get_file_id_by_path(path)
        if not folder_id:
            return []

        try:
            # Query for direct children
            query = f"'{folder_id}' in parents and trashed=false"

            results = await asyncio.to_thread(
                self.service.files()
                .list(q=query, spaces="drive", fields="files(name)", orderBy="name")
                .execute
            )
            self._stats["api_calls"] += 1

            files = results.get("files", [])
            # Type cast needed due to dict access - API returns list[dict[str, Any]]
            return sorted([cast(str, f["name"]) for f in files])

        except HttpError as e:
            print(f"Failed to list directory {path}: {e}")
            return []

    async def write_file(self, path: str, content: bytes) -> bool:
        """Write file content.

        Args:
            path: VFS path
            content: File content bytes

        Returns:
            True if written successfully
        """
        async with self._lock:
            try:
                path = self._normalize_path(path)

                # Get or create file
                file_id = await self._get_file_id_by_path(path)

                if file_id:
                    # Update existing file
                    media = MediaIoBaseUpload(
                        io.BytesIO(content),
                        mimetype="application/octet-stream",
                        resumable=True,
                    )

                    await asyncio.to_thread(
                        self.service.files()
                        .update(fileId=file_id, media_body=media)
                        .execute
                    )
                    self._stats["api_calls"] += 1

                else:
                    # Create new file
                    parent_path = str(Path(path).parent)
                    name = Path(path).name

                    parent_id = await self._get_file_id_by_path(parent_path)
                    if not parent_id:
                        print(f"Parent path not found: {parent_path}")
                        return False

                    file_metadata = {
                        "name": name,
                        "parents": [parent_id],
                    }

                    media = MediaIoBaseUpload(
                        io.BytesIO(content),
                        mimetype="application/octet-stream",
                        resumable=True,
                    )

                    created_file = await asyncio.to_thread(
                        self.service.files()
                        .create(body=file_metadata, media_body=media, fields="id")
                        .execute
                    )
                    self._stats["api_calls"] += 1

                    file_id = created_file["id"]
                    self._path_cache[path] = (file_id, asyncio.get_event_loop().time())

                self._stats["writes"] += 1

                # Clear node cache for this file
                if file_id in self._node_cache:
                    del self._node_cache[file_id]

                return True

            except HttpError as e:
                print(f"Failed to write file {path}: {e}")
                return False

    async def read_file(self, path: str) -> bytes | None:
        """Read file content.

        Args:
            path: VFS path

        Returns:
            File content bytes or None if not found
        """
        path = self._normalize_path(path)

        # Get file ID
        file_id = await self._get_file_id_by_path(path)
        if not file_id:
            return None

        try:
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                status, done = await asyncio.to_thread(downloader.next_chunk)

            self._stats["api_calls"] += 1
            self._stats["reads"] += 1

            return file_buffer.getvalue()

        except HttpError as e:
            print(f"Failed to read file {path}: {e}")
            return None

    async def exists(self, path: str) -> bool:
        """Check if path exists.

        Args:
            path: VFS path

        Returns:
            True if exists
        """
        file_id = await self._get_file_id_by_path(path)
        return file_id is not None

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get custom metadata for a path.

        Args:
            path: VFS path

        Returns:
            Custom metadata dict
        """
        node_info = await self.get_node_info(path)
        if not node_info:
            return {}
        return node_info.custom_meta

    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set custom metadata for a path.

        Args:
            path: VFS path
            metadata: Custom metadata dict

        Returns:
            True if set successfully
        """
        async with self._lock:
            try:
                file_id = await self._get_file_id_by_path(path)
                if not file_id:
                    return False

                # Update appProperties
                file_metadata = {
                    "appProperties": {
                        "custom_meta": json.dumps(metadata),
                    }
                }

                await asyncio.to_thread(
                    self.service.files()
                    .update(fileId=file_id, body=file_metadata)
                    .execute
                )
                self._stats["api_calls"] += 1

                # Clear cache
                if file_id in self._node_cache:
                    del self._node_cache[file_id]

                return True

            except HttpError as e:
                print(f"Failed to set metadata for {path}: {e}")
                return False

    async def get_storage_stats(self) -> dict:
        """Get storage statistics.

        Returns:
            Statistics dict
        """
        # Calculate totals by walking the tree
        # This is expensive, so we return cached stats mostly
        return {
            "provider": "google_drive",
            "root_folder": self.root_folder,
            "session_id": self.session_id,
            "sandbox_id": self.sandbox_id,
            "operations": {
                "reads": self._stats["reads"],
                "writes": self._stats["writes"],
                "creates": self._stats["creates"],
                "deletes": self._stats["deletes"],
                "api_calls": self._stats["api_calls"],
            },
            "cache": {
                "hits": self._stats["cache_hits"],
                "misses": self._stats["cache_misses"],
                "path_cache_size": len(self._path_cache),
                "node_cache_size": len(self._node_cache),
            },
        }

    async def cleanup(self) -> dict:
        """Cleanup expired nodes and temp files.

        Returns:
            Cleanup statistics
        """
        # Could implement TTL-based cleanup here
        # For now, just clear caches
        cleared_paths = len(self._path_cache)
        cleared_nodes = len(self._node_cache)

        self._path_cache.clear()
        self._node_cache.clear()

        return {
            "cache_cleared": True,
            "path_cache_entries_cleared": cleared_paths,
            "node_cache_entries_cleared": cleared_nodes,
        }
