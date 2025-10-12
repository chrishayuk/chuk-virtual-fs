"""
chuk_virtual_fs/search_utils.py - Async filesystem search and discovery utilities
"""

from __future__ import annotations

import asyncio
import fnmatch
import posixpath
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chuk_virtual_fs.provider_base import AsyncStorageProvider


class SearchUtils:
    """
    Async utility class for searching and discovering filesystem contents
    """

    @staticmethod
    async def find(
        fs_provider: AsyncStorageProvider,
        path: str = "/",
        recursive: bool = True,
        filter_func: Callable[[str], bool | Awaitable[bool]] | None = None,
    ) -> list[str]:
        """
        Find files and directories under a given path

        Args:
            fs_provider: Async filesystem storage provider
            path: Starting path for search (default: root)
            recursive: Whether to search subdirectories (default: True)
            filter_func: Optional async function to filter results

        Returns:
            List of full paths of files and directories
        """

        async def _recursive_find(current_path: str) -> list[str]:
            results: list[str] = []
            try:
                contents = await fs_provider.list_directory(current_path)
                for item in contents:
                    full_item_path = (current_path + "/" + item).replace("//", "/")

                    # Get node info
                    full_path_info = await fs_provider.get_node_info(full_item_path)

                    # Apply filter if provided
                    should_include = True
                    if filter_func:
                        result = filter_func(full_item_path)
                        if asyncio.iscoroutine(result):
                            should_include = await result
                        else:
                            should_include = result  # type: ignore[assignment]

                    if should_include:
                        results.append(full_item_path)

                    # Recursively search subdirectories
                    if recursive and full_path_info and full_path_info.is_dir:
                        results.extend(await _recursive_find(full_item_path))
            except Exception:
                pass
            return results

        return await _recursive_find(path)

    @staticmethod
    async def search(
        fs_provider: AsyncStorageProvider,
        path: str = "/",
        pattern: str = "*",
        recursive: bool = False,
    ) -> list[str]:
        """
        Search for files matching a pattern

        Args:
            fs_provider: Async filesystem storage provider
            path: Starting path for search
            pattern: Wildcard pattern to match (simple * supported)
            recursive: Whether to search subdirectories

        Returns:
            List of matching file paths
        """

        def _match_pattern(filename: str) -> bool:
            return fnmatch.fnmatch(posixpath.basename(filename), pattern)

        # Create async filter function
        async def async_filter(x: str) -> bool:
            info = await fs_provider.get_node_info(x)
            return info is not None and not info.is_dir and _match_pattern(x)

        return await SearchUtils.find(
            fs_provider, path, recursive, filter_func=async_filter
        )
