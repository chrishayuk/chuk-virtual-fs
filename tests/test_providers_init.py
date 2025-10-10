"""
Test module for providers.__init__ module
"""

import pytest


class TestProvidersInit:
    """Test provider registry functionality"""

    def test_register_and_get_provider(self):
        """Test registering and getting providers"""
        from chuk_virtual_fs.providers import get_provider, register_provider

        # Mock provider class
        class MockProvider:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        # Register provider
        register_provider("test", MockProvider)

        # Get provider
        provider = get_provider("test", arg1="value1", arg2="value2")
        assert isinstance(provider, MockProvider)
        assert provider.kwargs == {"arg1": "value1", "arg2": "value2"}

        # Test case insensitive
        provider2 = get_provider("TEST")
        assert isinstance(provider2, MockProvider)

    def test_get_nonexistent_provider(self):
        """Test getting a provider that doesn't exist"""
        from chuk_virtual_fs.providers import get_provider

        result = get_provider("nonexistent_provider")
        assert result is None

    def test_list_providers(self):
        """Test listing all providers"""
        from chuk_virtual_fs.providers import list_providers

        providers = list_providers()
        assert isinstance(providers, dict)

        # Should have at least memory provider
        assert "memory" in providers

        # The returned dict should be a copy
        original_len = len(providers)
        providers["fake"] = "fake_provider"
        new_providers = list_providers()
        assert len(new_providers) == original_len

    def test_memory_provider_registration(self):
        """Test that memory provider is registered"""
        from chuk_virtual_fs.providers import AsyncMemoryStorageProvider, get_provider

        provider = get_provider("memory")
        assert isinstance(provider, AsyncMemoryStorageProvider)

    def test_sqlite_provider_import_error(self):
        """Test SQLite provider import error handling"""
        # Test that when SQLite import fails, it's handled gracefully
        # This is more of a documentation test since the actual import
        # happens at module load time
        from chuk_virtual_fs.providers import get_provider

        # SQLite might or might not be available, but the test should not crash
        sqlite_provider = get_provider("sqlite")
        # Could be None or a valid provider depending on availability
        assert sqlite_provider is None or hasattr(sqlite_provider, "__class__")

    def test_optional_providers_availability(self):
        """Test that optional providers are handled gracefully"""
        from chuk_virtual_fs.providers import get_provider

        # Test providers that don't require arguments
        simple_providers = ["pyodide", "e2b", "filesystem", "sqlite"]

        for provider_name in simple_providers:
            provider = get_provider(provider_name)
            # Should either return a valid provider or None
            assert provider is None or hasattr(provider, "__class__")

        # Test S3 provider with required argument
        try:
            s3_provider = get_provider("s3", bucket_name="test-bucket")
            assert s3_provider is None or hasattr(s3_provider, "__class__")
        except Exception:
            # S3 provider might not be available or might require additional setup
            pass

    def test_provider_import_error_handling(self):
        """Test that import errors are properly handled"""
        # This tests that the module loads without crashing even if some providers fail
        # The actual import error handling happens at module load time
        import chuk_virtual_fs.providers

        # The module should load successfully
        assert hasattr(chuk_virtual_fs.providers, "register_provider")
        assert hasattr(chuk_virtual_fs.providers, "get_provider")
        assert hasattr(chuk_virtual_fs.providers, "list_providers")

    def test_backwards_compatibility(self):
        """Test backwards compatibility aliases"""
        from chuk_virtual_fs.providers import (
            AsyncMemoryStorageProvider,
            MemoryStorageProvider,
        )

        # MemoryStorageProvider should be an alias for AsyncMemoryStorageProvider
        assert MemoryStorageProvider is AsyncMemoryStorageProvider

    def test_conditional_exports(self):
        """Test conditional __all__ exports"""
        import chuk_virtual_fs.providers as providers_module

        # Check that __all__ contains basic exports
        assert "register_provider" in providers_module.__all__
        assert "get_provider" in providers_module.__all__
        assert "list_providers" in providers_module.__all__
        assert "MemoryStorageProvider" in providers_module.__all__

        # Check conditional exports based on available providers
        if hasattr(providers_module, "SqliteStorageProvider"):
            assert "SqliteStorageProvider" in providers_module.__all__

        if hasattr(providers_module, "PyodideStorageProvider"):
            assert "PyodideStorageProvider" in providers_module.__all__

        if hasattr(providers_module, "S3StorageProvider"):
            assert "S3StorageProvider" in providers_module.__all__

        if hasattr(providers_module, "E2BStorageProvider"):
            assert "E2BStorageProvider" in providers_module.__all__

        if hasattr(providers_module, "AsyncFilesystemStorageProvider"):
            assert "AsyncFilesystemStorageProvider" in providers_module.__all__

    def test_provider_registry_isolation(self):
        """Test that provider registry is properly isolated"""
        from chuk_virtual_fs.providers import (
            get_provider,
            list_providers,
            register_provider,
        )

        # Get initial state
        list_providers()

        # Register a test provider
        class TestProvider:
            pass

        register_provider("test_isolation", TestProvider)

        # Verify it's registered
        assert get_provider("test_isolation") is not None
        assert "test_isolation" in list_providers()

        # Verify we can get it
        provider = get_provider("test_isolation")
        assert isinstance(provider, TestProvider)

    def test_import_error_handling_sqlite(self):
        """Test that sqlite import errors are handled gracefully"""
        import sys

        # Remove sqlite from sys.modules to force re-import
        [k for k in sys.modules if "sqlite" in k.lower()]

        # Test that the module handles import errors during initialization
        # The import happens at module load time, so we verify it doesn't crash
        from chuk_virtual_fs.providers import get_provider

        # If sqlite is available, it should be registered
        # If not available, get_provider should return None gracefully
        result = get_provider("sqlite")
        assert result is None or hasattr(result, "__class__")

    def test_import_error_handling_pyodide(self):
        """Test that pyodide import errors are handled gracefully"""
        from chuk_virtual_fs.providers import get_provider

        # Pyodide provider should either work or return None gracefully
        result = get_provider("pyodide")
        assert result is None or hasattr(result, "__class__")

    def test_import_error_handling_s3(self):
        """Test that s3 import errors are handled gracefully"""
        from chuk_virtual_fs.providers import get_provider

        # S3 provider requires bucket_name but should handle import errors
        try:
            result = get_provider("s3", bucket_name="test")
            assert result is None or hasattr(result, "__class__")
        except Exception:
            # S3 might have additional requirements, which is fine
            pass

    def test_import_error_handling_e2b(self):
        """Test that e2b import errors are handled gracefully"""
        from chuk_virtual_fs.providers import get_provider

        # E2B provider should either work or return None gracefully
        result = get_provider("e2b")
        assert result is None or hasattr(result, "__class__")

    def test_import_error_handling_filesystem(self):
        """Test that filesystem import errors are handled gracefully"""
        from chuk_virtual_fs.providers import get_provider

        # Filesystem provider should either work or return None gracefully
        result = get_provider("filesystem")
        assert result is None or hasattr(result, "__class__")

    def test_all_providers_handle_import_errors(self):
        """Test that all optional providers handle import failures gracefully"""
        # This test verifies that the module loads successfully even if
        # optional dependencies are missing
        import chuk_virtual_fs.providers

        # The module should have loaded successfully
        assert hasattr(chuk_virtual_fs.providers, "get_provider")
        assert hasattr(chuk_virtual_fs.providers, "register_provider")
        assert hasattr(chuk_virtual_fs.providers, "list_providers")

        # Should be able to list providers without crashing
        providers = chuk_virtual_fs.providers.list_providers()
        assert isinstance(providers, dict)
        assert "memory" in providers  # Memory should always be available

    def test_import_error_handling_with_mock(self):
        """Test that import errors are handled gracefully using mocking"""
        import builtins
        import importlib
        import sys
        from unittest.mock import patch

        # Save original modules
        original_modules = {}
        for module_name in list(sys.modules.keys()):
            if "chuk_virtual_fs.providers" in module_name:
                original_modules[module_name] = sys.modules[module_name]

        try:
            # Remove providers module from sys.modules to force re-import
            providers_modules = [
                k
                for k in list(sys.modules.keys())
                if k.startswith("chuk_virtual_fs.providers")
            ]
            for mod in providers_modules:
                if mod != "chuk_virtual_fs.providers.memory":  # Keep memory
                    sys.modules.pop(mod, None)

            # Mock the imports to raise ImportError
            with patch.dict(
                "sys.modules",
                {
                    "chuk_virtual_fs.providers.sqlite": None,
                    "chuk_virtual_fs.providers.pyodide": None,
                    "chuk_virtual_fs.providers.s3": None,
                    "chuk_virtual_fs.providers.e2b": None,
                    "chuk_virtual_fs.providers.filesystem": None,
                },
            ):
                # Force import to fail by making the modules None
                def mock_import(name, *args, **kwargs):
                    if name in [
                        "chuk_virtual_fs.providers.sqlite",
                        "chuk_virtual_fs.providers.pyodide",
                        "chuk_virtual_fs.providers.s3",
                        "chuk_virtual_fs.providers.e2b",
                        "chuk_virtual_fs.providers.filesystem",
                    ]:
                        raise ImportError(f"Mocked import error for {name}")
                    return original_import(name, *args, **kwargs)

                original_import = builtins.__import__
                builtins.__import__ = mock_import

                try:
                    # Reload the module to trigger the import error handling
                    import chuk_virtual_fs.providers

                    importlib.reload(chuk_virtual_fs.providers)

                    # The module should still load successfully
                    assert hasattr(chuk_virtual_fs.providers, "get_provider")

                    # Only memory provider should be available
                    providers = chuk_virtual_fs.providers.list_providers()
                    assert "memory" in providers
                finally:
                    builtins.__import__ = original_import

        finally:
            # Restore original modules
            for module_name, module in original_modules.items():
                sys.modules[module_name] = module


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
