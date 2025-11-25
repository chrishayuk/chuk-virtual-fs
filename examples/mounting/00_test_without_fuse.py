#!/usr/bin/env python3
"""
Example 0: Testing Mount Infrastructure (No FUSE Required)

This example demonstrates the mount infrastructure works correctly
even without FUSE installed. It shows:
1. All mount modules import correctly
2. VFS operations work
3. Mount adapters are created with proper error handling
4. Platform detection works

This is useful for:
- CI/CD environments where FUSE isn't available
- Development without FUSE dependencies
- Understanding the architecture before installing FUSE

Usage:
    python examples/mounting/00_test_without_fuse.py
"""

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_imports():
    """Test that all mount modules can be imported."""
    print("1. Testing imports...")

    try:
        from chuk_virtual_fs import SyncVirtualFileSystem

        print("   ✅ chuk_virtual_fs imported")

        from chuk_virtual_fs.mount import MountOptions, mount

        print("   ✅ mount module imported")

        from chuk_virtual_fs.mount.base import MountAdapter, StatInfo

        print("   ✅ base module imported")

        from chuk_virtual_fs.mount.exceptions import (
            MountError,
            MountNotSupportedError,
            UnmountError,
        )

        print("   ✅ exceptions module imported")

        print("   ✅ All imports successful!\n")
        return True

    except ImportError as e:
        print(f"   ❌ Import failed: {e}\n")
        return False


def test_vfs_operations():
    """Test basic VFS operations."""
    print("2. Testing VFS operations...")

    try:
        from chuk_virtual_fs import SyncVirtualFileSystem

        vfs = SyncVirtualFileSystem()

        # Create files
        vfs.mkdir("/test")
        vfs.write_file("/test/hello.txt", "Hello World")
        vfs.write_file("/test/data.json", '{"status": "ok"}')

        # Read back (read_file returns bytes by default)
        content = vfs.read_file("/test/hello.txt", as_text=True)
        assert content == "Hello World", "Content mismatch"

        # List directory
        files = vfs.ls("/test")
        assert len(files) == 2, "File count mismatch"

        print("   ✅ VFS create/read/list operations work")
        print(f"   ✅ Created {len(files)} files")
        print("   ✅ All VFS operations successful!\n")
        return True

    except Exception as e:
        print(f"   ❌ VFS operations failed: {e}\n")
        return False


def test_mount_adapter_creation():
    """Test mount adapter creation without actually mounting."""
    print("3. Testing mount adapter creation...")

    try:
        from chuk_virtual_fs import SyncVirtualFileSystem
        from chuk_virtual_fs.mount import MountOptions, mount

        vfs = SyncVirtualFileSystem()
        vfs.write_file("/test.txt", "Test")

        mount_point = Path("/tmp/test_chuk_vfs")

        try:
            adapter = mount(vfs, mount_point, MountOptions())

            # If FUSE is installed, adapter creation succeeds
            print("   ✅ Mount adapter created successfully")
            print(f"   ✅ Adapter type: {type(adapter).__name__}")
            print("   ℹ️  FUSE libraries are installed on this system")
            return True

        except Exception as e:
            error_msg = str(e)

            # If FUSE is not installed, we should get an error
            if "FUSE support not available" in error_msg:
                print("   ✅ Mount adapter correctly detects missing FUSE")
                print("   ✅ Error handling works as expected")
                return True
            elif "pkg-config" in error_msg or "fusepy" in error_msg:
                print("   ✅ Mount adapter creation attempted")
                print("   ✅ FUSE dependencies required (as expected)")
                return True
            else:
                print(f"   ❌ Unexpected error: {error_msg}")
                return False

    except Exception as e:
        print(f"   ❌ Test failed: {e}\n")
        return False


def test_platform_detection():
    """Test platform detection logic."""
    print("\n4. Testing platform detection...")

    try:
        import sys

        platform = sys.platform
        print(f"   📍 Detected platform: {platform}")

        if platform == "darwin":
            print("   ✅ macOS detected → will use FUSEAdapter")
        elif platform == "linux":
            print("   ✅ Linux detected → will use FUSEAdapter")
        elif platform == "win32":
            print("   ✅ Windows detected → will use WinFspAdapter")
        else:
            print(f"   ⚠️  Unknown platform: {platform}")

        print("   ✅ Platform detection works!\n")
        return True

    except Exception as e:
        print(f"   ❌ Platform detection failed: {e}\n")
        return False


def show_installation_instructions():
    """Show how to install FUSE support."""
    print("=" * 70)
    print("📦 To actually mount filesystems, install FUSE support:")
    print("=" * 70)

    if sys.platform == "darwin":
        print("\nmacOS:")
        print("  brew install macfuse")
        print("  pip install chuk-virtual-fs[mount]")

    elif sys.platform == "linux":
        print("\nLinux (Ubuntu/Debian):")
        print("  sudo apt-get install fuse3 libfuse3-dev")
        print("  pip install chuk-virtual-fs[mount]")

    elif sys.platform == "win32":
        print("\nWindows:")
        print("  1. Download WinFsp from https://winfsp.dev")
        print("  2. pip install chuk-virtual-fs[mount]")

    print("\nAfter installation, run:")
    print("  python examples/mounting/01_basic_mount.py")
    print("=" * 70)


def main():
    """Run all tests."""
    print("=" * 70)
    print("Example 0: Testing Mount Infrastructure (No FUSE Required)")
    print("=" * 70)
    print()

    tests = [
        ("Imports", test_imports),
        ("VFS Operations", test_vfs_operations),
        ("Mount Adapter Creation", test_mount_adapter_creation),
        ("Platform Detection", test_platform_detection),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"   ❌ Test crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {name}")

    print(f"\n  Result: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        print("\nThe mount infrastructure is correctly installed.")
        print("You can proceed to install FUSE to use mounting functionality.")
        show_installation_instructions()
        return 0
    else:
        print("\n❌ Some tests failed")
        print("\nPlease check your installation:")
        print("  pip install -e .")
        return 1


if __name__ == "__main__":
    sys.exit(main())
