"""
chuk_virtual_fs/enhanced_node_info.py - Enhanced node information with metadata
"""

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EnhancedNodeInfo:
    """Enhanced node information with rich metadata support"""

    # Core attributes
    name: str
    is_dir: bool
    parent_path: str = "/"

    # Size and content
    size: int = 0
    mime_type: str = "application/octet-stream"

    # Checksums
    sha256: str | None = None
    md5: str | None = None

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    modified_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    accessed_at: str | None = None

    # TTL and expiration
    ttl: int | None = None  # Time to live in seconds
    expires_at: str | None = None

    # Permissions and ownership
    owner: str | None = None
    group: str | None = None
    permissions: str = field(default="644")

    # Session and security
    session_id: str | None = None
    sandbox_id: str | None = None

    # Custom metadata
    custom_meta: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)

    # Provider-specific
    provider: str | None = None
    storage_class: str | None = None

    def __post_init__(self):
        """Post-initialization to set defaults based on is_dir"""
        if self.permissions == "644" and self.is_dir:
            self.permissions = "755"

    def get_path(self) -> str:
        """Get the full path of the node"""
        if self.parent_path == "/":
            return f"/{self.name}" if self.name else "/"
        return f"{self.parent_path}/{self.name}".replace("//", "/")

    def update_modified(self) -> None:
        """Update the modified timestamp"""
        self.modified_at = datetime.utcnow().isoformat() + "Z"

    def update_accessed(self) -> None:
        """Update the accessed timestamp"""
        self.accessed_at = datetime.utcnow().isoformat() + "Z"

    def calculate_expiry(self) -> None:
        """Calculate expiry time based on TTL"""
        if self.ttl:
            expiry = datetime.utcnow().timestamp() + self.ttl
            self.expires_at = datetime.fromtimestamp(expiry).isoformat() + "Z"

    def is_expired(self) -> bool:
        """Check if the node has expired"""
        if not self.expires_at:
            return False
        expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return datetime.utcnow() > expiry.replace(tzinfo=None)

    def calculate_checksums(self, content: bytes) -> None:
        """Calculate checksums for the content"""
        self.sha256 = hashlib.sha256(content).hexdigest()
        self.md5 = hashlib.md5(content, usedforsecurity=False).hexdigest()  # nosec B324
        self.size = len(content)

    def set_mime_type(self, filename: str = None) -> None:
        """Set MIME type based on file extension"""
        if self.is_dir:
            self.mime_type = "inode/directory"
            return

        if not filename:
            filename = self.name

        # Comprehensive MIME type mappings
        mime_map = {
            # Text files
            ".txt": "text/plain",
            ".html": "text/html",
            ".htm": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".xml": "application/xml",
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".yaml": "text/yaml",
            ".yml": "text/yaml",
            ".toml": "text/toml",
            ".ini": "text/plain",
            ".cfg": "text/plain",
            ".conf": "text/plain",
            ".log": "text/plain",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            # Programming languages
            ".py": "text/x-python",
            ".rs": "text/x-rust",
            ".go": "text/x-go",
            ".java": "text/x-java",
            ".c": "text/x-c",
            ".cpp": "text/x-c++",
            ".cc": "text/x-c++",
            ".cxx": "text/x-c++",
            ".h": "text/x-c",
            ".hpp": "text/x-c++",
            ".hh": "text/x-c++",
            ".ts": "text/typescript",
            ".tsx": "text/typescript",
            ".jsx": "text/jsx",
            ".rb": "text/x-ruby",
            ".php": "text/x-php",
            ".sh": "text/x-shellscript",
            ".bash": "text/x-shellscript",
            ".sql": "text/x-sql",
            ".r": "text/x-r",
            ".swift": "text/x-swift",
            ".kt": "text/x-kotlin",
            ".scala": "text/x-scala",
            # Images
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".webp": "image/webp",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".heic": "image/heic",
            ".heif": "image/heif",
            # Documents - Microsoft Office
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".pptm": "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
            ".potx": "application/vnd.openxmlformats-officedocument.presentationml.template",
            ".ppsx": "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
            # Documents - OpenOffice / LibreOffice
            ".odt": "application/vnd.oasis.opendocument.text",
            ".ods": "application/vnd.oasis.opendocument.spreadsheet",
            ".odp": "application/vnd.oasis.opendocument.presentation",
            ".odg": "application/vnd.oasis.opendocument.graphics",
            # PDF and Archives
            ".pdf": "application/pdf",
            ".zip": "application/zip",
            ".rar": "application/x-rar-compressed",
            ".7z": "application/x-7z-compressed",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
            ".bz2": "application/x-bzip2",
            ".xz": "application/x-xz",
            # Audio
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".m4a": "audio/mp4",
            ".wma": "audio/x-ms-wma",
            # Video
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mkv": "video/x-matroska",
            ".mov": "video/quicktime",
            ".wmv": "video/x-ms-wmv",
            ".flv": "video/x-flv",
            ".webm": "video/webm",
            ".m4v": "video/x-m4v",
            ".mpg": "video/mpeg",
            ".mpeg": "video/mpeg",
            # Fonts
            ".ttf": "font/ttf",
            ".otf": "font/otf",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".eot": "application/vnd.ms-fontobject",
            # Other common formats
            ".epub": "application/epub+zip",
            ".mobi": "application/x-mobipocket-ebook",
            ".apk": "application/vnd.android.package-archive",
            ".dmg": "application/x-apple-diskimage",
            ".iso": "application/x-iso9660-image",
            ".exe": "application/x-msdownload",
            ".dll": "application/x-msdownload",
            ".deb": "application/x-debian-package",
            ".rpm": "application/x-rpm",
        }

        # Check for extension match (case-insensitive)
        filename_lower = filename.lower()
        for ext, mime in mime_map.items():
            if filename_lower.endswith(ext):
                self.mime_type = mime
                return

    def detect_mime_from_content(self, content: bytes, max_bytes: int = 8192) -> None:
        """
        Detect MIME type from file content using magic bytes

        Args:
            content: File content as bytes
            max_bytes: Maximum bytes to examine
        """
        if not content:
            return

        sample = content[:max_bytes]

        # Magic byte signatures
        signatures = [
            # Images
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"GIF87a", "image/gif"),
            (b"GIF89a", "image/gif"),
            (b"BM", "image/bmp"),
            (b"RIFF", "image/webp"),  # Also WAV, but need more detection
            # Documents
            (b"%PDF", "application/pdf"),
            (b"PK\x03\x04", "application/zip"),  # Also DOCX, XLSX, PPTX, etc.
            # Microsoft Office (older formats)
            (
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
                "application/msword",
            ),  # DOC, XLS, PPT
            # Audio/Video
            (b"ID3", "audio/mpeg"),  # MP3
            (b"\xff\xfb", "audio/mpeg"),  # MP3
            (b"RIFF", "audio/wav"),
            (b"ftyp", "video/mp4", 4),  # MP4 (signature at offset 4)
            # Archives
            (b"Rar!\x1a\x07", "application/x-rar-compressed"),
            (b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
            (b"\x1f\x8b", "application/gzip"),
        ]

        for sig_data in signatures:
            if len(sig_data) == 2:
                signature, mime_type = sig_data
                offset = 0
            else:
                signature, mime_type, offset = sig_data

            if (
                len(sample) > offset + len(signature)
                and sample[offset : offset + len(signature)] == signature
            ):
                # Special handling for Office Open XML formats
                if signature == b"PK\x03\x04":
                    if b"word/" in content[:max_bytes]:
                        self.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    elif b"xl/" in content[:max_bytes]:
                        self.mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    elif b"ppt/" in content[:max_bytes]:
                        self.mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    else:
                        self.mime_type = mime_type
                else:
                    self.mime_type = mime_type
                return

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnhancedNodeInfo":
        """Create from dictionary representation"""
        return cls(**data)

    @classmethod
    def from_legacy(cls, legacy_info: Any) -> "EnhancedNodeInfo":
        """Create from legacy FSNodeInfo"""
        if hasattr(legacy_info, "to_dict"):
            data = legacy_info.to_dict()
            return cls(
                name=data.get("name", ""),
                is_dir=data.get("is_dir", False),
                parent_path=data.get("parent_path", "/"),
            )
        return cls(
            name=getattr(legacy_info, "name", ""),
            is_dir=getattr(legacy_info, "is_dir", False),
            parent_path=getattr(legacy_info, "parent_path", "/"),
        )

    def __str__(self) -> str:
        """String representation"""
        type_str = "DIR" if self.is_dir else "FILE"
        return f"[{type_str}] {self.get_path()} ({self.size} bytes)"


# Backwards compatibility alias
FSNodeInfo = EnhancedNodeInfo
