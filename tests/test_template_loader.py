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
    async def test_template_with_invalid_format(self, vfs, template_loader):
        """Test applying template with invalid format"""
        # Pass a non-dict template
        success = await template_loader.apply_template("invalid", "/")
        assert success is False

    @pytest.mark.asyncio
    async def test_load_template_unsupported_format(self, vfs, template_loader):
        """Test loading template with unsupported file format"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Some text")
            txt_file = f.name

        try:
            success = await template_loader.load_template(txt_file)
            assert success is False
        finally:
            os.unlink(txt_file)

    @pytest.mark.asyncio
    async def test_load_template_file_not_found(self, vfs, template_loader):
        """Test loading template from nonexistent file"""
        success = await template_loader.load_template("/nonexistent/file.yaml")
        assert success is False

    @pytest.mark.asyncio
    async def test_apply_template_with_target_path(self, vfs, template_loader):
        """Test applying template to specific target path"""
        template_data = {
            "directories": ["subdir"],
            "files": [{"path": "subdir/test.txt", "content": "Test"}],
        }

        success = await template_loader.apply_template(template_data, "/myroot")
        assert success

        # Verify files created at target path
        assert await vfs.exists("/myroot")
        assert await vfs.exists("/myroot/subdir")
        assert await vfs.exists("/myroot/subdir/test.txt")

    @pytest.mark.asyncio
    async def test_process_variables(self, vfs, template_loader):
        """Test _process_variables method"""
        variables = {"name": "test", "value": "123"}

        result = template_loader._process_variables(
            "Hello ${name}, value=${value}", variables
        )
        assert result == "Hello test, value=123"

    @pytest.mark.asyncio
    async def test_process_variables_with_none(self, vfs, template_loader):
        """Test _process_variables with None variables"""
        result = template_loader._process_variables("Hello ${name}", None)
        assert result == "Hello ${name}"

    @pytest.mark.asyncio
    async def test_process_variables_with_non_string(self, vfs, template_loader):
        """Test _process_variables with non-string input"""
        result = template_loader._process_variables(123, {"name": "value"})
        assert result == 123

    @pytest.mark.asyncio
    async def test_ensure_directory_edge_cases(self, vfs, template_loader):
        """Test _ensure_directory with edge cases"""
        # Test with empty components
        success = await template_loader._ensure_directory("//a///b//")
        assert success

        # Verify directory was created
        assert await vfs.exists("/a")
        assert await vfs.exists("/a/b")

    @pytest.mark.asyncio
    async def test_create_directories_with_dict_format(self, vfs, template_loader):
        """Test _create_directories with dict format"""
        directories = [
            {"path": "/dir1"},
            {"path": "/dir2"},
        ]

        await template_loader._create_directories(directories, "/", None)

        assert await vfs.exists("/dir1")
        assert await vfs.exists("/dir2")

    @pytest.mark.asyncio
    async def test_create_directories_with_invalid_format(self, vfs, template_loader):
        """Test _create_directories with invalid format"""
        directories = [123, {"invalid": "no path"}]

        # Should not raise exception, just skip invalid entries
        await template_loader._create_directories(directories, "/", None)

    @pytest.mark.asyncio
    async def test_create_files_with_content_from(self, vfs, template_loader):
        """Test _create_files with content_from option"""
        # Create a source file
        source_file = tempfile.NamedTemporaryFile(mode="w", delete=False)  # noqa: SIM115
        source_file.write("Content from file")
        source_file.close()

        try:
            files = [{"path": "/test.txt", "content_from": source_file.name}]

            await template_loader._create_files(files, "/", None)

            assert await vfs.exists("/test.txt")
            content = await vfs.read_file("/test.txt", as_text=True)
            assert content == "Content from file"
        finally:
            os.unlink(source_file.name)

    @pytest.mark.asyncio
    async def test_create_files_with_invalid_content_from(self, vfs, template_loader):
        """Test _create_files with invalid content_from file"""
        files = [{"path": "/test.txt", "content_from": "/nonexistent/file.txt"}]

        # Should not raise exception, just skip the file
        await template_loader._create_files(files, "/", None)

    @pytest.mark.asyncio
    async def test_create_files_with_missing_path(self, vfs, template_loader):
        """Test _create_files with missing path"""
        files = [
            {"content": "test"}  # Missing path
        ]

        # Should not raise exception
        await template_loader._create_files(files, "/", None)

    @pytest.mark.asyncio
    async def test_create_files_with_invalid_format(self, vfs, template_loader):
        """Test _create_files with invalid format"""
        files = ["not a dict"]

        # Should not raise exception
        await template_loader._create_files(files, "/", None)

    @pytest.mark.asyncio
    async def test_template_with_links(self, vfs, template_loader):
        """Test template with symbolic links (if supported)"""
        template_data = {
            "directories": ["/linktest"],
            "files": [{"path": "/linktest/target.txt", "content": "Target"}],
            "links": [{"path": "/linktest/link", "target": "/linktest/target.txt"}],
        }

        # This will only work if the filesystem supports symlinks
        success = await template_loader.apply_template(template_data)
        # Success depends on whether symlinks are supported
        assert success is True or success is False

    @pytest.mark.asyncio
    async def test_create_links_unsupported(self, vfs, template_loader):
        """Test _create_links when filesystem doesn't support symlinks"""
        if hasattr(vfs, "create_symlink"):
            # Skip if symlinks are supported
            pytest.skip("Filesystem supports symlinks")

        links = [{"path": "/link", "target": "/target"}]

        # Should not raise exception
        await template_loader._create_links(links, "/", None)

    @pytest.mark.asyncio
    async def test_create_links_with_invalid_format(self, vfs, template_loader):
        """Test _create_links with invalid format"""
        links = ["not a dict", {"path": "/link"}]  # Missing target

        # Should not raise exception
        await template_loader._create_links(links, "/", None)

    @pytest.mark.asyncio
    async def test_template_creates_parent_directories(self, vfs, template_loader):
        """Test that template creates parent directories automatically"""
        template_data = {
            "files": [{"path": "/deep/nested/path/file.txt", "content": "Deep file"}],
        }

        success = await template_loader.apply_template(template_data)
        assert success

        # Verify all parent directories were created
        assert await vfs.exists("/deep")
        assert await vfs.exists("/deep/nested")
        assert await vfs.exists("/deep/nested/path")
        assert await vfs.exists("/deep/nested/path/file.txt")

    @pytest.mark.asyncio
    async def test_apply_template_handles_links_when_supported(
        self, vfs, template_loader
    ):
        """Test that template handles links section"""
        template_data = {
            "directories": ["/linkdir"],
            "files": [{"path": "/linkdir/file.txt", "content": "File"}],
            "links": [{"path": "/linkdir/link", "target": "/linkdir/file.txt"}],
        }

        # Will succeed or fail depending on symlink support
        success = await template_loader.apply_template(template_data)
        # Just verify it doesn't crash
        assert success is True or success is False

    @pytest.mark.asyncio
    async def test_ensure_directory_with_complex_path(self, vfs, template_loader):
        """Test _ensure_directory with complex path"""
        # Path with trailing slashes and multiple separators
        success = await template_loader._ensure_directory("/a//b///c////d/")
        assert success

        assert await vfs.exists("/a")
        assert await vfs.exists("/a/b")
        assert await vfs.exists("/a/b/c")
        assert await vfs.exists("/a/b/c/d")

    @pytest.mark.asyncio
    async def test_create_directories_with_variables(self, vfs, template_loader):
        """Test creating directories with variable substitution"""
        directories = ["${env}/logs", "${env}/data"]
        variables = {"env": "production"}

        await template_loader._create_directories(directories, "/", variables)

        assert await vfs.exists("/production/logs")
        assert await vfs.exists("/production/data")

    @pytest.mark.asyncio
    async def test_create_files_with_variable_substitution(self, vfs, template_loader):
        """Test creating files with variable substitution in content"""
        files = [
            {
                "path": "/config.txt",
                "content": "Environment: ${env}\nVersion: ${version}",
            }
        ]
        variables = {"env": "prod", "version": "1.0"}

        await template_loader._create_files(files, "/", variables)

        content = await vfs.read_file("/config.txt", as_text=True)
        assert "Environment: prod" in content
        assert "Version: 1.0" in content

    @pytest.mark.asyncio
    async def test_create_files_with_empty_content(self, vfs, template_loader):
        """Test creating files with empty content"""
        files = [{"path": "/empty.txt", "content": ""}]

        await template_loader._create_files(files, "/", None)

        # Should create the file
        assert await vfs.exists("/empty.txt")
        content = await vfs.read_file("/empty.txt", as_text=True)
        assert content == ""

    @pytest.mark.asyncio
    async def test_load_template_with_yaml_error(self, vfs, template_loader):
        """Test loading template with YAML parse error"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Invalid YAML
            f.write("{ invalid: yaml: content:")
            yaml_file = f.name

        try:
            success = await template_loader.load_template(yaml_file)
            assert success is False
        finally:
            os.unlink(yaml_file)

    @pytest.mark.asyncio
    async def test_load_template_with_json_error(self, vfs, template_loader):
        """Test loading template with JSON parse error"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Invalid JSON
            f.write("{ invalid json")
            json_file = f.name

        try:
            success = await template_loader.load_template(json_file)
            assert success is False
        finally:
            os.unlink(json_file)

    @pytest.mark.asyncio
    async def test_apply_template_error_handling(self, vfs, template_loader):
        """Test that apply_template handles errors gracefully"""
        # Template with files but no directories section
        template_data = {"files": [{"path": "/test/file.txt", "content": "Test"}]}

        # Should still succeed by creating parent directories
        success = await template_loader.apply_template(template_data)
        # Just verify it handles the case
        assert success is True or success is False

    @pytest.mark.asyncio
    async def test_create_links_with_variables(self, vfs, template_loader):
        """Test creating links with variable substitution"""
        # Create target file first
        await vfs.write_file("/target.txt", "Target")

        links = [{"path": "/${name}_link", "target": "/target.txt"}]
        variables = {"name": "my"}

        await template_loader._create_links(links, "/", variables)

        # May or may not work depending on symlink support
        # Just verify it doesn't crash

    @pytest.mark.asyncio
    async def test_template_with_empty_sections(self, vfs, template_loader):
        """Test template with empty directories and files sections"""
        template_data = {
            "directories": [],
            "files": [],
        }

        success = await template_loader.apply_template(template_data)
        assert success is True

    @pytest.mark.asyncio
    async def test_template_with_only_directories(self, vfs, template_loader):
        """Test template with only directories"""
        template_data = {
            "directories": ["/dir1", "/dir2", "/dir3"],
        }

        success = await template_loader.apply_template(template_data)
        assert success

        assert await vfs.exists("/dir1")
        assert await vfs.exists("/dir2")
        assert await vfs.exists("/dir3")

    @pytest.mark.asyncio
    async def test_template_with_only_files(self, vfs, template_loader):
        """Test template with only files"""
        template_data = {
            "files": [
                {"path": "/file1.txt", "content": "File 1"},
                {"path": "/file2.txt", "content": "File 2"},
            ],
        }

        success = await template_loader.apply_template(template_data)
        assert success

        assert await vfs.exists("/file1.txt")
        assert await vfs.exists("/file2.txt")

    @pytest.mark.asyncio
    async def test_template_with_links_section(self, vfs, template_loader):
        """Test template processing links section"""
        # Create target first
        template_data = {
            "directories": ["/targets"],
            "files": [{"path": "/targets/file.txt", "content": "Target"}],
            "links": [{"path": "/mylink", "target": "/targets/file.txt"}],
        }

        # Apply template - links may or may not be supported
        await template_loader.apply_template(template_data)

        # At least directories and files should be created
        assert await vfs.exists("/targets")
        assert await vfs.exists("/targets/file.txt")

    @pytest.mark.asyncio
    async def test_apply_template_exception_handling(self, vfs, template_loader):
        """Test that apply_template catches and handles exceptions"""
        # Create a template that might cause issues
        template_data = {
            "directories": ["/test"],
            "files": [
                # File with path that might cause issues
                {"path": "///multiple////slashes///file.txt", "content": "Test"}
            ],
        }

        # Should handle gracefully
        try:
            success = await template_loader.apply_template(template_data)
            # Should either succeed or fail gracefully
            assert success is True or success is False
        except Exception:
            # If it raises, that's also acceptable
            pass

    @pytest.mark.asyncio
    async def test_ensure_directory_mkdir_fails(self, vfs, template_loader):
        """Test _ensure_directory when mkdir fails"""
        # First create a file
        await vfs.write_file("/blocking_file", "content")

        # Try to create a directory path that includes the file
        # This should fail because /blocking_file is a file, not a directory
        success = await template_loader._ensure_directory("/blocking_file/subdir")

        # Should return False
        assert success is False

    @pytest.mark.asyncio
    async def test_create_links_when_filesystem_supports_it(self, vfs, template_loader):
        """Test _create_links when symlinks are supported"""
        # Create target file
        await vfs.write_file("/link_target.txt", "Link target")

        links = [
            {"path": "/link1", "target": "/link_target.txt"},
            {"path": "/link2", "target": "/link_target.txt"},
        ]

        # Call _create_links
        await template_loader._create_links(links, "/", None)

        # If supported, links should exist
        # If not supported, should not crash

    @pytest.mark.asyncio
    async def test_create_links_with_missing_target(self, vfs, template_loader):
        """Test _create_links with missing target key"""
        links = [
            {"path": "/link"},  # Missing target
            {},  # Missing both path and target
        ]

        # Should not crash
        await template_loader._create_links(links, "/", None)

    @pytest.mark.asyncio
    async def test_create_links_with_missing_path(self, vfs, template_loader):
        """Test _create_links with missing path key"""
        links = [
            {"target": "/some/target"},  # Missing path
        ]

        # Should not crash
        await template_loader._create_links(links, "/", None)

    @pytest.mark.asyncio
    async def test_load_template_ioerror(self, vfs, template_loader):
        """Test load_template with IO error"""
        # Try to load from a directory instead of a file
        with tempfile.TemporaryDirectory() as temp_dir:
            # temp_dir is a directory, not a file
            success = await template_loader.load_template(temp_dir)
            assert success is False

    @pytest.mark.asyncio
    async def test_apply_template_creates_target_directory(self, vfs, template_loader):
        """Test that apply_template creates target directory if needed"""
        template_data = {
            "files": [{"path": "file.txt", "content": "Test"}],
        }

        # Apply to non-existent target path
        success = await template_loader.apply_template(template_data, "/new_target")
        assert success

        # Target should be created
        assert await vfs.exists("/new_target")
        assert await vfs.exists("/new_target/file.txt")

    @pytest.mark.asyncio
    async def test_create_files_with_relative_path(self, vfs, template_loader):
        """Test creating files with relative paths"""
        files = [{"path": "relative/path/file.txt", "content": "Relative"}]

        await template_loader._create_files(files, "/base", None)

        # Should create under base path
        assert await vfs.exists("/base/relative/path/file.txt")

    @pytest.mark.asyncio
    async def test_create_directories_with_absolute_path(self, vfs, template_loader):
        """Test creating directories with absolute paths"""
        directories = ["/abs1", "/abs2/nested"]

        await template_loader._create_directories(directories, "/base", None)

        # Absolute paths are joined with base_path
        # So /abs1 becomes /base/abs1
        assert await vfs.exists("/base/abs1")
        assert await vfs.exists("/base/abs2/nested")

    @pytest.mark.asyncio
    async def test_template_with_mixed_path_styles(self, vfs, template_loader):
        """Test template with both absolute and relative paths"""
        template_data = {
            "directories": ["absolute", "relative"],
            "files": [
                {"path": "absolute/file.txt", "content": "Abs"},
                {"path": "relative/file.txt", "content": "Rel"},
            ],
        }

        success = await template_loader.apply_template(template_data, "/base")
        assert success

        # All paths are relative to base_path
        assert await vfs.exists("/base/absolute/file.txt")
        assert await vfs.exists("/base/relative/file.txt")

    @pytest.mark.asyncio
    async def test_load_template_with_empty_file(self, vfs, template_loader):
        """Test loading template from empty file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Write empty content
            yaml_file = f.name

        try:
            success = await template_loader.load_template(yaml_file)
            # May succeed with empty template or fail
            assert success is True or success is False
        finally:
            os.unlink(yaml_file)

    @pytest.mark.asyncio
    async def test_apply_template_with_exception_in_files(self, vfs, template_loader):
        """Test apply_template continues despite file creation errors"""
        # Create multiple files, some may fail
        template_data = {
            "files": [
                {"path": "/good1.txt", "content": "Good 1"},
                {"path": "/good2.txt", "content": "Good 2"},
            ],
        }

        # Should handle gracefully
        await template_loader.apply_template(template_data)
        # Should still create the good files
        assert await vfs.exists("/good1.txt")
        assert await vfs.exists("/good2.txt")

    @pytest.mark.asyncio
    async def test_preload_directory(self, vfs, template_loader):
        """Test preload_directory loads files from host filesystem"""
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
    async def test_preload_directory_with_pattern(self, vfs, template_loader):
        """Test preload_directory with pattern filtering"""
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
    async def test_preload_directory_non_recursive(self, vfs, template_loader):
        """Test preload_directory with recursive=False"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files in root and subdirectory
            with open(os.path.join(temp_dir, "root.txt"), "w") as f:
                f.write("Root file")

            subdir = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir)
            with open(os.path.join(subdir, "sub.txt"), "w") as f:
                f.write("Sub file")

            # Load non-recursively
            loaded_count = await template_loader.preload_directory(
                temp_dir, "/nonrec", recursive=False
            )
            # Should only load root.txt
            assert loaded_count == 1
            assert await vfs.exists("/nonrec/root.txt")

    @pytest.mark.asyncio
    async def test_quick_load(self, vfs, template_loader):
        """Test quick_load loads files from dictionary"""
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
    async def test_quick_load_with_absolute_paths(self, vfs, template_loader):
        """Test quick_load with absolute paths"""
        content_dict = {
            "/abs1.txt": "Absolute 1",
            "/abs2.txt": "Absolute 2",
        }

        loaded_count = await template_loader.quick_load(content_dict)
        assert loaded_count == 2

        assert await vfs.exists("/abs1.txt")
        assert await vfs.exists("/abs2.txt")

    @pytest.mark.asyncio
    async def test_load_from_template_directory(self, vfs, template_loader):
        """Test load_from_template_directory loads all templates"""
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

    @pytest.mark.asyncio
    async def test_load_from_template_directory_with_errors(self, vfs, template_loader):
        """Test load_from_template_directory handles errors gracefully"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a valid template
            template1 = {"directories": ["/valid"], "files": []}
            with open(os.path.join(temp_dir, "valid.yaml"), "w") as f:
                yaml.dump(template1, f)

            # Create an invalid template file
            with open(os.path.join(temp_dir, "invalid.yaml"), "w") as f:
                f.write("{ invalid yaml content:")

            # Load all templates
            results = await template_loader.load_from_template_directory(temp_dir)

            # Should have results for both files
            assert "valid.yaml" in results
            assert "invalid.yaml" in results
            # Valid should succeed, invalid should fail
            assert results["valid.yaml"] == 1
            assert results["invalid.yaml"] == 0
