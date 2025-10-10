"""
chuk_virtual_fs/exceptions.py - Custom exception classes for virtual filesystem

Provides descriptive, structured exceptions for better error handling and debugging.
"""


class VirtualFSError(Exception):
    """Base exception for all virtual filesystem errors"""

    def __init__(self, message: str, path: str = None, **details):
        """
        Initialize filesystem error

        Args:
            message: Error message
            path: Path related to the error (optional)
            **details: Additional error details
        """
        self.message = message
        self.path = path
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with path and details"""
        msg = self.message

        if self.path:
            msg = f"{msg}: {self.path}"

        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            msg = f"{msg} ({detail_str})"

        return msg


# Path-related errors


class PathError(VirtualFSError):
    """Base exception for path-related errors"""


class PathNotFoundError(PathError):
    """Exception raised when a path does not exist"""

    def __init__(self, path: str, **details):
        super().__init__("Path not found", path=path, **details)


class PathExistsError(PathError):
    """Exception raised when a path already exists"""

    def __init__(self, path: str, **details):
        super().__init__("Path already exists", path=path, **details)


class InvalidPathError(PathError):
    """Exception raised when a path is invalid"""

    def __init__(self, path: str, reason: str = None, **details):
        message = "Invalid path"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message, path=path, **details)


class PathTraversalError(PathError):
    """Exception raised when attempting directory traversal attack"""

    def __init__(self, path: str, base: str = None, **details):
        message = "Path traversal detected"
        if base:
            details["base"] = base
        super().__init__(message, path=path, **details)


# Node-related errors


class NodeError(VirtualFSError):
    """Base exception for node-related errors"""


class NotAFileError(NodeError):
    """Exception raised when expecting a file but got a directory"""

    def __init__(self, path: str, **details):
        super().__init__("Not a file", path=path, **details)


class NotADirectoryError(NodeError):
    """Exception raised when expecting a directory but got a file"""

    def __init__(self, path: str, **details):
        super().__init__("Not a directory", path=path, **details)


class DirectoryNotEmptyError(NodeError):
    """Exception raised when attempting to delete non-empty directory"""

    def __init__(self, path: str, item_count: int = None, **details):
        if item_count:
            details["items"] = item_count
        super().__init__("Directory not empty", path=path, **details)


class NodeTypeError(NodeError):
    """Exception raised for node type mismatches"""

    def __init__(self, path: str, expected: str, actual: str, **details):
        super().__init__(f"Expected {expected}, got {actual}", path=path, **details)


# Permission and security errors


class PermissionError(VirtualFSError):
    """Exception raised for permission-related errors"""

    def __init__(self, path: str, operation: str = None, **details):
        message = "Permission denied"
        if operation:
            message = f"{message} for operation: {operation}"
        super().__init__(message, path=path, **details)


class SecurityViolationError(VirtualFSError):
    """Exception raised for security policy violations"""

    def __init__(
        self, message: str, path: str = None, violation_type: str = None, **details
    ):
        if violation_type:
            details["violation_type"] = violation_type
        super().__init__(message, path=path, **details)


class QuotaExceededError(VirtualFSError):
    """Exception raised when storage quota is exceeded"""

    def __init__(
        self, message: str = None, quota: int = None, attempted: int = None, **details
    ):
        if not message:
            message = "Storage quota exceeded"
        if quota:
            details["quota"] = quota
        if attempted:
            details["attempted"] = attempted
        super().__init__(message, **details)


# File operation errors


class FileOperationError(VirtualFSError):
    """Base exception for file operation errors"""


class ReadError(FileOperationError):
    """Exception raised when reading a file fails"""

    def __init__(self, path: str, reason: str = None, **details):
        message = "Failed to read file"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message, path=path, **details)


class WriteError(FileOperationError):
    """Exception raised when writing to a file fails"""

    def __init__(self, path: str, reason: str = None, **details):
        message = "Failed to write file"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message, path=path, **details)


class CopyError(FileOperationError):
    """Exception raised when copying fails"""

    def __init__(self, source: str, destination: str, reason: str = None, **details):
        message = "Failed to copy"
        if reason:
            message = f"{message}: {reason}"
        details["destination"] = destination
        super().__init__(message, path=source, **details)


class MoveError(FileOperationError):
    """Exception raised when moving fails"""

    def __init__(self, source: str, destination: str, reason: str = None, **details):
        message = "Failed to move"
        if reason:
            message = f"{message}: {reason}"
        details["destination"] = destination
        super().__init__(message, path=source, **details)


class DeleteError(FileOperationError):
    """Exception raised when deleting fails"""

    def __init__(self, path: str, reason: str = None, **details):
        message = "Failed to delete"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message, path=path, **details)


# Provider-related errors


class ProviderError(VirtualFSError):
    """Base exception for storage provider errors"""


class ProviderNotInitializedError(ProviderError):
    """Exception raised when provider is not initialized"""

    def __init__(self, provider_name: str = None, **details):
        message = "Provider not initialized"
        if provider_name:
            details["provider"] = provider_name
        super().__init__(message, **details)


class ProviderClosedError(ProviderError):
    """Exception raised when attempting to use closed provider"""

    def __init__(self, provider_name: str = None, **details):
        message = "Provider is closed"
        if provider_name:
            details["provider"] = provider_name
        super().__init__(message, **details)


class ProviderConnectionError(ProviderError):
    """Exception raised for provider connection issues"""

    def __init__(self, message: str, provider_name: str = None, **details):
        if provider_name:
            details["provider"] = provider_name
        super().__init__(message, **details)


class ProviderConfigError(ProviderError):
    """Exception raised for provider configuration errors"""

    def __init__(self, message: str, provider_name: str = None, **details):
        if provider_name:
            details["provider"] = provider_name
        super().__init__(message, **details)


# Encoding and content errors


class EncodingError(VirtualFSError):
    """Exception raised for encoding-related errors"""

    def __init__(self, path: str, encoding: str = None, reason: str = None, **details):
        message = "Encoding error"
        if reason:
            message = f"{message}: {reason}"
        if encoding:
            details["encoding"] = encoding
        super().__init__(message, path=path, **details)


class BinaryFileError(VirtualFSError):
    """Exception raised when attempting text operations on binary files"""

    def __init__(self, path: str, operation: str = None, **details):
        message = "Cannot perform text operation on binary file"
        if operation:
            message = f"{message}: {operation}"
        super().__init__(message, path=path, **details)


# Validation errors


class ValidationError(VirtualFSError):
    """Exception raised for validation failures"""

    def __init__(self, message: str, field: str = None, value=None, **details):
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = value
        super().__init__(message, **details)


class ChecksumMismatchError(ValidationError):
    """Exception raised when checksums don't match"""

    def __init__(self, path: str, expected: str, actual: str, **details):
        details.update({"expected": expected, "actual": actual})
        super().__init__("Checksum mismatch", path=path, **details)


# Convenience function for converting exceptions


def convert_error(
    error: Exception, path: str = None, operation: str = None
) -> VirtualFSError:
    """
    Convert a standard exception to a VirtualFSError

    Args:
        error: Original exception
        path: Path related to the error
        operation: Operation that caused the error

    Returns:
        Converted VirtualFSError
    """
    error_type = type(error).__name__
    message = str(error)

    if "permission" in message.lower() or "access" in message.lower():
        return PermissionError(
            path=path, operation=operation, original_error=error_type
        )

    if "not found" in message.lower() or "does not exist" in message.lower():
        return PathNotFoundError(path=path, original_error=error_type)

    if "exists" in message.lower():
        return PathExistsError(path=path, original_error=error_type)

    if "directory" in message.lower() and "not empty" in message.lower():
        return DirectoryNotEmptyError(path=path, original_error=error_type)

    # Default conversion
    return VirtualFSError(
        message=f"{error_type}: {message}",
        path=path,
        operation=operation,
        original_error=error_type,
    )
