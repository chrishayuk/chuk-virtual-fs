"""
tests/chuk_virtual_fs/filesystem/test_node_info.py
"""

import time

from chuk_virtual_fs.node_info import FSNodeInfo


def test_get_path_no_parent():
    # When parent_path is empty and name is provided, path should be "/<name>"
    node = FSNodeInfo(name="file.txt", is_dir=False, parent_path="")
    assert node.get_path() == "/file.txt"


def test_get_path_root():
    # When name is empty, it is considered root
    node = FSNodeInfo(name="", is_dir=True, parent_path="")
    assert node.get_path() == "/"


def test_get_path_with_root_parent():
    # When parent_path is "/" the result should be "/<name>"
    node = FSNodeInfo(name="folder", is_dir=True, parent_path="/")
    assert node.get_path() == "/folder"


def test_get_path_nested():
    # When parent_path is non-root, the path should be "parent_path/name"
    node = FSNodeInfo(name="document.txt", is_dir=False, parent_path="/home/user")
    assert node.get_path() == "/home/user/document.txt"


def test_to_dict():
    # Create a node and convert to dictionary.
    node = FSNodeInfo(name="data", is_dir=True, parent_path="/var")
    info_dict = node.to_dict()

    # Check essential keys exist (EnhancedNodeInfo has many more fields)
    expected_keys = {"name", "is_dir", "parent_path", "modified_at"}
    assert expected_keys <= set(info_dict.keys())

    # Validate values are correctly mapped
    assert info_dict["name"] == "data"
    assert info_dict["is_dir"] is True
    assert info_dict["parent_path"] == "/var"
    # Check that modified_at is a non-empty string
    assert isinstance(info_dict["modified_at"], str) and info_dict["modified_at"]


def test_from_dict():
    # Create a node, convert it to a dict, then create a new node from that dict.
    original = FSNodeInfo(name="config.json", is_dir=False, parent_path="/etc")
    # Set some custom metadata
    original.custom_meta = {"size": 1024}
    data = original.to_dict()
    # Simulate a time delay to ensure the new node's modified_at isn't accidentally updated
    time.sleep(0.01)
    recreated = FSNodeInfo.from_dict(data)

    # Check that all attributes match
    assert recreated.name == original.name
    assert recreated.is_dir == original.is_dir
    assert recreated.parent_path == original.parent_path
    assert recreated.get_path() == original.get_path()
    assert recreated.modified_at == original.modified_at
    assert recreated.custom_meta == original.custom_meta


def test_unique_timestamps():
    # Ensure that multiple instances have different timestamps when created at different times.
    node1 = FSNodeInfo(name="a", is_dir=False)
    time.sleep(0.001)  # Small delay
    node2 = FSNodeInfo(name="b", is_dir=False)
    # Both should have timestamps, and they should be different if created at different times
    assert (
        node1.created_at != node2.created_at or node1.modified_at != node2.modified_at
    )
