"""
Test module for security_config module
"""

import pytest

from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider
from chuk_virtual_fs.security_config import (
    SECURITY_PROFILES,
    create_custom_security_profile,
    create_secure_provider,
    get_available_profiles,
    get_profile_settings,
    setup_profile_paths,
)
from chuk_virtual_fs.security_wrapper import SecurityWrapper


class TestSecurityProfiles:
    """Test predefined security profiles"""

    def test_default_profile_exists(self):
        """Test that default profile exists"""
        assert "default" in SECURITY_PROFILES
        profile = SECURITY_PROFILES["default"]
        assert profile["max_file_size"] == 10 * 1024 * 1024
        assert profile["max_total_size"] == 100 * 1024 * 1024
        assert profile["read_only"] is False

    def test_strict_profile_exists(self):
        """Test that strict profile exists"""
        assert "strict" in SECURITY_PROFILES
        profile = SECURITY_PROFILES["strict"]
        assert profile["max_file_size"] == 1 * 1024 * 1024
        assert profile["max_total_size"] == 20 * 1024 * 1024

    def test_readonly_profile_exists(self):
        """Test that readonly profile exists"""
        assert "readonly" in SECURITY_PROFILES
        profile = SECURITY_PROFILES["readonly"]
        assert profile["read_only"] is True

    def test_untrusted_profile_exists(self):
        """Test that untrusted profile exists"""
        assert "untrusted" in SECURITY_PROFILES
        profile = SECURITY_PROFILES["untrusted"]
        assert profile["allowed_paths"] == ["/sandbox"]

    def test_testing_profile_exists(self):
        """Test that testing profile exists"""
        assert "testing" in SECURITY_PROFILES
        profile = SECURITY_PROFILES["testing"]
        assert profile["max_file_size"] == 100 * 1024 * 1024


class TestCreateSecureProvider:
    """Test create_secure_provider function"""

    @pytest.mark.asyncio
    async def test_create_with_default_profile(self):
        """Test creating a secure provider with default profile"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        secure_provider = create_secure_provider(provider, profile="default")
        assert isinstance(secure_provider, SecurityWrapper)
        assert secure_provider.max_file_size == 10 * 1024 * 1024
        assert secure_provider.read_only is False

    @pytest.mark.asyncio
    async def test_create_with_strict_profile(self):
        """Test creating a secure provider with strict profile"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        secure_provider = create_secure_provider(provider, profile="strict")
        assert isinstance(secure_provider, SecurityWrapper)
        assert secure_provider.max_file_size == 1 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_create_with_readonly_profile(self):
        """Test creating a secure provider with readonly profile"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        secure_provider = create_secure_provider(provider, profile="readonly")
        assert isinstance(secure_provider, SecurityWrapper)
        assert secure_provider.read_only is True

    @pytest.mark.asyncio
    async def test_create_with_untrusted_profile(self):
        """Test creating a secure provider with untrusted profile"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        secure_provider = create_secure_provider(provider, profile="untrusted")
        assert isinstance(secure_provider, SecurityWrapper)
        assert secure_provider.allowed_paths == ["/sandbox"]

    @pytest.mark.asyncio
    async def test_create_with_testing_profile(self):
        """Test creating a secure provider with testing profile"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        secure_provider = create_secure_provider(provider, profile="testing")
        assert isinstance(secure_provider, SecurityWrapper)
        assert secure_provider.max_files == 10000

    def test_create_with_invalid_profile(self):
        """Test creating a secure provider with invalid profile"""
        provider = AsyncMemoryStorageProvider()

        with pytest.raises(ValueError, match="Unknown security profile"):
            create_secure_provider(provider, profile="nonexistent")

    @pytest.mark.asyncio
    async def test_create_with_overrides(self):
        """Test creating a secure provider with overrides"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        secure_provider = create_secure_provider(
            provider,
            profile="default",
            max_file_size=5 * 1024 * 1024,
            read_only=True,
        )
        assert isinstance(secure_provider, SecurityWrapper)
        assert secure_provider.max_file_size == 5 * 1024 * 1024
        assert secure_provider.read_only is True

    @pytest.mark.asyncio
    async def test_create_without_setup_allowed_paths(self):
        """Test creating a secure provider without setting up allowed paths"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        secure_provider = create_secure_provider(
            provider, profile="default", setup_allowed_paths=False
        )
        assert isinstance(secure_provider, SecurityWrapper)


class TestCustomSecurityProfile:
    """Test custom security profile functionality"""

    def test_create_custom_profile(self):
        """Test creating a custom security profile"""
        settings = {
            "max_file_size": 2 * 1024 * 1024,
            "max_total_size": 50 * 1024 * 1024,
            "read_only": False,
            "allowed_paths": ["/custom"],
        }

        create_custom_security_profile("custom_test", settings)
        assert "custom_test" in SECURITY_PROFILES
        assert SECURITY_PROFILES["custom_test"]["max_file_size"] == 2 * 1024 * 1024

    def test_create_custom_profile_duplicate(self):
        """Test creating a custom profile with duplicate name"""
        settings = {
            "max_file_size": 2 * 1024 * 1024,
            "max_total_size": 50 * 1024 * 1024,
            "read_only": False,
        }

        with pytest.raises(ValueError, match="already exists"):
            create_custom_security_profile("default", settings)

    def test_create_custom_profile_missing_required(self):
        """Test creating a custom profile missing required settings"""
        settings = {
            "max_file_size": 2 * 1024 * 1024,
            # Missing max_total_size and read_only
        }

        with pytest.raises(ValueError, match="Missing required setting"):
            create_custom_security_profile("incomplete", settings)

    def teardown_method(self):
        """Clean up custom profiles after each test"""
        if "custom_test" in SECURITY_PROFILES:
            del SECURITY_PROFILES["custom_test"]
        if "incomplete" in SECURITY_PROFILES:
            del SECURITY_PROFILES["incomplete"]


class TestGetAvailableProfiles:
    """Test get_available_profiles function"""

    def test_get_available_profiles(self):
        """Test getting list of available profiles"""
        profiles = get_available_profiles()
        assert isinstance(profiles, list)
        assert "default" in profiles
        assert "strict" in profiles
        assert "readonly" in profiles
        assert "untrusted" in profiles
        assert "testing" in profiles

    def test_get_available_profiles_returns_copy(self):
        """Test that get_available_profiles returns a copy"""
        profiles1 = get_available_profiles()
        profiles2 = get_available_profiles()
        profiles1.append("fake")
        assert "fake" not in profiles2


class TestGetProfileSettings:
    """Test get_profile_settings function"""

    def test_get_default_profile_settings(self):
        """Test getting default profile settings"""
        settings = get_profile_settings("default")
        assert isinstance(settings, dict)
        assert settings["max_file_size"] == 10 * 1024 * 1024
        assert settings["read_only"] is False

    def test_get_strict_profile_settings(self):
        """Test getting strict profile settings"""
        settings = get_profile_settings("strict")
        assert isinstance(settings, dict)
        assert settings["max_file_size"] == 1 * 1024 * 1024

    def test_get_invalid_profile_settings(self):
        """Test getting settings for invalid profile"""
        with pytest.raises(ValueError, match="Unknown security profile"):
            get_profile_settings("nonexistent")

    def test_get_profile_settings_returns_copy(self):
        """Test that get_profile_settings returns a copy"""
        settings = get_profile_settings("default")
        settings["max_file_size"] = 999
        original = SECURITY_PROFILES["default"]["max_file_size"]
        assert original == 10 * 1024 * 1024


class TestSetupProfilePaths:
    """Test setup_profile_paths function"""

    @pytest.mark.asyncio
    async def test_setup_profile_paths_default(self):
        """Test setting up paths for default profile"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        result = setup_profile_paths(provider, "default")
        assert result is True

    @pytest.mark.asyncio
    async def test_setup_profile_paths_untrusted(self):
        """Test setting up paths for untrusted profile"""
        provider = AsyncMemoryStorageProvider()
        await provider.initialize()

        result = setup_profile_paths(provider, "untrusted")
        assert result is True

    def test_setup_profile_paths_invalid(self):
        """Test setting up paths for invalid profile"""
        provider = AsyncMemoryStorageProvider()

        result = setup_profile_paths(provider, "nonexistent")
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
