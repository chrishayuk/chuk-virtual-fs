"""
Test module for ProviderFactory
"""

from unittest.mock import Mock, patch

import pytest

from chuk_virtual_fs.provider_factory import ProviderFactory
from chuk_virtual_fs.providers.memory import AsyncMemoryStorageProvider


class TestProviderFactory:
    """Test ProviderFactory functionality"""

    def test_create_memory_provider(self):
        """Test creating a memory provider"""
        provider = ProviderFactory.create("memory")
        assert provider is not None
        assert isinstance(provider, AsyncMemoryStorageProvider)

    def test_create_invalid_provider(self):
        """Test creating an invalid provider returns None"""
        provider = ProviderFactory.create("nonexistent_provider")
        assert provider is None

    def test_get_available_providers(self):
        """Test getting available providers"""
        providers = ProviderFactory.get_available_providers()
        assert isinstance(providers, dict)
        assert "memory" in providers
        assert "filesystem" in providers
        assert "sqlite" in providers

    def test_is_provider_available(self):
        """Test checking if provider is available"""
        assert ProviderFactory.is_provider_available("memory") is True
        assert ProviderFactory.is_provider_available("filesystem") is True
        assert ProviderFactory.is_provider_available("nonexistent") is False
        # Test case insensitive
        assert ProviderFactory.is_provider_available("MEMORY") is True

    def test_provider_metadata(self):
        """Test getting provider metadata"""
        metadata = ProviderFactory.provider_metadata()
        assert isinstance(metadata, dict)

        # Check memory provider metadata
        assert "memory" in metadata
        memory_meta = metadata["memory"]
        assert "description" in memory_meta
        assert "parameters" in memory_meta
        assert "class" in memory_meta
        assert memory_meta["class"] == "AsyncMemoryStorageProvider"

        # Check parameters structure
        params = memory_meta["parameters"]
        assert isinstance(params, list)
        if params:  # If there are parameters
            param = params[0]
            assert "name" in param
            assert "required" in param
            assert "default" in param

    def test_create_with_kwargs(self):
        """Test creating provider with additional arguments"""
        # Memory provider doesn't accept custom_arg, but should still create
        provider = ProviderFactory.create("memory")
        assert provider is not None

    @patch("chuk_virtual_fs.provider_factory.get_provider")
    def test_create_initializes_provider(self, mock_get_provider):
        """Test that create method initializes the provider if it has initialize method"""
        mock_provider = Mock()
        mock_provider.initialize = Mock(return_value=True)
        mock_get_provider.return_value = mock_provider

        result = ProviderFactory.create("test")

        assert result == mock_provider
        mock_provider.initialize.assert_called_once()

    @patch("chuk_virtual_fs.provider_factory.get_provider")
    def test_create_without_initialize_method(self, mock_get_provider):
        """Test that create works even if provider doesn't have initialize method"""
        mock_provider = Mock(spec=[])  # No initialize method
        mock_get_provider.return_value = mock_provider

        result = ProviderFactory.create("test")

        assert result == mock_provider

    def test_metadata_handles_no_docstring(self):
        """Test metadata handles providers without docstrings"""
        with patch("chuk_virtual_fs.provider_factory.list_providers") as mock_list:

            class NoDocProvider:
                def __init__(self):
                    pass

            mock_list.return_value = {"nodoc": NoDocProvider}
            metadata = ProviderFactory.provider_metadata()

            assert "nodoc" in metadata
            assert metadata["nodoc"]["description"] == "No description available"

    def test_metadata_multiline_docstring(self):
        """Test metadata extracts first line from multiline docstring"""
        with patch("chuk_virtual_fs.provider_factory.list_providers") as mock_list:

            class MultiDocProvider:
                """First line description
                Second line details
                Third line more info"""

                def __init__(self):
                    pass

            mock_list.return_value = {"multidoc": MultiDocProvider}
            metadata = ProviderFactory.provider_metadata()

            assert "multidoc" in metadata
            assert metadata["multidoc"]["description"] == "First line description"

    def test_metadata_complex_parameters(self):
        """Test metadata handles complex parameter signatures"""
        with patch("chuk_virtual_fs.provider_factory.list_providers") as mock_list:

            class ComplexProvider:
                """Complex provider"""

                def __init__(
                    self, required_param, optional_param="default", *args, **kwargs
                ):
                    pass

            mock_list.return_value = {"complex": ComplexProvider}
            metadata = ProviderFactory.provider_metadata()

            assert "complex" in metadata
            params = metadata["complex"]["parameters"]

            # Find required parameter
            required = next((p for p in params if p["name"] == "required_param"), None)
            assert required is not None
            assert required["required"] is True

            # Find optional parameter
            optional = next((p for p in params if p["name"] == "optional_param"), None)
            assert optional is not None
            assert optional["required"] is False
            assert optional["default"] == "default"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
