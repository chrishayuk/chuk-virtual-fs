"""
Adapters for exposing chuk-virtual-fs through different protocols.
"""

from chuk_virtual_fs.adapters.webdav import WebDAVAdapter, WebDAVProvider

__all__ = ["WebDAVAdapter", "WebDAVProvider"]
