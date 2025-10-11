"""
Tests for streaming operations
"""

import pytest

from chuk_virtual_fs import AsyncVirtualFileSystem


class TestStreamingBasics:
    """Test basic streaming operations"""

    @pytest.mark.asyncio
    async def test_stream_write_basic(self):
        """Test basic stream write"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def data_gen():
                for i in range(10):
                    yield f"line {i}\n".encode()

            result = await fs.stream_write("/test.txt", data_gen())
            assert result is True

            # Verify file exists and has content
            content = await fs.read_binary("/test.txt")
            assert content is not None
            assert b"line 0\n" in content
            assert b"line 9\n" in content

    @pytest.mark.asyncio
    async def test_stream_read_basic(self):
        """Test basic stream read"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            # Create a file
            test_data = b"chunk1" * 100 + b"chunk2" * 100
            await fs.write_binary("/test.dat", test_data)

            # Stream read
            chunks = []
            async for chunk in fs.stream_read("/test.dat", chunk_size=100):
                chunks.append(chunk)

            # Verify
            assert len(chunks) > 0
            reconstructed = b"".join(chunks)
            assert reconstructed == test_data

    @pytest.mark.asyncio
    async def test_stream_write_empty(self):
        """Test streaming with empty generator"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def empty_gen():
                return
                yield  # Never reached

            result = await fs.stream_write("/empty.txt", empty_gen())
            assert result is True

            content = await fs.read_binary("/empty.txt")
            assert content == b""

    @pytest.mark.asyncio
    async def test_stream_chunk_sizes(self):
        """Test different chunk sizes"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            # Write with large chunks
            async def large_chunks():
                yield b"x" * 10000

            await fs.stream_write("/large.dat", large_chunks())

            # Read with small chunks
            total = 0
            async for chunk in fs.stream_read("/large.dat", chunk_size=100):
                total += len(chunk)

            assert total == 10000

    @pytest.mark.asyncio
    async def test_stream_statistics(self):
        """Test that streaming updates statistics"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            initial_ops = fs.stats["operations"]

            async def data_gen():
                yield b"test data"

            await fs.stream_write("/test.txt", data_gen())

            # Verify operations are tracked
            assert fs.stats["operations"] > initial_ops
            # Note: bytes_written tracking for streaming may vary by implementation


class TestStreamingMemoryProvider:
    """Test streaming with memory provider"""

    @pytest.mark.asyncio
    async def test_memory_stream_write(self):
        """Test memory provider stream write"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def gen():
                for i in range(100):
                    yield f"line {i}\n".encode()

            result = await fs.stream_write("/data.txt", gen())
            assert result is True

            node_info = await fs.get_node_info("/data.txt")
            assert node_info is not None
            assert node_info.size > 0

    @pytest.mark.asyncio
    async def test_memory_stream_read(self):
        """Test memory provider stream read"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            data = b"test" * 1000
            await fs.write_binary("/test.dat", data)

            chunks = []
            async for chunk in fs.stream_read("/test.dat", chunk_size=256):
                chunks.append(chunk)

            assert len(chunks) > 1
            assert b"".join(chunks) == data


class TestStreamingFilesystemProvider:
    """Test streaming with filesystem provider"""

    @pytest.mark.asyncio
    async def test_filesystem_stream_write(self, tmp_path):
        """Test filesystem provider stream write"""
        async with AsyncVirtualFileSystem(
            provider="filesystem", root_path=str(tmp_path)
        ) as fs:

            async def gen():
                yield b"chunk1\n"
                yield b"chunk2\n"
                yield b"chunk3\n"

            result = await fs.stream_write("/stream.txt", gen())
            assert result is True

            # Verify file on disk
            file_path = tmp_path / "stream.txt"
            assert file_path.exists()
            content = file_path.read_bytes()
            assert content == b"chunk1\nchunk2\nchunk3\n"

    @pytest.mark.asyncio
    async def test_filesystem_stream_read(self, tmp_path):
        """Test filesystem provider stream read"""
        # Create test file
        test_file = tmp_path / "test.dat"
        test_data = b"stream test data\n" * 100
        test_file.write_bytes(test_data)

        async with AsyncVirtualFileSystem(
            provider="filesystem", root_path=str(tmp_path)
        ) as fs:
            chunks = []
            async for chunk in fs.stream_read("/test.dat", chunk_size=128):
                chunks.append(chunk)

            reconstructed = b"".join(chunks)
            assert reconstructed == test_data


class TestStreamingSQLiteProvider:
    """Test streaming with SQLite provider"""

    @pytest.mark.asyncio
    async def test_sqlite_stream_write(self):
        """Test SQLite provider stream write"""
        async with AsyncVirtualFileSystem(provider="sqlite", db_path=":memory:") as fs:

            async def gen():
                for i in range(50):
                    yield f"record {i}\n".encode()

            result = await fs.stream_write("/data.txt", gen())
            assert result is True

            content = await fs.read_binary("/data.txt")
            assert b"record 0\n" in content
            assert b"record 49\n" in content

    @pytest.mark.asyncio
    async def test_sqlite_stream_read(self):
        """Test SQLite provider stream read"""
        async with AsyncVirtualFileSystem(provider="sqlite", db_path=":memory:") as fs:
            test_data = b"sqlite test\n" * 200
            await fs.write_binary("/test.dat", test_data)

            chunks = []
            async for chunk in fs.stream_read("/test.dat", chunk_size=512):
                chunks.append(chunk)

            assert b"".join(chunks) == test_data


class TestStreamingLargeFiles:
    """Test streaming with large files"""

    @pytest.mark.asyncio
    async def test_large_file_streaming(self):
        """Test streaming with simulated large file"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            # Generate ~1MB of data
            async def large_gen():
                for i in range(1000):
                    yield (f"line {i}: " + "x" * 1000 + "\n").encode()

            result = await fs.stream_write("/large.txt", large_gen())
            assert result is True

            # Read in chunks
            total_bytes = 0
            chunk_count = 0
            async for chunk in fs.stream_read("/large.txt", chunk_size=8192):
                total_bytes += len(chunk)
                chunk_count += 1

            assert total_bytes > 1000000  # ~1MB
            assert chunk_count > 100  # Multiple chunks

    @pytest.mark.asyncio
    async def test_memory_efficient_streaming(self):
        """Test that streaming doesn't load entire file in memory at once"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            # This test verifies the streaming interface works correctly
            # In production, this would handle files larger than available RAM

            async def gen():
                for _ in range(10000):
                    yield b"x" * 100

            await fs.stream_write("/big.dat", gen())

            # Read in small chunks
            chunks_processed = 0
            async for _chunk in fs.stream_read("/big.dat", chunk_size=1024):
                chunks_processed += 1
                # Process chunk (in real usage, this wouldn't accumulate)

            assert chunks_processed > 900  # ~1000KB / 1KB chunks


class TestStreamingErrorHandling:
    """Test error handling in streaming operations"""

    @pytest.mark.asyncio
    async def test_stream_read_nonexistent_file(self):
        """Test streaming read of nonexistent file"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            chunks = []
            try:
                async for chunk in fs.stream_read("/nonexistent.txt"):
                    chunks.append(chunk)
            except Exception:
                pass  # Expected to fail

            # Should not have read any chunks
            assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_stream_write_with_metadata(self):
        """Test streaming write with metadata"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def gen():
                yield b"test data"

            result = await fs.stream_write("/test.txt", gen(), custom_meta="value")
            assert result is True

            # File should exist
            assert await fs.exists("/test.txt")

    @pytest.mark.asyncio
    async def test_stream_to_subdirectory(self):
        """Test streaming to file in subdirectory"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            await fs.mkdir("/subdir")

            async def gen():
                yield b"nested data"

            result = await fs.stream_write("/subdir/file.txt", gen())
            assert result is True

            content = await fs.read_binary("/subdir/file.txt")
            assert content == b"nested data"


class TestStreamingEdgeCases:
    """Test edge cases in streaming"""

    @pytest.mark.asyncio
    async def test_stream_binary_data(self):
        """Test streaming binary (non-text) data"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def binary_gen():
                # Generate binary data with null bytes
                yield b"\x00\x01\x02\x03\x04"
                yield b"\xff\xfe\xfd\xfc"

            await fs.stream_write("/binary.dat", binary_gen())

            content = await fs.read_binary("/binary.dat")
            assert content == b"\x00\x01\x02\x03\x04\xff\xfe\xfd\xfc"

    @pytest.mark.asyncio
    async def test_stream_unicode_data(self):
        """Test streaming unicode data"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def unicode_gen():
                yield "Hello 世界\n".encode()
                yield "مرحبا עולם\n".encode()

            await fs.stream_write("/unicode.txt", unicode_gen())

            content = await fs.read_text("/unicode.txt", encoding="utf-8")
            assert "世界" in content
            assert "עולם" in content

    @pytest.mark.asyncio
    async def test_stream_single_large_chunk(self):
        """Test streaming a single large chunk"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def single_chunk():
                yield b"x" * 100000  # 100KB in one chunk

            await fs.stream_write("/single.dat", single_chunk())

            node_info = await fs.get_node_info("/single.dat")
            assert node_info.size == 100000

    @pytest.mark.asyncio
    async def test_stream_many_small_chunks(self):
        """Test streaming many small chunks"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def many_chunks():
                for _ in range(10000):
                    yield b"x"

            await fs.stream_write("/many.dat", many_chunks())

            node_info = await fs.get_node_info("/many.dat")
            assert node_info.size == 10000


class TestStreamingConcurrent:
    """Test concurrent streaming operations"""

    @pytest.mark.asyncio
    async def test_concurrent_stream_writes(self):
        """Test multiple concurrent stream writes"""
        import asyncio

        async with AsyncVirtualFileSystem(provider="memory") as fs:

            async def write_stream(path, count):
                async def gen():
                    for i in range(count):
                        yield f"line {i}\n".encode()

                await fs.stream_write(path, gen())

            # Write to multiple files concurrently
            tasks = [write_stream(f"/file{i}.txt", 50) for i in range(5)]
            await asyncio.gather(*tasks)

            # Verify all files were created
            for i in range(5):
                assert await fs.exists(f"/file{i}.txt")

    @pytest.mark.asyncio
    async def test_concurrent_stream_reads(self):
        """Test multiple concurrent stream reads"""
        import asyncio

        async with AsyncVirtualFileSystem(provider="memory") as fs:
            # Create test files
            for i in range(3):
                await fs.write_binary(f"/file{i}.dat", b"test" * 100)

            async def read_stream(path):
                chunks = []
                async for chunk in fs.stream_read(path):
                    chunks.append(chunk)
                return b"".join(chunks)

            # Read multiple files concurrently
            tasks = [read_stream(f"/file{i}.dat") for i in range(3)]
            results = await asyncio.gather(*tasks)

            # Verify all reads succeeded
            assert all(result == b"test" * 100 for result in results)


class TestStreamingProviderSpecific:
    """Test provider-specific streaming behavior"""

    @pytest.mark.asyncio
    async def test_provider_stream_persistence(self, tmp_path):
        """Test that streamed data persists across provider instances"""
        test_data = b"persistent data\n" * 100

        # Write with one instance
        async with AsyncVirtualFileSystem(
            provider="filesystem", root_path=str(tmp_path)
        ) as fs:

            async def gen():
                yield test_data

            await fs.stream_write("/persist.txt", gen())

        # Read with another instance
        async with AsyncVirtualFileSystem(
            provider="filesystem", root_path=str(tmp_path)
        ) as fs:
            content = await fs.read_binary("/persist.txt")
            assert content == test_data

    @pytest.mark.asyncio
    async def test_stream_preserves_file_integrity(self):
        """Test that streaming preserves data integrity"""
        async with AsyncVirtualFileSystem(provider="memory") as fs:
            # Known data pattern
            expected = b""
            for i in range(256):
                expected += bytes([i])

            async def gen():
                for i in range(256):
                    yield bytes([i])

            await fs.stream_write("/integrity.dat", gen())

            # Verify byte-for-byte match
            actual = await fs.read_binary("/integrity.dat")
            assert actual == expected
