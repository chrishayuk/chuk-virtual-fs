"""
chuk_virtual_fs/filesystem/__init__.py - Virtual filesystem package initialization
"""

# Import core components
from chuk_virtual_fs.node_info import FSNodeInfo
from chuk_virtual_fs.provider_base import StorageProvider
from chuk_virtual_fs.fs_manager import VirtualFileSystem

# Import provider registry
from chuk_virtual_fs.providers import get_provider, list_providers, register_provider

# Import security components
from chuk_virtual_fs.security_wrapper import SecurityWrapper
from chuk_virtual_fs.security_config import (
    create_secure_provider, 
    create_custom_security_profile,
    get_available_profiles,
    get_profile_settings,
    SECURITY_PROFILES
)

# Keep original classes for backward compatibility
from chuk_virtual_fs.node_base import FSNode
from chuk_virtual_fs.directory import Directory
from chuk_virtual_fs.file import File

# Export main classes
__all__ = [
    # Core components
    'VirtualFileSystem',
    'FSNodeInfo',
    'StorageProvider',
    'get_provider',
    'list_providers',
    'register_provider',
    
    # Security components
    'SecurityWrapper',
    'create_secure_provider',
    'create_custom_security_profile',
    'get_available_profiles',
    'get_profile_settings',
    'SECURITY_PROFILES',
    
    # Legacy components
    'FSNode',
    'Directory',
    'File'
]