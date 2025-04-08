"""
chuk_virtual_fs/providers/__init__.py - Storage provider registry and factory
"""
from typing import Dict, Any, Optional

# Provider registry
_PROVIDERS = {}


def register_provider(name: str, provider_class):
    """
    Register a storage provider
    
    Args:
        name: Name of the provider
        provider_class: Provider class
    """
    _PROVIDERS[name.lower()] = provider_class


def get_provider(name: str, **kwargs) -> Optional[Any]:
    """
    Get a storage provider instance by name
    
    Args:
        name: Name of the provider to get
        **kwargs: Arguments to pass to the provider constructor
    
    Returns:
        Provider instance or None if not found
    """
    provider_class = _PROVIDERS.get(name.lower())
    if not provider_class:
        return None
    return provider_class(**kwargs)


def list_providers() -> Dict[str, Any]:
    """
    List all registered providers
    
    Returns:
        Dictionary of provider names and classes
    """
    return _PROVIDERS.copy()


# Import and register built-in providers
from chuk_virtual_fs.providers.memory import MemoryStorageProvider
register_provider("memory", MemoryStorageProvider)

# Try to import optional providers
try:
    from chuk_virtual_fs.providers.sqlite import SqliteStorageProvider
    register_provider("sqlite", SqliteStorageProvider)
except ImportError:
    pass

try:
    from chuk_virtual_fs.providers.pyodide import PyodideStorageProvider
    register_provider("pyodide", PyodideStorageProvider)
except ImportError:
    pass

try:
    from chuk_virtual_fs.providers.s3 import S3StorageProvider
    register_provider("s3", S3StorageProvider)
except ImportError:
    pass

try:
    from chuk_virtual_fs.providers.e2b import E2BStorageProvider
    register_provider("e2b", E2BStorageProvider)
except ImportError:
    pass


# Base exports
__all__ = [
    'register_provider',
    'get_provider',
    'list_providers',
    'MemoryStorageProvider'
]

# Add optional providers to __all__ if they're available
if 'SqliteStorageProvider' in globals():
    __all__.append('SqliteStorageProvider')
if 'PyodideStorageProvider' in globals():
    __all__.append('PyodideStorageProvider')
if 'S3StorageProvider' in globals():
    __all__.append('S3StorageProvider')
if 'E2BStorageProvider' in globals():
    __all__.append('E2BStorageProvider')    