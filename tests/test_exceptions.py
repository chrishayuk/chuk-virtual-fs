"""
Tests for exception classes
"""

from chuk_virtual_fs import exceptions


class TestBaseException:
    """Test base VirtualFSError exception"""

    def test_base_exception_message(self):
        error = exceptions.VirtualFSError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.path is None

    def test_base_exception_with_path(self):
        error = exceptions.VirtualFSError("Test error", path="/test/path")
        assert "/test/path" in str(error)
        assert error.path == "/test/path"

    def test_base_exception_with_details(self):
        error = exceptions.VirtualFSError("Test error", path="/test", reason="because")
        assert "reason=because" in str(error)
        assert error.details["reason"] == "because"


class TestPathErrors:
    """Test path-related exceptions"""

    def test_path_not_found_error(self):
        error = exceptions.PathNotFoundError("/missing/file.txt")
        assert "not found" in str(error).lower()
        assert error.path == "/missing/file.txt"

    def test_path_exists_error(self):
        error = exceptions.PathExistsError("/existing/file.txt")
        assert "exists" in str(error).lower()
        assert error.path == "/existing/file.txt"

    def test_invalid_path_error(self):
        error = exceptions.InvalidPathError("/invalid", reason="contains null byte")
        assert "invalid" in str(error).lower()
        assert error.path == "/invalid"

    def test_path_traversal_error(self):
        error = exceptions.PathTraversalError("../../etc/passwd", base="/home/user")
        assert "traversal" in str(error).lower()
        assert error.path == "../../etc/passwd"
        assert error.details["base"] == "/home/user"


class TestNodeErrors:
    """Test node-related exceptions"""

    def test_not_a_file_error(self):
        error = exceptions.NotAFileError("/path/to/directory")
        assert "not a file" in str(error).lower()
        assert error.path == "/path/to/directory"

    def test_not_a_directory_error(self):
        error = exceptions.NotADirectoryError("/path/to/file.txt")
        assert "not a directory" in str(error).lower()
        assert error.path == "/path/to/file.txt"

    def test_directory_not_empty_error(self):
        error = exceptions.DirectoryNotEmptyError("/path/to/dir", item_count=5)
        assert "not empty" in str(error).lower()
        assert error.path == "/path/to/dir"
        assert error.details["items"] == 5

    def test_node_type_error(self):
        error = exceptions.NodeTypeError("/path", expected="file", actual="directory")
        assert "expected file" in str(error).lower()
        assert "got directory" in str(error).lower()


class TestSecurityErrors:
    """Test security-related exceptions"""

    def test_permission_error(self):
        error = exceptions.PermissionError("/protected/file", operation="write")
        assert "permission denied" in str(error).lower()
        assert error.path == "/protected/file"

    def test_security_violation_error(self):
        error = exceptions.SecurityViolationError(
            "Access denied", path="/restricted", violation_type="path_restriction"
        )
        assert "access denied" in str(error).lower()
        assert error.details["violation_type"] == "path_restriction"

    def test_quota_exceeded_error(self):
        error = exceptions.QuotaExceededError(quota=1000000, attempted=2000000)
        assert "quota exceeded" in str(error).lower()
        assert error.details["quota"] == 1000000
        assert error.details["attempted"] == 2000000


class TestFileOperationErrors:
    """Test file operation exceptions"""

    def test_read_error(self):
        error = exceptions.ReadError("/file.txt", reason="disk error")
        assert "failed to read" in str(error).lower()
        assert error.path == "/file.txt"

    def test_write_error(self):
        error = exceptions.WriteError("/file.txt", reason="read only")
        assert "failed to write" in str(error).lower()
        assert error.path == "/file.txt"

    def test_copy_error(self):
        error = exceptions.CopyError("/source.txt", "/dest.txt", reason="no space")
        assert "failed to copy" in str(error).lower()
        assert error.path == "/source.txt"
        assert error.details["destination"] == "/dest.txt"

    def test_move_error(self):
        error = exceptions.MoveError("/source.txt", "/dest.txt", reason="cross device")
        assert "failed to move" in str(error).lower()
        assert error.path == "/source.txt"
        assert error.details["destination"] == "/dest.txt"

    def test_delete_error(self):
        error = exceptions.DeleteError("/file.txt", reason="in use")
        assert "failed to delete" in str(error).lower()
        assert error.path == "/file.txt"


class TestProviderErrors:
    """Test provider-related exceptions"""

    def test_provider_not_initialized_error(self):
        error = exceptions.ProviderNotInitializedError(provider_name="s3")
        assert "not initialized" in str(error).lower()
        assert error.details["provider"] == "s3"

    def test_provider_closed_error(self):
        error = exceptions.ProviderClosedError(provider_name="memory")
        assert "closed" in str(error).lower()
        assert error.details["provider"] == "memory"

    def test_provider_connection_error(self):
        error = exceptions.ProviderConnectionError(
            "Connection timeout", provider_name="s3"
        )
        assert "connection timeout" in str(error).lower()
        assert error.details["provider"] == "s3"

    def test_provider_config_error(self):
        error = exceptions.ProviderConfigError(
            "Missing credentials", provider_name="s3"
        )
        assert "missing credentials" in str(error).lower()
        assert error.details["provider"] == "s3"


class TestEncodingErrors:
    """Test encoding-related exceptions"""

    def test_encoding_error(self):
        error = exceptions.EncodingError(
            "/file.txt", encoding="utf-8", reason="invalid byte sequence"
        )
        assert "encoding error" in str(error).lower()
        assert error.path == "/file.txt"
        assert error.details["encoding"] == "utf-8"

    def test_binary_file_error(self):
        error = exceptions.BinaryFileError("/binary.dat", operation="read_text")
        assert "binary file" in str(error).lower()
        assert error.path == "/binary.dat"


class TestValidationErrors:
    """Test validation-related exceptions"""

    def test_validation_error(self):
        error = exceptions.ValidationError("Invalid value", field="size", value=-1)
        assert "invalid value" in str(error).lower()
        assert error.details["field"] == "size"
        assert error.details["value"] == -1

    def test_checksum_mismatch_error(self):
        error = exceptions.ChecksumMismatchError(
            "/file.txt", expected="abc123", actual="def456"
        )
        assert "checksum mismatch" in str(error).lower()
        assert error.details["expected"] == "abc123"
        assert error.details["actual"] == "def456"


class TestErrorConversion:
    """Test convert_error utility function"""

    def test_convert_permission_error(self):
        original = Exception("Permission denied")
        converted = exceptions.convert_error(
            original, path="/file.txt", operation="write"
        )
        assert isinstance(converted, exceptions.PermissionError)
        assert converted.path == "/file.txt"

    def test_convert_not_found_error(self):
        original = Exception("File not found")
        converted = exceptions.convert_error(original, path="/missing.txt")
        assert isinstance(converted, exceptions.PathNotFoundError)
        assert converted.path == "/missing.txt"

    def test_convert_exists_error(self):
        original = Exception("File exists")
        converted = exceptions.convert_error(original, path="/existing.txt")
        assert isinstance(converted, exceptions.PathExistsError)

    def test_convert_directory_not_empty_error(self):
        original = Exception("Directory not empty")
        converted = exceptions.convert_error(original, path="/dir")
        assert isinstance(converted, exceptions.DirectoryNotEmptyError)

    def test_convert_generic_error(self):
        original = Exception("Something went wrong")
        converted = exceptions.convert_error(
            original, path="/file.txt", operation="read"
        )
        assert isinstance(converted, exceptions.VirtualFSError)
        assert converted.path == "/file.txt"
        assert converted.details["operation"] == "read"
