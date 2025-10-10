"""
Tests for path utilities module
"""

import pytest

from chuk_virtual_fs import path_utils


class TestPathNormalization:
    """Test path normalization functions"""

    def test_normalize(self):
        assert path_utils.normalize("/home//user/../john/./docs") == "/home/john/docs"
        assert path_utils.normalize("/home/user/") == "/home/user"
        # Note: Leading double slash preserved in POSIX (has special meaning)
        assert path_utils.normalize("//home//user//") == "//home/user"
        assert path_utils.normalize("/") == "/"
        assert path_utils.normalize(".") == "."

    def test_join(self):
        assert path_utils.join("/home", "user", "docs") == "/home/user/docs"
        assert path_utils.join("/home/user", "../other") == "/home/other"
        assert path_utils.join("/", "home", "user") == "/home/user"
        assert path_utils.join("/home", "user/") == "/home/user"


class TestPathComponents:
    """Test path component extraction"""

    def test_dirname(self):
        assert path_utils.dirname("/home/user/file.txt") == "/home/user"
        assert path_utils.dirname("/home/user/") == "/home/user"
        assert path_utils.dirname("/file.txt") == "/"
        assert path_utils.dirname("/") == "/"

    def test_basename(self):
        assert path_utils.basename("/home/user/file.txt") == "file.txt"
        assert path_utils.basename("/home/user/") == "user"
        assert path_utils.basename("/") == ""
        assert path_utils.basename("file.txt") == "file.txt"

    def test_split(self):
        assert path_utils.split("/home/user/file.txt") == ("/home/user", "file.txt")
        assert path_utils.split("/file.txt") == ("/", "file.txt")
        assert path_utils.split("/") == ("/", "")

    def test_splitext(self):
        assert path_utils.splitext("/home/user/file.txt") == ("/home/user/file", ".txt")
        assert path_utils.splitext("/home/user/archive.tar.gz") == (
            "/home/user/archive.tar",
            ".gz",
        )
        assert path_utils.splitext("/home/user/noext") == ("/home/user/noext", "")

    def test_extension(self):
        assert path_utils.extension("/home/user/file.txt") == ".txt"
        assert path_utils.extension("/home/user/file.txt", include_dot=False) == "txt"
        assert path_utils.extension("/home/user/noext") == ""
        assert path_utils.extension("/home/user/noext", include_dot=False) == ""

    def test_get_all_extensions(self):
        assert path_utils.get_all_extensions("/home/user/archive.tar.gz") == [
            "tar",
            "gz",
        ]
        assert path_utils.get_all_extensions("/home/user/file.txt") == ["txt"]
        assert path_utils.get_all_extensions("/home/user/noext") == []

    def test_stem(self):
        assert path_utils.stem("/home/user/file.txt") == "file"
        assert path_utils.stem("/home/user/archive.tar.gz") == "archive.tar"
        assert path_utils.stem("/home/user/noext") == "noext"

    def test_parts(self):
        assert path_utils.parts("/home/user/docs/file.txt") == [
            "/",
            "home",
            "user",
            "docs",
            "file.txt",
        ]
        assert path_utils.parts("/") == ["/"]
        assert path_utils.parts("/home") == ["/", "home"]


class TestPathAnalysis:
    """Test path analysis functions"""

    def test_is_absolute(self):
        assert path_utils.is_absolute("/home/user") is True
        assert path_utils.is_absolute("user/docs") is False
        assert path_utils.is_absolute("/") is True

    def test_is_relative(self):
        assert path_utils.is_relative("user/docs") is True
        assert path_utils.is_relative("/home/user") is False

    def test_depth(self):
        assert path_utils.depth("/") == 0
        assert path_utils.depth("/home") == 1
        assert path_utils.depth("/home/user") == 2
        assert path_utils.depth("/home/user/docs/file.txt") == 4

    def test_parent(self):
        assert path_utils.parent("/home/user/docs/file.txt") == "/home/user/docs"
        assert path_utils.parent("/home/user/docs/file.txt", levels=2) == "/home/user"
        assert path_utils.parent("/home", levels=5) == "/"

    def test_is_parent(self):
        assert path_utils.is_parent("/home/user", "/home/user/docs/file.txt") is True
        assert path_utils.is_parent("/home/user", "/home/other") is False
        assert path_utils.is_parent("/", "/home/user") is True
        assert path_utils.is_parent("/home/user", "/home/user") is False

    def test_is_child(self):
        assert path_utils.is_child("/home/user/docs/file.txt", "/home/user") is True
        assert path_utils.is_child("/home/other", "/home/user") is False

    def test_relative_to(self):
        assert (
            path_utils.relative_to("/home/user/docs/file.txt", "/home/user")
            == "docs/file.txt"
        )
        assert path_utils.relative_to("/home/user/docs", "/home") == "user/docs"

    def test_common_path(self):
        assert (
            path_utils.common_path("/home/user/docs", "/home/user/pictures")
            == "/home/user"
        )
        assert path_utils.common_path("/home/user", "/var/log") == "/"
        assert path_utils.common_path() == "/"


class TestExtensionUtilities:
    """Test extension-related utilities"""

    def test_has_extension(self):
        assert path_utils.has_extension("/home/user/file.txt", ".txt", ".md") is True
        assert path_utils.has_extension("/home/user/file.txt", "txt", "md") is True
        assert path_utils.has_extension("/home/user/file.txt", ".pdf") is False
        assert (
            path_utils.has_extension("/home/user/file.txt", "TXT") is True
        )  # Case insensitive

    def test_change_extension(self):
        assert (
            path_utils.change_extension("/home/user/file.txt", ".md")
            == "/home/user/file.md"
        )
        assert (
            path_utils.change_extension("/home/user/file.txt", "pdf")
            == "/home/user/file.pdf"
        )
        assert (
            path_utils.change_extension("/home/user/noext", ".txt")
            == "/home/user/noext.txt"
        )


class TestSlashUtilities:
    """Test trailing slash utilities"""

    def test_ensure_trailing_slash(self):
        assert path_utils.ensure_trailing_slash("/home/user") == "/home/user/"
        assert path_utils.ensure_trailing_slash("/home/user/") == "/home/user/"

    def test_remove_trailing_slash(self):
        assert path_utils.remove_trailing_slash("/home/user/") == "/home/user"
        assert path_utils.remove_trailing_slash("/home/user") == "/home/user"
        assert path_utils.remove_trailing_slash("/") == "/"


class TestSafety:
    """Test security-related functions"""

    def test_safe_join_success(self):
        assert (
            path_utils.safe_join("/home/user", "docs", "file.txt")
            == "/home/user/docs/file.txt"
        )
        assert path_utils.safe_join("/home/user", "docs/../other") == "/home/user/other"

    def test_safe_join_failure(self):
        with pytest.raises(ValueError):
            path_utils.safe_join("/home/user", "../../etc/passwd")

        with pytest.raises(ValueError):
            path_utils.safe_join("/home/user", "../other/file.txt")


class TestPatternMatching:
    """Test pattern matching"""

    def test_glob_match(self):
        assert path_utils.glob_match("/home/user/file.txt", "*.txt") is True
        assert path_utils.glob_match("/home/user/file.txt", "/home/*/file.txt") is True
        assert path_utils.glob_match("/home/user/file.txt", "*.pdf") is False
        assert path_utils.glob_match("/home/user/file.txt", "/home/user/*") is True
