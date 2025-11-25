"""Exceptions for the mount system."""


class MountError(Exception):
    """Base exception for mount-related errors."""


class MountNotSupportedError(MountError):
    """Raised when the platform doesn't support filesystem mounting."""


class UnmountError(MountError):
    """Raised when unmounting fails."""


class MountAlreadyExistsError(MountError):
    """Raised when trying to mount at a location that's already mounted."""


class MountPointNotFoundError(MountError):
    """Raised when the mount point directory doesn't exist."""
