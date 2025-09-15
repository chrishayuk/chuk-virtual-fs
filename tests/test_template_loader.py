"""
tests/test_async_template_loader.py - Tests for async template loader
"""

import json
import os
import tempfile

import pytest
import yaml

from chuk_virtual_fs.fs_manager import AsyncVirtualFileSystem
from chuk_virtual_fs.template_loader import AsyncTemplateLoader


class TestAsyncTemplateLoader:
    """Test async template loader functionality"""

    @pytest.fixture
    async def vfs(self):
        """Create an async virtual filesystem for testing"""
        fs = AsyncVirtualFileSystem(provider="memory")
        await fs.initialize()
        yield fs
        await fs.close()

    @pytest.fixture
    async def template_loader(self, vfs):
        """Create a template loader for testing"""
        return AsyncTemplateLoader(vfs)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Template loader needs full async conversion")
    async def test_apply_basic_template(self, vfs, template_loader):
        """Test applying a basic template with directories and files"""
        template_data = {
            "directories": ["/app", "/app/config", "/app/data"],
            "files": [
                {
                    "path": "/app/config/settings.json",
                    "content": '{"debug": true, "port": 8080}',
                },
                {
                    "path": "/app/README.md",
                    "content": "# My Application\n\nThis is a test application.",
                },
            ],
        }

        success = await template_loader.apply_template(template_data)
        assert success

        # Verify directories were created
        assert await vfs.exists("/app")
        assert await vfs.exists("/app/config")
        assert await vfs.exists("/app/data")

        # Verify files were created
        assert await vfs.exists("/app/config/settings.json")
        assert await vfs.exists("/app/README.md")

        # Verify file contents
        settings_content = await vfs.read_file(
            "/app/config/settings.json", as_text=True
        )
        assert "debug" in settings_content
        assert "8080" in settings_content

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Template loader needs full async conversion")
    async def test_template_with_variables(self, vfs, template_loader):
        """Test template with variable substitution"""
        template_data = {
            "directories": ["/${app_name}"],
            "files": [
                {
                    "path": "/${app_name}/config.json",
                    "content": '{"name": "${app_name}", "version": "${version}"}',
                }
            ],
        }

        variables = {"app_name": "myapp", "version": "1.0.0"}

        success = await template_loader.apply_template(template_data, "/", variables)
        assert success

        # Verify directory and file with substituted names
        assert await vfs.exists("/myapp")
        assert await vfs.exists("/myapp/config.json")

        # Verify content substitution
        content = await vfs.read_file("/myapp/config.json", as_text=True)
        assert "myapp" in content
        assert "1.0.0" in content

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Template loader needs full async conversion")
    async def test_load_yaml_template(self, vfs, template_loader):
        """Test loading template from YAML file"""
        template_data = {
            "directories": ["/yaml_test"],
            "files": [{"path": "/yaml_test/test.txt", "content": "Test from YAML"}],
        }

        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(template_data, f)
            yaml_file = f.name

        try:
            success = await template_loader.load_template(yaml_file)
            assert success

            assert await vfs.exists("/yaml_test")
            assert await vfs.exists("/yaml_test/test.txt")

            content = await vfs.read_file("/yaml_test/test.txt", as_text=True)
            assert content == "Test from YAML"

        finally:
            os.unlink(yaml_file)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Template loader needs full async conversion")
    async def test_load_json_template(self, vfs, template_loader):
        """Test loading template from JSON file"""
        template_data = {
            "directories": ["/json_test"],
            "files": [
                {
                    "path": "/json_test/data.json",
                    "content": '{"source": "JSON template"}',
                }
            ],
        }

        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(template_data, f)
            json_file = f.name

        try:
            success = await template_loader.load_template(json_file)
            assert success

            assert await vfs.exists("/json_test")
            assert await vfs.exists("/json_test/data.json")

        finally:
            os.unlink(json_file)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Template loader needs full async conversion")
    async def test_quick_load(self, vfs, template_loader):
        """Test quick loading of files from dictionary"""
        content_dict = {
            "app.py": "print('Hello World')",
            "config/settings.ini": "[DEFAULT]\ndebug = True",
            "data/sample.txt": "Sample data",
        }

        loaded_count = await template_loader.quick_load(content_dict, "/project")
        assert loaded_count == 3

        # Verify files were created
        assert await vfs.exists("/project/app.py")
        assert await vfs.exists("/project/config/settings.ini")
        assert await vfs.exists("/project/data/sample.txt")

        # Verify content
        app_content = await vfs.read_file("/project/app.py", as_text=True)
        assert "Hello World" in app_content

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Template loader needs full async conversion")
    async def test_preload_directory(self, vfs, template_loader):
        """Test preloading files from a host directory"""
        # Create a temporary directory with test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = {
                "file1.txt": "Content 1",
                "file2.txt": "Content 2",
                "subdir/file3.txt": "Content 3",
            }

            for file_path, content in test_files.items():
                full_path = os.path.join(temp_dir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)

            # Preload directory
            loaded_count = await template_loader.preload_directory(temp_dir, "/loaded")
            assert loaded_count == 3

            # Verify files were loaded
            assert await vfs.exists("/loaded/file1.txt")
            assert await vfs.exists("/loaded/file2.txt")
            assert await vfs.exists("/loaded/subdir/file3.txt")

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Template loader needs full async conversion")
    async def test_preload_directory_with_pattern(self, vfs, template_loader):
        """Test preloading files with pattern filtering"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mixed file types
            test_files = {
                "data.txt": "Text file",
                "config.json": '{"test": true}',
                "script.py": "print('test')",
                "image.png": "fake png data",
            }

            for file_path, content in test_files.items():
                full_path = os.path.join(temp_dir, file_path)
                with open(full_path, "w") as f:
                    f.write(content)

            # Load only .txt files
            loaded_count = await template_loader.preload_directory(
                temp_dir, "/filtered", pattern="*.txt"
            )
            assert loaded_count == 1

            # Verify only txt file was loaded
            assert await vfs.exists("/filtered/data.txt")
            assert not await vfs.exists("/filtered/config.json")

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Template loader needs full async conversion")
    async def test_load_from_template_directory(self, vfs, template_loader):
        """Test loading all templates from a directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create template files
            template1 = {"directories": ["/template1"], "files": []}
            template2 = {"directories": ["/template2"], "files": []}

            with open(os.path.join(temp_dir, "template1.yaml"), "w") as f:
                yaml.dump(template1, f)

            with open(os.path.join(temp_dir, "template2.json"), "w") as f:
                json.dump(template2, f)

            # Load all templates
            results = await template_loader.load_from_template_directory(temp_dir)

            assert len(results) == 2
            assert "template1.yaml" in results
            assert "template2.json" in results
            assert results["template1.yaml"] == 1  # success
            assert results["template2.json"] == 1  # success

            # Verify directories were created
            assert await vfs.exists("/template1")
            assert await vfs.exists("/template2")
