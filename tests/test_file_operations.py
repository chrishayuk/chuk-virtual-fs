"""
Comprehensive pytest test suite for async file operations
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from chuk_virtual_fs.file_operations import FileOperations
from chuk_virtual_fs.node_info import EnhancedNodeInfo


@pytest.fixture
def mock_fs_provider():
    """Create a mock filesystem provider"""
    provider = AsyncMock()
    provider.current_directory_path = "/"
    return provider


@pytest.fixture
def mock_path_resolver():
    """Create a mock path resolver"""
    resolver = MagicMock()

    # Simple implementation that just joins paths
    def resolve(base, path):
        if path.startswith("/"):
            return path
        return f"{base.rstrip('/')}/{path}"

    resolver.resolve_path = MagicMock(side_effect=resolve)
    return resolver


class TestCopyOperations:
    """Test copy operations"""

    @pytest.mark.asyncio
    async def test_copy_file_success(self, mock_fs_provider, mock_path_resolver):
        """Test successful file copy"""
        # Setup source file
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        mock_fs_provider.read_file.return_value = b"file content"
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.write_file.return_value = True

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source.txt", "/dest.txt"
        )

        assert result is True
        mock_fs_provider.read_file.assert_called_once()
        mock_fs_provider.create_node.assert_called_once()
        mock_fs_provider.write_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_copy_file_source_not_found(
        self, mock_fs_provider, mock_path_resolver
    ):
        """Test copy when source file doesn't exist"""
        mock_fs_provider.get_node_info.return_value = None

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/nonexistent.txt", "/dest.txt"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_file_dest_parent_not_found(
        self, mock_fs_provider, mock_path_resolver
    ):
        """Test copy when destination parent doesn't exist"""
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists
            None,  # Dest parent doesn't exist
        ]

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source.txt", "/nonexistent/dest.txt"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_file_dest_parent_is_file(
        self, mock_fs_provider, mock_path_resolver
    ):
        """Test copy when destination parent is a file (not a directory)"""
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        dest_parent_info = EnhancedNodeInfo(
            name="file.txt", is_dir=False, parent_path="/"
        )

        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists
            dest_parent_info,  # Dest parent is a file
        ]

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source.txt", "/file.txt/dest.txt"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_file_read_failure(self, mock_fs_provider, mock_path_resolver):
        """Test copy when reading source file fails"""
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        mock_fs_provider.read_file.return_value = None

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source.txt", "/dest.txt"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_file_create_node_failure(
        self, mock_fs_provider, mock_path_resolver
    ):
        """Test copy when creating destination node fails"""
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        mock_fs_provider.read_file.return_value = b"file content"
        mock_fs_provider.create_node.return_value = False

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source.txt", "/dest.txt"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_file_write_failure(self, mock_fs_provider, mock_path_resolver):
        """Test copy when writing to destination fails"""
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        mock_fs_provider.read_file.return_value = b"file content"
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.write_file.return_value = False

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source.txt", "/dest.txt"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_directory_success(self, mock_fs_provider, mock_path_resolver):
        """Test successful directory copy"""
        source_dir_info = EnhancedNodeInfo(
            name="source_dir", is_dir=True, parent_path="/"
        )
        dest_parent_info = EnhancedNodeInfo(
            name="dest_parent", is_dir=True, parent_path="/"
        )

        mock_fs_provider.get_node_info.side_effect = [
            source_dir_info,  # Source directory
            dest_parent_info,  # Dest parent exists
        ]
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.list_directory.return_value = []  # Empty directory

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source_dir", "/dest_dir"
        )

        assert result is True
        mock_fs_provider.create_node.assert_called_once()
        mock_fs_provider.list_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_copy_directory_with_files(
        self, mock_fs_provider, mock_path_resolver
    ):
        """Test copying directory with files"""
        source_dir_info = EnhancedNodeInfo(
            name="source_dir", is_dir=True, parent_path="/"
        )
        dest_parent_info = EnhancedNodeInfo(
            name="dest_parent", is_dir=True, parent_path="/"
        )
        file_info = EnhancedNodeInfo(
            name="file.txt", is_dir=False, parent_path="/source_dir"
        )

        # Track call order
        call_count = [0]

        def get_node_info_side_effect(path):
            call_count[0] += 1
            if call_count[0] == 1:
                return source_dir_info  # First call - source directory
            elif call_count[0] == 2:
                return dest_parent_info  # Second call - dest parent
            elif call_count[0] == 3:
                return file_info  # Third call - source file
            elif call_count[0] == 4:
                return dest_parent_info  # Fourth call - dest parent for file
            return None

        mock_fs_provider.get_node_info.side_effect = get_node_info_side_effect
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.list_directory.return_value = ["file.txt"]
        mock_fs_provider.read_file.return_value = b"content"
        mock_fs_provider.write_file.return_value = True

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source_dir", "/dest_dir"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_copy_directory_create_failure(
        self, mock_fs_provider, mock_path_resolver
    ):
        """Test copy when creating destination directory fails"""
        source_dir_info = EnhancedNodeInfo(
            name="source_dir", is_dir=True, parent_path="/"
        )
        dest_parent_info = EnhancedNodeInfo(
            name="dest_parent", is_dir=True, parent_path="/"
        )

        mock_fs_provider.get_node_info.side_effect = [
            source_dir_info,  # Source directory
            dest_parent_info,  # Dest parent exists
        ]
        mock_fs_provider.create_node.return_value = False

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "/source_dir", "/dest_dir"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_with_relative_paths(self, mock_fs_provider, mock_path_resolver):
        """Test copy with relative paths"""
        source_info = EnhancedNodeInfo(
            name="source.txt", is_dir=False, parent_path="/home"
        )
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        mock_fs_provider.read_file.return_value = b"file content"
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.write_file.return_value = True

        result = await FileOperations.copy(
            mock_fs_provider, mock_path_resolver, "source.txt", "dest.txt"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_copy_provider_without_current_directory(self, mock_path_resolver):
        """Test copy with provider that doesn't have current_directory_path"""
        provider = AsyncMock()
        # Remove current_directory_path attribute
        delattr(provider, "current_directory_path")

        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        provider.get_node_info.side_effect = [
            source_info,  # Source exists
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        provider.read_file.return_value = b"file content"
        provider.create_node.return_value = True
        provider.write_file.return_value = True

        result = await FileOperations.copy(
            provider, mock_path_resolver, "/source.txt", "/dest.txt"
        )

        assert result is True


class TestMoveOperations:
    """Test move operations"""

    @pytest.mark.asyncio
    async def test_move_file_success(self, mock_fs_provider, mock_path_resolver):
        """Test successful file move"""
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists (for copy)
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        mock_fs_provider.read_file.return_value = b"file content"
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.write_file.return_value = True
        mock_fs_provider.delete_node.return_value = True

        result = await FileOperations.move(
            mock_fs_provider, mock_path_resolver, "/source.txt", "/dest.txt"
        )

        assert result is True
        mock_fs_provider.delete_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_move_file_copy_failure(self, mock_fs_provider, mock_path_resolver):
        """Test move when copy fails"""
        mock_fs_provider.get_node_info.return_value = None

        result = await FileOperations.move(
            mock_fs_provider, mock_path_resolver, "/nonexistent.txt", "/dest.txt"
        )

        assert result is False
        mock_fs_provider.delete_node.assert_not_called()

    @pytest.mark.asyncio
    async def test_move_file_delete_failure(self, mock_fs_provider, mock_path_resolver):
        """Test move when delete fails after successful copy"""
        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists (for copy)
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        mock_fs_provider.read_file.return_value = b"file content"
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.write_file.return_value = True
        mock_fs_provider.delete_node.return_value = False

        result = await FileOperations.move(
            mock_fs_provider, mock_path_resolver, "/source.txt", "/dest.txt"
        )

        assert result is False
        mock_fs_provider.delete_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_move_directory_success(self, mock_fs_provider, mock_path_resolver):
        """Test successful directory move"""
        source_dir_info = EnhancedNodeInfo(
            name="source_dir", is_dir=True, parent_path="/"
        )
        dest_parent_info = EnhancedNodeInfo(
            name="dest_parent", is_dir=True, parent_path="/"
        )

        mock_fs_provider.get_node_info.side_effect = [
            source_dir_info,  # Source directory
            dest_parent_info,  # Dest parent exists
        ]
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.list_directory.return_value = []
        mock_fs_provider.delete_node.return_value = True

        result = await FileOperations.move(
            mock_fs_provider, mock_path_resolver, "/source_dir", "/dest_dir"
        )

        assert result is True
        mock_fs_provider.delete_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_move_with_relative_paths(self, mock_fs_provider, mock_path_resolver):
        """Test move with relative paths"""
        source_info = EnhancedNodeInfo(
            name="source.txt", is_dir=False, parent_path="/home"
        )
        mock_fs_provider.get_node_info.side_effect = [
            source_info,  # Source exists
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        mock_fs_provider.read_file.return_value = b"file content"
        mock_fs_provider.create_node.return_value = True
        mock_fs_provider.write_file.return_value = True
        mock_fs_provider.delete_node.return_value = True

        result = await FileOperations.move(
            mock_fs_provider, mock_path_resolver, "source.txt", "dest.txt"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_move_provider_without_current_directory(self, mock_path_resolver):
        """Test move with provider that doesn't have current_directory_path"""
        provider = AsyncMock()
        # Remove current_directory_path attribute
        delattr(provider, "current_directory_path")

        source_info = EnhancedNodeInfo(name="source.txt", is_dir=False, parent_path="/")
        provider.get_node_info.side_effect = [
            source_info,  # Source exists
            EnhancedNodeInfo(
                name="dest_dir", is_dir=True, parent_path="/"
            ),  # Dest parent exists
        ]
        provider.read_file.return_value = b"file content"
        provider.create_node.return_value = True
        provider.write_file.return_value = True
        provider.delete_node.return_value = True

        result = await FileOperations.move(
            provider, mock_path_resolver, "/source.txt", "/dest.txt"
        )

        assert result is True
