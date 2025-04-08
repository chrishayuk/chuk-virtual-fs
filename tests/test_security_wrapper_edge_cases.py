"""
tests/filesystem/test_security_wrapper_edge_cases.py - Edge Case and Robustness Testing for Security Wrapper
"""
import pytest
import re
from typing import List, Dict, Any

from chuk_virtual_fs import (
    VirtualFileSystem,
    SecurityWrapper,
    get_provider
)
from chuk_virtual_fs.node_info import FSNodeInfo


class TestSecurityWrapperEdgeCases:
    """Test edge cases and robustness of SecurityWrapper"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.provider = get_provider("memory")
        self.provider.initialize()
    
    def test_invalid_regex_patterns(self):
        """
        Test initialization and handling of invalid regex patterns
        
        This test ensures that:
        1. Invalid patterns don't break initialization
        2. Invalid patterns are logged but don't prevent wrapper creation
        3. Pattern matching continues to work for valid patterns
        """
        # Create wrapper with mix of valid and invalid patterns
        wrapper = SecurityWrapper(
            self.provider, 
            denied_patterns=[
                r"\.exe$",     # Valid pattern
                "***invalid",  # Invalid regex 
                r"[",          # Malformed regex
                r"\\",         # Escape sequence issue
            ]
        )
        
        # Verify that some patterns were compiled
        assert len(wrapper.denied_patterns) > 0, "No patterns should have been compiled"
        
        # Verify pattern matching still works for valid patterns
        assert wrapper.create_node(FSNodeInfo("valid.txt", False, "/")) is True
        assert wrapper.create_node(FSNodeInfo("program.exe", False, "/")) is False
    
    def test_pattern_matching_with_complex_filenames(self):
        """
        Test pattern matching with complex and edge case filenames
        """
        wrapper = SecurityWrapper(
            self.provider, 
            denied_patterns=[
                r"\.exe$",     # Executable files
                r"^\.hidden",  # Hidden files
                r"\.\.",       # Path traversal attempt
                r"^\.",        # All hidden files (including .env)
            ]
        )
        
        # Test various filename scenarios
        test_cases = [
            ("normal.txt", True),       # Normal file (allowed)
            ("program.exe", False),     # Executable (denied)
            (".hidden_file", False),    # Hidden file (denied)
            ("file..txt", False),       # Path traversal pattern (denied)
            ("file.with.dots.txt", True),  # Multiple dots (allowed)
            (".env", False),            # Specific hidden config file (denied)
        ]
        
        wrapper.clear_violations()  # Clear previous violations
        
        for filename, expected in test_cases:
            result = wrapper.create_node(FSNodeInfo(filename, False, "/"))
            
            # Verbose debugging for failed cases
            if result != expected:
                print(f"Failed case: {filename}")
                violations = wrapper.get_violation_log()
                for violation in violations:
                    print(f"Violation details: {violation}")
            
            assert result == expected, f"Failed for filename: {filename}"
        
        # Verify violation log captures rejections
        violations = wrapper.get_violation_log()
        assert len(violations) > 0
        assert all("Path matches denied pattern" in v["reason"] for v in violations)
    
    def test_initialization_with_problematic_configs(self):
        """
        Test wrapper initialization with various problematic configurations
        
        Ensures that:
        1. Initialization doesn't fail with extreme configs
        2. Security checks still work
        3. Warnings are generated for unusual configurations
        """
        # Test with extreme path depth
        wrapper = SecurityWrapper(
            self.provider, 
            max_path_depth=1,  # Very restrictive
            allowed_paths=["/test"],
            denied_paths=["/sensitive"]
        )
        
        # Verify basic security checks still work
        wrapper._in_setup = True
        wrapper.provider.create_node(FSNodeInfo("test", True, "/"))
        wrapper._in_setup = False
        
        # Attempt to create deeply nested path
        result = wrapper.create_node(FSNodeInfo("file.txt", False, "/test/too/deep"))
        assert result is False
        
        # Verify violation log captures the rejection
        violations = wrapper.get_violation_log()
        assert any("Path depth exceeds maximum" in v["reason"] for v in violations)
    
    def test_safe_pattern_matching_method(self):
        """
        Directly test the _safe_pattern_match method for robustness
        """
        wrapper = SecurityWrapper(self.provider)
        
        # Test cases covering different scenarios
        test_patterns = [
            (re.compile(r"\.exe$"), "program.exe", True),
            (re.compile(r"\.exe$"), "program.txt", False),
            (re.compile(r"^\."), ".hidden", True),
            (re.compile(r"^\."), "visible", False),
        ]
        
        for pattern, test_string, expected in test_patterns:
            result = wrapper._safe_pattern_match(pattern, test_string)
            assert result == expected, f"Failed for pattern {pattern.pattern} with {test_string}"
    
    def test_pattern_matching_with_unicode_and_special_chars(self):
        """
        Test pattern matching with unicode and special characters
        """
        wrapper = SecurityWrapper(
            self.provider, 
            denied_patterns=[
                r"[特殊]",     # Unicode character matching
                r"[!@#$%^&*()]",  # Special characters
            ]
        )
        
        test_cases = [
            ("normal.txt", True),
            ("特殊file.txt", False),
            ("file!with@special#chars", False),
            ("safe_filename", True)
        ]
        
        for filename, expected in test_cases:
            result = wrapper.create_node(FSNodeInfo(filename, False, "/"))
            assert result == expected, f"Failed for filename: {filename}"


def test_security_wrapper_error_handling():
    """
    Integration test to ensure security wrapper doesn't break system
    when initialized with problematic configurations
    """
    # Create filesystem with various challenging configurations
    try:
        fs = VirtualFileSystem(
            security_profile="default",
            security_denied_patterns=["***invalid"],
            security_max_file_size=-1,  # Negative file size
            security_max_path_depth=0   # Impossible path depth
        )
        
        # Basic operations should still work
        fs.mkdir("/test")
        fs.write_file("/test/sample.txt", "Test content")
    except Exception as e:
        pytest.fail(f"Security wrapper initialization failed unexpectedly: {e}")