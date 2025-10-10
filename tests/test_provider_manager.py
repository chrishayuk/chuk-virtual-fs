"""
Test module for ProviderManager
"""

from unittest.mock import Mock, patch

import pytest

from chuk_virtual_fs.node_info import FSNodeInfo
from chuk_virtual_fs.provider_manager import ProviderManager


class TestProviderManager:
    """Test ProviderManager functionality"""

    @patch("chuk_virtual_fs.provider_manager.get_provider")
    def test_create_provider_success(self, mock_get_provider):
        """Test successful provider creation"""
        mock_provider = Mock()
        mock_provider.initialize = Mock(return_value=True)
        mock_get_provider.return_value = mock_provider

        provider = ProviderManager.create_provider("test")

        assert provider == mock_provider
        mock_get_provider.assert_called_once_with("test")
        mock_provider.initialize.assert_called_once()

    @patch("chuk_virtual_fs.provider_manager.get_provider")
    def test_create_provider_not_found(self, mock_get_provider):
        """Test provider creation fails when provider not found"""
        mock_get_provider.return_value = None

        with pytest.raises(ValueError, match="Provider 'nonexistent' not found"):
            ProviderManager.create_provider("nonexistent")

    @patch("chuk_virtual_fs.provider_manager.get_provider")
    def test_create_provider_initialization_failure(self, mock_get_provider):
        """Test provider creation fails when initialization fails"""
        mock_provider = Mock()
        mock_provider.initialize = Mock(return_value=False)
        mock_get_provider.return_value = mock_provider

        with pytest.raises(ValueError, match="Failed to initialize provider 'test'"):
            ProviderManager.create_provider("test")

    @patch("chuk_virtual_fs.provider_manager.get_provider")
    def test_create_provider_with_args(self, mock_get_provider):
        """Test provider creation with arguments"""
        mock_provider = Mock()
        mock_provider.initialize = Mock(return_value=True)
        mock_get_provider.return_value = mock_provider

        provider = ProviderManager.create_provider("test", arg1="value1", arg2="value2")

        assert provider == mock_provider
        mock_get_provider.assert_called_once_with("test", arg1="value1", arg2="value2")

    def test_change_provider_success(self):
        """Test successful provider change"""
        current_provider = Mock()

        with patch.object(ProviderManager, "create_provider") as mock_create:
            new_provider = Mock()
            mock_create.return_value = new_provider

            result = ProviderManager.change_provider(
                current_provider, "new_provider", arg="value"
            )

            assert result == new_provider
            mock_create.assert_called_once_with("new_provider", arg="value")

    def test_change_provider_failure(self):
        """Test provider change returns None on failure"""
        current_provider = Mock()

        with patch.object(ProviderManager, "create_provider") as mock_create:
            mock_create.side_effect = ValueError("Creation failed")

            result = ProviderManager.change_provider(current_provider, "new_provider")

            assert result is None

    def test_initialize_basic_structure_root_exists(self):
        """Test initializing basic structure when root exists"""
        mock_provider = Mock()
        mock_root_info = Mock()
        mock_provider.get_node_info = Mock(return_value=mock_root_info)

        ProviderManager.initialize_basic_structure(mock_provider)

        mock_provider.get_node_info.assert_called_once_with("/")
        # Should not create root if it exists
        mock_provider.create_node.assert_not_called()

    def test_initialize_basic_structure_create_root(self):
        """Test initializing basic structure creates root if missing"""
        mock_provider = Mock()
        mock_provider.get_node_info = Mock(return_value=None)
        mock_provider.create_node = Mock(return_value=True)

        ProviderManager.initialize_basic_structure(mock_provider)

        mock_provider.get_node_info.assert_called_once_with("/")
        # Should create root
        mock_provider.create_node.assert_called_once()

        # Check the created node is a root directory
        created_node = mock_provider.create_node.call_args[0][0]
        assert isinstance(created_node, FSNodeInfo)
        assert created_node.name == ""
        assert created_node.is_dir is True

    def test_create_provider_memory(self):
        """Test creating actual memory provider"""
        provider = ProviderManager.create_provider("memory")
        assert provider is not None
        # Memory provider should initialize successfully

    def test_change_provider_memory_to_memory(self):
        """Test changing from memory to memory provider"""
        current_provider = ProviderManager.create_provider("memory")
        new_provider = ProviderManager.change_provider(current_provider, "memory")
        assert new_provider is not None
        assert new_provider != current_provider  # Should be a new instance

    @patch("chuk_virtual_fs.provider_manager.get_provider")
    def test_create_provider_exception_in_init(self, mock_get_provider):
        """Test handling exception during provider initialization"""
        mock_provider = Mock()
        mock_provider.initialize = Mock(side_effect=Exception("Init error"))
        mock_get_provider.return_value = mock_provider

        with pytest.raises(Exception, match="Init error"):
            ProviderManager.create_provider("test")

    def test_initialize_basic_structure_with_mock_filesystem(self):
        """Test basic structure initialization with full mock"""
        mock_provider = Mock()

        # Simulate no root initially
        mock_provider.get_node_info = Mock(return_value=None)
        mock_provider.create_node = Mock(return_value=True)

        ProviderManager.initialize_basic_structure(mock_provider)

        # Verify root creation
        calls = mock_provider.create_node.call_args_list
        assert len(calls) == 1
        root_node = calls[0][0][0]
        assert root_node.name == ""
        assert root_node.is_dir is True

    def test_change_provider_preserves_current_on_failure(self):
        """Test that current provider is preserved when change fails"""
        current_provider = Mock()
        current_provider.some_data = "test_data"

        with patch.object(ProviderManager, "create_provider") as mock_create:
            mock_create.side_effect = ValueError("Cannot create")

            result = ProviderManager.change_provider(current_provider, "bad_provider")

            assert result is None
            # Current provider should still be valid
            assert current_provider.some_data == "test_data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
