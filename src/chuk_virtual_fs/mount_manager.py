"""
chuk_virtual_fs/mount_manager.py - Virtual mount manager for multiple providers

Allows mounting different storage providers at different paths within the virtual filesystem.
"""

import logging
import posixpath
from typing import Any

from chuk_virtual_fs.provider_base import AsyncStorageProvider

logger = logging.getLogger(__name__)


class Mount:
    """Represents a mounted provider at a specific path"""

    def __init__(
        self,
        mount_point: str,
        provider: AsyncStorageProvider,
        provider_name: str,
        options: dict[str, Any] | None = None,
    ):
        """
        Initialize a mount

        Args:
            mount_point: Path where provider is mounted (e.g., "/cloud")
            provider: Storage provider instance
            provider_name: Name of the provider (for display)
            options: Additional mount options
        """
        self.mount_point = mount_point.rstrip("/") or "/"
        self.provider = provider
        self.provider_name = provider_name
        self.options = options or {}
        self.read_only = self.options.get("read_only", False)

    def is_under_mount(self, path: str) -> bool:
        """Check if a path is under this mount point"""
        path = path.rstrip("/") or "/"
        mount = self.mount_point.rstrip("/") or "/"

        if mount == "/":
            # Root mount matches everything
            return True

        # Check if path starts with mount point
        return path == mount or path.startswith(mount + "/")

    def translate_path(self, path: str) -> str:
        """Translate a path from virtual to provider-local"""
        path = path.rstrip("/") or "/"
        mount = self.mount_point.rstrip("/") or "/"

        if mount == "/":
            return path

        # Remove mount point prefix
        if path == mount:
            return "/"
        elif path.startswith(mount + "/"):
            return path[len(mount) :]

        raise ValueError(f"Path {path} is not under mount {mount}")


class MountManager:
    """
    Manages multiple provider mounts in a virtual filesystem

    Allows mounting different providers at different paths, similar to
    Unix filesystem mounts.
    """

    def __init__(self) -> None:
        """Initialize the mount manager"""
        self.mounts: list[Mount] = []

    async def mount(
        self,
        mount_point: str,
        provider: str,
        provider_kwargs: dict[str, Any] | None = None,
        mount_options: dict[str, Any] | None = None,
    ) -> bool:
        """
        Mount a provider at a specific path

        Args:
            mount_point: Path where provider should be mounted
            provider: Provider name ("s3", "filesystem", "memory")
            provider_kwargs: Arguments for provider initialization
            mount_options: Mount-specific options (e.g., read_only)

        Returns:
            True if mount was successful

        Example:
            await manager.mount(
                "/cloud",
                provider="s3",
                provider_kwargs={"bucket": "my-bucket"}
            )
        """
        # Normalize mount point
        mount_point = posixpath.normpath(mount_point)

        # Check if already mounted
        for mount in self.mounts:
            if mount.mount_point == mount_point:
                logger.warning(f"Mount point {mount_point} already in use")
                return False

        # Create provider instance
        provider_kwargs = provider_kwargs or {}
        provider_instance = await self._create_provider(provider, provider_kwargs)

        if not provider_instance:
            logger.error(f"Failed to create provider: {provider}")
            return False

        # Initialize provider
        try:
            await provider_instance.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize provider: {e}")
            return False

        # Create mount
        mount = Mount(mount_point, provider_instance, provider, mount_options)
        self.mounts.append(mount)

        # Sort mounts by depth (deepest first) for correct path resolution
        self.mounts.sort(key=lambda m: m.mount_point.count("/"), reverse=True)

        logger.info(f"Mounted {provider} at {mount_point}")
        return True

    async def unmount(self, mount_point: str) -> bool:
        """
        Unmount a provider

        Args:
            mount_point: Path to unmount

        Returns:
            True if unmount was successful
        """
        mount_point = posixpath.normpath(mount_point)

        for i, mount in enumerate(self.mounts):
            if mount.mount_point == mount_point:
                # Close provider
                try:
                    await mount.provider.close()
                except Exception as e:
                    logger.warning(f"Error closing provider during unmount: {e}")

                # Remove mount
                del self.mounts[i]
                logger.info(f"Unmounted {mount_point}")
                return True

        logger.warning(f"No mount found at {mount_point}")
        return False

    def find_mount(self, path: str) -> Mount | None:
        """
        Find the mount that handles a given path

        Args:
            path: Path to look up

        Returns:
            Mount object or None if no mount found
        """
        # Mounts are sorted by depth, so first match is the correct one
        for mount in self.mounts:
            if mount.is_under_mount(path):
                return mount

        return None

    def get_provider(self, path: str) -> tuple[AsyncStorageProvider, str] | None:
        """
        Get the provider for a given path and translate the path

        Args:
            path: Virtual path

        Returns:
            Tuple of (provider, translated_path) or None
        """
        mount = self.find_mount(path)
        if not mount:
            return None

        try:
            translated_path = mount.translate_path(path)
            return (mount.provider, translated_path)
        except ValueError as e:
            logger.error(f"Path translation error: {e}")
            return None

    def list_mounts(self) -> list[dict[str, Any]]:
        """
        List all active mounts

        Returns:
            List of mount information dictionaries
        """
        return [
            {
                "mount_point": mount.mount_point,
                "provider": mount.provider_name,
                "read_only": mount.read_only,
                "options": mount.options,
            }
            for mount in sorted(self.mounts, key=lambda m: m.mount_point)
        ]

    async def close_all(self) -> None:
        """Close all mounted providers"""
        for mount in self.mounts:
            try:
                await mount.provider.close()
            except Exception as e:
                logger.warning(f"Error closing provider at {mount.mount_point}: {e}")

        self.mounts.clear()

    async def _create_provider(
        self, provider_name: str, kwargs: dict[str, Any]
    ) -> AsyncStorageProvider | None:
        """Create a provider instance"""
        try:
            if provider_name == "memory":
                from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider

                return AsyncMemoryStorageProvider(**kwargs)

            elif provider_name == "s3":
                from chuk_virtual_fs.providers.s3 import S3StorageProvider

                return S3StorageProvider(**kwargs)

            elif provider_name == "filesystem":
                from chuk_virtual_fs.providers.filesystem import (
                    AsyncFilesystemStorageProvider,
                )

                return AsyncFilesystemStorageProvider(**kwargs)

            elif provider_name == "sqlite":
                from chuk_virtual_fs.providers.sqlite import SqliteStorageProvider

                return SqliteStorageProvider(**kwargs)

            else:
                logger.error(f"Unknown provider: {provider_name}")
                return None

        except ImportError as e:
            logger.error(f"Failed to import provider {provider_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating provider {provider_name}: {e}")
            return None
