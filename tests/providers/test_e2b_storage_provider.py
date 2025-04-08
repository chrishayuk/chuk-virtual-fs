"""
tests/filesystem/providers/test_e2b_storage_provider.py
"""
import os
import posixpath
import json
import sys
import time
import pytest
from unittest.mock import MagicMock, patch

# Add src directory to Python path
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Adjust import path based on project structure
from chuk_virtual_fs.providers.e2b import E2BStorageProvider
from chuk_virtual_fs.node_info import FSNodeInfo

# Skip all tests if e2b_code_interpreter is not installed
pytest.importorskip("e2b_code_interpreter")

class MockSandbox:
    """Mock Sandbox class for testing E2B provider without actual E2B API calls"""
    
    def __init__(self, sandbox_id=None, **kwargs):
        self.sandbox_id = sandbox_id or "mock-sandbox-123"
        self.files = MagicMock()
        self.commands = MagicMock()
        self.run_code = MagicMock()
        
        # Setup default behaviors
        self.files.list = MagicMock(return_value=[])
        self.files.read = MagicMock(return_value="")
        self.files.write = MagicMock(return_value=True)
        
        # Command execution results
        self.command_result = MagicMock()
        self.command_result.exit_code = 0
        self.command_result.stdout = ""
        self.commands.run.return_value = self.command_result
    
    @classmethod
    def connect(cls, sandbox_id):
        """Mock connect to existing sandbox"""
        return cls(sandbox_id=sandbox_id)
    
    @classmethod
    def list(cls):
        """Mock list of running sandboxes"""
        return [MagicMock(sandbox_id="mock-sandbox-123")]

@pytest.fixture
def mock_sandbox():
    """Fixture to create and configure a mock sandbox"""
    sandbox = MockSandbox()
    
    # Configure root directory check
    def mock_stat_command(command):
        if "stat" in command and "2>/dev/null" in command:
            result = MagicMock()
            if "/home/user/vfs_test" in command:
                result.exit_code = 0
                result.stdout = "directory"
            else:
                result.exit_code = 1
                result.stdout = "not_found"
            return result
        elif "ls" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = ""
            return result
        elif "mkdir" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = ""
            return result
        return sandbox.command_result
    
    sandbox.commands.run.side_effect = mock_stat_command
    return sandbox

@pytest.fixture
def provider(mock_sandbox):
    """Fixture to create an E2B provider with mocked sandbox"""
    with patch('e2b_code_interpreter.Sandbox', return_value=mock_sandbox) as mock_sandbox_class:
        mock_sandbox_class.connect = MockSandbox.connect
        mock_sandbox_class.list = MockSandbox.list
        
        prov = E2BStorageProvider(root_dir="/home/user/vfs_test")
        assert prov.initialize() is True
        yield prov

def test_initialize(provider, mock_sandbox):
    """Test that the provider initializes properly"""
    # The root node ("/") should exist after initialization
    root_info = provider.get_node_info("/")
    assert root_info is not None
    assert root_info.name == ""
    assert root_info.is_dir is True
    
    # Should have checked if the root directory exists and created it if needed
    mock_sandbox.commands.run.assert_any_call("mkdir -p /home/user/vfs_test")

def test_create_node_file(provider, mock_sandbox):
    """Test creating a file node"""
    # Configure mock to recognize node creation
    def mock_touch_command(command):
        result = MagicMock()
        result.exit_code = 0
        result.stdout = ""
        return result
    
    mock_sandbox.commands.run.side_effect = mock_touch_command
    
    # Set up directory check for /home to return it exists
    def mock_stat(path):
        if path == "/home/user/vfs_test/home":
            result = MagicMock()
            result.exit_code = 0
            result.stdout = "directory"
            return result
        result = MagicMock()
        result.exit_code = 1
        return result
    
    provider._check_path_exists = MagicMock(return_value=True)
    
    # First, create a parent directory /home
    home_info = FSNodeInfo(name="home", is_dir=True, parent_path="/")
    assert provider.create_node(home_info) is True
    
    # Create a file under /home
    file_info = FSNodeInfo(name="test.txt", is_dir=False, parent_path="/home")
    result = provider.create_node(file_info)
    assert result is True
    
    # Verify touch command was called
    mock_sandbox.commands.run.assert_any_call("touch /home/user/vfs_test/home/test.txt")

def test_list_directory(provider, mock_sandbox):
    """Test listing a directory"""
    # Configure mock to return directory contents
    def mock_ls_command(command):
        if "ls -A /home/user/vfs_test/docs" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = "a.txt\nb.txt"
            return result
        result = MagicMock()
        result.exit_code = 0
        result.stdout = ""
        return result
    
    mock_sandbox.commands.run.side_effect = mock_ls_command
    
    # Mock get_node_info to say /docs exists and is a directory
    provider.get_node_info = MagicMock(return_value=FSNodeInfo("docs", True, "/"))
    
    # List the directory
    listing = provider.list_directory("/docs")
    
    # The listing should contain "a.txt" and "b.txt"
    assert set(listing) == {"a.txt", "b.txt"}
    mock_sandbox.commands.run.assert_any_call("ls -A /home/user/vfs_test/docs")

def test_write_and_read_file(provider, mock_sandbox):
    """Test writing and reading a file"""
    # Mock file existence check
    provider.get_node_info = MagicMock(return_value=FSNodeInfo("log.txt", False, "/logs"))
    
    # Configure file read mock
    test_content = "This is a test log."
    mock_sandbox.files.read.return_value = test_content
    
    # Write file content
    result = provider.write_file("/logs/log.txt", test_content)
    assert result is True
    
    # Verify file.write was called with correct path and content
    mock_sandbox.files.write.assert_called()
    
    # Read back the file content
    read_content = provider.read_file("/logs/log.txt")
    assert read_content == test_content
    
    # Verify file.read was called with correct path
    mock_sandbox.files.read.assert_called_with("/home/user/vfs_test/logs/log.txt")

def test_delete_node_file(provider, mock_sandbox):
    """Test deleting a file node"""
    # Mock file existence check
    provider.get_node_info = MagicMock(return_value=FSNodeInfo("delete_me.txt", False, "/temp"))
    
    # Configure rm command to succeed
    def mock_rm_command(command):
        if "rm /home/user/vfs_test/temp/delete_me.txt" in command:
            result = MagicMock()
            result.exit_code = 0
            return result
        result = MagicMock()
        result.exit_code = 1
        return result
    
    mock_sandbox.commands.run.side_effect = mock_rm_command
    
    # Delete the file
    result = provider.delete_node("/temp/delete_me.txt")
    assert result is True
    
    # Verify rm command was called
    mock_sandbox.commands.run.assert_any_call("rm /home/user/vfs_test/temp/delete_me.txt")

def test_delete_node_directory_nonempty(provider, mock_sandbox):
    """Test that deleting a non-empty directory fails"""
    # Mock directory existence check
    provider.get_node_info = MagicMock(return_value=FSNodeInfo("nonempty", True, "/"))
    
    # Configure ls command to show directory has contents
    def mock_ls_command(command):
        if "ls -A /home/user/vfs_test/nonempty" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = "child.txt"
            return result
        result = MagicMock()
        result.exit_code = 0
        result.stdout = ""
        return result
    
    mock_sandbox.commands.run.side_effect = mock_ls_command
    
    # Attempt to delete the non-empty directory should fail
    result = provider.delete_node("/nonempty")
    assert result is False

def test_get_storage_stats(provider, mock_sandbox):
    """Test getting storage statistics"""
    # Configure command mocks for stats
    def mock_stats_command(command):
        if "find /home/user/vfs_test -type d | wc -l" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = "3"
            return result
        elif "find /home/user/vfs_test -type f | wc -l" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = "2"
            return result
        elif "du -sb /home/user/vfs_test | cut -f1" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = "1024"
            return result
        result = MagicMock()
        result.exit_code = 0
        result.stdout = ""
        return result
    
    mock_sandbox.commands.run.side_effect = mock_stats_command
    
    stats = provider.get_storage_stats()
    assert isinstance(stats, dict)
    
    # Verify stats have expected fields
    assert stats["directory_count"] == 3
    assert stats["file_count"] == 2
    assert stats["total_size_bytes"] == 1024
    assert stats["total_size_mb"] == 1024 / (1024 * 1024)
    assert stats["node_count"] == 5  # 3 directories + 2 files
    assert stats["sandbox_id"] == mock_sandbox.sandbox_id
    assert stats["root_dir"] == "/home/user/vfs_test"

def test_cleanup(provider, mock_sandbox):
    """Test cleanup operation"""
    # Set initial stats
    provider._stats = {
        "total_size_bytes": 2048,
        "file_count": 5,
        "directory_count": 3
    }
    
    # Configure cleanup command
    def mock_cleanup_command(command):
        if "mkdir -p /home/user/vfs_test/tmp" in command:
            result = MagicMock()
            result.exit_code = 0
            return result
        elif "find /home/user/vfs_test/tmp -type f -delete" in command:
            result = MagicMock()
            result.exit_code = 0
            return result
        # Updated stats after cleanup
        elif "find /home/user/vfs_test -type f | wc -l" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = "3"  # Removed 2 files
            return result
        elif "du -sb /home/user/vfs_test | cut -f1" in command:
            result = MagicMock()
            result.exit_code = 0
            result.stdout = "1024"  # Freed 1024 bytes
            return result
        result = MagicMock()
        result.exit_code = 0
        result.stdout = ""
        return result
    
    mock_sandbox.commands.run.side_effect = mock_cleanup_command
    
    # Run cleanup
    result = provider.cleanup()
    
    # Verify cleanup results
    assert "bytes_freed" in result
    assert result["bytes_freed"] == 1024  # 2048 - 1024
    assert result["files_removed"] == 2   # 5 - 3
    assert result["sandbox_id"] == mock_sandbox.sandbox_id

def test_sandbox_reconnection(mock_sandbox):
    """Test reconnecting to an existing sandbox"""
    with patch('e2b_code_interpreter.Sandbox', return_value=mock_sandbox) as mock_sandbox_class:
        mock_sandbox_class.connect = MockSandbox.connect
        mock_sandbox_class.list = MockSandbox.list
        
        # First create a provider with a new sandbox
        prov1 = E2BStorageProvider(root_dir="/home/user/vfs_test")
        assert prov1.initialize() is True
        
        # Store the sandbox ID
        sandbox_id = prov1.sandbox_id
        
        # Now create a new provider with this sandbox ID
        prov2 = E2BStorageProvider(sandbox_id=sandbox_id, root_dir="/home/user/vfs_test")
        assert prov2.initialize() is True
        
        # Verify connect was called with the correct ID
        mock_sandbox_class.connect.assert_called_with(sandbox_id)