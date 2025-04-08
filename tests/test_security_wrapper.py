"""
tests/test_security_wrapper.py - Comprehensive Security Testing
"""
import pytest
import re
from typing import List, Dict, Any

from chuk_virtual_fs import (
    VirtualFileSystem,
    SecurityWrapper,
    create_secure_provider,
    get_available_profiles,
    get_profile_settings
)
from chuk_virtual_fs.providers import get_provider
from chuk_virtual_fs.node_info import FSNodeInfo


class TestSecurityWrapper:
    """Test the SecurityWrapper implementation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.provider = get_provider("memory")
        self.provider.initialize()
        
    def test_basic_initialization(self):
        """Test basic initialization of security wrapper"""
        wrapper = SecurityWrapper(self.provider)
        assert wrapper.max_file_size == 10 * 1024 * 1024  # 10MB
        assert wrapper.max_total_size == 100 * 1024 * 1024  # 100MB
        assert wrapper.read_only is False
        assert wrapper.allowed_paths == ["/"]
        assert len(wrapper.denied_paths) > 0
        assert len(wrapper.denied_patterns) > 0
        
    def test_readonly_mode(self):
        """Test read-only mode restrictions"""
        # Create a read-only wrapper
        wrapper = SecurityWrapper(self.provider, read_only=True)
        # Setup test data before applying read-only check
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("test.txt", False, "/"))
        wrapper.provider.write_file("/test.txt", "Test content")
        wrapper._in_setup = False
        
        # Verify read operations work
        assert wrapper.get_node_info("/test.txt") is not None
        assert wrapper.read_file("/test.txt") == "Test content"
        
        # Verify write operations are blocked
        assert wrapper.write_file("/test.txt", "Modified content") is False
        assert wrapper.create_node(FSNodeInfo("new.txt", False, "/")) is False
        assert wrapper.delete_node("/test.txt") is False
        
        # Verify violation log for the three blocked operations
        violations = wrapper.get_violation_log()
        assert len(violations) == 3
        for violation in violations:
            assert "read-only mode" in violation["reason"]
            
    def test_file_size_limit(self):
        """Test file size limit restrictions"""
        max_size = 100  # 100 bytes
        wrapper = SecurityWrapper(self.provider, max_file_size=max_size)
        
        # Create a file node first
        wrapper.create_node(FSNodeInfo("small.txt", False, "/"))
        
        # Test small file (within limit)
        small_content = "x" * 50
        assert wrapper.write_file("/small.txt", small_content) is True
        
        # Test large file (exceeds limit)
        large_content = "x" * 200
        assert wrapper.write_file("/small.txt", large_content) is False
        
        # Verify violation log
        violations = wrapper.get_violation_log()
        assert len(violations) == 1
        assert "File size exceeds maximum" in violations[0]["reason"]
        
    def test_allowed_paths(self):
        """Test allowed paths restrictions"""
        allowed = ["/home", "/tmp"]
        wrapper = SecurityWrapper(self.provider, allowed_paths=allowed)
        
        # Setup allowed paths if needed
        wrapper._setup_allowed_paths()
        
        # Test nodes created in allowed paths
        assert wrapper.create_node(FSNodeInfo("test.txt", False, "/home")) is True
        assert wrapper.create_node(FSNodeInfo("temp.txt", False, "/tmp")) is True
        
        # Test node creation outside allowed areas (should be blocked)
        assert wrapper.create_node(FSNodeInfo("blocked.txt", False, "/etc")) is False
        
        # Verify violation log
        violations = wrapper.get_violation_log()
        assert len(violations) == 1
        assert "Path not in allowed paths list" in violations[0]["reason"]
    
    def test_denied_paths(self):
        """Test denied paths restrictions"""
        denied = ["/etc/passwd", "/private"]
        wrapper = SecurityWrapper(self.provider, denied_paths=denied)
        
        # Create parent directory first during setup phase
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("home", True, "/"))
        wrapper._in_setup = False
        
        # Create a node in an allowed path
        assert wrapper.create_node(FSNodeInfo("test.txt", False, "/home")) is True
        
        # Set up denied path structure
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("etc", True, "/"))
        wrapper.provider.create_node(FSNodeInfo("passwd", True, "/etc"))
        wrapper._in_setup = False
        
        # Attempt to create a node in a denied path; should be blocked
        assert wrapper.create_node(FSNodeInfo("block.txt", False, "/etc/passwd")) is False
        
        # Verify violation log
        violations = wrapper.get_violation_log()
        assert len(violations) > 0
        assert any("Path in denied paths list" in v["reason"] for v in violations)
    
    def test_denied_patterns(self):
        """Test denied patterns restrictions"""
        patterns = [r"\.exe$", r"^\."]
        wrapper = SecurityWrapper(self.provider, denied_patterns=patterns)
        
        # Test node with a normal filename (allowed)
        assert wrapper.create_node(FSNodeInfo("test.txt", False, "/")) is True
        
        # Test node creation that matches denied patterns
        assert wrapper.create_node(FSNodeInfo("test.exe", False, "/")) is False
        assert wrapper.create_node(FSNodeInfo(".hidden", False, "/")) is False
        
        # Verify violation log contains pattern-match violations
        violations = wrapper.get_violation_log()
        assert len(violations) == 2
        assert "Path matches denied pattern" in violations[0]["reason"]
        
    def test_path_depth_limit(self):
        """Test path depth limit restrictions"""
        max_depth = 2
        wrapper = SecurityWrapper(self.provider, max_path_depth=max_depth)
        
        # Create a shallow directory structure
        wrapper.create_node(FSNodeInfo("level1", True, "/"))
        assert wrapper.create_node(FSNodeInfo("file.txt", False, "/level1")) is True
        
        # Create a deeper structure for testing
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("level2", True, "/level1"))
        wrapper.provider.create_node(FSNodeInfo("level3", True, "/level1/level2"))
        wrapper._in_setup = False
        
        # Attempt to create a node in a deeply nested path; should be blocked
        assert wrapper.create_node(FSNodeInfo("deep.txt", False, "/level1/level2/level3")) is False
        
        # Verify violation log
        violations = wrapper.get_violation_log()
        assert len(violations) == 1
        assert "Path depth exceeds maximum" in violations[0]["reason"]
        
    def test_total_quota(self):
        """Test total storage quota restrictions"""
        quota = 200  # 200 bytes
        wrapper = SecurityWrapper(self.provider, max_total_size=quota)
        
        # Write files until quota is exceeded
        wrapper.create_node(FSNodeInfo("file1.txt", False, "/"))
        assert wrapper.write_file("/file1.txt", "x" * 100) is True
        
        wrapper.create_node(FSNodeInfo("file2.txt", False, "/"))
        assert wrapper.write_file("/file2.txt", "x" * 50) is True
        
        wrapper.create_node(FSNodeInfo("file3.txt", False, "/"))
        assert wrapper.write_file("/file3.txt", "x" * 100) is False
        
        # Verify violation log
        violations = wrapper.get_violation_log()
        assert len(violations) == 1
        assert "Total storage quota exceeded" in violations[0]["reason"]
        
    def test_violation_log(self):
        """Test violation logging"""
        wrapper = SecurityWrapper(
            self.provider, 
            read_only=True,
            denied_paths=["/etc"],
            denied_patterns=[r"\.exe$"]
        )
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("test.txt", False, "/"))
        wrapper._in_setup = False
        wrapper.write_file("/test.txt", "Modified")  # read-only violation
        wrapper.create_node(FSNodeInfo("program.exe", False, "/"))  # pattern violation
        wrapper.create_node(FSNodeInfo("config", False, "/etc"))  # path violation
        
        violations = wrapper.get_violation_log()
        assert len(violations) == 3
        
        wrapper.clear_violations()
        assert len(wrapper.get_violation_log()) == 0


class TestSecurityProfiles:
    """Test security profiles and integration"""
    
    def test_available_profiles(self):
        """Test available security profiles"""
        profiles = get_available_profiles()
        expected_profiles = ["default", "strict", "readonly", "untrusted", "testing"]
        
        for profile in expected_profiles:
            assert profile in profiles, f"Profile {profile} missing from available profiles"
        
    def test_profile_integration(self):
        """Test security profile integration with filesystem"""
        fs = VirtualFileSystem(security_profile="default")
        
        # Verify provider is wrapped with security
        assert "SecurityWrapper" in fs.get_provider_name()
        
        # Test basic operations
        fs.mkdir("/home/user")
        fs.write_file("/home/user/test.txt", "Test content")
        
        # Test security violation
        result = fs.write_file("/etc/passwd", "root:x:0:0:")
        assert result is False
        
        # Verify violations are tracked
        violations = fs.get_security_violations()
        assert len(violations) > 0
        
    def test_readonly_profile(self):
        """Test readonly profile integration"""
        fs = VirtualFileSystem()
        # Setup basic directories
        for directory in ["/bin", "/home", "/tmp", "/etc"]:
            fs.mkdir(directory)
        fs.mkdir("/home/user")
        fs.write_file("/home/user/test.txt", "Original content")
        
        # Apply readonly profile (which now resets the provider state minimally)
        fs.apply_security("readonly")
        
        # Verify that write operations are blocked
        assert fs.write_file("/home/user/test.txt", "Modified") is False
        assert fs.mkdir("/home/newdir") is False
        
        # Verify that the file can still be read with its original content
        assert fs.read_file("/home/user/test.txt") == "Original content"
        
    def test_untrusted_profile(self):
        """Test untrusted profile integration"""
        fs = VirtualFileSystem(security_profile="untrusted")
        
        # Sandbox directory should be automatically created
        assert fs.get_node_info("/sandbox") is not None
        
        # Verify sandbox restrictions
        assert fs.mkdir("/sandbox/allowed") is True
        assert fs.mkdir("/home/user") is False
        
        # Verify file size limits
        small_data = "x" * 1000  # 1KB
        large_data = "x" * (600 * 1024)  # 600KB
        
        fs.write_file("/sandbox/small.txt", small_data)
        assert fs.write_file("/sandbox/large.txt", large_data) is False


class TestVirtualFileSystemSecurity:
    """Test VirtualFileSystem security integration"""
    
    def test_security_constructor(self):
        """Test security constructor parameters"""
        fs = VirtualFileSystem(
            security_profile="default",
            security_read_only=True,
            security_max_file_size=1000
        )
        
        # Verify settings were applied
        assert fs.is_read_only() is True
        
        # Test file size restriction
        fs._in_setup = True  # Disable checks temporarily
        fs.mkdir("/test")
        fs._in_setup = False
        
        fs.write_file("/test/small.txt", "x" * 500)
        assert fs.write_file("/test/large.txt", "x" * 2000) is False
        
    def test_apply_security(self):
        """Test applying security after creation"""
        fs = VirtualFileSystem()
        
        # Setup basic directory and file
        fs.mkdir("/etc")
        fs.write_file("/etc/test.conf", "test")
        
        # Apply security that restricts /etc
        fs.apply_security("default")
        
        # Test restriction is in effect
        assert fs.write_file("/etc/passwd", "root:x:0:0:") is False
        
    def test_security_info(self):
        """Test security info in filesystem info"""
        fs = VirtualFileSystem(security_profile="default")
        info = fs.get_fs_info()
        assert "security" in info
        assert "read_only" in info["security"]
        assert "violations" in info["security"]
