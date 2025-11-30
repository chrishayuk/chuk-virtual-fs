"""Git repository provider for chuk-virtual-fs.

Provides two modes:
1. snapshot: Read-only view of a repository at a specific commit/branch
2. worktree: Writable working directory backed by a git repository

Perfect for:
- MCP devboxes: "mount this repo for the LLM"
- Code review tools: Read-only snapshot at a commit
- AI coding: Clone, modify, commit workflow
"""

import asyncio
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider
from chuk_virtual_fs.providers.git_models import (
    GitCommitInfo,
    GitFileChange,
    GitFileChangeType,
    GitMetadata,
    GitMode,
    GitOperationStats,
    GitProviderConfig,
    GitRepositoryInfo,
    GitStatus,
    GitStorageStats,
)

if TYPE_CHECKING:
    from git import Repo


class GitProvider(AsyncStorageProvider):
    """Git repository storage provider.

    Two modes:
    - snapshot: Read-only filesystem at a specific commit/branch
    - worktree: Writable working directory backed by a git repo

    Examples:
        # Read-only snapshot of main branch
        provider = GitProvider(
            repo_url="https://github.com/user/repo",
            mode="snapshot",
            ref="main"
        )

        # Writable worktree
        provider = GitProvider(
            repo_url="/path/to/local/repo",
            mode="worktree",
            branch="feature-branch"
        )
    """

    def __init__(
        self,
        repo_url: str,
        mode: str | GitMode = GitMode.SNAPSHOT,
        ref: str | None = None,
        branch: str | None = None,
        clone_dir: str | None = None,
        depth: int | None = None,
        sparse_checkout: list[str] | None = None,
    ):
        """Initialize Git provider.

        Args:
            repo_url: Git repository URL or local path
            mode: "snapshot" (read-only) or "worktree" (writable)
            ref: Commit SHA, tag, or branch for snapshot mode
            branch: Branch name for worktree mode
            clone_dir: Directory to clone into (default: temp dir)
            depth: Clone depth for shallow clones (default: None = full clone)
            sparse_checkout: Paths for sparse checkout (default: None = full checkout)
        """
        super().__init__()

        # Parse and validate config with Pydantic
        try:
            # Convert string mode to enum if needed
            if isinstance(mode, str):
                mode = GitMode(mode)

            self.config = GitProviderConfig(
                repo_url=repo_url,
                mode=mode,
                ref=ref,
                branch=branch,
                clone_dir=clone_dir,
                depth=depth,
                sparse_checkout=sparse_checkout,
            )
        except (ValidationError, ValueError) as e:
            raise ValueError(f"Invalid Git provider configuration: {e}")

        # Will be set in initialize()
        self.repo: Repo | None = None
        self._temp_dir: str | None = None
        self._repo_path: str | None = None

        # Statistics (Pydantic model)
        self._stats = GitOperationStats()

    async def initialize(self) -> bool:
        """Initialize Git repository.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Import GitPython
            try:
                from git import Repo
            except ImportError as e:
                print(
                    f"Failed to import GitPython: {e}\n"
                    "Install with: pip install chuk-virtual-fs[git]"
                )
                return False

            # Determine repo path
            if self.config.clone_dir:
                self._repo_path = self.config.clone_dir
            else:
                # Create temp directory
                self._temp_dir = tempfile.mkdtemp(prefix="chuk-git-")
                self._repo_path = self._temp_dir

            # Clone or open repository
            if os.path.exists(self.config.repo_url) and os.path.isdir(
                self.config.repo_url
            ):
                # Local repository
                if self.config.mode == GitMode.WORKTREE:
                    # For worktree mode, use the repo directly
                    self._repo_path = self.config.repo_url
                    self.repo = Repo(self._repo_path)
                else:
                    # For snapshot mode, clone to temp location
                    await asyncio.to_thread(self._clone_repo, Repo)
            else:
                # Remote repository - clone it
                await asyncio.to_thread(self._clone_repo, Repo)

            # Ensure repo is initialized
            assert self.repo is not None, "Repository must be initialized"

            # For snapshot mode, checkout the ref
            if self.config.mode == GitMode.SNAPSHOT:
                ref = self.config.ref or "HEAD"
                await asyncio.to_thread(self.repo.git.checkout, ref)

            # For worktree mode, ensure we're on the right branch
            elif self.config.mode == GitMode.WORKTREE:
                branch = self.config.branch or "main"
                current_branch = self.repo.active_branch.name
                if current_branch != branch:
                    # Check if branch exists
                    if branch in [b.name for b in self.repo.branches]:
                        await asyncio.to_thread(self.repo.git.checkout, branch)
                    else:
                        # Create new branch
                        await asyncio.to_thread(self.repo.git.checkout, "-b", branch)

            return True

        except Exception as e:
            print(f"Failed to initialize Git provider: {e}")
            return False

    def _clone_repo(self, Repo: Any) -> None:
        """Clone repository (sync helper for asyncio.to_thread).

        Args:
            Repo: GitPython Repo class
        """
        clone_kwargs: dict[str, Any] = {}

        if self.config.depth:
            clone_kwargs["depth"] = self.config.depth

        if self.config.sparse_checkout:
            # Sparse checkout requires special handling
            clone_kwargs["filter"] = "blob:none"

        self.repo = Repo.clone_from(
            self.config.repo_url, self._repo_path, **clone_kwargs
        )

        if self.config.sparse_checkout:
            # Configure sparse checkout
            self.repo.git.sparse_checkout("set", *self.config.sparse_checkout)

    def _get_fs_path(self, vfs_path: str) -> str:
        """Convert VFS path to filesystem path.

        Args:
            vfs_path: Virtual filesystem path

        Returns:
            Filesystem path
        """
        # Normalize path
        if not vfs_path.startswith("/"):
            vfs_path = "/" + vfs_path

        # Remove leading slash and join with repo path
        rel_path = vfs_path[1:] if vfs_path.startswith("/") else vfs_path
        # _repo_path is guaranteed to be set in initialize()
        assert self._repo_path is not None
        return os.path.join(self._repo_path, rel_path)

    def _get_vfs_path(self, fs_path: str) -> str:
        """Convert filesystem path to VFS path.

        Args:
            fs_path: Filesystem path

        Returns:
            VFS path
        """
        # Make relative to repo root
        rel_path = os.path.relpath(fs_path, self._repo_path)

        # Convert to POSIX-style path with leading slash
        vfs_path = "/" + rel_path.replace(os.sep, "/")

        # Handle current directory
        if vfs_path == "/.":
            vfs_path = "/"

        return vfs_path

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get node information.

        Args:
            path: VFS path

        Returns:
            EnhancedNodeInfo or None if not found
        """
        fs_path = self._get_fs_path(path)

        if not os.path.exists(fs_path):
            return None

        stat = await asyncio.to_thread(os.stat, fs_path)
        is_dir = os.path.isdir(fs_path)

        # Get parent path
        parent_path = str(Path(path).parent) if path != "/" else "/"

        # Get name
        name = os.path.basename(path) if path != "/" else ""

        # Get timestamps
        created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
        modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()

        return EnhancedNodeInfo(
            name=name,
            is_dir=is_dir,
            parent_path=parent_path,
            size=stat.st_size if not is_dir else 0,
            created_at=created_at,
            modified_at=modified_at,
            provider="git",
            custom_meta={
                "mode": str(
                    self.config.mode
                ),  # mode is already a string with use_enum_values
                "repo_url": self.config.repo_url,
                "ref": (
                    self.config.ref
                    if self.config.mode == GitMode.SNAPSHOT
                    else self.config.branch
                ),
            },
        )

    async def list_directory(self, path: str) -> list[str]:
        """List directory contents.

        Args:
            path: VFS path to directory

        Returns:
            List of child names (sorted)
        """
        fs_path = self._get_fs_path(path)

        if not os.path.isdir(fs_path):
            return []

        try:
            entries = await asyncio.to_thread(os.listdir, fs_path)
            # Filter out .git directory at root
            if path == "/":
                entries = [e for e in entries if e != ".git"]
            return sorted(entries)
        except Exception:
            return []

    async def read_file(self, path: str) -> bytes | None:
        """Read file content.

        Args:
            path: VFS path

        Returns:
            File content bytes or None if not found
        """
        fs_path = self._get_fs_path(path)

        if not os.path.isfile(fs_path):
            return None

        try:
            content = await asyncio.to_thread(Path(fs_path).read_bytes)
            # Update stats (mutable model)
            self._stats.reads += 1
            return content
        except Exception:
            return None

    async def write_file(self, path: str, content: bytes) -> bool:
        """Write file content.

        Only works in worktree mode.

        Args:
            path: VFS path
            content: File content bytes

        Returns:
            True if written successfully
        """
        if self.config.mode != GitMode.WORKTREE:
            print("Write operations only supported in worktree mode")
            return False

        fs_path = self._get_fs_path(path)

        try:
            # Ensure parent directory exists
            parent = os.path.dirname(fs_path)
            if parent:
                await asyncio.to_thread(os.makedirs, parent, exist_ok=True)

            # Write file
            await asyncio.to_thread(Path(fs_path).write_bytes, content)
            self._stats.writes += 1

            return True
        except Exception as e:
            print(f"Failed to write file {path}: {e}")
            return False

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a file or directory node.

        Only works in worktree mode.

        Args:
            node_info: Node information

        Returns:
            True if created successfully
        """
        if self.config.mode != GitMode.WORKTREE:
            print("Create operations only supported in worktree mode")
            return False

        path = node_info.get_path()
        fs_path = self._get_fs_path(path)

        try:
            if node_info.is_dir:
                await asyncio.to_thread(os.makedirs, fs_path, exist_ok=True)
            else:
                # Ensure parent exists
                parent = os.path.dirname(fs_path)
                if parent:
                    await asyncio.to_thread(os.makedirs, parent, exist_ok=True)
                # Create empty file
                await asyncio.to_thread(Path(fs_path).touch)

            return True
        except Exception as e:
            print(f"Failed to create node {path}: {e}")
            return False

    async def delete_node(self, path: str) -> bool:
        """Delete a file or directory node.

        Only works in worktree mode.

        Args:
            path: VFS path to delete

        Returns:
            True if deleted successfully
        """
        if self.config.mode != GitMode.WORKTREE:
            print("Delete operations only supported in worktree mode")
            return False

        fs_path = self._get_fs_path(path)

        if not os.path.exists(fs_path):
            return False

        try:
            if os.path.isdir(fs_path):
                await asyncio.to_thread(shutil.rmtree, fs_path)
            else:
                await asyncio.to_thread(os.remove, fs_path)

            return True
        except Exception as e:
            print(f"Failed to delete node {path}: {e}")
            return False

    async def exists(self, path: str) -> bool:
        """Check if path exists.

        Args:
            path: VFS path

        Returns:
            True if exists
        """
        fs_path = self._get_fs_path(path)
        return await asyncio.to_thread(os.path.exists, fs_path)

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get custom metadata for a path.

        Returns Git-specific metadata like commit info.

        Args:
            path: VFS path

        Returns:
            Metadata dict (from Pydantic model)
        """
        commit_info: GitCommitInfo | None = None

        if self.repo:
            try:
                if self.config.mode == GitMode.SNAPSHOT:
                    ref = self.config.ref or "HEAD"
                    commit = self.repo.commit(ref)
                else:
                    commit = self.repo.head.commit

                commit_info = GitCommitInfo(
                    sha=commit.hexsha,
                    message=str(commit.message),
                    author=str(commit.author),
                    date=commit.committed_datetime,
                    parents=[p.hexsha for p in commit.parents],
                )
            except Exception:
                pass

        metadata_model = GitMetadata(
            mode=self.config.mode,
            repo_url=self.config.repo_url,
            ref=self.config.ref if self.config.mode == GitMode.SNAPSHOT else None,
            branch=self.config.branch if self.config.mode == GitMode.WORKTREE else None,
            commit=commit_info,
        )

        result: dict[str, Any] = metadata_model.model_dump()
        return result

    async def set_metadata(self, path: str, metadata: dict[str, Any]) -> bool:
        """Set custom metadata for a path.

        Not supported for Git provider (metadata is derived from Git).

        Args:
            path: VFS path
            metadata: Metadata dict

        Returns:
            False (not supported)
        """
        return False

    async def get_storage_stats(self) -> dict:
        """Get storage statistics.

        Returns:
            Statistics dict (from Pydantic model)
        """
        repo_info: GitRepositoryInfo | None = None
        total_size: int | None = None

        if self.repo:
            try:
                # Get current commit info
                commit_info: GitCommitInfo | None = None
                try:
                    commit = self.repo.head.commit
                    commit_info = GitCommitInfo(
                        sha=commit.hexsha,
                        message=str(commit.message),
                        author=str(commit.author),
                        date=commit.committed_datetime,
                        parents=[p.hexsha for p in commit.parents],
                    )
                except Exception:
                    pass

                # Build repo info
                repo_info = GitRepositoryInfo(
                    active_branch=(
                        self.repo.active_branch.name
                        if self.repo.active_branch
                        else None
                    ),
                    is_dirty=self.repo.is_dirty(),
                    untracked_count=len(self.repo.untracked_files),
                    commit=commit_info,
                )

                # Get repo size
                if self._repo_path:
                    total_size = 0
                    for dirpath, _, filenames in os.walk(self._repo_path):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            if os.path.exists(fp):
                                total_size += os.path.getsize(fp)

            except Exception:
                pass

        # Build and return Pydantic model
        stats_model = GitStorageStats(
            mode=self.config.mode,
            repo_url=self.config.repo_url,
            operations=self._stats,
            repo_info=repo_info,
            total_size_bytes=total_size,
        )

        result: dict = stats_model.model_dump()
        return result

    async def cleanup(self) -> dict:
        """Cleanup resources.

        Returns:
            Cleanup statistics
        """
        # Nothing to cleanup - close() handles temp dir removal
        return {"cleaned": False}

    async def close(self) -> None:
        """Close Git provider and cleanup resources."""
        import contextlib

        # Close repo
        if self.repo:
            with contextlib.suppress(Exception):
                self.repo.close()
            self.repo = None

        # Remove temp directory if we created one
        if self._temp_dir and os.path.exists(self._temp_dir):
            with contextlib.suppress(Exception):
                shutil.rmtree(self._temp_dir)
            self._temp_dir = None

    # Git-specific operations

    async def commit(self, message: str, author: str | None = None) -> bool:
        """Commit changes in worktree mode.

        Args:
            message: Commit message
            author: Optional author string (format: "Name <email>")

        Returns:
            True if committed successfully
        """
        if self.config.mode != GitMode.WORKTREE:
            print("Commit only supported in worktree mode")
            return False

        assert self.repo is not None, "Repository must be initialized"

        try:
            # Add all changes
            await asyncio.to_thread(self.repo.git.add, "-A")

            # Check if there are changes to commit
            if not self.repo.is_dirty() and not self.repo.untracked_files:
                print("No changes to commit")
                return False

            # Commit with author if provided
            if author:
                await asyncio.to_thread(
                    self.repo.git.commit, "-m", message, f"--author={author}"
                )
            else:
                await asyncio.to_thread(self.repo.git.commit, "-m", message)

            self._stats.commits += 1
            return True

        except Exception as e:
            print(f"Failed to commit: {e}")
            return False

    async def push(self, remote: str = "origin", branch: str | None = None) -> bool:
        """Push commits to remote in worktree mode.

        Args:
            remote: Remote name (default: "origin")
            branch: Branch to push (default: current branch)

        Returns:
            True if pushed successfully
        """
        if self.config.mode != GitMode.WORKTREE:
            print("Push only supported in worktree mode")
            return False

        assert self.repo is not None, "Repository must be initialized"

        try:
            branch = branch or self.config.branch
            await asyncio.to_thread(self.repo.git.push, remote, branch)
            return True
        except Exception as e:
            print(f"Failed to push: {e}")
            return False

    async def pull(self, remote: str = "origin", branch: str | None = None) -> bool:
        """Pull changes from remote in worktree mode.

        Args:
            remote: Remote name (default: "origin")
            branch: Branch to pull (default: current branch)

        Returns:
            True if pulled successfully
        """
        if self.config.mode != GitMode.WORKTREE:
            print("Pull only supported in worktree mode")
            return False

        assert self.repo is not None, "Repository must be initialized"

        try:
            branch = branch or self.config.branch
            await asyncio.to_thread(self.repo.git.pull, remote, branch)
            return True
        except Exception as e:
            print(f"Failed to pull: {e}")
            return False

    async def get_status(self) -> dict[str, Any]:
        """Get Git status in worktree mode.

        Returns:
            Status dict with changed/untracked files (from Pydantic model)
        """
        if self.config.mode != GitMode.WORKTREE:
            return {}

        assert self.repo is not None, "Repository must be initialized"

        try:
            # Collect changed files
            changed_files: list[GitFileChange] = []
            for item in self.repo.index.diff(None):
                # Map GitPython change type to our enum
                try:
                    change_type = GitFileChangeType(item.change_type)
                except ValueError:
                    # Default to MODIFIED if unknown type
                    change_type = GitFileChangeType.MODIFIED

                changed_files.append(
                    GitFileChange(path=str(item.a_path or ""), change_type=change_type)
                )

            # Build status model
            status_model = GitStatus(
                is_dirty=self.repo.is_dirty(),
                untracked_files=list(self.repo.untracked_files),
                changed_files=changed_files,
            )

            result: dict[str, Any] = status_model.model_dump()
            return result
        except Exception:
            return {}
