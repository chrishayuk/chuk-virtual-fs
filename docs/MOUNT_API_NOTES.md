# Mount API Compatibility Notes

## VFS API Mapping

The mount adapters use the following VFS API methods:

| Mount Operation | VFS Method | Notes |
|----------------|------------|-------|
| Check if path exists | `vfs.exists(path)` | ✅ Available |
| Check if directory | `vfs.is_dir(path)` | ✅ Available |
| Check if file | `vfs.is_file(path)` | ✅ Available |
| Read file | `vfs.read_file(path)` | ✅ Available |
| Write file | `vfs.write_file(path, content)` | ✅ Available |
| List directory | `vfs.ls(path)` | ✅ Available |
| Create directory | `vfs.mkdir(path)` | ✅ Available |
| Delete file/dir | `vfs.rm(path)` | ✅ Available |
| Delete directory | `vfs.rmdir(path)` | ✅ Available |
| Create empty file | `vfs.touch(path)` | ✅ Available |

## Usage with Current API

```python
from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.mount import mount, MountOptions
from pathlib import Path

# Create VFS instance
vfs = SyncVirtualFileSystem()

# Add files
vfs.write_file("/hello.txt", "Hello World")
vfs.mkdir("/src")
vfs.write_file("/src/main.py", "print('Hello')")

# Mount it
options = MountOptions(readonly=False)
adapter = mount(vfs, Path("/mnt/chukfs"), options)

# Note: Actual mounting requires FUSE/WinFsp to be installed
# Install with: pip install chuk-virtual-fs[mount]
```

## Type Hints

The mount module uses `TYPE_CHECKING` to reference VFS types without circular imports:

```python
if TYPE_CHECKING:
    from chuk_virtual_fs.fs_manager import VirtualFS
```

This means the mount adapters are compatible with any VFS-like object that implements the required methods.

## Required Methods

For an object to be mountable, it must implement:

- `exists(path: str) -> bool`
- `is_dir(path: str) -> bool` or `is_file(path: str) -> bool`
- `read_file(path: str) -> str | bytes`
- `write_file(path: str, content: str | bytes) -> None`
- `ls(path: str) -> list[str]`
- `mkdir(path: str) -> None`
- `rm(path: str) -> None`
- `rmdir(path: str) -> None`
- `touch(path: str) -> None`

## Future Compatibility

As the VFS API evolves, the mount adapters will be updated to support:

- Rename operations (when `mv` supports cross-directory moves)
- Extended attributes (if added to VFS)
- File locking (if added to VFS)
- Symbolic links (if added to VFS)
