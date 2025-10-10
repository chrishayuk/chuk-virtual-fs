"""
Tests for config.py - Configuration management
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from chuk_virtual_fs.config import (
    LoggingConfig,
    PerformanceConfig,
    SecurityConfig,
    SessionConfig,
    StorageConfig,
    VirtualFSConfig,
    get_config,
    load_config,
    set_config,
)


class TestDataclasses:
    """Test configuration dataclasses"""

    def test_storage_config_defaults(self):
        """Test StorageConfig default values"""
        config = StorageConfig()
        assert config.provider == "memory"
        assert config.aws_region == "us-east-1"
        assert config.s3_bucket == "vfs-artifacts"
        assert config.fs_root == "./vfs-data"

    def test_session_config_defaults(self):
        """Test SessionConfig default values"""
        config = SessionConfig()
        assert config.enabled is True
        assert config.default_ttl == 3600
        assert config.max_sessions == 1000
        assert config.session_provider == "memory"

    def test_performance_config_defaults(self):
        """Test PerformanceConfig default values"""
        config = PerformanceConfig()
        assert config.async_enabled is True
        assert config.max_concurrent_operations == 10
        assert config.batch_chunk_size == 100
        assert config.retry_enabled is True

    def test_security_config_defaults(self):
        """Test SecurityConfig default values"""
        config = SecurityConfig()
        assert config.enable_access_control is True
        assert config.enable_audit_logging is False
        assert config.max_file_size_mb == 100
        assert "/etc/passwd" in config.denied_paths

    def test_logging_config_defaults(self):
        """Test LoggingConfig default values"""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.console is True
        assert config.file is None


class TestVirtualFSConfig:
    """Test VirtualFSConfig"""

    def test_default_initialization(self):
        """Test default VirtualFSConfig initialization"""
        config = VirtualFSConfig()
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.session, SessionConfig)
        assert isinstance(config.performance, PerformanceConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert config.debug is False
        assert config.environment == "development"

    def test_from_env(self):
        """Test creating config from environment variables"""
        env_vars = {
            "VFS_PROVIDER": "s3",
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_REGION": "us-west-2",
            "VFS_BUCKET": "test-bucket",
            "VFS_SESSION_ENABLED": "false",
            "VFS_SESSION_TTL": "7200",
            "VFS_MAX_CONCURRENT": "20",
            "VFS_BATCH_SIZE": "50",
            "VFS_CACHE_ENABLED": "false",
            "VFS_RETRY_MAX": "5",
            "VFS_ACCESS_CONTROL": "false",
            "VFS_MAX_FILE_SIZE_MB": "200",
            "VFS_DEBUG": "true",
            "VFS_ENVIRONMENT": "production",
            "VFS_LOG_LEVEL": "DEBUG",
            "VFS_LOG_CONSOLE": "false",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = VirtualFSConfig.from_env()

        assert config.storage.provider == "s3"
        assert config.storage.aws_access_key_id == "test-key"
        assert config.storage.aws_region == "us-west-2"
        assert config.storage.s3_bucket == "test-bucket"
        assert config.session.enabled is False
        assert config.session.default_ttl == 7200
        assert config.performance.max_concurrent_operations == 20
        assert config.performance.batch_chunk_size == 50
        assert config.performance.cache_enabled is False
        assert config.performance.retry_max_attempts == 5
        assert config.security.enable_access_control is False
        assert config.security.max_file_size_mb == 200
        assert config.debug is True
        assert config.environment == "production"
        assert config.logging.level == "DEBUG"
        assert config.logging.console is False

    def test_to_dict(self):
        """Test converting config to dictionary"""
        config = VirtualFSConfig()
        config.debug = True
        config.environment = "test"

        data = config.to_dict()

        assert "storage" in data
        assert "session" in data
        assert "performance" in data
        assert "security" in data
        assert "logging" in data
        assert data["debug"] is True
        assert data["environment"] == "test"
        assert data["storage"]["provider"] == "memory"

    def test_from_dict(self):
        """Test creating config from dictionary"""
        data = {
            "storage": {
                "provider": "filesystem",
                "fs_root": "/custom/path",
            },
            "session": {
                "enabled": False,
                "default_ttl": 1800,
            },
            "performance": {
                "max_concurrent_operations": 15,
                "retry_enabled": False,
            },
            "security": {
                "max_file_size_mb": 50,
            },
            "logging": {
                "level": "WARNING",
            },
            "debug": True,
            "environment": "staging",
        }

        config = VirtualFSConfig.from_dict(data)

        assert config.storage.provider == "filesystem"
        assert config.storage.fs_root == "/custom/path"
        assert config.session.enabled is False
        assert config.session.default_ttl == 1800
        assert config.performance.max_concurrent_operations == 15
        assert config.performance.retry_enabled is False
        assert config.security.max_file_size_mb == 50
        assert config.logging.level == "WARNING"
        assert config.debug is True
        assert config.environment == "staging"

    def test_from_file_json(self):
        """Test loading configuration from JSON file"""
        config_data = {
            "storage": {"provider": "memory"},
            "debug": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = VirtualFSConfig.from_file(temp_path)
            assert config.storage.provider == "memory"
            assert config.debug is True
        finally:
            os.unlink(temp_path)

    def test_from_file_not_found(self):
        """Test loading from non-existent file"""
        with pytest.raises(FileNotFoundError):
            VirtualFSConfig.from_file("/nonexistent/config.json")

    def test_from_file_unsupported_format(self):
        """Test loading from unsupported file format"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("invalid")
            temp_path = f.name

        try:
            with pytest.raises(
                ValueError, match="Unsupported configuration file format"
            ):
                VirtualFSConfig.from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_save_json(self):
        """Test saving configuration to JSON file"""
        config = VirtualFSConfig()
        config.debug = True

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            config.save(temp_path)

            # Load and verify
            with open(temp_path) as f:
                data = json.load(f)

            assert data["debug"] is True
            assert "storage" in data
        finally:
            os.unlink(temp_path)

    def test_validate_valid_config(self):
        """Test validation of valid configuration"""
        config = VirtualFSConfig()
        warnings = config.validate()
        assert isinstance(warnings, list)
        # Memory provider is valid, should have no warnings
        assert len(warnings) == 0

    def test_validate_invalid_provider(self):
        """Test validation with invalid provider"""
        config = VirtualFSConfig()
        config.storage.provider = "invalid_provider"

        warnings = config.validate()
        assert len(warnings) > 0
        assert any("Unknown storage provider" in w for w in warnings)

    def test_validate_s3_without_credentials(self):
        """Test validation of S3 config without credentials"""
        config = VirtualFSConfig()
        config.storage.provider = "s3"
        config.storage.aws_access_key_id = None

        with patch.dict(os.environ, {}, clear=True):
            warnings = config.validate()
            assert any("AWS credentials not configured" in w for w in warnings)

    def test_validate_filesystem_nonexistent_root(self):
        """Test validation of filesystem with non-existent root"""
        config = VirtualFSConfig()
        config.storage.provider = "filesystem"
        config.storage.fs_root = "/nonexistent/path/that/does/not/exist"

        warnings = config.validate()
        assert any("does not exist" in w for w in warnings)

    def test_validate_redis_without_url(self):
        """Test validation of Redis session provider without URL"""
        config = VirtualFSConfig()
        config.session.session_provider = "redis"
        config.session.redis_url = None

        warnings = config.validate()
        assert any("redis_url not configured" in w for w in warnings)

    def test_validate_invalid_performance_settings(self):
        """Test validation of invalid performance settings"""
        config = VirtualFSConfig()
        config.performance.max_concurrent_operations = 0
        config.performance.batch_chunk_size = 0

        warnings = config.validate()
        assert any("max_concurrent_operations" in w for w in warnings)
        assert any("batch_chunk_size" in w for w in warnings)

    def test_validate_invalid_security_settings(self):
        """Test validation of invalid security settings"""
        config = VirtualFSConfig()
        config.security.max_file_size_mb = 0

        warnings = config.validate()
        assert any("max_file_size_mb" in w for w in warnings)


class TestGlobalConfig:
    """Test global configuration management"""

    def test_get_config_creates_default(self):
        """Test that get_config creates default config"""
        # Reset global config
        import chuk_virtual_fs.config

        chuk_virtual_fs.config._config = None

        config = get_config()
        assert isinstance(config, VirtualFSConfig)

    def test_set_and_get_config(self):
        """Test setting and getting global config"""
        custom_config = VirtualFSConfig()
        custom_config.debug = True

        set_config(custom_config)
        retrieved_config = get_config()

        assert retrieved_config.debug is True

    def test_load_config_from_file(self):
        """Test load_config with file path"""
        config_data = {"debug": True, "environment": "test"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config.debug is True
            assert config.environment == "test"
        finally:
            os.unlink(temp_path)

    def test_load_config_from_default_location(self):
        """Test load_config from default location"""
        config_data = {"debug": True}

        # Create a config file in a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "vfs-config.json"
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            # Patch the default paths to include our temp file
            with (
                patch(
                    "chuk_virtual_fs.config.Path.expanduser", return_value=config_path
                ),
                patch("chuk_virtual_fs.config.Path.exists", return_value=True),
            ):
                config = load_config(None)
                assert isinstance(config, VirtualFSConfig)

    def test_load_config_fallback_to_env(self):
        """Test load_config falls back to environment variables"""
        # Ensure no default config files exist
        with patch("chuk_virtual_fs.config.Path.exists", return_value=False):  # noqa: SIM117
            with patch.dict(os.environ, {"VFS_DEBUG": "true"}, clear=False):
                config = load_config(None)
                assert config.debug is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
