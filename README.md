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
- **S3 Provider**: Cloud storage with AWS S3 backend
- **E2B Sandbox Provider**: Remote sandbox environment filesystem
- Easy to extend with custom providers

### 🔒 Advanced Security
- Multiple predefined security profiles
- Customizable access controls
- Path and file type restrictions
- Quota management
- Security violation tracking

### 🚀 Advanced Capabilities
- Snapshot and versioning support
- Template-based filesystem setup
- Flexible path resolution
- Comprehensive file and directory operations

## 📦 Installation

```bash
pip install chuk-virtual-fs
```

## 🚀 Quick Start

### Basic Usage

```python
from chuk_virtual_fs import VirtualFileSystem

# Create a filesystem with default memory provider
fs = VirtualFileSystem()

# Create directories
fs.mkdir("/home/user/documents")

# Write to a file
fs.write_file("/home/user/documents/hello.txt", "Hello, Virtual World!")

# Read from a file
content = fs.read_file("/home/user/documents/hello.txt")
print(content)
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
```

## 📂 Available Storage Providers

1. **Memory Provider**: 
   - Lightweight, in-memory filesystem
   - Great for testing and temporary storage

2. **SQLite Provider**:
   - Persistent storage using SQLite
   - Supports both in-memory and on-disk databases

3. **Pyodide Provider**:
   - Designed for web browser environments
   - Integrates with Pyodide filesystem

4. **S3 Provider**:
   - Cloud storage using AWS S3
   - Supports custom S3-compatible services

5. **E2B Sandbox Provider**:
   - Remote sandbox environment
   - Ideal for isolated, controlled execution environments
   - Supports code execution and file management in sandboxed contexts

## 🛡️ Security Features

- Predefined security profiles (default, strict, readonly, untrusted)
- Custom security configuration
- File size and total storage quotas
- Path traversal protection
- Deny/allow path and pattern rules
- Security violation logging

## 📋 Snapshot and Template Management

```python
from chuk_virtual_fs import VirtualFileSystem
from chuk_virtual_fs.snapshot_manager import SnapshotManager
from chuk_virtual_fs.template_loader import TemplateLoader

# Create filesystem
fs = VirtualFileSystem()

# Snapshot management
snapshot_mgr = SnapshotManager(fs)
initial_snapshot = snapshot_mgr.create_snapshot("initial_state")

# Template loading
template_loader = TemplateLoader(fs)
project_template = {
    "directories": ["/project"],
    "files": [
        {
            "path": "/project/README.md",
            "content": "# My Project\n\nProject details here."
        }
    ]
}
template_loader.apply_template(project_template)
```

## 🔍 Use Cases

- Development sandboxing
- Educational environments
- Web-based IDEs
- Reproducible computing environments
- Testing and simulation
- Isolated code execution

## 🤝 Contributing

Contributions are welcome! Please submit pull requests or open issues on our GitHub repository.

## 📄 License

MIT License

## 🔗 Resources

- Documentation: [Link to full documentation]
- GitHub Repository: [Link to GitHub]
- Issues: [Link to Issues]

## 💡 Requirements

- Python 3.8+
- Optional dependencies:
  - `sqlite3` for SQLite provider
  - `boto3` for S3 provider
  - `e2b` for E2B sandbox provider

## 🚨 Disclaimer

This library provides a flexible virtual filesystem abstraction. Always validate and sanitize inputs in production environments.