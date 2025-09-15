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
        self.md5 = hashlib.md5(content).hexdigest()
        self.size = len(content)

    def set_mime_type(self, filename: str = None) -> None:
        """Set MIME type based on file extension"""
        if self.is_dir:
            self.mime_type = "inode/directory"
            return

        if not filename:
            filename = self.name

        # Common MIME type mappings
        mime_map = {
            ".txt": "text/plain",
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".xml": "application/xml",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
            ".zip": "application/zip",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
            ".mp3": "audio/mpeg",
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".py": "text/x-python",
            ".rs": "text/x-rust",
            ".go": "text/x-go",
            ".java": "text/x-java",
            ".c": "text/x-c",
            ".cpp": "text/x-c++",
            ".h": "text/x-c",
            ".hpp": "text/x-c++",
            ".md": "text/markdown",
            ".yaml": "text/yaml",
            ".yml": "text/yaml",
            ".toml": "text/toml",
        }

        for ext, mime in mime_map.items():
            if filename.lower().endswith(ext):
                self.mime_type = mime
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
