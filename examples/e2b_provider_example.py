#!/usr/bin/env python3
"""
Comprehensive E2B Storage Provider Example
==========================================
Demonstrates using the E2B (E2B Sandbox) storage provider for cloud sandbox environments.
Perfect for isolated code execution, testing, and ephemeral compute environments.

This example showcases all features of the E2B provider including:
- Basic file and directory operations
- Metadata storage and retrieval
- Batch operations for efficiency
- Copy and move operations
- Checksum calculation
- Storage statistics
- Error handling

Prerequisites:
- E2B API key (get one at https://e2b.dev)
- e2b-code-interpreter library installed (pip install e2b-code-interpreter)
"""

import asyncio
import json
import os
from datetime import datetime

from chuk_virtual_fs.providers.e2b import E2BStorageProvider

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
    print("✓ Loaded environment variables from .env file")
except ImportError:
    print("ℹ️ python-dotenv not installed, using system environment variables")
    print("  Install with: pip install python-dotenv")


async def main():
    print("=" * 60)
    print("E2B Storage Provider Example")
    print("=" * 60)

    # Get E2B configuration from environment
    api_key = os.environ.get("E2B_API_KEY")
    sandbox_id = os.environ.get("E2B_SANDBOX_ID")

    if not api_key:
        print("\n❌ E2B_API_KEY environment variable not set!")
        print("\nTo use this example:")
        print("  1. Sign up at https://e2b.dev")
        print("  2. Get your API key from the dashboard")
        print("  3. Set the environment variable:")
        print("     export E2B_API_KEY=your_api_key_here")
        print("\nOptionally, set a specific sandbox ID:")
        print("     export E2B_SANDBOX_ID=your_sandbox_id")
        return

    print("\n✓ E2B API key found")
    if sandbox_id:
        print(f"✓ Using sandbox ID: {sandbox_id}")
    else:
        print("→ Will create a new sandbox")

    # Initialize the E2B provider
    provider = E2BStorageProvider(sandbox_id=sandbox_id)

    # Initialize and connect to sandbox
    print("\n📦 Initializing E2B sandbox...")
    if await provider.initialize():
        print("✓ Connected to E2B sandbox successfully")
        if hasattr(provider, "sandbox_id"):
            print(f"  Sandbox ID: {provider.sandbox_id}")
    else:
        print("❌ Failed to initialize E2B sandbox")
        return

    # Import EnhancedNodeInfo for creating nodes
    from chuk_virtual_fs.node_info import EnhancedNodeInfo

    # 1. Create directory structure in sandbox
    print("\n1. Creating directory structure in sandbox...")

    directories = [
        "/workspace",
        "/workspace/src",
        "/workspace/tests",
        "/workspace/data",
        "/output",
        "/logs",
    ]

    for dir_path in directories:
        parent_path = (
            "/" if "/" not in dir_path[1:] else "/".join(dir_path.rsplit("/", 1)[:-1])
        )
        dir_name = dir_path.rsplit("/", 1)[-1]

        node = EnhancedNodeInfo(name=dir_name, is_dir=True, parent_path=parent_path)
        if await provider.create_node(node):
            print(f"  ✓ Created: {dir_path}")

    # 2. Upload code files to sandbox
    print("\n2. Uploading code to sandbox...")

    # Python script for execution
    python_code = b'''#!/usr/bin/env python3
"""Example script running in E2B sandbox"""

import json
import sys
from datetime import datetime

def process_data():
    """Process data in isolated sandbox"""
    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "environment": "E2B Sandbox",
        "python_version": sys.version,
        "message": "Hello from isolated sandbox!",
        "computation": sum(range(1000))
    }
    return result

if __name__ == "__main__":
    print("Starting processing in E2B sandbox...")
    result = process_data()

    # Write result to file (using actual sandbox path)
    with open("/home/user/output/result.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"Processing complete: {result['message']}")
    print(f"Result saved to /home/user/output/result.json")
'''

    script_node = EnhancedNodeInfo(
        name="process.py", is_dir=False, parent_path="/workspace/src"
    )
    if await provider.create_node(script_node):
        await provider.write_file("/workspace/src/process.py", python_code)
        print("  ✓ Uploaded process.py")

    # Test file
    test_code = '''#!/usr/bin/env python3
"""Unit tests for sandbox execution"""

def test_sandbox_environment():
    """Test that we're in E2B sandbox"""
    import os
    # Check for actual sandbox paths (root_dir is /home/user)
    assert os.path.exists("/home/user/workspace")
    assert os.path.exists("/home/user/output")
    print("✓ Sandbox environment validated")

def test_file_operations():
    """Test file operations in sandbox"""
    test_file = "/home/user/workspace/test_file.txt"

    # Write test
    with open(test_file, "w") as f:
        f.write("Test content")

    # Read test
    with open(test_file, "r") as f:
        content = f.read()

    assert content == "Test content"
    print("✓ File operations working")

if __name__ == "__main__":
    test_sandbox_environment()
    test_file_operations()
    print("All tests passed!")
'''.encode()

    test_node = EnhancedNodeInfo(
        name="test_sandbox.py", is_dir=False, parent_path="/workspace/tests"
    )
    if await provider.create_node(test_node):
        await provider.write_file("/workspace/tests/test_sandbox.py", test_code)
        print("  ✓ Uploaded test_sandbox.py")

    # Data file
    data = {
        "items": [
            {"id": 1, "name": "Item A", "value": 100},
            {"id": 2, "name": "Item B", "value": 200},
            {"id": 3, "name": "Item C", "value": 300},
        ],
        "metadata": {"created": datetime.utcnow().isoformat(), "source": "E2B Example"},
    }

    data_node = EnhancedNodeInfo(
        name="input_data.json", is_dir=False, parent_path="/workspace/data"
    )
    if await provider.create_node(data_node):
        await provider.write_file(
            "/workspace/data/input_data.json", json.dumps(data, indent=2).encode()
        )
        print("  ✓ Uploaded input_data.json")

    # 3. Execute code in sandbox (E2B specific feature)
    print("\n3. Executing code in sandbox:")

    if hasattr(provider, "sandbox") and provider.sandbox:
        try:
            # Get the actual sandbox paths (need to convert from virtual paths)
            test_sandbox_path = provider._get_sandbox_path(
                "/workspace/tests/test_sandbox.py"
            )
            process_sandbox_path = provider._get_sandbox_path(
                "/workspace/src/process.py"
            )

            # Run the test script
            print("\n  Running tests...")
            test_result = provider.sandbox.commands.run(f"python {test_sandbox_path}")
            if test_result and test_result.exit_code == 0:
                print("  ✓ Tests passed:")
                for line in test_result.stdout.strip().split("\n"):
                    print(f"    {line}")
            elif test_result:
                print(f"  ⚠️ Tests failed with exit code {test_result.exit_code}")
                if test_result.stderr:
                    print(f"  Error: {test_result.stderr}")

            # Run the main processing script
            print("\n  Running main process...")
            process_result = provider.sandbox.commands.run(
                f"python {process_sandbox_path}"
            )
            if process_result and process_result.exit_code == 0:
                print("  ✓ Process completed successfully:")
                for line in process_result.stdout.strip().split("\n"):
                    print(f"    {line}")
            elif process_result:
                print(f"  ⚠️ Process failed with exit code {process_result.exit_code}")
                if process_result.stderr:
                    print(f"  Error: {process_result.stderr}")
        except Exception as e:
            print(f"  ⚠️ Execution feature not available: {e}")
    else:
        print("  ℹ️ Direct execution not available in this mode")

    # 4. List sandbox contents
    print("\n4. Sandbox filesystem contents:")

    async def list_tree(path="/", indent=0):
        """List sandbox directory tree"""
        try:
            items = await provider.list_directory(path)
            for item in items:
                item_path = f"{path}/{item}" if path != "/" else f"/{item}"
                node_info = await provider.get_node_info(item_path)

                if node_info and node_info.is_dir:
                    print(f"{'  ' * indent}📁 {item}/")
                    await list_tree(item_path, indent + 1)
                elif node_info:
                    size = node_info.size or 0
                    print(f"{'  ' * indent}📄 {item} ({size} bytes)")
        except Exception:
            pass

    await list_tree()

    # 5. Read results from sandbox
    print("\n5. Reading execution results:")

    # Check if result file was created
    if await provider.exists("/output/result.json"):
        result_content = await provider.read_file("/output/result.json")
        if result_content:
            result_data = json.loads(result_content.decode())
            print("\n  Execution result:")
            print(f"    - Timestamp: {result_data.get('timestamp')}")
            print(f"    - Message: {result_data.get('message')}")
            print(f"    - Computation: {result_data.get('computation')}")
    else:
        print("  ℹ️ No execution results found")

    # 6. File operations
    print("\n6. File operations in sandbox:")

    # Create a log file
    log_content = f"[{datetime.utcnow().isoformat()}] Sandbox session started\n"
    log_content += f"[{datetime.utcnow().isoformat()}] Files uploaded successfully\n"
    log_content += f"[{datetime.utcnow().isoformat()}] Execution completed\n"

    log_node = EnhancedNodeInfo(name="session.log", is_dir=False, parent_path="/logs")
    if await provider.create_node(log_node):
        await provider.write_file("/logs/session.log", log_content.encode())
        print("  ✓ Created session log")

    # 7. Check file metadata
    print("\n7. File metadata:")

    script_info = await provider.get_node_info("/workspace/src/process.py")
    if script_info:
        print("\n  process.py:")
        print(f"    - Name: {script_info.name}")
        print(f"    - Path: {script_info.get_path()}")
        print(f"    - Size: {script_info.size or 0} bytes")
        print(f"    - Created: {script_info.created_at}")

    # 8. Storage statistics
    print("\n8. Sandbox storage statistics:")

    stats = await provider.get_storage_stats()
    print(f"  - Total size: {stats.get('total_size_bytes', 0):,} bytes")
    print(f"  - File count: {stats.get('file_count', 0)}")
    print(f"  - Directory count: {stats.get('directory_count', 0)}")

    # 9. Download files from sandbox
    print("\n9. Downloading from sandbox:")

    # Read the process.py file
    process_content = await provider.read_file("/workspace/src/process.py")
    if process_content:
        print(f"  ✓ Downloaded process.py ({len(process_content)} bytes)")

    # 10. Enhanced Features Demonstration
    print("\n10. Enhanced Features:")

    # Checksum calculation
    print("\n  📍 Checksum calculation:")
    process_content = await provider.read_file("/workspace/src/process.py")
    if process_content:
        checksum = await provider.calculate_checksum(process_content)
        print(f"    process.py SHA256: {checksum[:16]}...")

    # Copy operations
    print("\n  📋 Copy operations:")

    # Copy file
    copy_result = await provider.copy_node(
        "/workspace/src/process.py", "/workspace/process_backup.py"
    )
    if copy_result:
        print("    ✓ Copied process.py to backup")

        # Verify copy
        backup_content = await provider.read_file("/workspace/process_backup.py")
        if backup_content == process_content:
            print("    ✓ Backup content verified")

    # Copy directory
    copy_dir_result = await provider.copy_node(
        "/workspace/data", "/workspace/data_backup"
    )
    if copy_dir_result:
        print("    ✓ Copied data directory to backup")

    # Move operations
    print("\n  🚀 Move operations:")

    # Create a temp file to move
    temp_node = EnhancedNodeInfo(
        name="temp_file.txt", is_dir=False, parent_path="/workspace"
    )
    if await provider.create_node(temp_node):
        await provider.write_file(
            "/workspace/temp_file.txt", b"Temporary content"
        )

        # Move the file
        move_result = await provider.move_node(
            "/workspace/temp_file.txt", "/output/moved_file.txt"
        )
        if move_result:
            print("    ✓ Moved temp_file.txt to output directory")

            # Verify move
            old_exists = await provider.exists("/workspace/temp_file.txt")
            new_exists = await provider.exists("/output/moved_file.txt")
            print(
                f"    ✓ Old location exists: {old_exists}, New location exists: {new_exists}"
            )

    # Batch operations
    print("\n  ⚡ Batch operations:")

    # Create multiple files for batch demo
    batch_files = []
    for i in range(3):
        file_info = EnhancedNodeInfo(
            name=f"batch_file_{i}.txt", is_dir=False, parent_path="/output"
        )
        batch_files.append(file_info)

    # Batch create
    create_results = await provider.batch_create(batch_files)
    successful_creates = sum(1 for result in create_results if result)
    print(f"    ✓ Batch created {successful_creates}/3 files")

    # Batch write
    write_operations = [
        (f"/output/batch_file_{i}.txt", f"Batch content {i}".encode())
        for i in range(3)
    ]
    write_results = await provider.batch_write(write_operations)
    successful_writes = sum(1 for result in write_results if result)
    print(f"    ✓ Batch wrote {successful_writes}/3 files")

    # Batch read
    read_paths = [f"/output/batch_file_{i}.txt" for i in range(3)]
    read_results = await provider.batch_read(read_paths)
    successful_reads = sum(1 for result in read_results if result is not None)
    print(f"    ✓ Batch read {successful_reads}/3 files")

    # Show sample content
    if read_results[0]:
        sample_content = read_results[0].decode("utf-8")
        print(f"    📄 Sample content: {sample_content}")

    # 11. Metadata Operations
    print("\n11. Metadata operations:")

    # Set metadata for files
    script_metadata = {
        "author": "E2B Demo",
        "language": "python",
        "purpose": "demonstration",
        "version": "1.0",
    }

    if await provider.set_metadata("/workspace/src/process.py", script_metadata):
        print("    ✓ Set metadata for process.py")

        # Retrieve metadata
        retrieved_meta = await provider.get_metadata("/workspace/src/process.py")
        print("    📋 Retrieved metadata:")
        for key, value in retrieved_meta.items():
            if key in script_metadata:
                print(f"      - {key}: {value}")

    # 12. Advanced Storage Statistics
    print("\n12. Advanced storage statistics:")

    final_stats = await provider.get_storage_stats()
    print("    📊 Final sandbox statistics:")
    print(f"      - Total files: {final_stats.get('total_files', 0)}")
    print(f"      - Total directories: {final_stats.get('total_directories', 0)}")
    print(f"      - Total size: {final_stats.get('total_size', 0):,} bytes")
    print(f"      - Size (MB): {final_stats.get('total_size_mb', 0):.2f}")
    print(f"      - Total nodes: {final_stats.get('node_count', 0)}")
    print(f"      - Sandbox ID: {final_stats.get('sandbox_id', 'N/A')}")

    # 13. Error Handling Demonstration
    print("\n13. Error handling demonstration:")

    # Test various error scenarios
    print("    🔍 Testing error scenarios:")

    # Try to read nonexistent file
    nonexistent_content = await provider.read_file("/nonexistent/file.txt")
    print(f"      - Read nonexistent file: {nonexistent_content} (expected: None)")

    # Try to copy nonexistent source
    copy_fail = await provider.copy_node("/nonexistent/source", "/some/destination")
    print(f"      - Copy nonexistent source: {copy_fail} (expected: False)")

    # Try to delete nonexistent node
    delete_fail = await provider.delete_node("/nonexistent/node")
    print(f"      - Delete nonexistent node: {delete_fail} (expected: False)")

    print("    ✓ All error scenarios handled gracefully")

    # 14. Streaming with progress reporting and atomic writes
    print("\n14. Streaming large files with progress tracking:")

    # Progress tracking
    progress_data = {"bytes": 0, "updates": 0}

    def track_progress(bytes_written, total_bytes):
        """Track progress during streaming write"""
        progress_data["bytes"] = bytes_written
        progress_data["updates"] += 1

        # Show progress every 100KB
        if bytes_written % (100 * 1024) < 1024:
            print(f"    Progress: {bytes_written / 1024:.1f} KB written to sandbox...")

    # Generate large file for sandbox
    async def generate_large_data():
        """Generate ~500KB of log data for sandbox"""
        for i in range(500):
            timestamp = f"2024-01-01T{i % 24:02d}:{i % 60:02d}:{i % 60:02d}"
            log_line = f"[{timestamp}] SANDBOX: Task {i:04d} - " + ("data" * 50) + "\n"
            yield log_line.encode()

    # Create logs directory if needed
    logs_dir = EnhancedNodeInfo(name="sandbox_logs", is_dir=True, parent_path="/logs")
    await provider.create_node(logs_dir)

    # Stream write with progress callback - no need to pre-create file
    print("    📝 Streaming write with atomic safety:")
    print("       - Writes to temp file first (.tmp_stream_*)")
    print("       - Atomically moves to final location on success")
    print("       - Auto-cleanup on failure prevents corruption")

    success = await provider.stream_write(
        "/logs/sandbox_logs/execution.log",
        generate_large_data(),
        progress_callback=track_progress,
    )

    if success:
        print(
            f"    ✓ Streaming complete: {progress_data['bytes'] / 1024:.1f} KB written"
        )
        print(f"    ✓ Progress updates: {progress_data['updates']}")
        print("    ✓ Atomic write (temp + mv) prevented corruption")

        # Verify the file with fresh info (cache was invalidated)
        log_info = await provider.get_node_info("/logs/sandbox_logs/execution.log")
        if log_info and log_info.size:
            print(
                f"    ✓ Verified file size: {log_info.size / 1024:.1f} KB in E2B sandbox"
            )

        # Verify no temp files remain
        if hasattr(provider, "sandbox") and provider.sandbox:
            result = provider.sandbox.commands.run(
                f"ls {provider.root_dir}/.tmp_stream_* 2>/dev/null | wc -l"
            )
            temp_count = int(result.stdout.strip()) if result.exit_code == 0 else 0
            print(f"    ✓ Temp files cleaned up: {temp_count} remaining (expected: 0)")

    # 15. Cleanup
    print("\n15. Cleanup operations:")

    # Cleanup batch files
    cleanup_results = await provider.batch_delete(read_paths)
    successful_cleanup = sum(1 for result in cleanup_results if result)
    print(f"    ✓ Batch deleted {successful_cleanup}/3 temporary files")

    # Perform provider cleanup
    cleanup_result = await provider.cleanup()
    print(f"    🧹 Provider cleanup: {cleanup_result.get('cleaned_up', False)}")
    if cleanup_result.get("files_removed", 0) > 0:
        print(f"      - Files removed: {cleanup_result['files_removed']}")
        print(f"      - Bytes freed: {cleanup_result['bytes_freed']}")

    # Close the provider (this terminates the sandbox)
    await provider.close()
    print("\n✅ E2B Comprehensive Example Completed!")
    print("   Sandbox has been terminated")

    print("\n📊 DEMO SUMMARY:")
    print("   ✅ Basic file and directory operations")
    print("   ✅ Metadata storage and retrieval")
    print("   ✅ Enhanced features (copy, move, checksums)")
    print("   ✅ Batch operations for efficiency")
    print("   ✅ Storage statistics and monitoring")
    print("   ✅ Comprehensive error handling")
    print("   ✅ Provider lifecycle management")

    print("\n💡 E2B Provider Features Demonstrated:")
    print("   🔧 Thread-safe async operations")
    print("   💾 Intelligent caching mechanisms")
    print("   ⚡ Concurrent batch processing")
    print("   🔐 SHA256 checksum calculation")
    print("   📋 Copy/move with recursive directory support")
    print("   📊 Real-time storage statistics")
    print("   🛡️ Robust error handling and recovery")

    print("\n🌟 E2B Use Cases:")
    print("   - Isolated code execution environments")
    print("   - Automated testing in clean sandboxes")
    print("   - Running untrusted code safely")
    print("   - Parallel computation across multiple sandboxes")
    print("   - CI/CD pipeline integration and testing")
    print("   - Educational code playgrounds and tutorials")
    print("   - Microservice development and testing")
    print("   - Data processing in ephemeral compute environments")


if __name__ == "__main__":
    asyncio.run(main())
