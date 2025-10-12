# chuk-virtual-fs: Modular Virtual Filesystem Library

A powerful, flexible virtual filesystem library for Python with advanced features, multiple storage providers, and robust security.

## 🌟 Key Features

### 🔧 Modular Design
- Pluggable storage providers
- Flexible filesystem abstraction
- Supports multiple backend implementations

### 💾 Storage Providers
- **Memory Provider**: In-memory filesystem for quick testing and lightweight use
- **SQLite Provider**: Persistent storage with SQLite database backend
- **Pyodide Provider**: Web browser filesystem integration
- **S3 Provider**: Cloud storage with AWS S3 or S3-compatible services
- **E2B Sandbox Provider**: Remote sandbox environment filesystem
- Easy to extend with custom providers

### 🔒 Advanced Security
- Multiple predefined security profiles
- Customizable access controls
- Path and file type restrictions
- Quota management
- Security violation tracking

### 🚀 Advanced Capabilities
- **Streaming Operations**: Memory-efficient streaming for large files with:
  - Real-time progress tracking callbacks
  - Atomic write safety (temp file + atomic move)
  - Automatic error recovery and cleanup
  - Support for both sync and async callbacks
- **Virtual Mounts**: Unix-like mounting system to combine multiple providers
- Snapshot and versioning support
- Template-based filesystem setup
- Flexible path resolution
- Comprehensive file and directory operations
- CLI tools for bucket management

## 📦 Installation

### From PyPI

```bash
pip install chuk-virtual-fs
```

### With Optional Dependencies

```bash
# Install with S3 support
pip install "chuk-virtual-fs[s3]"

# Using uv
uv pip install -e ".[s3]"

# Add S3 dependency to existing project
uv add . --optional s3
```

### For Development

```bash
# Clone the repository
git clone https://github.com/yourusername/chuk-virtual-fs.git
cd chuk-virtual-fs

# Install in development mode with all dependencies
pip install -e ".[dev,s3,e2b]"

# Using uv
uv pip install -e ".[dev,s3,e2b]"
```

## 🚀 Quick Start

### Basic Usage (Async)

The library uses async/await for all operations:

```python
from chuk_virtual_fs import AsyncVirtualFileSystem
import asyncio

async def main():
    # Use async context manager
    async with AsyncVirtualFileSystem(provider="memory") as fs:

        # Create directories
        await fs.mkdir("/home/user/documents")

        # Write to a file
        await fs.write_file("/home/user/documents/hello.txt", "Hello, Virtual World!")

        # Read from a file
        content = await fs.read_text("/home/user/documents/hello.txt")
        print(content)  # Outputs: Hello, Virtual World!

        # List directory contents
        files = await fs.ls("/home/user/documents")
        print(files)  # Outputs: ['hello.txt']

        # Change directory
        await fs.cd("/home/user/documents")
        print(fs.pwd())  # Outputs: /home/user/documents

        # Copy and move operations
        await fs.cp("hello.txt", "hello_copy.txt")
        await fs.mv("hello_copy.txt", "/home/user/hello_moved.txt")

        # Find files matching pattern
        results = await fs.find("*.txt", path="/home", recursive=True)
        print(results)  # Finds all .txt files under /home

# Run the async function
asyncio.run(main())
```

> **Note**: The library also provides a synchronous `VirtualFileSystem` alias for backward compatibility, but the async API (`AsyncVirtualFileSystem`) is recommended for new code and required for streaming and mount operations.

## 💾 Storage Providers

### Available Providers

The virtual filesystem supports multiple storage providers:

- **Memory**: In-memory storage (default)
- **SQLite**: SQLite database storage
- **S3**: AWS S3 or S3-compatible storage
- **Pyodide**: Native integration with Pyodide environment
- **E2B**: E2B Sandbox environments

### Using the S3 Provider

The S3 provider allows you to use AWS S3 or S3-compatible storage (like Tigris Storage) as the backend for your virtual filesystem.

#### Installation

```bash
# Install with S3 support
pip install "chuk-virtual-fs[s3]"

# Or with uv
uv pip install "chuk-virtual-fs[s3]"
```

#### Configuration

Create a `.env` file with your S3 credentials:

```ini
# AWS credentials for S3 provider
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# For S3-compatible storage (e.g., Tigris Storage)
AWS_ENDPOINT_URL_S3=https://your-endpoint.example.com
S3_BUCKET_NAME=your-bucket-name
```

#### Example Usage

```python
from dotenv import load_dotenv
from chuk_virtual_fs import VirtualFileSystem

# Load environment variables
load_dotenv()

# Create filesystem with S3 provider
fs = VirtualFileSystem("s3", 
                       bucket_name="your-bucket-name",
                       prefix="your-prefix",  # Optional namespace in bucket
                       endpoint_url="https://your-endpoint.example.com")  # For S3-compatible storage

# Use the filesystem as normal
fs.mkdir("/projects")
fs.write_file("/projects/notes.txt", "Virtual filesystem backed by S3")

# List directory contents
print(fs.ls("/projects"))
```

### E2B Sandbox Provider Example

```python
import os
from dotenv import load_dotenv

# Load E2B API credentials from .env file
load_dotenv()

# Ensure E2B API key is set
if not os.getenv("E2B_API_KEY"):
    raise ValueError("E2B_API_KEY must be set in .env file")

from chuk_virtual_fs import VirtualFileSystem

# Create a filesystem in an E2B sandbox
# API key will be automatically used from environment variables
fs = VirtualFileSystem("e2b", root_dir="/home/user/sandbox")

# Create project structure
fs.mkdir("/projects")
fs.mkdir("/projects/python")

# Write a Python script
fs.write_file("/projects/python/hello.py", 'print("Hello from E2B sandbox!")')

# List directory contents
print(fs.ls("/projects/python"))

# Execute code in the sandbox (if supported)
if hasattr(fs.provider, 'sandbox') and hasattr(fs.provider.sandbox, 'run_code'):
    result = fs.provider.sandbox.run_code(
        fs.read_file("/projects/python/hello.py")
    )
    print(result.logs)
```

#### E2B Authentication

To use the E2B Sandbox Provider, you need to:

1. Install the E2B SDK:
   ```bash
   pip install e2b-code-interpreter
   ```

2. Create a `.env` file in your project root:
   ```
   E2B_API_KEY=your_e2b_api_key_here
   ```

3. Make sure to add `.env` to your `.gitignore` to keep credentials private.

Note: You can obtain an E2B API key from the [E2B platform](https://e2b.dev).

## 🛡️ Security Features

The virtual filesystem provides robust security features to protect against common vulnerabilities and limit resource usage.

### Security Profiles

```python
from chuk_virtual_fs import VirtualFileSystem

# Create a filesystem with strict security
fs = VirtualFileSystem(
    security_profile="strict",
    security_max_file_size=1024 * 1024,  # 1MB max file size
    security_allowed_paths=["/home", "/tmp"]
)

# Attempt to write to a restricted path
fs.write_file("/etc/sensitive", "This will fail")

# Get security violations
violations = fs.get_security_violations()
```

### Available Security Profiles

- **default**: Standard security with moderate restrictions
- **strict**: High security with tight constraints
- **readonly**: Completely read-only, no modifications allowed
- **untrusted**: Highly restrictive environment for untrusted code
- **testing**: Relaxed security for development and testing

### Security Features

- File size and total storage quotas
- Path traversal protection
- Deny/allow path and pattern rules
- Security violation logging
- Read-only mode

## 🛠️ CLI Tools

### S3 Bucket Management CLI

The package includes a CLI tool for managing S3 buckets:

```bash
# List all buckets
python s3_bucket_cli.py list

# Create a new bucket
python s3_bucket_cli.py create my-bucket

# Show bucket information
python s3_bucket_cli.py info my-bucket --show-top 5

# List objects in a bucket
python s3_bucket_cli.py ls my-bucket --prefix data/

# Clear all objects in a bucket or prefix
python s3_bucket_cli.py clear my-bucket --prefix tmp/

# Delete a bucket (must be empty)
python s3_bucket_cli.py delete my-bucket

# Copy objects between buckets or prefixes
python s3_bucket_cli.py copy source-bucket dest-bucket --source-prefix data/ --dest-prefix backup/
```

## 📋 Advanced Features

### Snapshots

Create and restore filesystem snapshots:

```python
from chuk_virtual_fs import VirtualFileSystem
from chuk_virtual_fs.snapshot_manager import SnapshotManager

fs = VirtualFileSystem()
snapshot_mgr = SnapshotManager(fs)

# Create initial content
fs.mkdir("/home/user")
fs.write_file("/home/user/file.txt", "Original content")

# Create a snapshot
snapshot_id = snapshot_mgr.create_snapshot("initial_state", "Initial filesystem setup")

# Modify content
fs.write_file("/home/user/file.txt", "Modified content")
fs.write_file("/home/user/new_file.txt", "New file")

# List available snapshots
snapshots = snapshot_mgr.list_snapshots()
for snap in snapshots:
    print(f"{snap['name']}: {snap['description']}")

# Restore to initial state
snapshot_mgr.restore_snapshot("initial_state")

# Verify restore
print(fs.read_file("/home/user/file.txt"))  # Outputs: Original content
print(fs.get_node_info("/home/user/new_file.txt"))  # Outputs: None

# Export a snapshot
snapshot_mgr.export_snapshot("initial_state", "/tmp/snapshot.json")
```

### Templates

Load filesystem structures from templates:

```python
from chuk_virtual_fs import VirtualFileSystem
from chuk_virtual_fs.template_loader import TemplateLoader

fs = VirtualFileSystem()
template_loader = TemplateLoader(fs)

# Define a template
project_template = {
    "directories": [
        "/projects/app",
        "/projects/app/src",
        "/projects/app/docs"
    ],
    "files": [
        {
            "path": "/projects/app/README.md",
            "content": "# ${project_name}\n\n${project_description}"
        },
        {
            "path": "/projects/app/src/main.py",
            "content": "def main():\n    print('Hello from ${project_name}!')"
        }
    ]
}

# Apply the template with variables
template_loader.apply_template(project_template, variables={
    "project_name": "My App",
    "project_description": "A sample project created with the virtual filesystem"
})
```

### Streaming Operations

Handle large files efficiently with streaming support, progress tracking, and atomic write safety:

```python
from chuk_virtual_fs import AsyncVirtualFileSystem

async def main():
    async with AsyncVirtualFileSystem(provider="memory") as fs:

        # Stream write with progress tracking
        async def data_generator():
            for i in range(1000):
                yield f"Line {i}: {'x' * 1000}\n".encode()

        # Track upload progress
        def progress_callback(bytes_written, total_bytes):
            if bytes_written % (100 * 1024) < 1024:  # Every 100KB
                print(f"Uploaded {bytes_written / 1024:.1f} KB...")

        # Write large file with progress reporting and atomic safety
        await fs.stream_write(
            "/large_file.txt",
            data_generator(),
            progress_callback=progress_callback
        )

        # Stream read - process chunks as they arrive
        total_bytes = 0
        async for chunk in fs.stream_read("/large_file.txt", chunk_size=8192):
            total_bytes += len(chunk)
            # Process chunk without loading entire file

        print(f"Processed {total_bytes} bytes")

# Run with asyncio
import asyncio
asyncio.run(main())
```

#### Progress Reporting

Track upload/download progress with callbacks:

```python
async def upload_with_progress():
    async with AsyncVirtualFileSystem(provider="s3", bucket_name="my-bucket") as fs:

        # Progress tracking with sync callback
        def track_progress(bytes_written, total_bytes):
            percent = (bytes_written / total_bytes * 100) if total_bytes > 0 else 0
            print(f"Progress: {percent:.1f}% ({bytes_written:,} bytes)")

        # Or use async callback
        async def async_track_progress(bytes_written, total_bytes):
            # Can perform async operations here
            await update_progress_db(bytes_written, total_bytes)

        # Stream large file with progress tracking
        async def generate_data():
            for i in range(10000):
                yield f"Record {i}\n".encode()

        await fs.stream_write(
            "/exports/large_dataset.csv",
            generate_data(),
            progress_callback=track_progress  # or async_track_progress
        )
```

#### Atomic Write Safety

All streaming writes use atomic operations to prevent file corruption:

```python
async def safe_streaming():
    async with AsyncVirtualFileSystem(provider="filesystem", root_path="/data") as fs:

        # Streaming write is automatically atomic:
        # 1. Writes to temporary file (.tmp_*)
        # 2. Atomically moves to final location on success
        # 3. Auto-cleanup of temp files on failure

        try:
            await fs.stream_write("/critical_data.json", data_stream())
            # File appears atomically - never partially written
        except Exception as e:
            # On failure, no partial file exists
            # Temp files are automatically cleaned up
            print(f"Upload failed safely: {e}")
```

#### Provider-Specific Features

Different providers implement atomic writes differently:

| Provider | Atomic Write Method | Progress Support |
|----------|-------------------|------------------|
| **Memory** | Temp buffer → swap | ✅ Yes |
| **Filesystem** | Temp file → `os.replace()` (OS-level atomic) | ✅ Yes |
| **SQLite** | Temp file → atomic move | ✅ Yes |
| **S3** | Multipart upload (inherently atomic) | ✅ Yes |
| **E2B Sandbox** | Temp file → `mv` command (atomic) | ✅ Yes |

**Key Features:**
- Memory-efficient processing of large files
- Real-time progress tracking with callbacks
- Atomic write safety prevents corruption
- Automatic temp file cleanup on errors
- Customizable chunk sizes
- Works with all storage providers
- Perfect for streaming uploads/downloads
- Both sync and async callback support

### Virtual Mounts

Combine multiple storage providers in a single filesystem:

```python
from chuk_virtual_fs import AsyncVirtualFileSystem

async def main():
    async with AsyncVirtualFileSystem(
        provider="memory",
        enable_mounts=True
    ) as fs:

        # Mount S3 bucket at /cloud
        await fs.mount(
            "/cloud",
            provider="s3",
            bucket_name="my-bucket",
            endpoint_url="https://my-endpoint.com"
        )

        # Mount local filesystem at /local
        await fs.mount(
            "/local",
            provider="filesystem",
            root_path="/tmp/storage"
        )

        # Now use paths transparently across providers
        await fs.write_file("/cloud/data.txt", "Stored in S3")
        await fs.write_file("/local/cache.txt", "Stored locally")
        await fs.write_file("/memory.txt", "Stored in memory")

        # List all active mounts
        mounts = fs.list_mounts()
        for mount in mounts:
            print(f"{mount['mount_point']}: {mount['provider']}")

        # Copy between providers seamlessly
        await fs.cp("/cloud/data.txt", "/local/backup.txt")

        # Unmount when done
        await fs.unmount("/cloud")

import asyncio
asyncio.run(main())
```

**Key Features:**
- Unix-like mount system
- Transparent path routing to correct provider
- Combine cloud, local, and in-memory storage
- Read-only mount support
- Seamless cross-provider operations (copy, move)

## 📖 API Reference

### Core Methods

#### Basic Operations
- `mkdir(path)`: Create a directory
- `touch(path)`: Create an empty file
- `write_file(path, content)`: Write content to a file
- `read_file(path)`: Read content from a file
- `ls(path)`: List directory contents
- `cd(path)`: Change current directory
- `pwd()`: Get current directory
- `rm(path)`: Remove a file or directory
- `cp(source, destination)`: Copy a file or directory
- `mv(source, destination)`: Move a file or directory
- `find(path, recursive)`: Find files and directories
- `search(path, pattern, recursive)`: Search for files matching a pattern
- `get_node_info(path)`: Get information about a node
- `get_fs_info()`: Get comprehensive filesystem information

#### Streaming Operations
- `stream_write(path, stream, chunk_size=8192, progress_callback=None, **metadata)`: Write from async iterator
  - `progress_callback`: Optional callback function `(bytes_written, total_bytes) -> None`
  - Supports both sync and async callbacks
  - Atomic write safety with automatic temp file cleanup
- `stream_read(path, chunk_size=8192)`: Read as async iterator

#### Mount Management
- `mount(mount_point, provider, **provider_kwargs)`: Mount a provider at a path
- `unmount(mount_point)`: Unmount a provider
- `list_mounts()`: List all active mounts

## 🔍 Use Cases

- **Large File Processing**: Stream large files (GB+) without memory constraints
  - Real-time progress tracking for user feedback
  - Atomic writes prevent corruption on network failures
  - Perfect for video uploads, data exports, log processing
- **Multi-Provider Storage**: Combine local, cloud, and in-memory storage seamlessly
- **Cloud Data Pipelines**: Stream data between S3, local storage, and processing systems
  - Monitor upload/download progress
  - Automatic retry and recovery with atomic operations
- Development sandboxing and isolated code execution
- Educational environments and web-based IDEs
- Reproducible computing environments
- Testing and simulation with multiple storage backends
- Cloud storage abstraction for provider-agnostic applications

## 💡 Requirements

- Python 3.8+
- Optional dependencies:
  - `sqlite3` for SQLite provider
  - `boto3` for S3 provider
  - `e2b-code-interpreter` for E2B sandbox provider

## 🤝 Contributing

Contributions are welcome! Please submit pull requests or open issues on our GitHub repository.

## 📄 License

MIT License

## 🚨 Disclaimer

This library provides a flexible virtual filesystem abstraction. Always validate and sanitize inputs in production environments.