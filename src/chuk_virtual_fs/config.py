"""
chuk_virtual_fs/config.py - Configuration management for virtual filesystem
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """Storage provider configuration"""

    provider: str = "memory"

    # S3/AWS configuration
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "vfs-artifacts"
    s3_prefix: str = ""
    s3_signature_version: str = "s3v4"

    # Filesystem configuration
    fs_root: str = "./vfs-data"

    # E2B configuration
    e2b_api_key: str | None = None
    e2b_sandbox_id: str | None = None

    # Google Drive configuration
    google_drive_credentials: dict[str, Any] | None = None
    google_drive_root_folder: str = "CHUK"
    google_drive_cache_ttl: int = 60

    # Provider-specific settings
    provider_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionConfig:
    """Session management configuration"""

    enabled: bool = True
    default_ttl: int = 3600  # 1 hour
    max_sessions: int = 1000
    cleanup_interval: int = 300  # 5 minutes
    default_access_level: str = "read_write"

    # Session provider (memory, redis)
    session_provider: str = "memory"
    redis_url: str | None = None
    redis_ttl: int = 3600


@dataclass
class PerformanceConfig:
    """Performance and optimization configuration"""

    async_enabled: bool = True
    max_concurrent_operations: int = 10
    batch_chunk_size: int = 100
    cache_enabled: bool = True
    cache_ttl: int = 300  # 5 minutes
    cache_max_size: int = 1000

    # Retry configuration
    retry_enabled: bool = True
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_exponential_base: float = 2.0
    retry_jitter: bool = True


@dataclass
class SecurityConfig:
    """Security configuration"""

    enable_access_control: bool = True
    enable_audit_logging: bool = False
    enable_encryption: bool = False

    # Path restrictions
    allowed_root_paths: list[str] = field(default_factory=lambda: ["/"])
    denied_paths: list[str] = field(
        default_factory=lambda: ["/etc/passwd", "/etc/shadow"]
    )

    # File restrictions
    max_file_size_mb: int = 100
    allowed_mime_types: list[str] = field(default_factory=list)
    denied_mime_types: list[str] = field(
        default_factory=lambda: ["application/x-executable"]
    )

    # Session restrictions
    require_session_for_write: bool = True
    require_session_for_delete: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str | None = None
    console: bool = True

    # Component-specific logging levels
    component_levels: dict[str, str] = field(default_factory=dict)


@dataclass
class VirtualFSConfig:
    """Complete virtual filesystem configuration"""

    storage: StorageConfig = field(default_factory=StorageConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Grid architecture settings
    enable_grid: bool = False
    grid_sandbox_id: str = "default"
    grid_prefix: str = "grid"

    # Global settings
    debug: bool = False
    environment: str = "development"  # development, staging, production

    @classmethod
    def from_env(cls) -> "VirtualFSConfig":
        """Create configuration from environment variables"""
        config = cls()

        # Storage configuration
        config.storage.provider = os.getenv("VFS_PROVIDER", "memory")
        config.storage.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        config.storage.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        config.storage.aws_region = os.getenv("AWS_REGION", "us-east-1")
        config.storage.s3_endpoint_url = os.getenv("S3_ENDPOINT_URL")
        config.storage.s3_bucket = os.getenv("VFS_BUCKET", "vfs-artifacts")
        config.storage.s3_prefix = os.getenv("VFS_S3_PREFIX", "")
        config.storage.fs_root = os.getenv("VFS_FS_ROOT", "./vfs-data")
        config.storage.e2b_api_key = os.getenv("E2B_API_KEY")
        config.storage.e2b_sandbox_id = os.getenv("E2B_SANDBOX_ID")

        # Session configuration
        config.session.enabled = (
            os.getenv("VFS_SESSION_ENABLED", "true").lower() == "true"
        )
        config.session.default_ttl = int(os.getenv("VFS_SESSION_TTL", "3600"))
        config.session.max_sessions = int(os.getenv("VFS_MAX_SESSIONS", "1000"))
        config.session.session_provider = os.getenv("VFS_SESSION_PROVIDER", "memory")
        config.session.redis_url = os.getenv("VFS_REDIS_URL")

        # Performance configuration
        config.performance.async_enabled = (
            os.getenv("VFS_ASYNC", "true").lower() == "true"
        )
        config.performance.max_concurrent_operations = int(
            os.getenv("VFS_MAX_CONCURRENT", "10")
        )
        config.performance.batch_chunk_size = int(os.getenv("VFS_BATCH_SIZE", "100"))
        config.performance.cache_enabled = (
            os.getenv("VFS_CACHE_ENABLED", "true").lower() == "true"
        )
        config.performance.cache_ttl = int(os.getenv("VFS_CACHE_TTL", "300"))
        config.performance.retry_enabled = (
            os.getenv("VFS_RETRY_ENABLED", "true").lower() == "true"
        )
        config.performance.retry_max_attempts = int(os.getenv("VFS_RETRY_MAX", "3"))

        # Security configuration
        config.security.enable_access_control = (
            os.getenv("VFS_ACCESS_CONTROL", "true").lower() == "true"
        )
        config.security.enable_audit_logging = (
            os.getenv("VFS_AUDIT_LOG", "false").lower() == "true"
        )
        config.security.max_file_size_mb = int(os.getenv("VFS_MAX_FILE_SIZE_MB", "100"))

        # Grid configuration
        config.enable_grid = os.getenv("VFS_ENABLE_GRID", "false").lower() == "true"
        config.grid_sandbox_id = os.getenv("VFS_SANDBOX_ID", "default")
        config.grid_prefix = os.getenv("VFS_GRID_PREFIX", "grid")

        # Global settings
        config.debug = os.getenv("VFS_DEBUG", "false").lower() == "true"
        config.environment = os.getenv("VFS_ENVIRONMENT", "development")

        # Logging configuration
        config.logging.level = os.getenv("VFS_LOG_LEVEL", "INFO")
        config.logging.file = os.getenv("VFS_LOG_FILE")
        config.logging.console = os.getenv("VFS_LOG_CONSOLE", "true").lower() == "true"

        return config

    @classmethod
    def from_file(cls, path: str) -> "VirtualFSConfig":
        """Load configuration from JSON or YAML file"""
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        if file_path.suffix in [".yaml", ".yml"]:
            try:
                import yaml

                with open(file_path) as f:
                    data = yaml.safe_load(f)
            except ImportError:
                raise ImportError(
                    "PyYAML is required to load YAML configuration files"
                ) from None
        elif file_path.suffix == ".json":
            with open(file_path) as f:
                data = json.load(f)
        else:
            raise ValueError(
                f"Unsupported configuration file format: {file_path.suffix}"
            )

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VirtualFSConfig":
        """Create configuration from dictionary"""
        config = cls()

        # Update storage config
        if "storage" in data:
            for key, value in data["storage"].items():
                if hasattr(config.storage, key):
                    setattr(config.storage, key, value)

        # Update session config
        if "session" in data:
            for key, value in data["session"].items():
                if hasattr(config.session, key):
                    setattr(config.session, key, value)

        # Update performance config
        if "performance" in data:
            for key, value in data["performance"].items():
                if hasattr(config.performance, key):
                    setattr(config.performance, key, value)

        # Update security config
        if "security" in data:
            for key, value in data["security"].items():
                if hasattr(config.security, key):
                    setattr(config.security, key, value)

        # Update logging config
        if "logging" in data:
            for key, value in data["logging"].items():
                if hasattr(config.logging, key):
                    setattr(config.logging, key, value)

        # Update global settings
        for key in [
            "enable_grid",
            "grid_sandbox_id",
            "grid_prefix",
            "debug",
            "environment",
        ]:
            if key in data:
                setattr(config, key, data[key])

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "storage": asdict(self.storage),
            "session": asdict(self.session),
            "performance": asdict(self.performance),
            "security": asdict(self.security),
            "logging": asdict(self.logging),
            "enable_grid": self.enable_grid,
            "grid_sandbox_id": self.grid_sandbox_id,
            "grid_prefix": self.grid_prefix,
            "debug": self.debug,
            "environment": self.environment,
        }

    def save(self, path: str) -> None:
        """Save configuration to file"""
        file_path = Path(path)
        data = self.to_dict()

        if file_path.suffix in [".yaml", ".yml"]:
            try:
                import yaml

                with open(file_path, "w") as f:
                    yaml.safe_dump(data, f, default_flow_style=False)
            except ImportError:
                raise ImportError(
                    "PyYAML is required to save YAML configuration files"
                ) from None
        else:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

    def setup_logging(self) -> None:
        """Setup logging based on configuration"""
        # Set root logger level
        logging.basicConfig(
            level=getattr(logging, self.logging.level.upper()),
            format=self.logging.format,
        )

        # Add file handler if specified
        if self.logging.file:
            file_handler = logging.FileHandler(self.logging.file)
            file_handler.setFormatter(logging.Formatter(self.logging.format))
            logging.getLogger().addHandler(file_handler)

        # Set component-specific levels
        for component, level in self.logging.component_levels.items():
            logging.getLogger(component).setLevel(getattr(logging, level.upper()))

        # Set console output
        if not self.logging.console:
            # Remove console handler
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.StreamHandler):
                    logging.getLogger().removeHandler(handler)

    def validate(self) -> list[str]:
        """Validate configuration and return list of warnings"""
        warnings = []

        # Check storage provider
        valid_providers = ["memory", "s3", "filesystem", "e2b", "sqlite"]
        if self.storage.provider not in valid_providers:
            warnings.append(f"Unknown storage provider: {self.storage.provider}")

        # Check S3 configuration
        if (
            self.storage.provider == "s3"
            and not self.storage.aws_access_key_id
            and not os.getenv("AWS_ACCESS_KEY_ID")
        ):
            warnings.append("S3 provider selected but AWS credentials not configured")

        # Check filesystem configuration
        if self.storage.provider == "filesystem":
            fs_root = Path(self.storage.fs_root)
            if not fs_root.exists():
                warnings.append(
                    f"Filesystem root does not exist: {self.storage.fs_root}"
                )

        # Check session configuration
        if self.session.session_provider == "redis" and not self.session.redis_url:
            warnings.append(
                "Redis session provider selected but redis_url not configured"
            )

        # Check performance settings
        if self.performance.max_concurrent_operations < 1:
            warnings.append("max_concurrent_operations should be at least 1")

        if self.performance.batch_chunk_size < 1:
            warnings.append("batch_chunk_size should be at least 1")

        # Check security settings
        if self.security.max_file_size_mb < 1:
            warnings.append("max_file_size_mb should be at least 1")

        return warnings


# Global configuration instance
_config: VirtualFSConfig | None = None


def get_config() -> VirtualFSConfig:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = VirtualFSConfig.from_env()
    return _config


def set_config(config: VirtualFSConfig) -> None:
    """Set the global configuration instance"""
    global _config
    _config = config


def load_config(path: str | None = None) -> VirtualFSConfig:
    """
    Load configuration from file or environment

    Args:
        path: Optional path to configuration file

    Returns:
        Loaded configuration
    """
    if path:
        config = VirtualFSConfig.from_file(path)
    else:
        # Try to load from default locations
        default_paths = [
            "./vfs-config.yaml",
            "./vfs-config.yml",
            "./vfs-config.json",
            "~/.vfs/config.yaml",
            "~/.vfs/config.json",
            "/etc/vfs/config.yaml",
            "/etc/vfs/config.json",
        ]

        config = None
        for default_path in default_paths:
            expanded_path = Path(default_path).expanduser()
            if expanded_path.exists():
                config = VirtualFSConfig.from_file(str(expanded_path))
                logger.info(f"Loaded configuration from: {expanded_path}")
                break

        if not config:
            # Fall back to environment variables
            config = VirtualFSConfig.from_env()
            logger.info("Loaded configuration from environment variables")

    # At this point config is guaranteed to be set
    if config is None:
        raise RuntimeError("Failed to load configuration from any source")

    # Setup logging
    config.setup_logging()

    # Validate configuration
    warnings = config.validate()
    for warning in warnings:
        logger.warning(f"Configuration warning: {warning}")

    # Set as global config
    set_config(config)

    return config
