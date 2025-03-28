"""
tests/filesystem/test_advanced_security_scenarios.py - Advanced Security Testing
"""
import pytest
import re
import posixpath
from typing import List, Dict, Any, Tuple

from chuk_virtual_fs import (
    VirtualFileSystem,
    SecurityWrapper,
    get_provider
)
from chuk_virtual_fs.node_info import FSNodeInfo


class TestAdvancedSecurityScenarios:
    """
    Comprehensive test suite for advanced security scenarios
    
    Covers:
    - Complex pattern matching
    - Path traversal protection
    - Quota and file limit testing
    - Boundary condition tests
    """
    
    def setup_method(self):
        """Set up test fixtures"""
        self.provider = get_provider("memory")
        self.provider.initialize()
    
    def _count_path_depth(self, path: str) -> int:
        """
        Count the depth of a path, excluding empty components
        """
        # Split the path and count non-empty components
        components = [p for p in path.split('/') if p]
        return len(components)
    
    def _is_in_allowed_path(self, path: str, allowed_paths: List[str]) -> bool:
        """
        Check if the path is within allowed paths
        """
        # Normalize the path
        normalized_path = posixpath.normpath(path)
        
        # Check if the path starts with any of the allowed paths
        return any(
            normalized_path == allowed or 
            normalized_path.startswith(allowed + '/') 
            for allowed in allowed_paths
        )
    
    def test_complex_pattern_matching(self):
        """
        Test advanced pattern matching scenarios
        """
        wrapper = SecurityWrapper(
            self.provider, 
            denied_patterns=[
                r"^sensitive_",        # Files starting with sensitive_
                r"data\d+\.txt$",      # Files like data123.txt
                r"temp_.*\.log$",      # Temp log files
                r"[^a-zA-Z0-9_\-\.]",  # Block files with special characters
            ]
        )
        
        # Test cases covering various pattern scenarios
        test_cases: List[Tuple[str, bool]] = [
            ("normal_file.txt", True),          # Normal file (allowed)
            ("sensitive_data.txt", False),      # Blocked by sensitive prefix
            ("data123.txt", False),             # Blocked by numeric pattern
            ("temp_system_log.log", False),     # Blocked by temp log pattern
            ("file@with!special#chars.txt", False),  # Blocked by special chars
            ("valid-file_name.txt", True),      # Allowed complex filename
        ]
        
        for filename, expected in test_cases:
            result = wrapper.create_node(FSNodeInfo(filename, False, "/"))
            assert result == expected, f"Failed for filename: {filename}"
        
        # Verify violation log
        violations = wrapper.get_violation_log()
        assert len(violations) == len([case for case in test_cases if not case[1]])
    
    def test_path_traversal_protection(self):
        """
        Comprehensive test for path traversal protection
        """
        wrapper = SecurityWrapper(
            self.provider, 
            allowed_paths=["/safe_area"],
            max_path_depth=3
        )
        
        # Create initial structure
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("safe_area", True, "/"))
        # Pre-create parent directory for valid nested nodes
        wrapper.provider.create_node(FSNodeInfo("valid", True, "/safe_area"))
        wrapper._in_setup = False
        
        # Test various path traversal attempts
        traversal_cases: List[Tuple[str, bool]] = [
            ("/safe_area/../etc/passwd", False),        # Classic traversal
            ("/safe_area/../../sensitive", False),      # Multi-level traversal
            ("/safe_area/nested/too/deep", False),      # Depth exceeded
            ("/safe_area/valid/nested", True),          # Valid nested path
            ("/safe_area/normal_file.txt", True),       # Normal file in allowed area
        ]
        
        for full_path, expected in traversal_cases:
            # Normalize the path
            normalized_path = posixpath.normpath(full_path)
            
            # Check depth
            path_depth = self._count_path_depth(full_path)
            path_in_allowed = self._is_in_allowed_path(full_path, ["/safe_area"])
            
            # Determine expected result based on depth and allowed paths
            calculated_expected = (
                path_depth <= 3 and 
                path_in_allowed and 
                '..' not in normalized_path
            )
            
            # Create node info
            filename = posixpath.basename(normalized_path)
            parent_path = posixpath.dirname(normalized_path)
            
            # Attempt to create node
            node = FSNodeInfo(filename, False, parent_path)
            result = wrapper.create_node(node)
            
            assert result == calculated_expected, (
                f"Failed for path: {full_path}, "
                f"depth: {path_depth}, "
                f"in_allowed: {path_in_allowed}, "
                f"calculated: {calculated_expected}"
            )
        
        # Optional: Verify violation log
        violations = wrapper.get_violation_log()
        failed_paths = [path for path, expected in traversal_cases if not expected]
        assert len(violations) == len(failed_paths)
    
    def test_mixed_security_scenarios(self):
        """
        Complex test combining multiple security rules
        """
        wrapper = SecurityWrapper(
            self.provider, 
            denied_patterns=[r"secret", r"\.tmp$"],    # Block files with 'secret' or .tmp
            allowed_paths=["/workspace"],              # Only allow /workspace
            max_path_depth=2,                          # Max 2 levels deep
            max_file_size=500,                         # 500 bytes max
            max_files=2                                # Max 2 files
        )
        
        # Create workspace
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("workspace", True, "/"))
        wrapper._in_setup = False
        
        # Test scenarios
        test_cases: List[Tuple[str, str, bool]] = [
            ("/workspace/normal.txt", "normal content", True),          # Normal file
            ("/workspace/secret_file.txt", "confidential", False),      # Blocked by pattern
            ("/workspace/temp.tmp", "temporary data", False),           # Blocked by .tmp
            ("/another/deep/path/file.txt", "test", False),             # Wrong path
            ("/workspace/large_file.txt", "x" * 600, False),            # Too large (should pass creation but fail write)
        ]
        
        for full_path, content, expected in test_cases:
            # Normalize the path
            normalized_path = posixpath.normpath(full_path)
            
            # Check depth
            path_depth = self._count_path_depth(full_path)
            path_in_allowed = self._is_in_allowed_path(full_path, ["/workspace"])
            filename_blocked = any(
                re.search(pattern, posixpath.basename(full_path)) 
                for pattern in [r"secret", r"\.tmp$"]
            )
            content_size = len(content.encode('utf-8'))
            
            # For file size violations, the write operation is expected to fail while node creation succeeds.
            if content_size > wrapper.max_file_size:
                expected_create = True
                expected_write = False
            else:
                expected_create = (path_depth <= 2 and path_in_allowed and not filename_blocked)
                expected_write = expected_create
            
            # Create node info
            filename = posixpath.basename(normalized_path)
            parent_path = posixpath.dirname(normalized_path)
            
            # Attempt to create node
            node = FSNodeInfo(filename, False, parent_path)
            create_result = wrapper.create_node(node)
            write_result = wrapper.write_file(full_path, content) if create_result else False
            
            if content_size > wrapper.max_file_size:
                assert create_result == expected_create, (
                    f"Unexpected node creation result for {full_path}"
                )
                assert write_result == expected_write, f"Write should fail for {full_path} due to file size"
            else:
                assert create_result == expected_create, (
                    f"Create failed for {full_path}, "
                    f"depth: {path_depth}, "
                    f"in_allowed: {path_in_allowed}, "
                    f"filename_blocked: {filename_blocked}, "
                    f"expected: {expected_create}"
                )
                assert write_result == expected_write, f"Write failed for {full_path}"
        
        # Verify violations
        violations = wrapper.get_violation_log()
        expected_violation_count = len([case for case in test_cases if not case[2]])
        assert len(violations) == expected_violation_count
    
    def test_quota_and_file_limit_boundary_conditions(self):
        """
        Test storage quota and file limit boundary conditions
        """
        # Create wrapper with strict limits
        wrapper = SecurityWrapper(
            self.provider, 
            max_file_size=1000,         # 1000 bytes max file size
            max_total_size=5000,        # 5000 bytes total
            max_files=3                 # Max 3 files
        )
        
        # Scenario 1: Create files up to the limit
        for i in range(3):
            filename = f"file{i}.txt"
            content = "x" * 1000  # 1000-byte file
            wrapper.create_node(FSNodeInfo(filename, False, "/"))
            result = wrapper.write_file(f"/{filename}", content)
            assert result is True, f"Failed to create {filename}"
        
        # Attempt to create 4th file (should fail)
        result = wrapper.create_node(FSNodeInfo("fourth_file.txt", False, "/"))
        assert result is False, "Should not allow 4th file creation"
        
        # Attempt to write over size limit
        result = wrapper.write_file("/file0.txt", "x" * 2000)  # Exceeds max file size
        assert result is False, "Should not allow file larger than max size"
        
        # Verify violation log captures all restrictions
        violations = wrapper.get_violation_log()
        assert len(violations) >= 2  # At least file count and size violations
    
    def test_unicode_and_special_character_handling(self):
        """
        Test security wrapper's handling of unicode and special characters
        """
        wrapper = SecurityWrapper(
            self.provider, 
            denied_patterns=[
                r"[特殊]",     # Block files with specific unicode chars
                r"[!@#$%^&*()]"  # Block files with special symbols
            ]
        )
        
        # Test cases with unicode and special characters
        test_cases: List[Tuple[str, bool]] = [
            ("normal_file.txt", True),
            ("特殊_document.txt", False),
            ("file!with@special#chars.txt", False),
            ("safe_unicode_文件.txt", True),
            ("valid-file_name.txt", True)
        ]
        
        for filename, expected in test_cases:
            result = wrapper.create_node(FSNodeInfo(filename, False, "/"))
            assert result == expected, f"Failed for filename: {filename}"
        
        # Verify violation log
        violations = wrapper.get_violation_log()
        assert len(violations) == len([case for case in test_cases if not case[1]])
    
    def test_mixed_extreme_security_rules(self):
        """
        Test combining multiple extreme security rules
        """
        wrapper = SecurityWrapper(
            self.provider, 
            allowed_paths=["/secure"],
            denied_patterns=[r"^\."],             # Block hidden files
            max_path_depth=1,                     # Very shallow path depth
            max_file_size=100,                    # Very small file size
            max_total_size=500,                   # Very small total size
            max_files=1                           # Only one file allowed
        )
        
        # Create secure directory
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("secure", True, "/"))
        wrapper._in_setup = False
        
        # Test scenarios
        test_cases: List[Tuple[str, str, bool]] = [
            # Update expected outcome for /secure/normal.txt to False since its depth is 2 (> max_path_depth of 1)
            ("/secure/normal.txt", "small content", False),
            ("/secure/.hidden", "secret", False),              # Hidden file
            ("/secure/big_file.txt", "x" * 200, False),        # Too large
            ("/secure/extra_file.txt", "content", False),      # Exceeds file limit
            ("/another/path/file.txt", "test", False)          # Wrong path
        ]
        
        for full_path, content, expected in test_cases:
            # Normalize the path
            normalized_path = posixpath.normpath(full_path)
            
            # Check conditions
            path_depth = self._count_path_depth(full_path)
            path_in_allowed = self._is_in_allowed_path(full_path, ["/secure"])
            filename_blocked = any(
                re.search(pattern, posixpath.basename(full_path))
                for pattern in [r"^\."]
            )
            content_size = len(content.encode('utf-8'))
            
            # Determine expected result based on security rules
            calculated_expected = (
                path_depth <= 1 and
                path_in_allowed and
                not filename_blocked and
                content_size <= 100
            )
            
            # Create node info
            filename = posixpath.basename(normalized_path)
            parent_path = posixpath.dirname(normalized_path)
            
            # Attempt to create node
            node = FSNodeInfo(filename, False, parent_path)
            create_result = wrapper.create_node(node)
            write_result = wrapper.write_file(full_path, content) if create_result else False
            
            assert create_result == calculated_expected, (
                f"Create failed for {full_path}, "
                f"depth: {path_depth}, "
                f"in_allowed: {path_in_allowed}, "
                f"filename_blocked: {filename_blocked}, "
                f"content_size: {content_size}, "
                f"calculated: {calculated_expected}"
            )
            assert write_result == calculated_expected, f"Write failed for {full_path}"
        
        # Verify violations
        violations = wrapper.get_violation_log()
        expected_violation_count = len([case for case in test_cases if not case[2]])
        assert len(violations) == expected_violation_count, f"Violations: {violations}"


def test_security_configuration_resilience():
    """
    Test the security wrapper's ability to handle extreme or unusual configurations
    """
    # Test various edge case configurations
    edge_cases = [
        # Negative limits should default to safe values
        {"max_file_size": -100, "max_total_size": -1000, "max_files": -5},
        
        # Extremely large limits
        {"max_file_size": 10**9, "max_total_size": 10**10, "max_files": 10**6},
        
        # Empty or None configurations
        {"allowed_paths": None, "denied_paths": None, "denied_patterns": None},
        
        # Conflicting configurations
        {"allowed_paths": ["/"], "denied_paths": ["/"]}
    ]
    
    for config in edge_cases:
        try:
            # Create filesystem with edge case configuration
            fs = VirtualFileSystem(**{f"security_{k}": v for k, v in config.items()})
            
            # Basic operations should still work
            fs.mkdir("/test")
            fs.write_file("/test/sample.txt", "Test content")
        except Exception as e:
            pytest.fail(f"Security configuration failed for {config}: {e}")
