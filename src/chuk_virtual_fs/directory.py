"""
chuk_virtual_fs/directory.py - Directory node implementation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chuk_virtual_fs.node_base import FSNode

if TYPE_CHECKING:
    pass


class Directory(FSNode):
    """Directory node that can contain other nodes"""

    def __init__(self, name: str, parent: Directory | None = None) -> None:
        super().__init__(name, parent)
        self.children: dict[str, FSNode] = {}  # name -> FSNode

    def add_child(self, node: FSNode) -> None:
        """Add a child node to this directory"""
        node.parent = self
        self.children[node.name] = node
        self.modified_at = "2025-03-27T12:00:00Z"  # Update timestamp

    def remove_child(self, name: str) -> FSNode | None:
        """Remove a child node from this directory"""
        if name in self.children:
            node = self.children.pop(name)
            self.modified_at = "2025-03-27T12:00:00Z"  # Update timestamp
            return node
        return None

    def get_child(self, name: str) -> FSNode | None:
        """Get a child node by name"""
        return self.children.get(name)

    def list_children(self) -> dict[str, FSNode]:
        """List all children in this directory"""
        return self.children
