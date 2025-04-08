"""
tests/chuk_virtual_fs/filesystem/test_fs_manager_provider.py
"""
import pytest
from chuk_virtual_fs.fs_manager import VirtualFileSystem
from chuk_virtual_fs.node_info import FSNodeInfo

# Fixture that creates a VirtualFileSystem using the memory provider
# and sets up the basic directory structure.
@pytest.fixture
def vfs():
    fs = VirtualFileSystem(provider_name="memory")
    # Explicitly create the basic directories expected by most tests.
    for directory in ["/bin", "/home", "/tmp", "/etc"]:
        # Use mkdir to create a directory; if it exists already, the test might expect mkdir to return False,
        # so we ignore duplicate failures.
        fs.mkdir(directory)
    return fs

def test_resolve_path(vfs):
    # Test absolute path remains unchanged.
    assert vfs.resolve_path("/etc") == "/etc"
    vfs.current_directory_path = "/home/user"
    assert vfs.resolve_path("docs") == "/home/user/docs"
    vfs.current_directory_path = "/home/user"
    resolved = vfs.resolve_path("./../bin")
    assert resolved == "/home/bin"
    assert vfs.resolve_path("") == "/home/user"

def test_mkdir(vfs):
    result = vfs.mkdir("/projects")
    assert result is True
    result_dup = vfs.mkdir("/projects")
    assert result_dup is False
    node = vfs.get_node_info("/projects")
    assert node is not None and node.is_dir

def test_touch(vfs):
    result = vfs.touch("/home/test.txt")
    assert result is True
    result_dup = vfs.touch("/home/test.txt")
    assert result_dup is True
    node = vfs.get_node_info("/home/test.txt")
    assert node is not None and not node.is_dir

def test_write_and_read_file(vfs):
    text = "Hello Virtual FS!"
    result = vfs.write_file("/etc/welcome.txt", text)
    assert result is True
    content = vfs.read_file("/etc/welcome.txt")
    assert content == text

def test_rm_file(vfs):
    vfs.touch("/tmp/remove_me.txt")
    assert vfs.get_node_info("/tmp/remove_me.txt") is not None
    result = vfs.rm("/tmp/remove_me.txt")
    assert result is True
    assert vfs.get_node_info("/tmp/remove_me.txt") is None

def test_rmdir(vfs):
    result = vfs.mkdir("/tmp/emptydir")
    assert result is True
    rm_result = vfs.rmdir("/tmp/emptydir")
    assert rm_result is True
    rm_nonexistent = vfs.rmdir("/tmp/emptydir")
    assert rm_nonexistent is False

def test_ls(vfs):
    listing = vfs.ls("/")
    expected = {"bin", "home", "tmp", "etc"}
    for d in expected:
        assert d in listing, f"Expected directory '{d}' in root listing, got {listing}"

def test_cd_and_pwd(vfs):
    result = vfs.cd("/home")
    assert result is True
    assert vfs.pwd() == "/home"
    assert vfs.mkdir("/home/user") is True
    result2 = vfs.cd("user")
    assert result2 is True
    assert vfs.pwd() == "/home/user"
    vfs.touch("/home/user/file.txt")
    result_fail = vfs.cd("file.txt")
    assert result_fail is False

def test_get_storage_stats(vfs):
    stats = vfs.get_storage_stats()
    assert isinstance(stats, dict)
    assert stats.get("directory_count", 0) >= 4
    assert "file_count" in stats

def test_cleanup(vfs):
    assert vfs.touch("/tmp/tempfile.txt") is True
    text = "Temporary data"
    assert vfs.write_file("/tmp/tempfile.txt", text) is True
    stats_before = vfs.get_storage_stats()
    size_before = stats_before.get("total_size_bytes", 0)
    result = vfs.cleanup()
    assert result.get("files_removed", 0) >= 1
    assert result.get("bytes_freed", 0) > 0
    assert vfs.get_node_info("/tmp/tempfile.txt") is None

def test_get_node_info(vfs):
    vfs.touch("/etc/test_motd.txt")
    node_info = vfs.get_node_info("/etc/test_motd.txt")
    assert node_info is not None
    assert isinstance(node_info, FSNodeInfo)

def test_cp_and_mv(vfs):
    vfs.write_file("/tmp/source.txt", "Copy content")
    assert vfs.cp("/tmp/source.txt", "/tmp/destination.txt") is True
    assert vfs.read_file("/tmp/destination.txt") == "Copy content"
    assert vfs.mv("/tmp/source.txt", "/tmp/moved.txt") is True
    assert vfs.read_file("/tmp/moved.txt") == "Copy content"
    assert vfs.get_node_info("/tmp/source.txt") is None

def test_find_and_search(vfs):
    vfs.mkdir("/test_search")
    vfs.write_file("/test_search/file1.txt", "Content 1")
    vfs.write_file("/test_search/file2.txt", "Content 2")
    vfs.write_file("/test_search/file3.log", "Content 3")
    found_files = vfs.find("/test_search")
    assert set(found_files) == {
        "/test_search/file1.txt",
        "/test_search/file2.txt",
        "/test_search/file3.log"
    }
    txt_files = vfs.search("/test_search", "*.txt")
    assert set(txt_files) == {
        "/test_search/file1.txt",
        "/test_search/file2.txt"
    }

def test_get_fs_info(vfs):
    fs_info = vfs.get_fs_info()
    assert isinstance(fs_info, dict)
    assert "current_directory" in fs_info
    assert "provider_name" in fs_info
    assert "storage_stats" in fs_info
    assert "total_files" in fs_info

def test_change_provider(vfs):
    # Change provider resets the filesystem to a blank state.
    result = vfs.change_provider("memory")
    assert result is True
    assert vfs.pwd() == "/"
    listing = vfs.ls("/")
    # Since the virtual filesystem now always starts blank,
    # we expect that no directories exist after provider change.
    assert listing == [], f"Expected an empty listing after provider change, got {listing}"
