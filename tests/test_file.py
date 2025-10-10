"""
tests/chuk_virtual_fs/filesystem/test_file.py
"""

from chuk_virtual_fs.file import File


def test_file_initialization():
    file_node = File("test.txt", content="Hello")
    assert file_node.name == "test.txt"
    assert file_node.content == "Hello"  # Property still works for backward compat
    assert file_node.size == len("Hello")
    # Check that timestamps are set (using the example fixed timestamp)
    assert file_node.created_at == "2025-03-27T12:00:00Z"
    assert file_node.modified_at == "2025-03-27T12:00:00Z"


def test_file_write_text():
    """Test writing text with new API"""
    file_node = File("test.txt", content="Initial")
    file_node.write_text("New Content")
    assert file_node.read_text() == "New Content"
    assert file_node.size == len(b"New Content")
    assert file_node.modified_at == "2025-03-27T12:00:00Z"


def test_file_write_bytes():
    """Test writing bytes with new API"""
    file_node = File("test.bin")
    file_node.write(b"Binary Content")
    assert file_node.read() == b"Binary Content"
    assert file_node.size == len(b"Binary Content")


def test_file_append_text():
    """Test appending text with new API"""
    file_node = File("test.txt", content="Hello")
    file_node.append_text(" World")
    assert file_node.read_text() == "Hello World"
    assert file_node.size == len(b"Hello World")


def test_file_append_bytes():
    """Test appending bytes with new API"""
    file_node = File("test.bin", content=b"Hello")
    file_node.append(b" World")
    assert file_node.read() == b"Hello World"
    assert file_node.size == len(b"Hello World")


def test_file_read():
    """Test read() returns bytes"""
    file_node = File("test.txt", content="Some content")
    assert file_node.read() == b"Some content"


def test_file_read_text():
    """Test read_text() returns str"""
    file_node = File("test.txt", content="Some content")
    assert file_node.read_text() == "Some content"


# New tests for binary support


def test_file_binary_content():
    """Test file with binary content"""
    binary_data = b"\x00\x01\x02\x03\x04"
    file_node = File("binary.dat", content=binary_data)
    assert file_node.content == binary_data
    assert file_node.size == 5
    assert file_node.is_binary() is True


def test_file_text_content():
    """Test file with text content"""
    text_data = "Hello World"
    file_node = File("text.txt", content=text_data)
    assert file_node.content == text_data  # Property returns str for text
    assert file_node.read_text() == text_data
    assert file_node.size == len(text_data.encode("utf-8"))
    assert file_node.is_binary() is False


def test_file_binary_detection_null_bytes():
    """Test binary detection with null bytes"""
    content_with_null = b"Hello\x00World"
    file_node = File("file.bin", content=content_with_null)
    assert file_node.is_binary() is True


def test_file_read_bytes():
    """Test read_bytes method"""
    binary_data = b"\xff\xfe\xfd"
    file_node = File("binary.dat", content=binary_data)
    assert file_node.read_bytes() == binary_data


def test_file_read_text():  # noqa: F811
    """Test read_text method"""
    file_node = File("text.txt", content="Hello World")
    assert file_node.read_text() == "Hello World"


def test_file_read_text_with_encoding():
    """Test read_text with specific encoding"""
    file_node = File("text.txt", content="Café")
    assert file_node.read_text(encoding="utf-8") == "Café"


def test_file_get_encoding():
    """Test get_encoding method"""
    # UTF-8 text
    utf8_file = File("utf8.txt", content="Hello")
    assert utf8_file.get_encoding() == "utf-8"

    # Binary file
    binary_file = File("binary.dat", content=b"\x00\x01\x02")
    assert binary_file.get_encoding() == "binary"


def test_file_write_binary_with_type_check():
    """Test writing binary content with type checking"""
    file_node = File("test.bin")
    # Use content with null byte to ensure binary detection
    binary_data = b"\x00\xff\xfe\xfd"
    file_node.write(binary_data)
    assert file_node.content == binary_data
    assert file_node.is_binary() is True


def test_file_write_rejects_string():
    """Test that write() rejects strings"""
    file_node = File("test.bin")
    import pytest

    with pytest.raises(TypeError, match="write\\(\\) requires bytes"):
        file_node.write("This should fail")


def test_file_write_text_rejects_bytes():
    """Test that write_text() rejects bytes"""
    file_node = File("test.txt")
    import pytest

    with pytest.raises(TypeError, match="write_text\\(\\) requires str"):
        file_node.write_text(b"This should fail")


def test_file_append_rejects_string():
    """Test that append() rejects strings"""
    file_node = File("test.bin", content=b"data")
    import pytest

    with pytest.raises(TypeError, match="append\\(\\) requires bytes"):
        file_node.append("This should fail")


def test_file_append_text_rejects_bytes():
    """Test that append_text() rejects bytes"""
    file_node = File("test.txt", content="data")
    import pytest

    with pytest.raises(TypeError, match="append_text\\(\\) requires str"):
        file_node.append_text(b"This should fail")


def test_file_mixed_content():
    """Test file with mixed binary/text operations"""
    # Start with text
    file_node = File("mixed.txt", content="Hello")
    assert file_node.is_binary() is False

    # Append text using new API
    file_node.append_text(" World")
    assert file_node.read_text() == "Hello World"
    assert file_node.is_binary() is False


def test_file_backwards_compatibility():
    """Test backwards compatibility with content property"""
    # Creating file still works
    file_node = File("old.txt", content="Old content")
    assert file_node.content == "Old content"  # Property works

    # Use new API for reading/writing
    assert file_node.read_text() == "Old content"
    file_node.write_text("New content")
    assert file_node.content == "New content"


def test_file_pathlib_style_api():
    """Test that API matches pathlib.Path style"""
    # Text operations
    text_file = File("text.txt", content="Hello")
    assert text_file.read_text() == "Hello"
    text_file.write_text("World")
    assert text_file.read_text() == "World"

    # Binary operations
    binary_file = File("binary.dat")
    binary_file.write(b"\x00\x01\x02")
    assert binary_file.read() == b"\x00\x01\x02"
    assert binary_file.read_bytes() == b"\x00\x01\x02"

    # write_bytes is alias for write
    binary_file.write_bytes(b"\x03\x04")
    assert binary_file.read() == b"\x03\x04"


def test_file_content_property_unicode_error():
    """Test content property handling of UnicodeDecodeError"""
    # Create file with invalid UTF-8 bytes
    file_node = File("test.bin", content=b"\xff\xfe\xfd\xfc")
    file_node._was_string = True  # Pretend it was a string
    file_node._is_binary = False  # Pretend it's not binary

    # Should return bytes when decode fails
    content = file_node.content
    assert isinstance(content, bytes)
    assert content == b"\xff\xfe\xfd\xfc"


def test_file_content_property_setter():
    """Test content property setter (backward compatibility)"""
    file_node = File("test.txt", content="Initial")

    # Set with string
    file_node.content = "Updated content"
    assert file_node.content == "Updated content"
    assert file_node._was_string is True
    assert file_node.size == len(b"Updated content")

    # Set with bytes
    file_node.content = b"Binary content"
    assert file_node.content == b"Binary content"
    assert file_node._was_string is False
    assert file_node.size == len(b"Binary content")


def test_file_get_encoding_latin1():
    """Test get_encoding with latin-1 encoding"""
    # Create content that's valid latin-1 but not UTF-8
    latin1_content = b"\xe9\xe8\xe0"  # é è à in latin-1
    file_node = File("latin1.txt", content=latin1_content)
    file_node._is_binary = False

    encoding = file_node.get_encoding()
    # Should detect latin-1 or cp1252 (cp1252 is superset of latin-1)
    assert encoding in ["latin-1", "cp1252"]


def test_file_get_encoding_ascii():
    """Test get_encoding with ASCII encoding"""
    ascii_content = b"Hello World"
    file_node = File("ascii.txt", content=ascii_content)
    file_node._is_binary = False

    encoding = file_node.get_encoding()
    # ASCII is valid UTF-8, so should detect as UTF-8
    assert encoding == "utf-8"


def test_file_get_encoding_unknown():
    """Test get_encoding with unknown encoding"""
    # Create content that's not valid in common encodings
    # but also not binary (less than 30% non-text)
    unknown_content = b"\x80\x81\x82" + b"A" * 100
    file_node = File("unknown.dat", content=unknown_content)
    file_node._is_binary = False

    encoding = file_node.get_encoding()
    # Should fall back to unknown or detect latin-1 (which accepts all bytes)
    assert encoding in ["unknown", "latin-1", "cp1252"]


def test_file_read_text_with_errors():
    """Test read_text with error handling"""
    # Create file with invalid UTF-8
    file_node = File("invalid.txt", content=b"Hello\xff\xfeWorld")

    # strict mode should raise
    import pytest

    with pytest.raises(UnicodeDecodeError):
        file_node.read_text(encoding="utf-8", errors="strict")

    # ignore mode should skip invalid bytes
    result = file_node.read_text(encoding="utf-8", errors="ignore")
    assert result == "HelloWorld"

    # replace mode should replace with �
    result = file_node.read_text(encoding="utf-8", errors="replace")
    assert "Hello" in result
    assert "World" in result
