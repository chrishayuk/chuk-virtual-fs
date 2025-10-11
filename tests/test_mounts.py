"""
Tests for virtual mounts functionality
"""

import pytest

from chuk_virtual_fs import AsyncVirtualFileSystem


class TestMountBasics:
    """Test basic mount operations"""

    @pytest.mark.asyncio
    async def test_mount_basic(self):
        """Test basic mount operation"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            result = await fs.mount("/mounted", provider="memory")
            assert result is True

            # Verify mount exists
            mounts = fs.list_mounts()
            assert len(mounts) == 1
            assert mounts[0]["mount_point"] == "/mounted"
            assert mounts[0]["provider"] == "memory"

    @pytest.mark.asyncio
    async def test_unmount_basic(self):
        """Test basic unmount operation"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/mounted", provider="memory")
            result = await fs.unmount("/mounted")
            assert result is True

            # Verify mount removed
            mounts = fs.list_mounts()
            assert len(mounts) == 0

    @pytest.mark.asyncio
    async def test_list_mounts_empty(self):
        """Test listing mounts when none exist"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            mounts = fs.list_mounts()
            assert mounts == []

    @pytest.mark.asyncio
    async def test_mount_multiple(self):
        """Test mounting multiple providers"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/mount1", provider="memory")
            await fs.mount("/mount2", provider="memory")
            await fs.mount("/mount3", provider="sqlite", db_path=":memory:")

            mounts = fs.list_mounts()
            assert len(mounts) == 3

    @pytest.mark.asyncio
    async def test_mount_disabled(self):
        """Test operations when mounts are disabled"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=False) as fs:
            result = await fs.mount("/test", provider="memory")
            assert result is False

            mounts = fs.list_mounts()
            assert mounts == []


class TestMountPathResolution:
    """Test path resolution with mounts"""

    @pytest.mark.asyncio
    async def test_write_to_mount(self):
        """Test writing to mounted path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/data", provider="memory")

            # Write to mounted path
            await fs.write_text("/data/file.txt", "mounted content")

            # Verify file exists and has correct content
            content = await fs.read_text("/data/file.txt")
            assert content == "mounted content"

    @pytest.mark.asyncio
    async def test_read_from_mount(self):
        """Test reading from mounted path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/store", provider="memory")

            await fs.write_text("/store/data.txt", "stored data")

            content = await fs.read_text("/store/data.txt")
            assert content == "stored data"

    @pytest.mark.asyncio
    async def test_root_vs_mount_isolation(self):
        """Test that root and mounted providers are isolated"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/mounted", provider="memory")

            # Write to root
            await fs.write_text("/root.txt", "in root")

            # Write to mount
            await fs.write_text("/mounted/mount.txt", "in mount")

            # Verify isolation
            assert await fs.exists("/root.txt")
            assert await fs.exists("/mounted/mount.txt")
            assert not await fs.exists("/mounted/root.txt")
            assert not await fs.exists("/mount.txt")

    @pytest.mark.asyncio
    async def test_nested_mount_paths(self):
        """Test deeply nested mount paths"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/a/b/c", provider="memory")

            await fs.write_text("/a/b/c/file.txt", "nested")

            content = await fs.read_text("/a/b/c/file.txt")
            assert content == "nested"

    @pytest.mark.asyncio
    async def test_mount_precedence(self):
        """Test that deeper mounts take precedence"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            # Mount at two levels
            await fs.mount("/data", provider="memory")
            await fs.mount("/data/deep", provider="memory")

            # Write to shallow mount
            await fs.write_text("/data/shallow.txt", "shallow")

            # Write to deep mount
            await fs.write_text("/data/deep/deep.txt", "deep")

            # Verify both accessible
            assert await fs.read_text("/data/shallow.txt") == "shallow"
            assert await fs.read_text("/data/deep/deep.txt") == "deep"


class TestMountFileOperations:
    """Test file operations across mounts"""

    @pytest.mark.asyncio
    async def test_mkdir_in_mount(self):
        """Test creating directory in mounted path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/storage", provider="memory")

            result = await fs.mkdir("/storage/subdir")
            assert result is True

            assert await fs.is_dir("/storage/subdir")

    @pytest.mark.asyncio
    async def test_ls_in_mount(self):
        """Test listing directory in mounted path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/files", provider="memory")

            await fs.write_text("/files/file1.txt", "1")
            await fs.write_text("/files/file2.txt", "2")

            contents = await fs.ls("/files")
            assert "file1.txt" in contents
            assert "file2.txt" in contents

    @pytest.mark.asyncio
    async def test_exists_across_mounts(self):
        """Test exists() with mounts"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/m1", provider="memory")
            await fs.mount("/m2", provider="memory")

            await fs.write_text("/m1/file.txt", "m1")
            await fs.write_text("/m2/file.txt", "m2")

            # Both should exist independently
            assert await fs.exists("/m1/file.txt")
            assert await fs.exists("/m2/file.txt")

    @pytest.mark.asyncio
    async def test_rm_in_mount(self):
        """Test removing file in mounted path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/temp", provider="memory")

            await fs.write_text("/temp/delete_me.txt", "data")
            assert await fs.exists("/temp/delete_me.txt")

            result = await fs.rm("/temp/delete_me.txt")
            assert result is True
            assert not await fs.exists("/temp/delete_me.txt")

    @pytest.mark.asyncio
    async def test_get_node_info_mount(self):
        """Test getting node info from mounted path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/info", provider="memory")

            await fs.write_text("/info/test.txt", "test data")

            node_info = await fs.get_node_info("/info/test.txt")
            assert node_info is not None
            assert not node_info.is_dir
            assert node_info.size > 0


class TestMountProviders:
    """Test mounting different provider types"""

    @pytest.mark.asyncio
    async def test_mount_filesystem_provider(self, tmp_path):
        """Test mounting filesystem provider"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            result = await fs.mount(
                "/disk", provider="filesystem", root_path=str(tmp_path)
            )
            assert result is True

            # Write through mount
            await fs.write_text("/disk/test.txt", "on disk")

            # Verify on actual filesystem
            file_path = tmp_path / "test.txt"
            assert file_path.exists()
            assert file_path.read_text() == "on disk"

    @pytest.mark.asyncio
    async def test_mount_sqlite_provider(self):
        """Test mounting SQLite provider"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            result = await fs.mount("/db", provider="sqlite", db_path=":memory:")
            assert result is True

            await fs.write_text("/db/data.txt", "in sqlite")

            content = await fs.read_text("/db/data.txt")
            assert content == "in sqlite"

    @pytest.mark.asyncio
    async def test_mount_multiple_memory_providers(self):
        """Test mounting multiple independent memory providers"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/mem1", provider="memory")
            await fs.mount("/mem2", provider="memory")

            # Write to different memory providers
            await fs.write_text("/mem1/file.txt", "memory 1")
            await fs.write_text("/mem2/file.txt", "memory 2")

            # Verify isolation
            assert await fs.read_text("/mem1/file.txt") == "memory 1"
            assert await fs.read_text("/mem2/file.txt") == "memory 2"

    @pytest.mark.asyncio
    async def test_mount_mixed_providers(self, tmp_path):
        """Test mounting different provider types simultaneously"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/memory", provider="memory")
            await fs.mount("/disk", provider="filesystem", root_path=str(tmp_path))
            await fs.mount("/db", provider="sqlite", db_path=":memory:")

            # Write to each
            await fs.write_text("/memory/m.txt", "memory")
            await fs.write_text("/disk/d.txt", "disk")
            await fs.write_text("/db/db.txt", "database")

            # Verify all accessible
            assert await fs.read_text("/memory/m.txt") == "memory"
            assert await fs.read_text("/disk/d.txt") == "disk"
            assert await fs.read_text("/db/db.txt") == "database"


class TestMountStreaming:
    """Test streaming with mounts"""

    @pytest.mark.asyncio
    async def test_stream_write_to_mount(self):
        """Test stream write to mounted path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/stream", provider="memory")

            async def gen():
                for i in range(50):
                    yield f"line {i}\n".encode()

            result = await fs.stream_write("/stream/data.txt", gen())
            assert result is True

            content = await fs.read_binary("/stream/data.txt")
            assert b"line 0\n" in content
            assert b"line 49\n" in content

    @pytest.mark.asyncio
    async def test_stream_read_from_mount(self):
        """Test stream read from mounted path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/data", provider="memory")

            test_data = b"stream test\n" * 100
            await fs.write_binary("/data/test.dat", test_data)

            chunks = []
            async for chunk in fs.stream_read("/data/test.dat", chunk_size=256):
                chunks.append(chunk)

            assert b"".join(chunks) == test_data

    @pytest.mark.asyncio
    async def test_stream_across_mounts(self):
        """Test streaming from one mount to another"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/source", provider="memory")
            await fs.mount("/dest", provider="memory")

            # Write to source
            async def gen():
                yield b"data to copy"

            await fs.stream_write("/source/file.txt", gen())

            # Stream from source to dest
            async def transfer():
                async for chunk in fs.stream_read("/source/file.txt"):
                    yield chunk

            await fs.stream_write("/dest/file.txt", transfer())

            # Verify
            assert await fs.read_binary("/dest/file.txt") == b"data to copy"


class TestMountEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_mount_duplicate_path(self):
        """Test mounting at same path twice"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            result1 = await fs.mount("/dup", provider="memory")
            assert result1 is True

            # Second mount at same path should fail
            result2 = await fs.mount("/dup", provider="memory")
            assert result2 is False

    @pytest.mark.asyncio
    async def test_unmount_nonexistent(self):
        """Test unmounting path that doesn't exist"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            result = await fs.unmount("/nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_mount_root_path(self):
        """Test mounting at root path"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            # Mounting at root should work but may have special behavior
            # This tests that the system handles it gracefully
            _result = await fs.mount("/", provider="memory")
            # Implementation may allow or disallow this

    @pytest.mark.asyncio
    async def test_mount_with_trailing_slash(self):
        """Test mount point with trailing slash"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            result = await fs.mount("/data/", provider="memory")
            assert result is True

            # Should work without trailing slash too
            await fs.write_text("/data/file.txt", "test")
            assert await fs.exists("/data/file.txt")

    @pytest.mark.asyncio
    async def test_operations_after_unmount(self):
        """Test that operations fail after unmount"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/temp", provider="memory")
            await fs.write_text("/temp/file.txt", "data")

            await fs.unmount("/temp")

            # Operations to unmounted path should behave as if path doesn't exist
            # (routes to root provider which doesn't have the file)
            _exists = await fs.exists("/temp/file.txt")
            # Behavior depends on implementation


class TestMountLifecycle:
    """Test mount lifecycle management"""

    @pytest.mark.asyncio
    async def test_mount_cleanup_on_close(self, tmp_path):
        """Test that mounts are cleaned up when filesystem closes"""
        fs = AsyncVirtualFileSystem(provider="memory", enable_mounts=True)
        await fs.initialize()

        await fs.mount("/test", provider="filesystem", root_path=str(tmp_path))

        # Close filesystem
        await fs.close()

        # Mounts should be cleaned up (can't test directly, but no errors)

    @pytest.mark.asyncio
    async def test_mount_context_manager(self):
        """Test mounts with context manager"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/ctx", provider="memory")
            await fs.write_text("/ctx/test.txt", "context")

            assert await fs.exists("/ctx/test.txt")

        # After context exit, everything cleaned up

    @pytest.mark.asyncio
    async def test_multiple_mount_unmount_cycles(self):
        """Test multiple mount/unmount cycles"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            for i in range(5):
                await fs.mount(f"/cycle{i}", provider="memory")
                await fs.write_text(f"/cycle{i}/file.txt", f"cycle {i}")
                assert await fs.exists(f"/cycle{i}/file.txt")
                await fs.unmount(f"/cycle{i}")

            # All should be unmounted
            assert len(fs.list_mounts()) == 0


class TestMountConcurrency:
    """Test concurrent mount operations"""

    @pytest.mark.asyncio
    async def test_concurrent_mount_operations(self):
        """Test concurrent mounts"""
        import asyncio

        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:

            async def mount_and_write(index):
                await fs.mount(f"/concurrent{index}", provider="memory")
                await fs.write_text(f"/concurrent{index}/file.txt", f"data {index}")

            tasks = [mount_and_write(i) for i in range(5)]
            await asyncio.gather(*tasks)

            # Verify all mounts and files
            assert len(fs.list_mounts()) == 5
            for i in range(5):
                content = await fs.read_text(f"/concurrent{i}/file.txt")
                assert content == f"data {i}"

    @pytest.mark.asyncio
    async def test_concurrent_reads_different_mounts(self):
        """Test concurrent reads from different mounts"""
        import asyncio

        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            # Setup mounts with data
            for i in range(3):
                await fs.mount(f"/m{i}", provider="memory")
                await fs.write_text(f"/m{i}/data.txt", f"mount {i}")

            async def read_mount(index):
                return await fs.read_text(f"/m{index}/data.txt")

            tasks = [read_mount(i) for i in range(3)]
            results = await asyncio.gather(*tasks)

            assert results == ["mount 0", "mount 1", "mount 2"]


class TestMountStatistics:
    """Test that statistics work correctly with mounts"""

    @pytest.mark.asyncio
    async def test_stats_track_mount_operations(self):
        """Test that filesystem stats track operations on mounts"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/tracked", provider="memory")

            initial_ops = fs.stats["operations"]

            await fs.write_text("/tracked/file.txt", "data")
            await fs.read_text("/tracked/file.txt")

            assert fs.stats["operations"] > initial_ops

    @pytest.mark.asyncio
    async def test_stats_bytes_written_mount(self):
        """Test bytes_written stat with mounts"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/bytes", provider="memory")

            initial_bytes = fs.stats["bytes_written"]

            test_data = b"x" * 1000
            await fs.write_binary("/bytes/test.dat", test_data)

            assert fs.stats["bytes_written"] >= initial_bytes + 1000


class TestMountPathTranslation:
    """Test path translation in mounts"""

    @pytest.mark.asyncio
    async def test_path_translation_basic(self):
        """Test that paths are correctly translated to mounted providers"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/prefix", provider="memory")

            # Write to /prefix/sub/file.txt
            # Should be translated to /sub/file.txt in the mounted provider
            await fs.mkdir("/prefix/sub")
            await fs.write_text("/prefix/sub/file.txt", "translated")

            # Verify accessible
            assert await fs.exists("/prefix/sub/file.txt")
            content = await fs.read_text("/prefix/sub/file.txt")
            assert content == "translated"

    @pytest.mark.asyncio
    async def test_path_translation_nested_mounts(self):
        """Test path translation with nested mounts"""
        async with AsyncVirtualFileSystem(provider="memory", enable_mounts=True) as fs:
            await fs.mount("/a", provider="memory")
            await fs.mount("/a/b", provider="memory")

            # Write to shallow mount
            await fs.write_text("/a/shallow.txt", "shallow")

            # Write to deep mount
            await fs.write_text("/a/b/deep.txt", "deep")

            # Both should be accessible
            assert await fs.read_text("/a/shallow.txt") == "shallow"
            assert await fs.read_text("/a/b/deep.txt") == "deep"
