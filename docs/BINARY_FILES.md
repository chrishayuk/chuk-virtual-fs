# Binary File Support

The virtual filesystem now has comprehensive support for binary files, making it ideal for working with PowerPoint presentations, PDFs, images, and other binary formats.

## Table of Contents

- [Overview](#overview)
- [Explicit Binary and Text Methods](#explicit-binary-and-text-methods)
- [Binary Detection](#binary-detection)
- [MIME Type Detection](#mime-type-detection)
- [Path Utilities](#path-utilities)
- [Exception Handling](#exception-handling)
- [Examples](#examples)

## Overview

The virtual filesystem has been enhanced with:

1. **Explicit binary and text operations** - Clear APIs for working with binary vs text content
2. **Automatic binary detection** - Smart detection of binary vs text files
3. **Enhanced MIME type detection** - Support for 80+ file formats including Office documents
4. **Comprehensive path utilities** - 25+ path manipulation functions
5. **Better error handling** - Structured exception classes for all operations

## Explicit Binary and Text Methods

### Writing Files

#### `write_binary(path, content, **metadata)`

Explicitly write binary content to a file. This method enforces type safety and will raise a `TypeError` if you accidentally pass a string.

```python
from chuk_virtual_fs import AsyncVirtualFileSystem

async with AsyncVirtualFileSystem() as fs:
    # Write a PDF file
    pdf_content = b'%PDF-1.4...'
    await fs.write_binary("/documents/report.pdf", pdf_content)

    # Write an image
    with open("logo.png", "rb") as f:
        image_data = f.read()
    await fs.write_binary("/images/logo.png", image_data)

    # Write a PowerPoint presentation
    with open("presentation.pptx", "rb") as f:
        pptx_data = f.read()
    await fs.write_binary("/presentations/slides.pptx", pptx_data)
```

#### `write_text(path, content, encoding='utf-8', **metadata)`

Explicitly write text content to a file with encoding support.

```python
# Write UTF-8 text (default)
await fs.write_text("/docs/readme.txt", "Hello World")

# Write with specific encoding
await fs.write_text("/docs/latin.txt", "Caf\u00e9", encoding="latin-1")

# Type safety - this will raise TypeError
await fs.write_text("/docs/bad.txt", b"bytes")  # ❌ Error!
```

#### `write_file(path, content, **metadata)`

Legacy method that accepts both strings and bytes (converts strings to bytes automatically).

```python
# Still works for backward compatibility
await fs.write_file("/docs/file.txt", "text content")
await fs.write_file("/docs/binary.bin", b"binary content")
```

### Reading Files

#### `read_binary(path)`

Explicitly read file content as bytes. Returns `None` if the file doesn't exist.

```python
# Read a PDF file
pdf_bytes = await fs.read_binary("/documents/report.pdf")
if pdf_bytes:
    print(f"PDF size: {len(pdf_bytes)} bytes")

# Read an image
image_bytes = await fs.read_binary("/images/photo.jpg")

# Read any file as bytes
data = await fs.read_binary("/any/file.ext")
```

#### `read_text(path, encoding='utf-8', errors='strict')`

Explicitly read file content as text with encoding support.

```python
# Read UTF-8 text (default)
content = await fs.read_text("/docs/readme.txt")

# Read with specific encoding
content = await fs.read_text("/docs/latin.txt", encoding="latin-1")

# Handle decode errors gracefully
content = await fs.read_text("/docs/maybe-binary.txt", errors="replace")
```

#### `read_file(path, as_text=False)`

Legacy method for reading files.

```python
# Read as bytes (default)
bytes_content = await fs.read_file("/file.bin")

# Read as text
text_content = await fs.read_file("/file.txt", as_text=True)
```

## Binary Detection

The `File` class now has built-in binary detection that analyzes file content to determine if it's text or binary.

```python
from chuk_virtual_fs.file import File

# Create file with binary content
pdf_file = File("document.pdf", content=b'%PDF-1.4...')
print(pdf_file.is_binary())  # True
print(pdf_file.get_encoding())  # 'binary'

# Create file with text content
text_file = File("readme.txt", content="Hello World")
print(text_file.is_binary())  # False
print(text_file.get_encoding())  # 'utf-8'

# Read content
binary_data = pdf_file.read_bytes()  # Always returns bytes
text_data = text_file.read_text()    # Returns decoded string
```

### Binary Detection Algorithm

The detection checks for:
1. **Null bytes (\\x00)** - Strong indicator of binary data
2. **Non-text characters** - Control characters excluding tab, newline, carriage return
3. **Threshold** - If more than 30% of sampled bytes are non-text, file is considered binary

## MIME Type Detection

The filesystem now supports comprehensive MIME type detection for 80+ file formats.

### Extension-Based Detection

```python
from chuk_virtual_fs.node_info import EnhancedNodeInfo

node_info = EnhancedNodeInfo(name="presentation.pptx", is_dir=False)
node_info.set_mime_type()
print(node_info.mime_type)  # 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
```

### Content-Based Detection (Magic Bytes)

```python
# Detect MIME type from file content
content = await fs.read_binary("/unknown/file")
node_info = await fs.get_node_info("/unknown/file")
node_info.detect_mime_from_content(content)
print(node_info.mime_type)  # Detected from content
```

### Supported File Formats

#### Microsoft Office Documents
- **PowerPoint**: `.ppt`, `.pptx`, `.pptm`, `.ppsx`, `.potx`
- **Word**: `.doc`, `.docx`
- **Excel**: `.xls`, `.xlsx`

#### Documents & PDFs
- **PDF**: `.pdf`
- **OpenOffice**: `.odt`, `.ods`, `.odp`, `.odg`
- **eBooks**: `.epub`, `.mobi`

#### Images
- `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`, `.ico`, `.webp`, `.tiff`, `.heic`, `.heif`

#### Archives
- `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2`, `.xz`

#### Audio
- `.mp3`, `.wav`, `.ogg`, `.flac`, `.aac`, `.m4a`, `.wma`

#### Video
- `.mp4`, `.avi`, `.mkv`, `.mov`, `.wmv`, `.flv`, `.webm`, `.mpg`, `.mpeg`

#### Programming Languages
- `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.rb`, `.php`, `.sh`, `.sql`

And many more!

## Path Utilities

A comprehensive set of path manipulation utilities is now available via `chuk_virtual_fs.path_utils`.

```python
from chuk_virtual_fs import path_utils

# Basic operations
path_utils.dirname("/home/user/docs/file.txt")     # '/home/user/docs'
path_utils.basename("/home/user/docs/file.txt")    # 'file.txt'
path_utils.extension("/home/user/docs/file.txt")   # '.txt'
path_utils.stem("/home/user/docs/file.txt")        # 'file'

# Path manipulation
path_utils.join("/home", "user", "docs")           # '/home/user/docs'
path_utils.normalize("/home/user/../other")        # '/home/other'
path_utils.parent("/home/user/docs", levels=2)     # '/home'

# Path analysis
path_utils.parts("/home/user/docs")                # ['/', 'home', 'user', 'docs']
path_utils.depth("/home/user")                     # 2
path_utils.is_parent("/home", "/home/user/docs")   # True

# Extension utilities
path_utils.has_extension("file.txt", ".txt", ".md")  # True
path_utils.change_extension("file.txt", ".pdf")      # 'file.pdf'
path_utils.get_all_extensions("file.tar.gz")         # ['tar', 'gz']

# Security
path_utils.safe_join("/home/user", "docs/file.txt")  # Safe
path_utils.safe_join("/home/user", "../../etc/passwd")  # Raises ValueError

# Pattern matching
path_utils.glob_match("/home/user/file.txt", "*.txt")  # True
```

### Available Functions

- `normalize(path)` - Normalize path
- `join(*paths)` - Join path components
- `dirname(path)` - Get directory name
- `basename(path)` - Get base name
- `split(path)` - Split into (dir, basename)
- `splitext(path)` - Split into (root, extension)
- `extension(path, include_dot=True)` - Get extension
- `get_all_extensions(path)` - Get all extensions
- `stem(path)` - Get filename without extension
- `is_absolute(path)` - Check if absolute
- `is_relative(path)` - Check if relative
- `relative_to(path, base)` - Get relative path
- `common_path(*paths)` - Find common base
- `parent(path, levels=1)` - Get parent directory
- `parts(path)` - Split into components
- `depth(path)` - Get path depth
- `is_parent(parent, child)` - Check parent relationship
- `is_child(child, parent)` - Check child relationship
- `has_extension(path, *exts)` - Check extensions
- `change_extension(path, new_ext)` - Change extension
- `ensure_trailing_slash(path)` - Add trailing slash
- `remove_trailing_slash(path)` - Remove trailing slash
- `safe_join(base, *paths)` - Safely join paths
- `glob_match(path, pattern)` - Match glob pattern

## Exception Handling

Structured exception classes provide better error messages and error handling.

```python
from chuk_virtual_fs import exceptions

try:
    # Attempt path traversal
    path_utils.safe_join("/home/user", "../../etc/passwd")
except exceptions.PathTraversalError as e:
    print(f"Security error: {e.message}")
    print(f"Path: {e.path}")

try:
    # Type mismatch
    await fs.write_binary("/file.txt", "not bytes")
except TypeError as e:
    print(f"Type error: {e}")

try:
    # Read non-existent file
    content = await fs.read_text("/nonexistent.txt")
    if content is None:
        print("File not found")
except Exception as e:
    print(f"Error: {e}")
```

### Exception Classes

Base exceptions:
- `VirtualFSError` - Base exception for all errors
- `PathError` - Base for path-related errors
- `NodeError` - Base for node-related errors
- `FileOperationError` - Base for file operations
- `ProviderError` - Base for provider errors

Specific exceptions:
- `PathNotFoundError` - Path doesn't exist
- `PathExistsError` - Path already exists
- `InvalidPathError` - Invalid path format
- `PathTraversalError` - Directory traversal attempt
- `NotAFileError` - Expected file, got directory
- `NotADirectoryError` - Expected directory, got file
- `DirectoryNotEmptyError` - Cannot delete non-empty directory
- `PermissionError` - Permission denied
- `ReadError` - Failed to read file
- `WriteError` - Failed to write file
- `EncodingError` - Encoding/decoding error

## Examples

### Working with PowerPoint Files

```python
import asyncio
from chuk_virtual_fs import AsyncVirtualFileSystem

async def powerpoint_example():
    async with AsyncVirtualFileSystem(provider="memory") as fs:
        # Read a PowerPoint file
        with open("presentation.pptx", "rb") as f:
            pptx_data = f.read()

        # Store in virtual filesystem
        await fs.mkdir("/presentations")
        await fs.write_binary("/presentations/slides.pptx", pptx_data)

        # Read it back
        stored_data = await fs.read_binary("/presentations/slides.pptx")

        # Check MIME type
        node_info = await fs.get_node_info("/presentations/slides.pptx")
        node_info.detect_mime_from_content(stored_data)
        print(f"MIME type: {node_info.mime_type}")
        # Output: application/vnd.openxmlformats-officedocument.presentationml.presentation

asyncio.run(powerpoint_example())
```

### Working with Images

```python
async def image_example():
    async with AsyncVirtualFileSystem(provider="s3", bucket_name="my-bucket") as fs:
        # Upload an image
        with open("photo.jpg", "rb") as f:
            image_data = f.read()

        await fs.write_binary("/images/photo.jpg", image_data)

        # Generate metadata
        node_info = await fs.get_node_info("/images/photo.jpg")
        node_info.calculate_checksums(image_data)

        print(f"Size: {node_info.size} bytes")
        print(f"MD5: {node_info.md5}")
        print(f"SHA256: {node_info.sha256}")

asyncio.run(image_example())
```

### Mixed Binary and Text Files

```python
async def mixed_example():
    async with AsyncVirtualFileSystem(provider="filesystem", root_path="./data") as fs:
        # Create directory structure
        await fs.mkdir("/project")
        await fs.mkdir("/project/docs")
        await fs.mkdir("/project/assets")

        # Write text files
        await fs.write_text("/project/README.md", "# My Project\\n\\nDocumentation here")
        await fs.write_text("/project/config.json", '{"version": "1.0"}')

        # Write binary files
        with open("logo.png", "rb") as f:
            await fs.write_binary("/project/assets/logo.png", f.read())

        # Read and process
        readme = await fs.read_text("/project/README.md")
        logo = await fs.read_binary("/project/assets/logo.png")

        print(f"README: {len(readme)} characters")
        print(f"Logo: {len(logo)} bytes")

asyncio.run(mixed_example())
```

## Best Practices

1. **Use explicit methods**: Prefer `write_binary()` and `write_text()` over `write_file()` for clarity
2. **Handle None returns**: Always check if `read_binary()` or `read_text()` returns `None`
3. **Validate content types**: Use `is_binary()` to check before text operations
4. **Use path utilities**: Leverage `path_utils` for safe path manipulation
5. **Catch specific exceptions**: Handle `VirtualFSError` subclasses for better error handling
6. **Check MIME types**: Use `detect_mime_from_content()` for accurate file type detection

## Performance Considerations

- Binary operations are fast and memory-efficient
- MIME detection samples only first 8KB of content
- Path utilities use optimized POSIX path operations
- All providers (memory, filesystem, S3, etc.) support binary data equally well

## Migration Guide

### From Old API

```python
# Old way (still works)
await fs.write_file("/file.pdf", pdf_bytes)
content = await fs.read_file("/file.pdf")

# New way (recommended)
await fs.write_binary("/file.pdf", pdf_bytes)
content = await fs.read_binary("/file.pdf")
```

### Type Safety

```python
# This now raises TypeError
await fs.write_binary("/file.bin", "string")  # ❌

# This is correct
await fs.write_binary("/file.bin", b"bytes")  # ✅
await fs.write_text("/file.txt", "string")    # ✅
```

## Support

For more information, see:
- [Main README](../README.md)
- [API Reference](../README.md#api-reference)
- [Examples](../examples/)
