"""
chuk_virtual_fs/file_operations.py - Async file and directory operations
"""

from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING, Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo

if TYPE_CHECKING:
    from chuk_virtual_fs.provider_base import AsyncStorageProvider


class FileOperations:
    """
    Async file and directory operation utilities
    """

    @staticmethod
    async def copy(
        fs_provider: AsyncStorageProvider, path_resolver: Any, source: str, destination: str
    ) -> bool:
        """
        Copy a file or directory

        Args:
            fs_provider: Async filesystem storage provider
            path_resolver: Path resolution utility
            source: Path of the file or directory to copy
            destination: Destination path

        Returns:
            True if copy was successful, False otherwise
        """
        # Resolve paths
        source_path = path_resolver.resolve_path(
            (
                fs_provider.current_directory_path
                if hasattr(fs_provider, "current_directory_path")
                else "/"
            ),
            source,
        )
        dest_path = path_resolver.resolve_path(
            (
                fs_provider.current_directory_path
                if hasattr(fs_provider, "current_directory_path")
                else "/"
            ),
            destination,
        )

        # Get source node info
        source_info = await fs_provider.get_node_info(source_path)
        if not source_info:
            return False

        # Destination parent must exist
        dest_parent = posixpath.dirname(dest_path)
        dest_parent_info = await fs_provider.get_node_info(dest_parent)
        if not dest_parent_info or not dest_parent_info.is_dir:
            return False

        # Copy file
        if not source_info.is_dir:
            # Read source content
            content = await fs_provider.read_file(source_path)
            if content is None:
                return False

            # Create destination file node
            dest_name = posixpath.basename(dest_path)
            dest_node_info = EnhancedNodeInfo(
                name=dest_name, is_dir=False, parent_path=posixpath.dirname(dest_path)
            )

            # Create the destination node first
            if not await fs_provider.create_node(dest_node_info):
                return False

            # Write to destination
            return await fs_provider.write_file(dest_path, content)

        # Copy directory (create directories recursively)
        if source_info.is_dir:
            # Create destination directory
            dest_name = posixpath.basename(dest_path)
            dest_dir_info = EnhancedNodeInfo(
                name=dest_name, is_dir=True, parent_path=posixpath.dirname(dest_path)
            )
            if not await fs_provider.create_node(dest_dir_info):
                return False

            # Copy contents recursively
            for item in await fs_provider.list_directory(source_path):
                src_item = posixpath.join(source_path, item)
                dest_item = posixpath.join(dest_path, item)

                # Recursively copy each item
                await FileOperations.copy(
                    fs_provider, path_resolver, src_item, dest_item
                )

            return True

    @staticmethod
    async def move(
        fs_provider: AsyncStorageProvider, path_resolver: Any, source: str, destination: str
    ) -> bool:
        """
        Move a file or directory

        Args:
            fs_provider: Async filesystem storage provider
            path_resolver: Path resolution utility
            source: Path of the file or directory to move
            destination: Destination path

        Returns:
            True if move was successful, False otherwise
        """
        # Copy first
        if not await FileOperations.copy(
            fs_provider, path_resolver, source, destination
        ):
            return False

        # Then delete source
        return await fs_provider.delete_node(
            path_resolver.resolve_path(
                (
                    fs_provider.current_directory_path
                    if hasattr(fs_provider, "current_directory_path")
                    else "/"
                ),
                source,
            )
        )
