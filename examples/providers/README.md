# Storage Provider Examples

Examples demonstrating different storage backends for chuk-virtual-fs.

## 🚀 Quick Start

```bash
# Run the simplest example
python examples/providers/memory_provider_example.py
```

## 📋 Examples

### Basic Providers

| Example | Description | Dependencies |
|---------|-------------|--------------|
| [memory_provider_example.py](memory_provider_example.py) | In-memory storage (fastest) | None |
| [filesystem_provider_example.py](filesystem_provider_example.py) | Local disk storage | None |
| [sqlite_provider_example.py](sqlite_provider_example.py) | SQLite database backend | None |

### Cloud Providers

| Example | Description | Dependencies |
|---------|-------------|--------------|
| [s3_provider_example.py](s3_provider_example.py) | Amazon S3 storage | `pip install chuk-virtual-fs[s3]` |
| [e2b_provider_example.py](e2b_provider_example.py) | E2B sandbox integration | E2B account |

### Advanced Features

| Example | Description | Use Case |
|---------|-------------|----------|
| [secure_filesystem_example.py](secure_filesystem_example.py) | Encryption & security | Sensitive data |
| [binary_files_example.py](binary_files_example.py) | Binary file handling | Images, executables |
| [streaming_and_mounts_example.py](streaming_and_mounts_example.py) | Streaming operations | Large files |

---

## 💡 Example Details

### memory_provider_example.py

**Best for**: Development, testing, temporary data

```python
from chuk_virtual_fs import SyncVirtualFileSystem

vfs = SyncVirtualFileSystem()
vfs.write_file("/test.txt", "Hello!")
print(vfs.read_file("/test.txt"))
```

**Pros**:
- ✅ Fastest performance
- ✅ No setup required
- ✅ Perfect for testing

**Cons**:
- ❌ Data lost on exit
- ❌ Limited by RAM

### filesystem_provider_example.py

**Best for**: Persistent local storage

**Pros**:
- ✅ Data persists
- ✅ Simple to use
- ✅ No external dependencies

### sqlite_provider_example.py

**Best for**: Structured data, queryable storage

**Pros**:
- ✅ Transactional
- ✅ Single file
- ✅ Built-in to Python

### s3_provider_example.py

**Best for**: Cloud storage, distributed systems

**Requirements**:
```bash
pip install chuk-virtual-fs[s3]
# Set AWS credentials
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

**Pros**:
- ✅ Scalable
- ✅ Distributed
- ✅ Durable

### e2b_provider_example.py

**Best for**: Sandboxed code execution

**Requirements**: E2B account

**Use cases**:
- AI code execution
- Isolated builds
- Testing in sandboxes

---

## 🔄 Switching Providers

All providers implement the same interface, so switching is easy:

```python
# Memory (development)
from chuk_virtual_fs import SyncVirtualFileSystem
vfs = SyncVirtualFileSystem()

# Filesystem (local persistence)
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.providers import FilesystemProvider
vfs = SyncVirtualFileSystem(provider=FilesystemProvider("/path/to/data"))

# S3 (cloud storage)
from chuk_virtual_fs.providers import S3Provider
vfs = SyncVirtualFileSystem(provider=S3Provider(bucket="my-bucket"))
```

---

## 🧪 Testing

All provider examples are standalone and can be run directly:

```bash
python examples/providers/memory_provider_example.py
python examples/providers/filesystem_provider_example.py
python examples/providers/sqlite_provider_example.py
```

---

## 📚 Next Steps

1. Try the memory provider first (simplest)
2. Experiment with filesystem provider for persistence
3. Try S3 provider if you need cloud storage
4. Check out [WebDAV](../webdav/) or [FUSE mounting](../mounting/) to expose your VFS

---

See [main examples README](../README.md) for more information.
