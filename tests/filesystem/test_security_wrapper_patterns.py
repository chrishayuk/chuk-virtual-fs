# tests/test_security_wrapper_patterns.py

import re
import logging
import pytest
from datetime import datetime
from typing import Optional, Dict, Any, List

from chuk_virtual_fs.security_wrapper import SecurityWrapper
from chuk_virtual_fs.node_info import FSNodeInfo
from chuk_virtual_fs.provider_base import StorageProvider

# Disable logging output during tests (optional)
logging.disable(logging.CRITICAL)

class DummyProvider(StorageProvider):
    """
    A dummy storage provider that stores nodes in a dict.
    """
    def __init__(self):
        self.nodes = {}  # key: normalized path, value: FSNodeInfo
        self.stats = {"total_size_bytes": 0, "file_count": 0}
    
    def initialize(self) -> bool:
        return True

    def create_node(self, node_info: FSNodeInfo) -> bool:
        path = node_info.get_path()
        norm_path = posixpath.normpath(path)
        # For simplicity, update file_count if not a directory.
        if not node_info.is_dir:
            self.stats["file_count"] += 1
        self.nodes[norm_path] = node_info
        return True

    def get_node_info(self, path: str) -> Optional[FSNodeInfo]:
        norm_path = posixpath.normpath(path)
        return self.nodes.get(norm_path)
    
    def delete_node(self, path: str) -> bool:
        norm_path = posixpath.normpath(path)
        if norm_path in self.nodes:
            del self.nodes[norm_path]
            return True
        return False

    def list_directory(self, path: str) -> List[str]:
        # List nodes that start with the given normalized path.
        norm_path = posixpath.normpath(path)
        return [key for key in self.nodes.keys() if key.startswith(norm_path)]
    
    def write_file(self, path: str, content: str) -> bool:
        # For testing, simply update the file node's content.
        norm_path = posixpath.normpath(path)
        if norm_path in self.nodes:
            # Pretend to write the file and update stats.
            self.stats["total_size_bytes"] += len(content.encode('utf-8'))
            return True
        return False

    def read_file(self, path: str) -> Optional[str]:
        # For testing, return a dummy content.
        return "dummy"

    def get_storage_stats(self) -> Dict[str, Any]:
        return self.stats

    def cleanup(self) -> Dict[str, Any]:
        self.nodes.clear()
        self.stats = {"total_size_bytes": 0, "file_count": 0}
        return self.stats

import posixpath  # required by DummyProvider

# --- Tests begin here ---

def test_denied_patterns_with_compiled():
    """
    Test that SecurityWrapper correctly handles a mix of raw and precompiled denied patterns.
    """
    # Precompile a pattern that matches names starting with "deny"
    precompiled = re.compile(r"^deny")
    denied_patterns = ["^block", precompiled]
    provider = DummyProvider()
    sw = SecurityWrapper(provider, denied_patterns=denied_patterns)

    # Create a node with a filename that should be blocked by the raw string pattern.
    node_info1 = FSNodeInfo("block_this.txt", False, "/")
    result1 = sw.create_node(node_info1)
    # Expect creation to fail because filename matches "^block"
    assert result1 is False
    violations = sw.get_violation_log()
    assert any("matches denied pattern" in v["reason"] for v in violations)

    sw.clear_violations()

    # Create a node with a filename that should be blocked by the precompiled pattern.
    node_info2 = FSNodeInfo("deny_this.txt", False, "/")
    result2 = sw.create_node(node_info2)
    assert result2 is False
    violations = sw.get_violation_log()
    assert any("matches denied pattern" in v["reason"] for v in violations)


def test_invalid_denied_patterns():
    """
    Test that SecurityWrapper gracefully handles denied_patterns entries of unexpected types.
    """
    # Pass an invalid type (integer) along with a valid string.
    denied_patterns = [123, "^invalid"]
    provider = DummyProvider()
    sw = SecurityWrapper(provider, denied_patterns=denied_patterns)
    
    # The invalid entry should be skipped (logged as warning) and the valid one should work.
    node_info = FSNodeInfo("invalid_file.txt", False, "/")
    # This filename should match the valid pattern "^invalid"
    node_info_invalid = FSNodeInfo("invalid_file.txt", False, "/")
    result = sw.create_node(node_info_invalid)
    # Expect failure because filename "invalid_file.txt" matches "^invalid" pattern.
    assert result is False
    violations = sw.get_violation_log()
    assert any("matches denied pattern" in v["reason"] for v in violations)


def test_negative_configuration_fallback():
    """
    Test that negative numeric configurations are replaced with default safe values.
    """
    # Pass negative values; our improved version should log warnings and fallback.
    provider = DummyProvider()
    sw = SecurityWrapper(
        provider,
        max_file_size=-500,
        max_total_size=-1000,
        max_path_depth=-1,
        max_files=-10,
    )
    # Check that the attributes are set to defaults.
    assert sw.max_file_size == 10 * 1024 * 1024
    assert sw.max_total_size == 100 * 1024 * 1024
    # For max_path_depth and max_files our fallback defaults are set in our implementation:
    assert sw.max_path_depth == 10
    assert sw.max_files == 1000


def test_violation_logging_and_clearing():
    """
    Test that violations are logged and can be cleared.
    """
    provider = DummyProvider()
    sw = SecurityWrapper(provider)
    
    # Attempt to get info on a path that is not allowed (e.g. /forbidden when allowed_paths is ["/"])
    # For this dummy provider, let's simulate a denied pattern by trying to create a node with a hidden file.
    node_info = FSNodeInfo(".hidden", False, "/")
    result = sw.create_node(node_info)
    assert result is False
    violations = sw.get_violation_log()
    assert len(violations) > 0
    
    # Now clear the violations and ensure the log is empty.
    sw.clear_violations()
    assert len(sw.get_violation_log()) == 0
