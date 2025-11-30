"""Pydantic models and enums for Git provider.

This module defines type-safe models for Git operations.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GitMode(str, Enum):
    """Git provider operating mode."""

    SNAPSHOT = "snapshot"  # Read-only view at a specific ref
    WORKTREE = "worktree"  # Writable working directory


class GitFileChangeType(str, Enum):
    """Git file change types."""

    ADDED = "A"
    DELETED = "D"
    MODIFIED = "M"
    RENAMED = "R"
    COPIED = "C"
    UNMERGED = "U"


class GitCommitInfo(BaseModel):
    """Information about a Git commit."""

    model_config = ConfigDict(frozen=True)

    sha: str = Field(..., description="Commit SHA hash")
    message: str = Field(..., description="Commit message")
    author: str = Field(..., description="Commit author (name <email>)")
    date: datetime = Field(..., description="Commit date")
    parents: list[str] = Field(default_factory=list, description="Parent commit SHAs")


class GitFileChange(BaseModel):
    """Represents a changed file in Git."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(..., description="File path relative to repo root")
    change_type: GitFileChangeType = Field(..., description="Type of change")


class GitStatus(BaseModel):
    """Git working directory status."""

    model_config = ConfigDict(frozen=True)

    is_dirty: bool = Field(..., description="Whether working directory has changes")
    untracked_files: list[str] = Field(
        default_factory=list, description="List of untracked files"
    )
    changed_files: list[GitFileChange] = Field(
        default_factory=list, description="List of changed files"
    )


class GitProviderConfig(BaseModel):
    """Configuration for Git provider."""

    repo_url: str = Field(..., description="Git repository URL or local path")
    mode: GitMode = Field(
        default=GitMode.SNAPSHOT, description="Provider operating mode"
    )
    ref: str | None = Field(
        default=None, description="Commit SHA, tag, or branch for snapshot mode"
    )
    branch: str | None = Field(
        default=None, description="Branch name for worktree mode"
    )
    clone_dir: str | None = Field(
        default=None, description="Directory to clone into (default: temp dir)"
    )
    depth: int | None = Field(
        default=None, ge=1, description="Clone depth for shallow clones"
    )
    sparse_checkout: list[str] | None = Field(
        default=None, description="Paths for sparse checkout"
    )

    model_config = ConfigDict(use_enum_values=True, frozen=True)

    @model_validator(mode="after")
    def set_defaults(self) -> "GitProviderConfig":
        """Set default ref and branch based on mode."""
        # Set default ref for snapshot mode
        if self.ref is None and self.mode == GitMode.SNAPSHOT:
            object.__setattr__(self, "ref", "HEAD")

        # Set default branch for worktree mode
        if self.branch is None and self.mode == GitMode.WORKTREE:
            object.__setattr__(self, "branch", "main")

        return self


class GitRepositoryInfo(BaseModel):
    """Information about a Git repository."""

    model_config = ConfigDict(frozen=True)

    active_branch: str | None = Field(
        default=None, description="Currently active branch"
    )
    is_dirty: bool = Field(
        ..., description="Whether repository has uncommitted changes"
    )
    untracked_count: int = Field(
        default=0, ge=0, description="Number of untracked files"
    )
    commit: GitCommitInfo | None = Field(
        default=None, description="Current commit information"
    )


class GitOperationStats(BaseModel):
    """Statistics for Git operations."""

    model_config = ConfigDict(frozen=False)  # Mutable for stats tracking

    reads: int = Field(default=0, ge=0, description="Number of read operations")
    writes: int = Field(default=0, ge=0, description="Number of write operations")
    commits: int = Field(default=0, ge=0, description="Number of commits")


class GitStorageStats(BaseModel):
    """Complete storage statistics for Git provider."""

    model_config = ConfigDict(use_enum_values=True, frozen=True)

    provider: Literal["git"] = Field(default="git")
    mode: GitMode = Field(..., description="Operating mode")
    repo_url: str = Field(..., description="Repository URL or path")
    operations: GitOperationStats = Field(..., description="Operation statistics")
    repo_info: GitRepositoryInfo | None = Field(
        default=None, description="Repository information"
    )
    total_size_bytes: int | None = Field(
        default=None, ge=0, description="Total repository size in bytes"
    )


class GitMetadata(BaseModel):
    """Metadata for a Git-backed file or directory."""

    model_config = ConfigDict(use_enum_values=True, frozen=True)

    mode: GitMode = Field(..., description="Provider mode")
    repo_url: str = Field(..., description="Repository URL or path")
    ref: str | None = Field(default=None, description="Reference (for snapshot mode)")
    branch: str | None = Field(default=None, description="Branch (for worktree mode)")
    commit: GitCommitInfo | None = Field(default=None, description="Commit information")
