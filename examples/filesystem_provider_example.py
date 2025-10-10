#!/usr/bin/env python3
"""
Comprehensive example demonstrating the AsyncFilesystemStorageProvider

This example showcases all features of the filesystem provider including:
- Basic file and directory operations
- Metadata storage and retrieval
- Batch operations for efficiency
- Copy and move operations
- Checksum calculation
- Storage statistics
- Error handling
"""

import asyncio
import os
import tempfile
from pathlib import Path

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.providers.filesystem import AsyncFilesystemStorageProvider


async def demonstrate_basic_operations(provider):
    """Demonstrate basic file and directory operations"""
    print("\n🔨 Basic Operations")
    print("=" * 50)
    
    # Create directories
    print("📁 Creating directory structure...")
    documents_info = EnhancedNodeInfo(
        name="documents",
        is_dir=True,
        parent_path="/"
    )
    
    projects_info = EnhancedNodeInfo(
        name="projects",
        is_dir=True,
        parent_path="/documents"
    )
    
    await provider.create_node(documents_info)
    await provider.create_node(projects_info)
    print("✓ Created /documents and /documents/projects")
    
    # Create and write files
    print("\n📄 Creating and writing files...")
    readme_info = EnhancedNodeInfo(
        name="README.md",
        is_dir=False,
        parent_path="/documents"
    )
    
    config_info = EnhancedNodeInfo(
        name="config.json",
        is_dir=False,
        parent_path="/documents/projects"
    )
    
    await provider.create_node(readme_info)
    await provider.create_node(config_info)
    
    # Write content to files
    readme_content = b"""# Virtual Filesystem Demo
    
This is a demonstration of the AsyncFilesystemStorageProvider.
It provides a virtual filesystem interface over local storage.

## Features
- Async/await support
- Metadata storage
- Batch operations
- Copy/move operations
- And much more!
"""
    
    config_content = b"""{
    "name": "filesystem-demo",
    "version": "1.0.0",
    "provider": "filesystem",
    "settings": {
        "use_metadata": true,
        "create_root": true
    }
}"""
    
    await provider.write_file("/documents/README.md", readme_content)
    await provider.write_file("/documents/projects/config.json", config_content)
    print("✓ Written content to README.md and config.json")
    
    # List directory contents
    print("\n📋 Directory listings:")
    root_contents = await provider.list_directory("/")
    print(f"Root (/): {root_contents}")
    
    docs_contents = await provider.list_directory("/documents")
    print(f"Documents: {docs_contents}")
    
    projects_contents = await provider.list_directory("/documents/projects")
    print(f"Projects: {projects_contents}")
    
    # Read and display file content
    print("\n📖 Reading file content:")
    readme_data = await provider.read_file("/documents/README.md")
    print(f"README.md (first 100 chars): {readme_data[:100].decode('utf-8')}...")
    
    return True


async def demonstrate_metadata_operations(provider):
    """Demonstrate metadata storage and retrieval"""
    print("\n🏷️  Metadata Operations")
    print("=" * 50)
    
    # Set metadata for files
    readme_metadata = {
        "author": "Demo User",
        "created": "2024-01-01",
        "tags": ["documentation", "readme"],
        "language": "markdown",
        "importance": "high"
    }
    
    config_metadata = {
        "author": "System",
        "created": "2024-01-01",
        "tags": ["configuration", "json"],
        "schema_version": "1.0",
        "environment": "development"
    }
    
    print("💾 Setting metadata...")
    await provider.set_metadata("/documents/README.md", readme_metadata)
    await provider.set_metadata("/documents/projects/config.json", config_metadata)
    print("✓ Metadata set for both files")
    
    # Retrieve and display metadata
    print("\n🔍 Retrieving metadata:")
    readme_meta = await provider.get_metadata("/documents/README.md")
    print(f"README.md metadata: {readme_meta}")
    
    config_meta = await provider.get_metadata("/documents/projects/config.json")
    print(f"config.json metadata: {config_meta}")
    
    return True


async def demonstrate_node_information(provider):
    """Demonstrate node information retrieval"""
    print("\n📊 Node Information")
    print("=" * 50)
    
    # Get detailed node information
    paths_to_check = [
        "/documents",
        "/documents/README.md",
        "/documents/projects/config.json"
    ]
    
    for path in paths_to_check:
        node_info = await provider.get_node_info(path)
        if node_info:
            print(f"\n📍 {path}:")
            print(f"   Type: {'Directory' if node_info.is_dir else 'File'}")
            print(f"   Name: {node_info.name}")
            print(f"   Size: {getattr(node_info, 'size', 'N/A')} bytes")
            print(f"   Created: {node_info.created_at}")
            print(f"   Modified: {node_info.modified_at}")
            if node_info.custom_meta:
                print(f"   Custom metadata: {len(node_info.custom_meta)} entries")
        else:
            print(f"❌ {path}: Not found")
    
    return True


async def demonstrate_checksum_operations(provider):
    """Demonstrate checksum calculation"""
    print("\n🔐 Checksum Operations")
    print("=" * 50)
    
    # Calculate checksums for file contents
    files_to_check = [
        "/documents/README.md",
        "/documents/projects/config.json"
    ]
    
    for file_path in files_to_check:
        print(f"\n📄 {file_path}:")
        
        # Read file content
        content = await provider.read_file(file_path)
        if content:
            # Calculate checksum
            checksum = await provider.calculate_checksum(content)
            print(f"   Size: {len(content)} bytes")
            print(f"   SHA256: {checksum}")
        else:
            print("   ❌ Could not read file")
    
    return True


async def demonstrate_copy_move_operations(provider):
    """Demonstrate copy and move operations"""
    print("\n📋 Copy & Move Operations")
    print("=" * 50)
    
    # Copy a file
    print("📄 Copying README.md to backup location...")
    copy_result = await provider.copy_node(
        "/documents/README.md",
        "/documents/README_backup.md"
    )
    
    if copy_result:
        print("✓ Successfully copied README.md to README_backup.md")
        
        # Verify copy
        backup_exists = await provider.exists("/documents/README_backup.md")
        print(f"   Backup exists: {backup_exists}")
        
        # Compare content
        original_content = await provider.read_file("/documents/README.md")
        backup_content = await provider.read_file("/documents/README_backup.md")
        content_match = original_content == backup_content
        print(f"   Content matches: {content_match}")
    else:
        print("❌ Failed to copy file")
    
    # Create a directory to move
    print("\n📁 Creating temporary directory for move operation...")
    temp_info = EnhancedNodeInfo(
        name="temp_folder",
        is_dir=True,
        parent_path="/documents"
    )
    await provider.create_node(temp_info)
    
    # Move the directory
    print("🚀 Moving temp_folder to archive_folder...")
    move_result = await provider.move_node(
        "/documents/temp_folder",
        "/documents/archive_folder"
    )
    
    if move_result:
        print("✓ Successfully moved temp_folder to archive_folder")
        
        # Verify move
        old_exists = await provider.exists("/documents/temp_folder")
        new_exists = await provider.exists("/documents/archive_folder")
        print(f"   Old location exists: {old_exists}")
        print(f"   New location exists: {new_exists}")
    else:
        print("❌ Failed to move directory")
    
    return True


async def demonstrate_batch_operations(provider):
    """Demonstrate batch operations for efficiency"""
    print("\n⚡ Batch Operations")
    print("=" * 50)
    
    # Create multiple files for batch operations
    print("📄 Creating multiple files for batch demo...")
    batch_files = []
    
    for i in range(5):
        file_info = EnhancedNodeInfo(
            name=f"batch_file_{i}.txt",
            is_dir=False,
            parent_path="/documents"
        )
        batch_files.append(file_info)
    
    # Batch create
    print("🚀 Batch creating files...")
    create_results = await provider.batch_create(batch_files)
    successful_creates = sum(1 for result in create_results if result)
    print(f"✓ Successfully created {successful_creates}/{len(batch_files)} files")
    
    # Batch write content
    print("\n✍️  Batch writing content...")
    write_operations = []
    for i in range(5):
        path = f"/documents/batch_file_{i}.txt"
        content = f"This is batch file number {i}\nCreated for demonstration purposes.\nContent length: {len(f'batch file {i}')} chars".encode('utf-8')
        write_operations.append((path, content))
    
    write_results = await provider.batch_write(write_operations)
    successful_writes = sum(1 for result in write_results if result)
    print(f"✓ Successfully wrote {successful_writes}/{len(write_operations)} files")
    
    # Batch read
    print("\n📖 Batch reading files...")
    read_paths = [f"/documents/batch_file_{i}.txt" for i in range(5)]
    read_results = await provider.batch_read(read_paths)
    successful_reads = sum(1 for result in read_results if result is not None)
    print(f"✓ Successfully read {successful_reads}/{len(read_paths)} files")
    
    # Display sample content
    if read_results[0]:
        sample_content = read_results[0].decode('utf-8')
        print(f"   Sample content: {sample_content[:50]}...")
    
    # Batch delete (cleanup)
    print("\n🗑️  Batch deleting demo files...")
    delete_results = await provider.batch_delete(read_paths)
    successful_deletes = sum(1 for result in delete_results if result)
    print(f"✓ Successfully deleted {successful_deletes}/{len(read_paths)} files")
    
    return True


async def demonstrate_storage_statistics(provider):
    """Demonstrate storage statistics"""
    print("\n📈 Storage Statistics")
    print("=" * 50)
    
    # Get comprehensive storage stats
    stats = await provider.get_storage_stats()
    
    print("📊 Current storage statistics:")
    print(f"   Total files: {stats.get('total_files', 0)}")
    print(f"   Total directories: {stats.get('total_directories', 0)}")
    print(f"   Total size: {stats.get('total_size', 0)} bytes")
    print(f"   Root path: {stats.get('root_path', 'N/A')}")
    
    # Calculate some additional metrics
    if stats.get('total_files', 0) > 0:
        avg_file_size = stats.get('total_size', 0) / stats.get('total_files', 1)
        print(f"   Average file size: {avg_file_size:.1f} bytes")
    
    return True


async def demonstrate_error_handling(provider):
    """Demonstrate error handling scenarios"""
    print("\n⚠️  Error Handling")
    print("=" * 50)
    
    print("🔍 Testing various error scenarios...")
    
    # Test reading nonexistent file
    print("\n1. Reading nonexistent file:")
    nonexistent_content = await provider.read_file("/nonexistent/file.txt")
    print(f"   Result: {nonexistent_content} (expected: None)")
    
    # Test writing to nonexistent path
    print("\n2. Writing to nonexistent path:")
    write_result = await provider.write_file("/nonexistent/path/file.txt", b"content")
    print(f"   Result: {write_result} (expected: False)")
    
    # Test getting info for nonexistent node
    print("\n3. Getting info for nonexistent node:")
    node_info = await provider.get_node_info("/nonexistent/node")
    print(f"   Result: {node_info} (expected: None)")
    
    # Test copying nonexistent source
    print("\n4. Copying nonexistent source:")
    copy_result = await provider.copy_node("/nonexistent/source", "/some/destination")
    print(f"   Result: {copy_result} (expected: False)")
    
    # Test existence checks
    print("\n5. Existence checks:")
    exists_real = await provider.exists("/documents/README.md")
    exists_fake = await provider.exists("/fake/path")
    print(f"   Real file exists: {exists_real} (expected: True)")
    print(f"   Fake file exists: {exists_fake} (expected: False)")
    
    print("\n✓ All error scenarios handled gracefully")
    return True


async def perform_cleanup_demo(provider):
    """Demonstrate cleanup operations"""
    print("\n🧹 Cleanup Operations")
    print("=" * 50)
    
    # Perform provider cleanup
    print("🔧 Running provider cleanup...")
    cleanup_result = await provider.cleanup()
    print(f"✓ Cleanup completed: {cleanup_result}")
    
    return True


async def run_comprehensive_demo():
    """Run the complete filesystem provider demonstration"""
    print("🌟 AsyncFilesystemStorageProvider Comprehensive Demo")
    print("=" * 60)
    
    # Create a temporary directory for the demo
    with tempfile.TemporaryDirectory(prefix="filesystem_demo_") as temp_dir:
        print(f"📁 Demo root directory: {temp_dir}")
        
        # Initialize the provider
        print("\n🚀 Initializing filesystem provider...")
        provider = AsyncFilesystemStorageProvider(
            root_path=temp_dir,
            use_metadata=True,
            create_root=True
        )
        
        try:
            # Initialize the provider
            init_result = await provider.initialize()
            if not init_result:
                print("❌ Failed to initialize provider")
                return False
            
            print("✓ Provider initialized successfully")
            
            # Run all demonstrations
            demos = [
                ("Basic Operations", demonstrate_basic_operations),
                ("Metadata Operations", demonstrate_metadata_operations),
                ("Node Information", demonstrate_node_information),
                ("Checksum Operations", demonstrate_checksum_operations),
                ("Copy & Move Operations", demonstrate_copy_move_operations),
                ("Batch Operations", demonstrate_batch_operations),
                ("Storage Statistics", demonstrate_storage_statistics),
                ("Error Handling", demonstrate_error_handling),
                ("Cleanup Operations", perform_cleanup_demo),
            ]
            
            success_count = 0
            total_demos = len(demos)
            
            for demo_name, demo_func in demos:
                try:
                    print(f"\n{'='*60}")
                    print(f"🔄 Running: {demo_name}")
                    result = await demo_func(provider)
                    if result:
                        success_count += 1
                        print(f"✅ {demo_name} completed successfully")
                    else:
                        print(f"⚠️  {demo_name} completed with issues")
                except Exception as e:
                    print(f"❌ {demo_name} failed: {e}")
            
            # Final summary
            print(f"\n{'='*60}")
            print("📋 DEMO SUMMARY")
            print(f"✅ Successful demonstrations: {success_count}/{total_demos}")
            print(f"📁 Demo files created in: {temp_dir}")
            
            if success_count == total_demos:
                print("\n🎉 All demonstrations completed successfully!")
                print("   The AsyncFilesystemStorageProvider is working correctly.")
            else:
                print(f"\n⚠️  {total_demos - success_count} demonstrations had issues.")
                print("   Please review the output above for details.")
            
        except Exception as e:
            print(f"\n❌ Critical error during demo: {e}")
            return False
        
        finally:
            # Clean up
            print(f"\n🧹 Closing provider...")
            await provider.close()
            print("✓ Provider closed")
    
    print(f"\n✓ Demo completed - temporary directory automatically cleaned up")
    return True


if __name__ == "__main__":
    print("Starting AsyncFilesystemStorageProvider demonstration...")
    
    try:
        # Run the comprehensive demo
        success = asyncio.run(run_comprehensive_demo())
        
        if success:
            print("\n🎊 Demonstration completed successfully!")
            exit(0)
        else:
            print("\n💥 Demonstration failed!")
            exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        exit(1)