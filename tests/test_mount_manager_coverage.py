"""
Tests to improve mount_manager.py coverage
Focus on error conditions and edge cases
"""

from unittest.mock import AsyncMock, patch

import pytest

from chuk_virtual_fs.mount_manager import Mount, MountManager
from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider


class TestMountRootBehavior:
    """Test root mount special cases"""

    def test_root_mount_is_under_mount(self):
        """Test that root mount matches all paths"""
        provider = AsyncMemoryStorageProvider()
        mount = Mount("/", provider, "memory")

        # Root mount should match everything
        assert mount.is_under_mount("/")
        assert mount.is_under_mount("/file.txt")
        assert mount.is_under_mount("/deep/nested/path.txt")

    def test_root_mount_translate_path(self):
        """Test path translation for root mount"""
        provider = AsyncMemoryStorageProvider()
        mount = Mount("/", provider, "memory")

        # Root mount returns path as-is
        assert mount.translate_path("/") == "/"
        assert mount.translate_path("/file.txt") == "/file.txt"
        assert mount.translate_path("/deep/path.txt") == "/deep/path.txt"

    def test_translate_path_invalid(self):
        """Test ValueError when translating invalid path"""
        provider = AsyncMemoryStorageProvider()
        mount = Mount("/mounted", provider, "memory")

        # Path not under mount should raise ValueError
        with pytest.raises(ValueError, match="Path /other is not under mount /mounted"):
            mount.translate_path("/other")


class TestMountManagerErrorCases:
    """Test error handling in MountManager"""

    @pytest.mark.asyncio
    async def test_mount_unknown_provider(self):
        """Test mounting unknown provider type"""
        manager = MountManager()

        # Unknown provider should fail gracefully
        result = await manager.mount(
            "/unknown", provider="nonexistent_provider", provider_kwargs={}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_mount_provider_initialization_failure(self):
        """Test when provider initialization fails"""
        manager = MountManager()

        # Mock provider that fails to initialize
        with patch.object(
            AsyncMemoryStorageProvider,
            "initialize",
            side_effect=Exception("Init failed"),
        ):
            result = await manager.mount("/fail", provider="memory", provider_kwargs={})
            assert result is False

    @pytest.mark.asyncio
    async def test_mount_provider_creation_failure(self):
        """Test when provider creation returns None"""
        manager = MountManager()

        # Mock _create_provider to return None
        with patch.object(manager, "_create_provider", return_value=None):
            result = await manager.mount("/fail", provider="memory", provider_kwargs={})
            assert result is False

    @pytest.mark.asyncio
    async def test_unmount_with_close_error(self):
        """Test unmount when provider.close() raises exception"""
        manager = MountManager()

        # Mount a provider
        await manager.mount("/test", provider="memory")

        # Get the mount and mock its provider's close to raise
        mount = manager.mounts[0]
        mock_close = AsyncMock(side_effect=Exception("Close failed"))
        mount.provider.close = mock_close

        # Unmount should succeed despite close error
        result = await manager.unmount("/test")
        assert result is True
        assert len(manager.mounts) == 0

    @pytest.mark.asyncio
    async def test_close_all_with_errors(self):
        """Test close_all when some providers fail to close"""
        manager = MountManager()

        # Mount multiple providers
        await manager.mount("/m1", provider="memory")
        await manager.mount("/m2", provider="memory")

        # Mock one provider to fail on close
        mount1 = manager.mounts[0]
        mock_close = AsyncMock(side_effect=Exception("Close failed"))
        mount1.provider.close = mock_close

        # close_all should handle errors gracefully
        await manager.close_all()
        assert len(manager.mounts) == 0

    @pytest.mark.asyncio
    async def test_get_provider_translation_error(self):
        """Test get_provider when path translation fails"""
        manager = MountManager()

        # Mount at specific path
        await manager.mount("/mounted", provider="memory")

        # Try to get provider for path not under mount
        # This simulates a translation error
        mount = manager.find_mount("/other/path")

        # No mount should be found for /other/path
        assert mount is None

        # get_provider should return None
        result = manager.get_provider("/other/path")
        assert result is None


class TestMountManagerProviderCreation:
    """Test provider creation edge cases"""

    @pytest.mark.asyncio
    async def test_create_s3_provider(self):
        """Test S3 provider creation"""
        manager = MountManager()

        # S3 provider needs specific kwargs
        # This tests the S3 branch in _create_provider
        # We expect this to fail without proper credentials but should create provider
        with patch("chuk_virtual_fs.providers.s3.S3StorageProvider") as MockS3:
            mock_instance = AsyncMock()
            mock_instance.initialize = AsyncMock(
                side_effect=Exception("No credentials")
            )
            MockS3.return_value = mock_instance

            result = await manager.mount(
                "/s3", provider="s3", provider_kwargs={"bucket_name": "test"}
            )

            # Should fail at initialization, not creation
            assert result is False
            MockS3.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_provider_import_error(self):
        """Test handling of ImportError during provider creation"""
        manager = MountManager()

        # Simulate ImportError when importing provider module
        with patch(
            "chuk_virtual_fs.providers.memory.AsyncMemoryStorageProvider",
            side_effect=ImportError("Module not found"),
        ):
            result = await manager.mount(
                "/import_fail", provider="memory", provider_kwargs={}
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_create_provider_general_exception(self):
        """Test handling of general exception during provider creation"""
        manager = MountManager()

        # Simulate exception when creating provider instance
        with patch(
            "chuk_virtual_fs.providers.memory.AsyncMemoryStorageProvider",
            side_effect=RuntimeError("Creation error"),
        ):
            result = await manager.mount(
                "/error", provider="memory", provider_kwargs={}
            )
            assert result is False


class TestMountPathNormalization:
    """Test path normalization in mounts"""

    @pytest.mark.asyncio
    async def test_mount_point_normalization(self):
        """Test that mount points are normalized"""
        manager = MountManager()

        # Mount with non-normalized path
        result = await manager.mount("/path//with///slashes", provider="memory")
        assert result is True

        # Check that path was normalized
        mounts = manager.list_mounts()
        assert len(mounts) == 1
        # Path should be normalized
        assert "//" not in mounts[0]["mount_point"]

    @pytest.mark.asyncio
    async def test_unmount_normalization(self):
        """Test that unmount normalizes paths"""
        manager = MountManager()

        await manager.mount("/test", provider="memory")

        # Unmount with non-normalized path should still work
        result = await manager.unmount("/test/")
        assert result is True
        assert len(manager.mounts) == 0


class TestMountOptions:
    """Test mount options handling"""

    @pytest.mark.asyncio
    async def test_mount_with_read_only_option(self):
        """Test mounting with read_only option"""
        manager = MountManager()

        result = await manager.mount(
            "/readonly", provider="memory", mount_options={"read_only": True}
        )
        assert result is True

        # Verify mount has read_only flag
        mounts = manager.list_mounts()
        assert mounts[0]["read_only"] is True

    @pytest.mark.asyncio
    async def test_mount_without_options(self):
        """Test mounting without options (defaults)"""
        manager = MountManager()

        result = await manager.mount("/default", provider="memory")
        assert result is True

        # Verify default options
        mounts = manager.list_mounts()
        assert mounts[0]["read_only"] is False
        assert isinstance(mounts[0]["options"], dict)


class TestMountListSorting:
    """Test mount list sorting"""

    @pytest.mark.asyncio
    async def test_mounts_sorted_by_depth(self):
        """Test that mounts are sorted by depth for correct resolution"""
        manager = MountManager()

        # Mount in various orders
        await manager.mount("/shallow", provider="memory")
        await manager.mount("/very/deep/path", provider="memory")
        await manager.mount("/medium/path", provider="memory")

        # Verify mounts are sorted by depth (deepest first)
        # This ensures /very/deep/path is checked before /very
        depths = [m.mount_point.count("/") for m in manager.mounts]
        assert depths == sorted(depths, reverse=True)

    @pytest.mark.asyncio
    async def test_list_mounts_alphabetical(self):
        """Test that list_mounts returns alphabetically sorted"""
        manager = MountManager()

        await manager.mount("/z", provider="memory")
        await manager.mount("/a", provider="memory")
        await manager.mount("/m", provider="memory")

        mounts = manager.list_mounts()
        mount_points = [m["mount_point"] for m in mounts]

        # list_mounts should return alphabetically sorted
        assert mount_points == sorted(mount_points)


class TestMountCoverage:
    """Additional tests to hit uncovered lines"""

    @pytest.mark.asyncio
    async def test_mount_duplicate_handling(self):
        """Test duplicate mount detection"""
        manager = MountManager()

        # First mount succeeds
        result1 = await manager.mount("/dup", provider="memory")
        assert result1 is True

        # Second mount at same point fails
        result2 = await manager.mount("/dup", provider="memory")
        assert result2 is False

    @pytest.mark.asyncio
    async def test_unmount_not_found(self):
        """Test unmounting non-existent mount"""
        manager = MountManager()

        # Unmount when no mounts exist
        result = await manager.unmount("/nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_find_mount_no_matches(self):
        """Test find_mount when no mounts match"""
        manager = MountManager()

        # No mounts
        mount = manager.find_mount("/any/path")
        assert mount is None

        # Mount at specific path
        await manager.mount("/specific", provider="memory")

        # Path not under any mount (when root not mounted)
        mount = manager.find_mount("/other")
        assert mount is None

    @pytest.mark.asyncio
    async def test_provider_kwargs_none_handling(self):
        """Test that None provider_kwargs are handled"""
        manager = MountManager()

        # Pass None as provider_kwargs
        result = await manager.mount(
            "/test",
            provider="memory",
            provider_kwargs=None,  # Explicitly None
        )
        assert result is True
