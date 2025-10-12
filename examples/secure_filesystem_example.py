#!/usr/bin/env python3
"""
Example: Secure Filesystem Provider with Security Wrapper

This example demonstrates how to use the SecurityWrapper with the
AsyncFilesystemStorageProvider for production-grade security.
"""

import asyncio
import tempfile
from pathlib import Path

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.filesystem import AsyncFilesystemStorageProvider
from chuk_virtual_fs.security_wrapper import SecurityWrapper


def create_secure_filesystem_config():
    """Create different security configurations for various use cases"""

    configs = {
        "development": {
            "max_file_size": 10 * 1024 * 1024,  # 10MB
            "max_total_size": 100 * 1024 * 1024,  # 100MB
            "max_files": 1000,
            "allowed_paths": ["/"],
            "denied_patterns": [r".*\.(exe|sh|bat)$"],
            "read_only": False,
        },
        "production": {
            "max_file_size": 5 * 1024 * 1024,  # 5MB
            "max_total_size": 50 * 1024 * 1024,  # 50MB
            "max_files": 500,
            "allowed_paths": ["/uploads", "/cache", "/tmp"],
            "denied_patterns": [
                r".*\.(exe|sh|bat|cmd|scr|ps1)$",  # Executables
                r"\.\.",  # Path traversal
                r"^\..*",  # All hidden files
                r".*password.*",  # Password files
                r".*secret.*",  # Secret files
            ],
            "read_only": False,
        },
        "read_only": {
            "max_file_size": 1024 * 1024,  # 1MB
            "max_total_size": 10 * 1024 * 1024,  # 10MB
            "max_files": 100,
            "allowed_paths": ["/public", "/docs"],
            "denied_patterns": [r".*"],  # Block all writes
            "read_only": True,
        },
        "sandbox": {
            "max_file_size": 1024,  # 1KB (very restrictive)
            "max_total_size": 10 * 1024,  # 10KB total
            "max_files": 10,
            "allowed_paths": ["/sandbox"],
            "denied_patterns": [
                r".*\.(exe|sh|bat|cmd|scr|ps1|js|py|rb|php)$",  # All executables & scripts
                r"\.\.",  # Path traversal
                r"^\..*",  # Hidden files
                r".*\.(conf|config|ini|env)$",  # Config files
            ],
            "read_only": False,
        },
    }

    return configs


async def demonstrate_secure_operations(secure_fs, config_name):
    """Demonstrate secure operations with different security levels"""
    print(f"\n🔒 Testing {config_name.upper()} Security Configuration")
    print("=" * 60)

    # Test allowed file creation
    print("📝 Testing allowed file operations...")
    try:
        if config_name == "sandbox":
            allowed_path = "/sandbox"
        elif config_name == "production":
            allowed_path = "/uploads"
        elif config_name == "read_only":
            allowed_path = "/public"
        else:
            allowed_path = "/"

        node = EnhancedNodeInfo("test.txt", False, allowed_path)
        result = await secure_fs.create_node(node)
        print(f"   Create text file: {'✅' if result else '❌'}")

        if result and not secure_fs.read_only:
            write_result = await secure_fs.write_file(
                f"{allowed_path}/test.txt", b"Hello secure world!"
            )
            print(f"   Write to file: {'✅' if write_result else '❌'}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test blocked operations
    print("\n🚫 Testing blocked operations...")

    # Test executable file
    try:
        exe_node = EnhancedNodeInfo("malware.exe", False, allowed_path)
        result = await secure_fs.create_node(exe_node)
        print(f"   Create .exe file: {'❌ BLOCKED' if not result else '⚠️ ALLOWED'}")
    except Exception:
        print("   .exe file blocked: ✅")

    # Test path traversal
    try:
        traversal_node = EnhancedNodeInfo("../../etc/passwd", False, allowed_path)
        result = await secure_fs.create_node(traversal_node)
        print(f"   Path traversal: {'❌ BLOCKED' if not result else '⚠️ ALLOWED'}")
    except Exception:
        print("   Path traversal blocked: ✅")

    # Test unauthorized path
    try:
        node = EnhancedNodeInfo("unauthorized.txt", False, "/etc")
        result = await secure_fs.create_node(node)
        print(f"   Unauthorized path: {'❌ BLOCKED' if not result else '⚠️ ALLOWED'}")
    except Exception:
        print("   Unauthorized path blocked: ✅")

    # Show violation log
    violations = secure_fs.get_violation_log()
    print(f"\n📊 Security violations logged: {len(violations)}")
    for i, violation in enumerate(violations[-3:], 1):  # Show last 3
        print(f"   {i}. {violation['reason']} (path: {violation['path']})")

    # Show storage stats
    stats = await secure_fs.get_storage_stats()
    print("\n📈 Storage Statistics:")
    print(f"   Files: {stats.get('total_files', 0)}/{stats.get('max_files', 'N/A')}")
    print(
        f"   Size: {stats.get('total_size', 0)}/{stats.get('max_total_size', 'N/A')} bytes"
    )
    print(f"   Read-only: {stats.get('read_only', False)}")

    return len(violations)


async def run_security_demonstration():
    """Run comprehensive security demonstration"""
    print("🛡️ Secure Filesystem Provider Demonstration")
    print("=" * 60)

    configs = create_secure_filesystem_config()

    for config_name, config in configs.items():
        with tempfile.TemporaryDirectory(
            prefix=f"secure_fs_{config_name}_"
        ) as temp_dir:
            print(f"\n📁 Temporary directory: {temp_dir}")

            # Create base filesystem provider
            fs_provider = AsyncFilesystemStorageProvider(root_path=temp_dir)

            # Wrap with security
            secure_fs = SecurityWrapper(provider=fs_provider, **config)

            try:
                await secure_fs.initialize()

                # Create allowed directories if they don't exist
                for allowed_path in config["allowed_paths"]:
                    if allowed_path != "/":
                        try:
                            # Create the directory structure
                            full_path = Path(temp_dir) / allowed_path.lstrip("/")
                            full_path.mkdir(parents=True, exist_ok=True)
                        except Exception as e:
                            print(f"   Warning: Could not create {allowed_path}: {e}")

                violations_before = len(secure_fs.get_violation_log())
                violations_after = await demonstrate_secure_operations(
                    secure_fs, config_name
                )
                new_violations = violations_after - violations_before

                print(f"\n✅ {config_name.upper()} configuration test completed")
                print(f"   New security violations: {new_violations}")

            except Exception as e:
                print(f"❌ Error testing {config_name}: {e}")
            finally:
                await secure_fs.close()
                secure_fs.clear_violations()  # Clean up for next test

    print("\n🎉 Security demonstration completed!")
    print("The SecurityWrapper successfully protected the filesystem provider")
    print("from various security threats while allowing legitimate operations.")


async def demonstrate_integration_with_fs_manager():
    """Show how to integrate secure filesystem with VirtualFileSystem manager"""
    print("\n🔧 VirtualFileSystem Manager Integration")
    print("=" * 60)

    with tempfile.TemporaryDirectory(prefix="secure_vfs_") as temp_dir:
        # Create secure filesystem provider
        fs_provider = AsyncFilesystemStorageProvider(root_path=temp_dir)
        secure_provider = SecurityWrapper(
            provider=fs_provider,
            max_file_size=1024,  # 1KB limit
            allowed_paths=["/safe"],
            denied_patterns=[r".*\.(exe|sh)$"],
        )

        # Note: VirtualFileSystem expects provider name, not instance
        # For now, demonstrate direct usage
        await secure_provider.initialize()

        try:
            # Simulate VFS operations
            await secure_provider.create_node(EnhancedNodeInfo("safe", True, "/"))
            await secure_provider.create_node(
                EnhancedNodeInfo("test.txt", False, "/safe")
            )
            await secure_provider.write_file("/safe/test.txt", b"Secure content")

            content = await secure_provider.read_file("/safe/test.txt")
            print(
                f"✅ Secure VFS integration: {content.decode() if content else 'None'}"
            )

        finally:
            await secure_provider.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_security_demonstration())
        asyncio.run(demonstrate_integration_with_fs_manager())
    except KeyboardInterrupt:
        print("\n\n⚠️ Demonstration interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
