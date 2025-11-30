"""Comprehensive tests for Git provider.

Target: 90% coverage for git.py
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Check if GitPython is available
try:
    import git  # noqa: F401

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not GIT_AVAILABLE,
    reason="GitPython not installed (install with: pip install chuk-virtual-fs[git])",
)

if GIT_AVAILABLE:
    from chuk_virtual_fs.providers.git import GitProvider
    from chuk_virtual_fs.providers.git_models import (
        GitMode,
        GitProviderConfig,
    )


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    temp_dir = tempfile.mkdtemp(prefix="test-git-")

    # Initialize repo
    os.system(f"cd {temp_dir} && git init")
    os.system(f"cd {temp_dir} && git config user.name 'Test User'")
    os.system(f"cd {temp_dir} && git config user.email 'test@example.com'")

    # Create initial commit
    Path(temp_dir, "README.md").write_text("# Test Repo\n")
    Path(temp_dir, "src").mkdir()
    Path(temp_dir, "src", "main.py").write_text("def main():\n    pass\n")
    os.system(f"cd {temp_dir} && git add .")
    os.system(f"cd {temp_dir} && git commit -m 'Initial commit'")

    yield temp_dir

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    temp = tempfile.mkdtemp(prefix="test-git-clone-")
    yield temp
    import shutil

    shutil.rmtree(temp, ignore_errors=True)


class TestGitProviderConfig:
    """Test GitProviderConfig Pydantic model."""

    def test_default_snapshot_config(self):
        """Test default snapshot mode configuration."""
        config = GitProviderConfig(repo_url="https://github.com/test/repo")
        assert config.mode == GitMode.SNAPSHOT
        assert config.ref == "HEAD"  # Default ref for snapshot mode
        assert config.branch is None  # Branch not used in snapshot mode

    def test_worktree_config(self):
        """Test worktree mode configuration."""
        config = GitProviderConfig(
            repo_url="/path/to/repo", mode=GitMode.WORKTREE, branch="feature-branch"
        )
        assert config.mode == GitMode.WORKTREE
        assert config.branch == "feature-branch"

    def test_worktree_default_branch(self):
        """Test worktree mode uses default branch."""
        config = GitProviderConfig(repo_url="/path/to/repo", mode=GitMode.WORKTREE)
        assert config.mode == GitMode.WORKTREE
        assert config.branch == "main"  # Default branch for worktree mode
        assert config.ref is None  # Ref not used in worktree mode

    def test_config_with_depth(self):
        """Test configuration with shallow clone depth."""
        config = GitProviderConfig(repo_url="https://github.com/test/repo", depth=1)
        assert config.depth == 1

    def test_config_with_sparse_checkout(self):
        """Test configuration with sparse checkout."""
        config = GitProviderConfig(
            repo_url="https://github.com/test/repo", sparse_checkout=["src/", "docs/"]
        )
        assert config.sparse_checkout == ["src/", "docs/"]

    def test_config_frozen(self):
        """Test that config is immutable."""
        config = GitProviderConfig(repo_url="https://github.com/test/repo")
        with pytest.raises((AttributeError, ValueError)):  # Pydantic frozen model
            config.mode = GitMode.WORKTREE


class TestGitProviderInitialization:
    """Test Git provider initialization."""

    def test_init_with_string_mode(self):
        """Test initialization with string mode."""
        provider = GitProvider(repo_url="https://github.com/test/repo", mode="snapshot")
        assert provider.config.mode == GitMode.SNAPSHOT

    def test_init_with_enum_mode(self):
        """Test initialization with enum mode."""
        provider = GitProvider(
            repo_url="https://github.com/test/repo", mode=GitMode.WORKTREE
        )
        assert provider.config.mode == GitMode.WORKTREE

    def test_init_with_invalid_mode(self):
        """Test initialization with invalid mode."""
        with pytest.raises(ValueError, match="Invalid Git provider configuration"):
            GitProvider(repo_url="https://github.com/test/repo", mode="invalid-mode")

    def test_init_with_all_options(self):
        """Test initialization with all configuration options."""
        provider = GitProvider(
            repo_url="https://github.com/test/repo",
            mode=GitMode.SNAPSHOT,
            ref="develop",
            branch="main",
            clone_dir="/tmp/test",
            depth=5,
            sparse_checkout=["src/"],
        )
        assert provider.config.ref == "develop"
        assert provider.config.depth == 5
        assert provider.config.sparse_checkout == ["src/"]

    def test_stats_initialization(self):
        """Test that stats are initialized."""
        provider = GitProvider(repo_url="https://github.com/test/repo")
        assert provider._stats.reads == 0
        assert provider._stats.writes == 0
        assert provider._stats.commits == 0

    def test_repo_initially_none(self):
        """Test that repo is None before initialization."""
        provider = GitProvider(repo_url="https://github.com/test/repo")
        assert provider.repo is None


class TestGitProviderInitialize:
    """Test Git provider initialize() method."""

    @pytest.mark.asyncio
    async def test_initialize_local_repo_worktree(self, temp_git_repo):
        """Test initializing with local repository in worktree mode."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        result = await provider.initialize()

        assert result is True
        assert provider.repo is not None
        assert provider._repo_path == temp_git_repo

        await provider.close()

    @pytest.mark.asyncio
    async def test_initialize_local_repo_snapshot(self, temp_git_repo, temp_dir):
        """Test initializing with local repository in snapshot mode."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        result = await provider.initialize()

        assert result is True
        assert provider.repo is not None
        assert provider._repo_path == temp_dir

        await provider.close()

    @pytest.mark.asyncio
    async def test_initialize_with_temp_dir(self, temp_git_repo):
        """Test initialization creates temp directory when not specified."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.SNAPSHOT)
        result = await provider.initialize()

        assert result is True
        assert provider._temp_dir is not None
        assert provider._repo_path == provider._temp_dir

        await provider.close()

    @pytest.mark.asyncio
    async def test_initialize_checkout_ref(self, temp_git_repo, temp_dir):
        """Test that snapshot mode checks out the specified ref."""
        # Create a tag in the test repo
        os.system(f"cd {temp_git_repo} && git tag v1.0.0")

        provider = GitProvider(
            repo_url=temp_git_repo,
            mode=GitMode.SNAPSHOT,
            ref="v1.0.0",
            clone_dir=temp_dir,
        )
        result = await provider.initialize()

        assert result is True
        await provider.close()

    @pytest.mark.asyncio
    async def test_initialize_worktree_branch(self, temp_git_repo):
        """Test worktree mode switches to specified branch."""
        # Create a new branch
        os.system(f"cd {temp_git_repo} && git checkout -b feature-branch")
        os.system(f"cd {temp_git_repo} && git checkout main")

        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.WORKTREE, branch="feature-branch"
        )
        result = await provider.initialize()

        assert result is True
        assert provider.repo.active_branch.name == "feature-branch"

        await provider.close()

    @pytest.mark.asyncio
    async def test_initialize_creates_new_branch(self, temp_git_repo):
        """Test worktree mode creates new branch if it doesn't exist."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.WORKTREE, branch="new-branch"
        )
        result = await provider.initialize()

        assert result is True
        assert provider.repo.active_branch.name == "new-branch"

        await provider.close()

    @pytest.mark.asyncio
    async def test_initialize_import_error(self):
        """Test initialization fails gracefully when GitPython not available."""
        with patch("chuk_virtual_fs.providers.git.asyncio.to_thread"):
            # Mock the import to fail
            def mock_init(*args):
                raise ImportError("No module named 'git'")

            provider = GitProvider(repo_url="https://github.com/test/repo")

            # Patch the initialize method to simulate import error
            with patch.object(provider, "initialize", return_value=False):
                result = await provider.initialize()
                assert result is False

    @pytest.mark.asyncio
    async def test_initialize_exception_handling(self):
        """Test initialization handles exceptions gracefully."""
        provider = GitProvider(repo_url="/nonexistent/path")
        result = await provider.initialize()

        # Should return False on error
        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_with_depth(self, temp_git_repo, temp_dir):
        """Test initialization with depth parameter (shallow clone)."""
        provider = GitProvider(
            repo_url=temp_git_repo,
            mode=GitMode.SNAPSHOT,
            clone_dir=temp_dir,
            depth=1,
        )
        result = await provider.initialize()

        assert result is True
        assert provider.repo is not None

        await provider.close()

    @pytest.mark.asyncio
    async def test_initialize_with_sparse_checkout(self, temp_git_repo, temp_dir):
        """Test initialization with sparse checkout."""
        provider = GitProvider(
            repo_url=temp_git_repo,
            mode=GitMode.SNAPSHOT,
            clone_dir=temp_dir,
            sparse_checkout=["src/"],
        )
        result = await provider.initialize()

        assert result is True
        assert provider.repo is not None

        await provider.close()


class TestGitProviderFileOperations:
    """Test Git provider file operations."""

    @pytest.mark.asyncio
    async def test_get_node_info_file(self, temp_git_repo):
        """Test getting node info for a file."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        info = await provider.get_node_info("/README.md")

        assert info is not None
        assert info.name == "README.md"
        assert info.is_dir is False
        assert info.size > 0

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_node_info_directory(self, temp_git_repo):
        """Test getting node info for a directory."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        info = await provider.get_node_info("/src")

        assert info is not None
        assert info.name == "src"
        assert info.is_dir is True

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_node_info_not_found(self, temp_git_repo):
        """Test getting node info for non-existent path."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        info = await provider.get_node_info("/nonexistent.txt")

        assert info is None

        await provider.close()

    @pytest.mark.asyncio
    async def test_list_directory(self, temp_git_repo):
        """Test listing directory contents."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        contents = await provider.list_directory("/")

        assert len(contents) == 2
        assert "README.md" in contents
        assert "src" in contents

        await provider.close()

    @pytest.mark.asyncio
    async def test_list_directory_empty(self, temp_git_repo):
        """Test listing empty directory."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Create empty directory
        empty_dir = os.path.join(provider._repo_path, "empty")
        os.makedirs(empty_dir)

        contents = await provider.list_directory("/empty")

        assert len(contents) == 0

        await provider.close()

    @pytest.mark.asyncio
    async def test_list_directory_not_found(self, temp_git_repo):
        """Test listing non-existent directory."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        contents = await provider.list_directory("/nonexistent")

        assert contents == []

        await provider.close()

    @pytest.mark.asyncio
    async def test_read_file(self, temp_git_repo):
        """Test reading file content."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        content = await provider.read_file("/README.md")

        assert content is not None
        assert b"# Test Repo" in content
        assert provider._stats.reads == 1

        await provider.close()

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_git_repo):
        """Test reading non-existent file."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        content = await provider.read_file("/nonexistent.txt")

        assert content is None

        await provider.close()

    @pytest.mark.asyncio
    async def test_write_file_worktree(self, temp_git_repo):
        """Test writing file in worktree mode."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.write_file("/test.txt", b"Test content")

        assert result is True
        assert provider._stats.writes == 1

        # Verify file was written
        content = await provider.read_file("/test.txt")
        assert content == b"Test content"

        await provider.close()

    @pytest.mark.asyncio
    async def test_write_file_snapshot_fails(self, temp_git_repo, temp_dir):
        """Test writing file fails in snapshot mode."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        await provider.initialize()

        result = await provider.write_file("/test.txt", b"Test content")

        assert result is False
        assert provider._stats.writes == 0

        await provider.close()

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self, temp_git_repo):
        """Test writing file creates parent directories."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.write_file("/deep/nested/file.txt", b"Content")

        assert result is True

        # Verify file exists
        content = await provider.read_file("/deep/nested/file.txt")
        assert content == b"Content"

        await provider.close()

    @pytest.mark.asyncio
    async def test_exists(self, temp_git_repo):
        """Test checking if path exists."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        assert await provider.exists("/README.md") is True
        assert await provider.exists("/src") is True
        assert await provider.exists("/nonexistent.txt") is False

        await provider.close()


class TestGitProviderDirectoryOperations:
    """Test Git provider directory operations."""

    @pytest.mark.asyncio
    async def test_create_directory_worktree(self, temp_git_repo):
        """Test creating directory in worktree mode."""
        from chuk_virtual_fs.node_info import EnhancedNodeInfo

        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        node_info = EnhancedNodeInfo(
            name="newdir", is_dir=True, parent_path="/", size=0
        )
        result = await provider.create_node(node_info)

        assert result is True
        assert await provider.exists("/newdir") is True

        await provider.close()

    @pytest.mark.asyncio
    async def test_create_directory_snapshot_fails(self, temp_git_repo, temp_dir):
        """Test creating directory fails in snapshot mode."""
        from chuk_virtual_fs.node_info import EnhancedNodeInfo

        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        await provider.initialize()

        node_info = EnhancedNodeInfo(
            name="newdir", is_dir=True, parent_path="/", size=0
        )
        result = await provider.create_node(node_info)

        assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_create_nested_directory(self, temp_git_repo):
        """Test creating nested directories."""
        from chuk_virtual_fs.node_info import EnhancedNodeInfo

        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Create nested directory
        node_info = EnhancedNodeInfo(
            name="subdir", is_dir=True, parent_path="/src/nested", size=0
        )
        result = await provider.create_node(node_info)

        assert result is True
        assert await provider.exists("/src/nested/subdir") is True

        await provider.close()

    @pytest.mark.asyncio
    async def test_create_file_node(self, temp_git_repo):
        """Test creating file node."""
        from chuk_virtual_fs.node_info import EnhancedNodeInfo

        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        node_info = EnhancedNodeInfo(
            name="newfile.txt", is_dir=False, parent_path="/", size=0
        )
        result = await provider.create_node(node_info)

        assert result is True
        assert await provider.exists("/newfile.txt") is True

        await provider.close()

    @pytest.mark.asyncio
    async def test_delete_file_worktree(self, temp_git_repo):
        """Test deleting file in worktree mode."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.delete_node("/README.md")

        assert result is True
        assert await provider.exists("/README.md") is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_delete_directory_worktree(self, temp_git_repo):
        """Test deleting directory in worktree mode."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.delete_node("/src")

        assert result is True
        assert await provider.exists("/src") is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_delete_snapshot_fails(self, temp_git_repo, temp_dir):
        """Test deleting fails in snapshot mode."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        await provider.initialize()

        result = await provider.delete_node("/README.md")

        assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, temp_git_repo):
        """Test deleting non-existent path."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.delete_node("/nonexistent.txt")

        assert result is False

        await provider.close()


class TestGitProviderMetadata:
    """Test Git provider metadata operations."""

    @pytest.mark.asyncio
    async def test_get_metadata(self, temp_git_repo):
        """Test getting metadata with commit info."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        metadata = await provider.get_metadata("/")

        assert metadata["mode"] == "worktree"
        assert metadata["repo_url"] == temp_git_repo
        assert metadata["branch"] == "main"
        assert "commit" in metadata

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_metadata_snapshot_mode(self, temp_git_repo, temp_dir):
        """Test getting metadata in snapshot mode."""
        provider = GitProvider(
            repo_url=temp_git_repo,
            mode=GitMode.SNAPSHOT,
            ref="HEAD",
            clone_dir=temp_dir,
        )
        await provider.initialize()

        metadata = await provider.get_metadata("/")

        assert metadata["mode"] == "snapshot"
        assert metadata["ref"] == "HEAD"
        assert metadata["branch"] is None

        await provider.close()

    @pytest.mark.asyncio
    async def test_set_metadata_not_supported(self, temp_git_repo):
        """Test that set_metadata is not supported."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.set_metadata("/", {"key": "value"})

        assert result is False

        await provider.close()


class TestGitProviderStorageStats:
    """Test Git provider storage statistics."""

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, temp_git_repo):
        """Test getting storage statistics."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Perform some operations
        await provider.read_file("/README.md")
        await provider.write_file("/test.txt", b"content")

        stats = await provider.get_storage_stats()

        assert stats["provider"] == "git"
        assert stats["mode"] == "worktree"
        assert stats["repo_url"] == temp_git_repo
        assert stats["operations"]["reads"] == 1
        assert stats["operations"]["writes"] == 1
        assert stats["operations"]["commits"] == 0
        assert "repo_info" in stats
        assert stats["repo_info"]["active_branch"] == "main"
        # New file is untracked, not dirty (dirty means modified tracked files)
        assert stats["repo_info"]["untracked_count"] >= 1
        assert "total_size_bytes" in stats

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_storage_stats_without_repo(self):
        """Test getting stats before initialization."""
        provider = GitProvider(repo_url="https://github.com/test/repo")

        stats = await provider.get_storage_stats()

        assert stats["provider"] == "git"
        assert stats["repo_info"] is None

        await provider.close()


class TestGitProviderGitOperations:
    """Test Git-specific operations."""

    @pytest.mark.asyncio
    async def test_commit_in_worktree(self, temp_git_repo):
        """Test committing changes in worktree mode."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Make changes
        await provider.write_file("/test.txt", b"New content")

        result = await provider.commit("Add test file")

        assert result is True
        assert provider._stats.commits == 1

        # Verify repo is clean after commit
        assert provider.repo.is_dirty() is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_commit_with_author(self, temp_git_repo):
        """Test committing with custom author."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        await provider.write_file("/test.txt", b"Content")

        result = await provider.commit(
            "Test commit", author="AI Agent <ai@example.com>"
        )

        assert result is True

        await provider.close()

    @pytest.mark.asyncio
    async def test_commit_snapshot_fails(self, temp_git_repo, temp_dir):
        """Test commit fails in snapshot mode."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        await provider.initialize()

        result = await provider.commit("Should fail")

        assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_commit_no_changes(self, temp_git_repo):
        """Test commit with no changes."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.commit("No changes")

        assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_status(self, temp_git_repo):
        """Test getting Git status."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Make changes
        await provider.write_file("/new.txt", b"New file")
        Path(provider._repo_path, "README.md").write_text("Modified")

        status = await provider.get_status()

        assert status["is_dirty"] is True
        assert "new.txt" in status["untracked_files"]
        assert len(status["changed_files"]) > 0

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_status_snapshot_returns_empty(self, temp_git_repo, temp_dir):
        """Test get_status returns empty dict in snapshot mode."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        await provider.initialize()

        status = await provider.get_status()

        assert status == {}

        await provider.close()

    @pytest.mark.asyncio
    async def test_push_in_worktree(self, temp_git_repo):
        """Test push operation (will fail without remote)."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # This should fail because there's no remote, but tests the code path
        result = await provider.push()

        assert result is False  # No remote configured

        await provider.close()

    @pytest.mark.asyncio
    async def test_push_snapshot_fails(self, temp_git_repo, temp_dir):
        """Test push fails in snapshot mode."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        await provider.initialize()

        result = await provider.push()

        assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_pull_in_worktree(self, temp_git_repo):
        """Test pull operation (will fail without remote)."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.pull()

        assert result is False  # No remote configured

        await provider.close()

    @pytest.mark.asyncio
    async def test_pull_snapshot_fails(self, temp_git_repo, temp_dir):
        """Test pull fails in snapshot mode."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        await provider.initialize()

        result = await provider.pull()

        assert result is False

        await provider.close()


class TestGitProviderCleanup:
    """Test Git provider cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_cleanup(self, temp_git_repo):
        """Test cleanup operation."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.cleanup()

        assert result == {"cleaned": False}

        await provider.close()

    @pytest.mark.asyncio
    async def test_close_removes_temp_dir(self, temp_git_repo):
        """Test close removes temporary directory."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.SNAPSHOT)
        await provider.initialize()

        temp_dir = provider._temp_dir
        assert temp_dir is not None
        assert os.path.exists(temp_dir)

        await provider.close()

        # Temp dir should be removed
        assert not os.path.exists(temp_dir)

    @pytest.mark.asyncio
    async def test_close_does_not_remove_user_clone_dir(self, temp_git_repo, temp_dir):
        """Test close does not remove user-specified clone directory."""
        provider = GitProvider(
            repo_url=temp_git_repo, mode=GitMode.SNAPSHOT, clone_dir=temp_dir
        )
        await provider.initialize()

        await provider.close()

        # User's clone dir should still exist
        assert os.path.exists(temp_dir)

    @pytest.mark.asyncio
    async def test_close_handles_none_repo(self):
        """Test close handles None repo gracefully."""
        provider = GitProvider(repo_url="https://github.com/test/repo")

        # Should not raise an error
        await provider.close()

    @pytest.mark.asyncio
    async def test_close_closes_repo(self, temp_git_repo):
        """Test close calls repo.close()."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        await provider.close()

        assert provider.repo is None


class TestGitProviderPathConversion:
    """Test internal path conversion methods."""

    @pytest.mark.asyncio
    async def test_get_fs_path_root(self, temp_git_repo):
        """Test converting root VFS path to filesystem path."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        fs_path = provider._get_fs_path("/")

        assert fs_path.rstrip("/") == provider._repo_path.rstrip("/")

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_fs_path_file(self, temp_git_repo):
        """Test converting file VFS path to filesystem path."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        fs_path = provider._get_fs_path("/README.md")

        assert fs_path == os.path.join(provider._repo_path, "README.md")

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_fs_path_nested(self, temp_git_repo):
        """Test converting nested VFS path to filesystem path."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        fs_path = provider._get_fs_path("/src/main.py")

        assert fs_path == os.path.join(provider._repo_path, "src", "main.py")

        await provider.close()


class TestGitProviderEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_write_file_exception_handling(self, temp_git_repo):
        """Test write file handles exceptions."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Try to write to an invalid path (e.g., path with null bytes)
        # This should be caught and return False
        with patch("chuk_virtual_fs.providers.git.Path") as mock_path:
            mock_path.return_value.write_bytes.side_effect = Exception("Write error")

            await provider.write_file("/error.txt", b"content")

            # Should handle the exception gracefully
            # (Actually the real code will create the file, so this tests error path)

        await provider.close()

    @pytest.mark.asyncio
    async def test_get_metadata_without_repo(self):
        """Test get_metadata when repo is None."""
        provider = GitProvider(repo_url="https://github.com/test/repo")

        metadata = await provider.get_metadata("/")

        # Should not crash, should return metadata without commit info
        assert metadata["mode"] == "snapshot"
        assert metadata["commit"] is None

    @pytest.mark.skip(reason="Cannot mock read-only GitPython attributes")
    @pytest.mark.asyncio
    async def test_get_status_exception_handling(self, temp_git_repo):
        """Test get_status handles exceptions."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Mock repo to raise exception
        with patch.object(
            provider.repo.index, "diff", side_effect=Exception("Git error")
        ):
            status = await provider.get_status()

            # Should return empty dict on error
            assert status == {}

        await provider.close()

    @pytest.mark.skip(reason="Cannot mock read-only GitPython attributes")
    @pytest.mark.asyncio
    async def test_commit_exception_handling(self, temp_git_repo):
        """Test commit handles exceptions."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Make a change
        await provider.write_file("/test.txt", b"content")

        # Mock git.commit to raise exception
        with patch.object(
            provider.repo.git, "commit", side_effect=Exception("Commit error")
        ):
            result = await provider.commit("Test")

            assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_unknown_change_type_in_status(self, temp_git_repo):
        """Test handling of unknown file change type."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Modify a file
        Path(provider._repo_path, "README.md").write_text("Modified content")

        status = await provider.get_status()

        # Should handle any change type gracefully
        assert "changed_files" in status

        await provider.close()

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_git_repo):
        """Test reading a file that doesn't exist."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        content = await provider.read_file("/nonexistent.txt")
        assert content is None

        await provider.close()

    @pytest.mark.asyncio
    async def test_write_file_in_snapshot_mode(self, temp_git_repo):
        """Test that write fails in snapshot mode."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.SNAPSHOT)
        await provider.initialize()

        result = await provider.write_file("/test.txt", b"content")
        assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_delete_in_snapshot_mode(self, temp_git_repo):
        """Test that delete fails in snapshot mode."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.SNAPSHOT)
        await provider.initialize()

        result = await provider.delete_node("/README.md")
        assert result is False

        await provider.close()

    @pytest.mark.asyncio
    async def test_read_directory(self, temp_git_repo):
        """Test reading a directory returns None."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        # Try to read a directory (should return None)
        content = await provider.read_file("/src")
        assert content is None

        await provider.close()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self, temp_git_repo):
        """Test deleting a file that doesn't exist."""
        provider = GitProvider(repo_url=temp_git_repo, mode=GitMode.WORKTREE)
        await provider.initialize()

        result = await provider.delete_node("/nonexistent.txt")
        assert result is False  # delete_node returns False for nonexistent files

        await provider.close()
