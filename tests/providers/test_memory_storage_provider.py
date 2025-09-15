"""
tests/providers/test_memory_storage_provider.py - Async tests for memory storage provider
"""

import pytest

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider


@pytest.fixture
async def provider():
    prov = AsyncMemoryStorageProvider()
    await prov.initialize()
    yield prov
    await prov.close()


@pytest.mark.asyncio
async def test_initialize(provider):
    # After initialization, root ("/") should exist.
    root = await provider.get_node_info("/")
    assert root is not None
    assert root.name == ""  # Root node was created with an empty name.
    # Also, check that the root is marked as a directory.
    assert root.is_dir is True


@pytest.mark.asyncio
async def test_create_node_file(provider):
    # Create a file node under an existing directory.
    node_info = EnhancedNodeInfo(name="test.txt", is_dir=False, parent_path="/home")
    # First, create the parent directory.
    parent_info = EnhancedNodeInfo(name="home", is_dir=True, parent_path="/")
    await provider.create_node(parent_info)
    result = await provider.create_node(node_info)
    assert result is True
    # Verify that the node exists.
    created = await provider.get_node_info("/home/test.txt")
    assert created is not None
    assert created.name == "test.txt"


@pytest.mark.asyncio
async def test_create_node_directory_failure(provider):
    # Attempt to create a node where parent does not exist.
    node_info = EnhancedNodeInfo(
        name="orphan", is_dir=False, parent_path="/nonexistent"
    )
    result = await provider.create_node(node_info)
    assert result is False


@pytest.mark.asyncio
async def test_list_directory(provider):
    # Create a directory with children.
    dir_info = EnhancedNodeInfo(name="docs", is_dir=True, parent_path="/")
    await provider.create_node(dir_info)

    # Create two files in /docs.
    file1 = EnhancedNodeInfo(name="a.txt", is_dir=False, parent_path="/docs")
    file2 = EnhancedNodeInfo(name="b.txt", is_dir=False, parent_path="/docs")
    await provider.create_node(file1)
    await provider.create_node(file2)

    # List /docs.
    children = await provider.list_directory("/docs")
    assert "a.txt" in children
    assert "b.txt" in children


@pytest.mark.asyncio
async def test_write_and_read_file(provider):
    # Create a file node.
    file_info = EnhancedNodeInfo(name="readme.md", is_dir=False, parent_path="/")
    await provider.create_node(file_info)

    # Write to it.
    content = b"# Project Documentation"
    result = await provider.write_file("/readme.md", content)
    assert result is True

    # Read back.
    read_content = await provider.read_file("/readme.md")
    assert read_content == content


@pytest.mark.asyncio
async def test_write_to_directory_fails(provider):
    # Try to write to a directory.
    dir_info = EnhancedNodeInfo(name="folder", is_dir=True, parent_path="/")
    await provider.create_node(dir_info)

    content = b"Should not work"
    result = await provider.write_file("/folder", content)
    assert result is False


@pytest.mark.asyncio
async def test_delete_node(provider):
    # Create and then delete a file.
    file_info = EnhancedNodeInfo(name="temporary.txt", is_dir=False, parent_path="/")
    await provider.create_node(file_info)

    # Verify it exists.
    exists = await provider.get_node_info("/temporary.txt")
    assert exists is not None

    # Delete it.
    result = await provider.delete_node("/temporary.txt")
    assert result is True

    # Verify it's gone.
    gone = await provider.get_node_info("/temporary.txt")
    assert gone is None


@pytest.mark.asyncio
async def test_delete_non_empty_directory_fails(provider):
    # Create a directory with a child.
    parent_info = EnhancedNodeInfo(name="parent", is_dir=True, parent_path="/")
    child_info = EnhancedNodeInfo(name="child.txt", is_dir=False, parent_path="/parent")

    await provider.create_node(parent_info)
    await provider.create_node(child_info)

    # Try to delete parent (should fail).
    result = await provider.delete_node("/parent")
    assert result is False


@pytest.mark.asyncio
async def test_get_storage_stats(provider):
    # Create some nodes and check stats.
    await provider.create_node(
        EnhancedNodeInfo(name="folder", is_dir=True, parent_path="/")
    )
    await provider.create_node(
        EnhancedNodeInfo(name="file.txt", is_dir=False, parent_path="/folder")
    )
    await provider.write_file("/folder/file.txt", b"Test content")

    stats = await provider.get_storage_stats()
    assert "total_size_bytes" in stats
    assert "file_count" in stats
    assert "directory_count" in stats
    assert stats["file_count"] >= 1
    assert stats["directory_count"] >= 2  # At least root and folder


@pytest.mark.asyncio
async def test_cleanup(provider):
    # Create some temporary files.
    await provider.create_node(
        EnhancedNodeInfo(name="tmp", is_dir=True, parent_path="/")
    )
    await provider.create_node(
        EnhancedNodeInfo(name="temp1.txt", is_dir=False, parent_path="/tmp")
    )
    await provider.create_node(
        EnhancedNodeInfo(name="temp2.txt", is_dir=False, parent_path="/tmp")
    )

    await provider.write_file("/tmp/temp1.txt", b"Temp data 1")
    await provider.write_file("/tmp/temp2.txt", b"Temp data 2")

    # Run cleanup.
    result = await provider.cleanup()
    assert "bytes_freed" in result
    assert "files_removed" in result

    # /tmp contents should be cleaned.
    tmp_contents = await provider.list_directory("/tmp")
    assert len(tmp_contents) == 0
