"""
Synchronous wrapper for AsyncVirtualFileSystem

Provides a synchronous interface to the async filesystem for backward compatibility
"""

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from chuk_virtual_fs.fs_manager import AsyncVirtualFileSystem
from chuk_virtual_fs.node_info import EnhancedNodeInfo

T = TypeVar("T")


class SyncVirtualFileSystem:
    """Synchronous wrapper around AsyncVirtualFileSystem"""

    def __init__(self, provider_name: str = "memory", **kwargs: Any):
        """Initialize sync wrapper with an async filesystem"""
        self._async_fs = AsyncVirtualFileSystem(provider=provider_name, **kwargs)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._initialized = False

    def _run_async(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run an async coroutine synchronously"""
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                # Create a new event loop if closed
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._loop = loop
        except RuntimeError:
            # No event loop exists, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop

        if loop.is_running():
            # We're in an async context, use a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            # Run in the current loop
            return loop.run_until_complete(coro)

    def _ensure_initialized(self) -> None:
        """Ensure the filesystem is initialized"""
        if not self._initialized:
            self._run_async(self._async_fs.initialize())
            self._initialized = True

    @property
    def provider(self) -> Any:
        """Access to underlying provider"""
        self._ensure_initialized()
        return self._async_fs.provider

    def get_provider_name(self) -> str:
        """Get the name of the current provider"""
        return self._async_fs.provider_name

    def pwd(self) -> str:
        """Get current working directory"""
        self._ensure_initialized()
        return self._async_fs.current_directory

    def cd(self, path: str) -> bool:
        """Change directory"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.cd(path))
        return result

    def ls(self, path: str | None = None) -> list[str]:
        """List directory contents"""
        self._ensure_initialized()
        if path is None:
            path = self._async_fs.current_directory
        result = self._run_async(self._async_fs.ls(path))
        return result

    def mkdir(self, path: str) -> bool:
        """Create a directory"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.mkdir(path))
        return result

    def touch(self, path: str) -> bool:
        """Create an empty file"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.touch(path))
        return result

    def rm(self, path: str) -> bool:
        """Remove a file"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.rm(path))
        return result

    def rmdir(self, path: str) -> bool:
        """Remove a directory"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.rmdir(path))
        return result

    def read_file(self, path: str, as_text: bool = False) -> bytes | str | None:
        """Read file contents"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.read_file(path, as_text=as_text))
        return result

    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.write_file(path, content))
        return result

    def cp(self, source: str, dest: str) -> bool:
        """Copy a file"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.cp(source, dest))
        return result

    def mv(self, source: str, dest: str) -> bool:
        """Move a file"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.mv(source, dest))
        return result

    def exists(self, path: str) -> bool:
        """Check if path exists"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.exists(path))
        return result

    def is_file(self, path: str) -> bool:
        """Check if path is a file"""
        self._ensure_initialized()
        info = self._run_async(self._async_fs.get_node_info(path))
        return info is not None and not info.is_dir

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory"""
        self._ensure_initialized()
        info = self._run_async(self._async_fs.get_node_info(path))
        return info is not None and info.is_dir

    def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get node information"""
        self._ensure_initialized()
        result = self._run_async(self._async_fs.get_node_info(path))
        return result

    def resolve_path(self, path: str) -> str:
        """Resolve a path relative to current directory"""
        self._ensure_initialized()
        # resolve_path is not async, call it directly
        return self._async_fs.resolve_path(path)

    def get_fs_info(self) -> dict[str, Any]:
        """Get filesystem information"""
        self._ensure_initialized()
        return {
            "provider": self._async_fs.provider_name,
            "cwd": self._async_fs.current_directory,
            "stats": self._async_fs.stats,
        }

    def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics"""
        self._ensure_initialized()
        if self._async_fs.provider and hasattr(
            self._async_fs.provider, "get_storage_stats"
        ):
            result = self._run_async(self._async_fs.provider.get_storage_stats())
            return result
        return {}

    def find(self, pattern: str, path: str | None = None) -> list[str]:
        """Find files matching pattern"""
        self._ensure_initialized()
        search_path = path if path is not None else self._async_fs.current_directory
        result = self._run_async(self._async_fs.find(pattern, search_path))
        return result

    def search(
        self, pattern: str, path: str | None = None
    ) -> list[tuple[str, int, str]]:
        """Search for pattern in files"""
        self._ensure_initialized()
        # Note: AsyncVirtualFileSystem doesn't have a search method
        # This is a placeholder for future implementation
        return []

    def get_size(self, path: str) -> int:
        """Get file size"""
        self._ensure_initialized()
        info = self._run_async(self._async_fs.get_node_info(path))
        return info.size if info else 0

    def close(self) -> None:
        """Close the filesystem"""
        if self._initialized:
            self._run_async(self._async_fs.close())
            self._initialized = False
