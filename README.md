# chuk-virtual-fs: Modular Virtual Filesystem Library

A powerful, flexible virtual filesystem library for Python with advanced features, multiple storage providers, and robust security.

> **🎯 Perfect for MCP Servers**: Expose virtual filesystems to Claude Desktop and other MCP clients via FUSE mounting. Generate code, mount it, and let Claude run real tools (TypeScript, linters, compilers) on it with full POSIX semantics.

## 🤖 For MCP & AI Tooling

**Make your virtual filesystem the "OS for tools"** - Mount per-session workspaces via **FUSE** and let Claude / MCP clients run real tools on AI-generated content.

- ✅ **Real tools, virtual filesystem**: TypeScript, ESLint, Prettier, `tsc`, pytest, etc. work seamlessly
- ✅ **Full POSIX semantics**: Any command-line tool that expects a real filesystem works
- ✅ **Pluggable backends**: Memory, S3, SQLite, E2B, or custom providers
- ✅ **Perfect for MCP servers**: Expose workspaces to Claude Desktop and other MCP clients
- ✅ **Zero-copy streaming**: Handle large files efficiently with progress tracking

**Example workflow:**
1. Your MCP server creates a `VirtualFileSystem` with AI-generated code
2. Mount it via FUSE at `/tmp/workspace`
3. Claude runs `tsc /tmp/workspace/main.ts` or any other tool
4. Read results back and iterate

See [MCP Use Cases](#for-mcp-servers-model-context-protocol) for detailed examples and [Architecture](#-architecture) for how it all fits together.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Your MCP Server / AI App                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              chuk-virtual-fs (This Library)                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  VirtualFileSystem (Core API)                        │   │
│  │  • mkdir, write_file, read_file, ls, cp, mv, etc.   │   │
│  │  • Streaming operations (large files)                │   │
│  │  • Virtual mounts (combine providers)                │   │
│  └────────────┬─────────────────────────────────────────┘   │
│               │                                              │
│      ┌────────┴────────┐                                     │
│      ▼                 ▼                                     │
│  ┌────────┐      ┌──────────┐                               │
│  │ WebDAV │      │   FUSE   │  ◄── Mounting Adapters        │
│  │Adapter │      │ Adapter  │                               │
│  └────┬───┘      └────┬─────┘                               │
└───────┼───────────────┼──────────────────────────────────────┘
        │               │
        │               │
        ▼               ▼
┌────────────┐   ┌─────────────┐
│  WebDAV    │   │ /tmp/mount  │  ◄── Real OS Mounts
│  Server    │   │  (FUSE)     │
│ :8080      │   │             │
└──────┬─────┘   └──────┬──────┘
       │                │
       │                │
       ▼                ▼
┌───────────────────────────────────┐
│   Real Tools & Applications       │
│  • Finder/Explorer (WebDAV)       │
│  • TypeScript (tsc)               │
│  • Linters (ESLint, Ruff)         │
│  • Any POSIX tool (ls, cat, etc.) │
└───────────────────────────────────┘
       │
       │
       ▼
┌───────────────────────────────────┐
│    Storage Backends (Providers)   │
│  • Memory  • SQLite  • S3         │
│  • E2B     • Filesystem           │
└───────────────────────────────────┘
```

**Key Points:**
- **Single API**: Use VirtualFileSystem regardless of backend
- **Multiple Backends**: Memory, SQLite, S3, E2B, or custom providers
- **Two Mount Options**: WebDAV (quick) or FUSE (full POSIX)
- **Real Tools Work**: Once mounted, any tool can access your virtual filesystem

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
- **Google Drive Provider**: Store files in user's Google Drive (user owns data!)
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
- **WebDAV Mounting**: Expose virtual filesystems via WebDAV (no kernel extensions!)
  - Mount in macOS Finder, Windows Explorer, or Linux file managers
  - Perfect for AI coding assistants and development workflows
  - Background server support
  - Read-only mode option
- **FUSE Mounting**: Native filesystem mounting with full POSIX semantics
  - Mount virtual filesystems as real directories
  - Works with any tool that expects a filesystem
  - Docker support for testing without system modifications
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

# Install with Google Drive support
pip install "chuk-virtual-fs[google_drive]"

# Install with WebDAV mounting support (recommended!)
pip install "chuk-virtual-fs[webdav]"

# Install with FUSE mounting support
pip install "chuk-virtual-fs[mount]"

# Install everything
pip install "chuk-virtual-fs[all]"

# Using uv
uv pip install "chuk-virtual-fs[s3]"
uv pip install "chuk-virtual-fs[google_drive]"
uv pip install "chuk-virtual-fs[webdav]"
uv pip install "chuk-virtual-fs[mount]"
uv pip install "chuk-virtual-fs[all]"
```

### For Development

```bash
# Clone the repository
git clone https://github.com/chrishayuk/chuk-virtual-fs.git
cd chuk-virtual-fs

# Install in development mode with all dependencies
pip install -e ".[dev,s3,e2b]"

# Using uv
uv pip install -e ".[dev,s3,e2b]"
```

## 📚 Examples

**Try the interactive example runner:**

```bash
cd examples
./run_example.sh  # Interactive menu with 11 examples
```

**Or run specific examples:**
- WebDAV: `./run_example.sh 1` (Basic server)
- FUSE: `./run_example.sh 5` (Docker mount test)
- Providers: `./run_example.sh 7` (Memory provider)

**See**: [examples/](examples/) for comprehensive documentation

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
- **Google Drive**: User's Google Drive (user owns data!)
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

### Google Drive Provider

The Google Drive provider lets you store files in the user's own Google Drive. This approach offers unique advantages:

- ✅ **User Owns Data**: Files are stored in the user's Google Drive, not your infrastructure
- ✅ **Natural Discoverability**: Users can view/edit files directly in Google Drive UI
- ✅ **Built-in Sharing**: Use Drive's native sharing and collaboration features
- ✅ **Cross-Device Sync**: Files automatically sync across all user devices
- ✅ **No Infrastructure Cost**: No need to manage storage servers or buckets

#### Installation

```bash
# Install with Google Drive support
pip install "chuk-virtual-fs[google_drive]"

# Or with uv
uv pip install "chuk-virtual-fs[google_drive]"
```

#### OAuth Setup

Before using the Google Drive provider, you need to set up OAuth2 credentials:

**Step 1: Create Google Cloud Project**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the Google Drive API
4. Go to "Credentials" → Create OAuth 2.0 Client ID
5. Choose "Desktop app" as application type
6. Download the JSON file and save as `client_secret.json`

**Step 2: Run OAuth Setup**

```bash
# Run the OAuth setup helper
python examples/providers/google_drive_oauth_setup.py

# Or with custom client secrets file
python examples/providers/google_drive_oauth_setup.py --client-secrets /path/to/client_secret.json
```

This will:
- Open a browser for Google authorization
- Save credentials to `google_drive_credentials.json`
- Show you the configuration for Claude Desktop / MCP servers

#### Example Usage

```python
import json
from pathlib import Path
from chuk_virtual_fs import AsyncVirtualFileSystem

# Load credentials from OAuth setup
with open("google_drive_credentials.json") as f:
    credentials = json.load(f)

# Create filesystem with Google Drive provider
async with AsyncVirtualFileSystem(
    provider="google_drive",
    credentials=credentials,
    root_folder="CHUK",  # Creates /CHUK/ folder in Drive
    cache_ttl=60  # Cache file IDs for 60 seconds
) as fs:
    # Create project structure
    await fs.mkdir("/projects/demo")

    # Write files - they appear in Google Drive!
    await fs.write_file(
        "/projects/demo/README.md",
        "# My Project\n\nFiles stored in Google Drive!"
    )

    # Read files back
    content = await fs.read_file("/projects/demo/README.md")

    # List directory
    files = await fs.ls("/projects/demo")

    # Get file metadata
    info = await fs.get_node_info("/projects/demo/README.md")
    print(f"Size: {info.size} bytes")
    print(f"Modified: {info.modified_at}")

    # Files are now in Google Drive under /CHUK/projects/demo/
```

#### Configuration for Claude Desktop

After running OAuth setup, add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vfs": {
      "command": "uvx",
      "args": ["chuk-virtual-fs"],
      "env": {
        "VFS_PROVIDER": "google_drive",
        "GOOGLE_DRIVE_CREDENTIALS": "{\"token\": \"...\", \"refresh_token\": \"...\", ...}"
      }
    }
  }
}
```

(The OAuth setup helper generates the complete configuration)

#### Features

- **Two-Level Caching**: Path→file_id and file_id→metadata caches for performance
- **Metadata Storage**: Session IDs, custom metadata, and tags stored in Drive's `appProperties`
- **Async Operations**: Full async/await support using `asyncio.to_thread`
- **Standard Operations**: All VirtualFileSystem methods work (mkdir, write_file, read_file, ls, etc.)
- **Statistics**: Track API calls, cache hits/misses with `get_storage_stats()`

#### Provider-Specific Parameters

```python
from chuk_virtual_fs.providers import GoogleDriveProvider

provider = GoogleDriveProvider(
    credentials=credentials_dict,      # OAuth2 credentials
    root_folder="CHUK",               # Root folder name in Drive
    cache_ttl=60,                     # Cache TTL in seconds (default: 60)
    session_id="optional_session_id", # Optional session tracking
    sandbox_id="default"              # Optional sandbox tracking
)
```

#### Examples

See the `examples/providers/` directory for complete examples:

- **`google_drive_oauth_setup.py`**: Interactive OAuth2 setup helper
- **`google_drive_example.py`**: Comprehensive end-to-end example

Run the full example:

```bash
# First, set up OAuth credentials
python examples/providers/google_drive_oauth_setup.py

# Then run the example
python examples/providers/google_drive_example.py
```

#### How It Works

1. **OAuth2 Authentication**: Uses Google's OAuth2 flow for secure authorization
2. **Root Folder**: Creates a folder (default: `CHUK`) in the user's Drive as the filesystem root
3. **Path Mapping**: Virtual paths like `/projects/demo/file.txt` → `CHUK/projects/demo/file.txt` in Drive
4. **Metadata**: Custom metadata (session_id, tags, etc.) stored in Drive's `appProperties`
5. **Caching**: Two-level cache reduces API calls for better performance

#### Use Cases

Perfect for:
- **User-Owned Workspaces**: Give users their own persistent workspace in their Drive
- **Collaborative AI Projects**: Users can share their Drive folders with collaborators
- **Long-Term Storage**: User controls retention and can access files outside your app
- **Cross-Device Access**: Users access their files from any device with Drive
- **Zero Infrastructure**: No need to run storage servers or manage buckets

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

### WebDAV Mounting

**Recommended for most users** - Mount virtual filesystems without kernel extensions!

```python
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.adapters import WebDAVAdapter

# Create a virtual filesystem
vfs = SyncVirtualFileSystem()
vfs.write_file("/documents/hello.txt", "Hello World!")
vfs.write_file("/documents/notes.md", "# My Notes")

# Start WebDAV server
adapter = WebDAVAdapter(vfs, port=8080)
adapter.start()  # Server runs at http://localhost:8080

# Or run in background
adapter.start_background()
# Continue working...
vfs.write_file("/documents/updated.txt", "New content!")
adapter.stop()
```

**Mounting in Your OS:**

- **macOS**: Finder → Cmd+K → `http://localhost:8080`
- **Windows**: Map Network Drive → `http://localhost:8080`
- **Linux**: `davfs2` or file manager

**Why WebDAV?**
- ✅ No kernel extensions required
- ✅ Works immediately on macOS/Windows/Linux
- ✅ Perfect for AI coding assistants
- ✅ Easy to deploy and test
- ✅ Background operation support
- ✅ Read-only mode available

**Installation:**
```bash
pip install "chuk-virtual-fs[webdav]"
```

**See**: [WebDAV Examples](examples/webdav/) for detailed usage

### FUSE Mounting

Native filesystem mounting with full POSIX semantics.

```python
from chuk_virtual_fs import AsyncVirtualFileSystem
from chuk_virtual_fs.mount import mount, MountOptions

async def main():
    # Create virtual filesystem
    vfs = AsyncVirtualFileSystem()
    await vfs.write_file("/hello.txt", "Mounted!")

    # Mount at /tmp/mymount
    async with mount(vfs, "/tmp/mymount", MountOptions()) as adapter:
        # Filesystem is now accessible at /tmp/mymount
        # Any tool can access it: ls, cat, vim, TypeScript, etc.
        await asyncio.Event().wait()

import asyncio
asyncio.run(main())
```

**FUSE Options:**

```python
from chuk_virtual_fs.mount import MountOptions

options = MountOptions(
    readonly=False,      # Read-only mount
    allow_other=False,   # Allow other users to access
    debug=False,         # Enable FUSE debug output
    cache_timeout=1.0    # Stat cache timeout in seconds
)
```

**Installation & Requirements:**

```bash
# Install package with FUSE support
pip install "chuk-virtual-fs[mount]"

# macOS: Install macFUSE
brew install macfuse

# Linux: Install FUSE3
sudo apt-get install fuse3 libfuse3-dev

# Docker: No system modifications needed!
# See examples/mounting/README.md for Docker testing
```

**Docker Testing (No System Changes):**

```bash
cd examples
./run_example.sh 5  # Basic FUSE mount test
./run_example.sh 6  # TypeScript checker demo
```

**Why FUSE?**
- ✅ Full POSIX semantics
- ✅ Works with any tool expecting a filesystem
- ✅ **Perfect for MCP servers** - Expose virtual filesystems to Claude Desktop and other MCP clients
- ✅ Ideal for AI + tools integration (TypeScript, linters, compilers, etc.)
- ✅ True filesystem operations (stat, chmod, etc.)

**MCP Server Use Case:**
```python
# MCP server exposes a virtual filesystem via FUSE
# Claude Desktop can then access it like a real filesystem
async def mcp_filesystem_tool():
    vfs = AsyncVirtualFileSystem()
    # Populate with AI-generated code, data, etc.
    await vfs.write_file("/project/main.ts", generated_code)

    # Mount so tools can access it
    async with mount(vfs, "/tmp/mcp-workspace", MountOptions()):
        # Claude can now run: tsc /tmp/mcp-workspace/project/main.ts
        # Or any other tool that expects a real filesystem
        await process_with_real_tools()
```

**See**: [FUSE Examples](examples/mounting/) for detailed usage including Docker testing

### Choosing Between WebDAV and FUSE

| Feature | WebDAV | FUSE |
|---------|--------|------|
| **Setup** | No system changes | Requires kernel extension |
| **Installation** | `pip install` only | System FUSE + pip |
| **Compatibility** | All platforms | macOS/Linux (Windows WSL2) |
| **POSIX Semantics** | Basic | Full |
| **Speed** | Fast | Faster |
| **MCP Servers** | ⚠️ Limited tool support | ✅ **Perfect** - full tool compatibility |
| **Use Case** | Remote access, quick dev | MCP servers, local tools, full integration |
| **Best For** | Most users, simple sharing | **MCP servers**, power users, full POSIX needs |

**Which Should You Use?**

- **Building an MCP server?** → **Use FUSE** - Claude and MCP clients need full POSIX semantics to run real tools
- **Quick prototyping or sharing?** → **Use WebDAV** - Works immediately, no system setup
- **AI coding assistant with TypeScript/linters?** → **Use FUSE** - Full tool compatibility guaranteed
- **Remote file access?** → **Use WebDAV** - Built for network access, mounts in Finder/Explorer
- **Running in Docker/CI?** → **Use FUSE** - No kernel extensions needed in containers
- **Maximum performance with local tools?** → **Use FUSE** - Native filesystem performance

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

### For MCP Servers (Model Context Protocol)
- **FUSE Mounting for MCP**: Expose virtual filesystems to Claude Desktop and MCP clients
  - MCP server maintains virtual filesystem with AI-generated code
  - Mount via FUSE so Claude can run real tools (TypeScript, linters, compilers)
  - Full POSIX semantics - works with ANY command-line tool
  - Perfect for code generation → validation → iteration workflows
  - See: [examples/mounting/02_typescript_checker.py](examples/mounting/02_typescript_checker.py)

**Example MCP Integration:**
```python
# Your MCP server can expose a filesystem tool
@mcp.tool()
async def create_project(project_type: str):
    vfs = AsyncVirtualFileSystem()
    # Generate project structure
    await vfs.write_file("/project/main.ts", generated_code)

    # Mount so Claude can run tools on it
    async with mount(vfs, "/tmp/mcp-workspace", MountOptions()):
        # Now Claude can: tsc /tmp/mcp-workspace/project/main.ts
        # Or: eslint /tmp/mcp-workspace/project/
        # Any tool that expects a real filesystem works!
        return "/tmp/mcp-workspace"
```

**Complete End-to-End MCP Workflow:**

```python
# 1. MCP Server Setup - your_mcp_server.py
from chuk_virtual_fs import AsyncVirtualFileSystem
from chuk_virtual_fs.mount import mount, MountOptions
import mcp

@mcp.tool()
async def generate_and_validate_typescript(code: str):
    """Generate TypeScript code and validate it with tsc."""

    # Step 1: Create virtual filesystem with AI-generated code
    vfs = AsyncVirtualFileSystem()
    await vfs.mkdir("/project/src")
    await vfs.write_file("/project/src/main.ts", code)
    await vfs.write_file("/project/tsconfig.json", '''{
        "compilerOptions": {
            "target": "ES2020",
            "module": "commonjs",
            "strict": true
        }
    }''')

    # Step 2: Mount the virtual filesystem via FUSE
    mount_point = "/tmp/mcp-typescript-workspace"
    async with mount(vfs, mount_point, MountOptions()):

        # Step 3: Claude can now run REAL TypeScript compiler
        result = await run_bash_command(f"tsc --noEmit {mount_point}/project/src/main.ts")

        if result.exit_code != 0:
            # Step 4: Return errors to Claude for fixes
            return {
                "status": "error",
                "errors": result.stderr,
                "path": mount_point
            }

        # Step 5: Success! Run linter for extra validation
        lint_result = await run_bash_command(f"eslint {mount_point}/project/src/")

        return {
            "status": "success",
            "typescript_check": "passed",
            "lint_result": lint_result.stdout,
            "path": mount_point
        }

# 2. Claude Desktop sees this and can:
#    - Call generate_and_validate_typescript() with AI-generated code
#    - Get real TypeScript compiler feedback
#    - Iterate on fixes based on actual tool output
#    - Run any other tool (prettier, webpack, jest, etc.)
```

**What happens:**
1. Your MCP server creates a virtual filesystem with AI-generated content
2. Mounts it via FUSE at a real path
3. Claude Desktop runs actual tools (tsc, eslint, etc.) via MCP bash commands
4. Tools see a real filesystem and work perfectly
5. Results flow back to Claude for iteration

**Why this is powerful:**
- ✅ No mocking tool behavior - use real compilers and linters
- ✅ Works with ANY tool expecting a filesystem
- ✅ Full validation and error messages
- ✅ Claude can iterate based on real tool feedback
- ✅ Virtual filesystem = easy cleanup, no state pollution

### For AI Coding Assistants
- **WebDAV Mounting**: Quick setup, no kernel extensions
  - AI generates code, mount it via WebDAV, tools can access it immediately
  - No system modifications required
  - Perfect for running TypeScript, linters, formatters on AI-generated code
  - See: [examples/webdav/02_background_server.py](examples/webdav/02_background_server.py)

- **FUSE Mounting**: Full POSIX integration for maximum tool compatibility
  - AI generates TypeScript → mount → `tsc` checks it → AI fixes errors
  - See: [examples/mounting/02_typescript_checker.py](examples/mounting/02_typescript_checker.py)

### For Production Applications
- **Large File Processing**: Stream large files (GB+) without memory constraints
  - Real-time progress tracking for user feedback
  - Atomic writes prevent corruption on network failures
  - Perfect for video uploads, data exports, log processing

- **Multi-Provider Storage**: Combine local, cloud, and in-memory storage seamlessly
  - Mount S3 at `/cloud`, local disk at `/cache`, memory at `/tmp`
  - Transparent routing to correct provider

- **Cloud Data Pipelines**: Stream data between S3, local storage, and processing systems
  - Monitor upload/download progress
  - Automatic retry and recovery with atomic operations

### For Development
- Development sandboxing and isolated code execution
- Educational environments and web-based IDEs
- Reproducible computing environments
- Testing and simulation with multiple storage backends
- Cloud storage abstraction for provider-agnostic applications
- Share filesystems via WebDAV without complex setup

## 🌐 CHUK Ecosystem

`chuk-virtual-fs` is part of the CHUK toolkit for building AI agents and MCP servers:

- **[chuk-virtual-fs](https://github.com/chrishayuk/chuk-virtual-fs)** - This library: Virtual filesystem with mounting (WebDAV/FUSE)
- **[chuk-mcp-server](https://github.com/chrishayuk/chuk-mcp-server)** - MCP server framework that uses chuk-virtual-fs for workspace management
- **[chuk-tools](https://github.com/chrishayuk/chuk-tools)** - Command-line tools that work with mounted virtual filesystems

**Example integration:**
1. Use `chuk-virtual-fs` to create a virtual filesystem with AI-generated code
2. Mount it via FUSE or WebDAV
3. Use `chuk-tools` or any standard tools to validate, lint, and process the code
4. Wrap it all in `chuk-mcp-server` to expose to Claude Desktop and other MCP clients

**Perfect for:**
- Building MCP servers that need filesystem workspaces
- Creating sandboxed environments for AI agents
- Tool-augmented AI workflows (code generation → validation → iteration)

## 💡 Requirements

- Python 3.8+
- Optional dependencies:
  - `sqlite3` for SQLite provider
  - `boto3` for S3 provider
  - `e2b-code-interpreter` for E2B sandbox provider
  - `wsgidav` and `cheroot` for WebDAV mounting
  - `pyfuse3` for FUSE mounting
  - System FUSE (macFUSE on macOS, fuse3 on Linux) for FUSE mounting

## 🤝 Contributing

Contributions are welcome! Please submit pull requests or open issues on our GitHub repository.

## 📄 License

MIT License

## 🚨 Disclaimer

This library provides a flexible virtual filesystem abstraction. Always validate and sanitize inputs in production environments.