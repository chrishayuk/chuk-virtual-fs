"""
debug/s3_provider_example.py - Example usage of the AWS S3 storage provider with Tigris Storage
Includes comprehensive cleanup after each example and testing for root directory files
"""
import os
import time
import logging
import json
import sys
from dotenv import load_dotenv
from chuk_virtual_fs import VirtualFileSystem
from chuk_virtual_fs.template_loader import TemplateLoader

# Enable detailed boto3 logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('boto3').setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.INFO)

# Create custom logger for testing
test_logger = logging.getLogger('s3-test')
test_logger.setLevel(logging.INFO)

# Load environment variables (for AWS credentials)
load_dotenv()

def create_bucket_manually():
    """
    Create S3 bucket manually before running the rest of the example
    This is needed because Tigris Storage might have different requirements for bucket creation
    """
    import boto3
    
    print("===== Creating Bucket Manually =====")
    bucket_name = os.environ.get("S3_BUCKET_NAME", "my-virtual-fs-test")
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    
    try:
        # Create a standalone S3 client
        s3 = boto3.client('s3', endpoint_url=endpoint_url)
        
        # Check if the bucket already exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' already exists")
            return True
        except Exception as e:
            if "404" in str(e):
                # Bucket doesn't exist, try to create it
                print(f"Bucket '{bucket_name}' doesn't exist, creating it...")
                try:
                    # For Tigris Storage, you might need different parameters than standard AWS S3
                    # Check Tigris documentation for the correct parameters
                    
                    # Try with minimal parameters first
                    create_response = s3.create_bucket(Bucket=bucket_name)
                    print(f"Bucket created successfully: {create_response}")
                    return True
                except Exception as create_e:
                    print(f"Failed to create bucket: {create_e}")
                    
                    # Try with LocationConstraint if the first attempt failed
                    try:
                        region = os.environ.get("AWS_REGION", "us-east-1")
                        create_response = s3.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                        print(f"Bucket created with region constraint: {create_response}")
                        return True
                    except Exception as region_e:
                        print(f"Failed to create bucket with region constraint: {region_e}")
                        return False
            else:
                print(f"Error checking bucket: {e}")
                return False
    except Exception as e:
        print(f"Error accessing S3: {e}")
        return False

def cleanup_prefix(bucket_name, prefix, endpoint_url=None):
    """
    Clean up all objects with a specific prefix in the bucket
    
    Args:
        bucket_name: Name of the S3 bucket
        prefix: Prefix to clean up
        endpoint_url: Optional endpoint URL for S3-compatible storage
    """
    import boto3
    
    print(f"\nCleaning up prefix '{prefix}' in bucket '{bucket_name}'...")
    
    try:
        # Create S3 client
        client_kwargs = {}
        if endpoint_url:
            client_kwargs['endpoint_url'] = endpoint_url
            
        s3 = boto3.client('s3', **client_kwargs)
        
        # List all objects with the prefix
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
        # Initialize counters
        total_objects = 0
        total_deleted = 0
        
        # Process each page of results
        for page in pages:
            if 'Contents' in page:
                # Collect objects to delete
                delete_keys = []
                for obj in page['Contents']:
                    delete_keys.append({'Key': obj['Key']})
                    total_objects += 1
                
                # Delete objects in batches
                if delete_keys:
                    response = s3.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': delete_keys}
                    )
                    
                    # Count deleted objects
                    if 'Deleted' in response:
                        total_deleted += len(response['Deleted'])
                    
                    # Report errors
                    if 'Errors' in response and response['Errors']:
                        for error in response['Errors']:
                            print(f"  Error deleting {error['Key']}: {error['Code']} - {error['Message']}")
        
        print(f"Cleanup complete: {total_deleted}/{total_objects} objects deleted from prefix '{prefix}'")
        return True
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False

def basic_s3_example():
    """Basic usage example with S3 storage provider"""
    print("===== AWS S3 Storage Provider Example =====")
    
    # Get environment variables
    bucket_name = os.environ.get("S3_BUCKET_NAME", "my-virtual-fs-test")
    prefix = "demo"
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    
    # First clean up any existing data from previous runs
    cleanup_prefix(bucket_name, prefix, endpoint_url)
    
    # Create filesystem with S3 provider
    try:
        fs = VirtualFileSystem("s3", 
                               bucket_name=bucket_name,
                               prefix=prefix,
                               region_name=os.environ.get("AWS_REGION", "us-east-1"),
                               endpoint_url=endpoint_url)
        
        print(f"Provider: {fs.get_provider_name()}")
        print(f"Bucket: {fs.provider.bucket_name}")
        print(f"Prefix: {fs.provider.prefix}")
        
        # Create directories
        print("\nCreating directories...")
        fs.mkdir("/projects")
        fs.mkdir("/projects/python")
        fs.mkdir("/data")
        
        # Create and write files
        print("\nCreating files...")
        fs.write_file("/projects/python/hello.py", 'print("Hello from S3 storage!")')
        fs.write_file("/data/sample.txt", "This is sample data stored in the S3 bucket.")
        
        # List directory contents
        print("\nDirectory contents:")
        print(f"/ contents: {fs.ls('/')}")
        print(f"/projects contents: {fs.ls('/projects')}")
        print(f"/projects/python contents: {fs.ls('/projects/python')}")
        
        # Read file content
        print("\nReading file content:")
        hello_py = fs.read_file("/projects/python/hello.py")
        print(f"hello.py content: {hello_py}")
        
        # Get storage stats
        print("\nStorage statistics:")
        stats = fs.get_storage_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Final cleanup of this example's data
        print("\nExample completed. Cleaning up...")
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        
        return fs
    except Exception as e:
        print(f"Error in basic S3 example: {e}")
        # Attempt cleanup even if example failed
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        return None

def test_root_directory_files():
    """Test specifically for files in the root directory"""
    print("\n===== Root Directory Files Test =====")
    
    # Get environment variables
    bucket_name = os.environ.get("S3_BUCKET_NAME", "my-virtual-fs-test")
    prefix = "root_test"
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    
    # First clean up any existing data from previous runs
    cleanup_prefix(bucket_name, prefix, endpoint_url)
    
    try:
        # Create filesystem with S3 provider
        fs = VirtualFileSystem("s3", 
                              bucket_name=bucket_name,
                              prefix=prefix,
                              endpoint_url=endpoint_url)
        
        print(f"Provider: {fs.get_provider_name()}")
        print(f"Bucket: {fs.provider.bucket_name}")
        print(f"Prefix: {fs.provider.prefix}")
        
        # Create files directly in the root directory
        print("\nCreating files in root directory...")
        fs.write_file("/root_file1.txt", "This is a file in root directory")
        fs.write_file("/root_file2.txt", "This is another root file")
        
        # Also create a directory and file in it for comparison
        fs.mkdir("/test_dir")
        fs.write_file("/test_dir/nested_file.txt", "This is a nested file")
        
        # List root directory contents
        print("\nRoot directory contents:")
        root_contents = fs.ls("/")
        print(f"/ contents: {root_contents}")
        
        # Verify root files are present
        for file in ["root_file1.txt", "root_file2.txt"]:
            if file in root_contents:
                print(f"✓ File '{file}' correctly appears in root directory listing")
            else:
                print(f"✗ ERROR: File '{file}' is MISSING from root directory listing!")
        
        # Test reading root files
        print("\nReading files from root directory:")
        try:
            content = fs.read_file("/root_file1.txt")
            print(f"Content of root_file1.txt: '{content}'")
            if content == "This is a file in root directory":
                print("✓ Successfully read root file with correct content")
            else:
                print("✗ Root file content doesn't match what was written")
        except Exception as e:
            print(f"✗ Error reading root file: {e}")
        
        # Test nested file too
        print("\nVerifying nested file works too:")
        try:
            nested_content = fs.read_file("/test_dir/nested_file.txt")
            print(f"Content of nested file: '{nested_content}'")
            if nested_content == "This is a nested file":
                print("✓ Successfully read nested file")
            else:
                print("✗ Nested file content doesn't match")
        except Exception as e:
            print(f"✗ Error reading nested file: {e}")
        
        # Final cleanup
        print("\nTest completed. Cleaning up...")
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        
        return True
    except Exception as e:
        print(f"Error in root directory files test: {e}")
        # Attempt cleanup even if example failed
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        return False

def working_with_files():
    """Example of working with files in S3 storage"""
    print("\n===== Working with Files in S3 Storage =====")
    
    # Get environment variables
    bucket_name = os.environ.get("S3_BUCKET_NAME", "my-virtual-fs-test")
    prefix = "files_example"
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    
    # First clean up any existing data from previous runs
    cleanup_prefix(bucket_name, prefix, endpoint_url)
    
    try:
        # Create filesystem with S3 provider
        fs = VirtualFileSystem("s3", 
                               bucket_name=bucket_name,
                               prefix=prefix,
                               endpoint_url=endpoint_url)
        
        # Create a template loader
        template_loader = TemplateLoader(fs)
        
        # Define a simple project template
        web_project_template = {
            "directories": [
                "/web_project",
                "/web_project/css",
                "/web_project/js",
                "/web_project/images"
            ],
            "files": [
                {
                    "path": "/web_project/index.html",
                    "content": """<!DOCTYPE html>
<html>
<head>
    <title>${project_name}</title>
    <link rel="stylesheet" href="css/style.css">
    <script src="js/main.js"></script>
</head>
<body>
    <h1>${project_name}</h1>
    <p>${project_description}</p>
</body>
</html>"""
                },
                {
                    "path": "/web_project/css/style.css",
                    "content": """body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}

h1 {
    color: #333;
}"""
                },
                {
                    "path": "/web_project/js/main.js",
                    "content": """// ${project_name} main JavaScript file
document.addEventListener('DOMContentLoaded', function() {
    console.log('${project_name} loaded!');
});"""
                }
            ]
        }
        
        # Apply the template with variables
        print("Creating web project from template...")
        template_loader.apply_template(web_project_template, variables={
            "project_name": "S3 Web Demo",
            "project_description": "A web project stored in S3 bucket"
        })
        
        # List created files
        print("\nCreated files:")
        created_files = fs.find("/web_project", recursive=True)
        for file_path in sorted(created_files):
            node_info = fs.get_node_info(file_path)
            file_type = "Directory" if node_info and node_info.is_dir else "File"
            print(f"  {file_type}: {file_path}")
        
        # Upload a local file to S3 if it exists
        local_file = "local_sample/example.txt"
        if os.path.exists(local_file):
            print(f"\nUploading local file {local_file} to S3...")
            with open(local_file, "r") as file:
                fs.write_file("/web_project/uploads/example.txt", file.read())
            print(f"File uploaded to: /web_project/uploads/example.txt")
        
        # Create a data file and run an analysis (simulated - since S3 is storage only)
        print("\nCreating a data file...")
        fs.write_file("/web_project/data.csv", """date,value
2023-01-01,10
2023-01-02,15
2023-01-03,8
2023-01-04,20
2023-01-05,12""")
        
        # Read back the CSV data to confirm it's stored properly
        print("\nReading back CSV data:")
        csv_content = fs.read_file("/web_project/data.csv")
        print(csv_content)
        
        # Demonstrate file operations
        print("\nPerforming file operations...")
        
        # Copy a file
        fs.cp("/web_project/data.csv", "/web_project/data_backup.csv")
        
        # Move a file
        fs.mv("/web_project/data_backup.csv", "/data/backup.csv")
        
        # Verify operations
        print("\nVerifying file operations:")
        print(f"Original file exists: {fs.get_node_info('/web_project/data.csv') is not None}")
        print(f"Copy exists in new location: {fs.get_node_info('/data/backup.csv') is not None}")
        
        # Final cleanup
        print("\nExample completed. Cleaning up...")
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        
        return True
    except Exception as e:
        print(f"Error in working with files example: {e}")
        # Attempt cleanup even if example failed
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        return False

def s3_snapshots_demo():
    """Example showing snapshot functionality with S3 provider"""
    print("\n===== S3 Snapshots Example =====")
    
    # Get environment variables
    bucket_name = os.environ.get("S3_BUCKET_NAME", "my-virtual-fs-test")
    prefix = "snapshots_test"
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    
    # First clean up any existing data from previous runs
    cleanup_prefix(bucket_name, prefix, endpoint_url)
    
    try:
        # Create filesystem with S3 provider
        fs = VirtualFileSystem("s3", 
                               bucket_name=bucket_name,
                               prefix=prefix,
                               endpoint_url=endpoint_url)
        
        # Create snapshot manager
        from chuk_virtual_fs.snapshot_manager import SnapshotManager
        snapshot_mgr = SnapshotManager(fs)
        
        # Set up initial file structure
        print("Setting up initial file structure...")
        fs.mkdir("/config")
        fs.mkdir("/data")
        fs.write_file("/config/settings.json", '{"debug": false, "version": "1.0.0"}')
        fs.write_file("/data/records.txt", "Initial records data")
        
        # Create initial snapshot
        print("\nCreating initial snapshot...")
        initial_snapshot = snapshot_mgr.create_snapshot("initial_state", "Initial file setup")
        print(f"Snapshot created: {initial_snapshot}")
        
        # Modify files
        print("\nModifying files...")
        fs.write_file("/config/settings.json", '{"debug": true, "version": "1.0.1", "mode": "testing"}')
        fs.write_file("/data/records.txt", "Updated records data\nNew line added")
        fs.write_file("/data/logs.txt", "System initialized")
        
        # Create modified snapshot
        print("\nCreating snapshot after modifications...")
        modified_snapshot = snapshot_mgr.create_snapshot("modified_state", "After file modifications")
        print(f"Snapshot created: {modified_snapshot}")
        
        # List snapshots
        print("\nAvailable snapshots:")
        snapshots = snapshot_mgr.list_snapshots()
        for snap in snapshots:
            print(f"  {snap['name']}: {snap['description']} (created: {snap['created']})")
        
        # Restore to initial state
        print("\nRestoring to initial state...")
        snapshot_mgr.restore_snapshot("initial_state")
        
        # Verify restore
        print("\nVerifying restored state:")
        settings = fs.read_file("/config/settings.json")
        records = fs.read_file("/data/records.txt")
        logs_exists = fs.get_node_info("/data/logs.txt") is not None
        
        print(f"Settings file content: {settings}")
        print(f"Records file content: {records}")
        print(f"Logs file exists: {logs_exists} (should be False)")
        
        # Export snapshot for later use
        export_path = "/tmp/s3_snapshot.json"
        snapshot_mgr.export_snapshot("modified_state", export_path)
        print(f"\nSnapshot exported to: {export_path}")
        
        # Final cleanup
        print("\nExample completed. Cleaning up...")
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        
        # Remove exported snapshot file
        if os.path.exists(export_path):
            os.remove(export_path)
            print(f"Removed exported snapshot file: {export_path}")
        
        return True
    except Exception as e:
        print(f"Error in snapshots example: {e}")
        # Attempt cleanup even if example failed
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        return False

def s3_custom_endpoint_example():
    """Example showing S3 with the Tigris Storage endpoints"""
    print("\n===== Tigris Storage Example =====")
    
    # Get environment variables
    bucket_name = os.environ.get("S3_BUCKET_NAME", "my-virtual-fs-test")
    prefix = "tigris_test"
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    
    # First clean up any existing data from previous runs
    cleanup_prefix(bucket_name, prefix, endpoint_url)
    
    try:
        # Create filesystem with S3 provider pointing to Tigris endpoints
        fs = VirtualFileSystem("s3", 
                               bucket_name=bucket_name,
                               prefix=prefix,
                               endpoint_url=endpoint_url,
                               region_name=os.environ.get("AWS_REGION", "us-east-1"))
        
        print(f"Connected to S3-compatible storage at {fs.provider.endpoint_url}")
        
        # Basic operations
        fs.mkdir("/test")
        fs.write_file("/test/hello.txt", "Hello from S3-compatible storage!")
        
        # List files
        files = fs.ls("/test")
        print(f"Files in /test: {files}")
        
        # Read file
        content = fs.read_file("/test/hello.txt")
        print(f"File content: {content}")
        
        # Final cleanup
        print("\nExample completed. Cleaning up...")
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        
        return True
    except Exception as e:
        print(f"Error accessing S3-compatible storage: {e}")
        print("This example requires a running S3-compatible server (e.g., MinIO)")
        # Attempt cleanup even if example failed
        cleanup_prefix(bucket_name, prefix, endpoint_url)
        return False

def main():
    # First, try to create the bucket manually
    bucket_created = create_bucket_manually()
    if not bucket_created:
        print("Warning: Could not create bucket. Examples may fail if bucket doesn't exist.")
    
    # Run the specific test for root directory files first
    print("\n======= TESTING ROOT DIRECTORY FILES FUNCTIONALITY =======")
    root_files_test_result = test_root_directory_files()
    if root_files_test_result:
        print("✓ ROOT DIRECTORY FILES TEST SUCCESSFUL")
    else:
        print("✗ ROOT DIRECTORY FILES TEST FAILED")
    
    # Run the regular examples
    fs = basic_s3_example()
    
    # Only continue with other examples if the first one succeeded
    if fs:
        working_with_files()
        s3_snapshots_demo()
        s3_custom_endpoint_example()
    else:
        print("Skipping remaining examples due to initial setup failure")
    
    print("\nS3 provider examples completed. All examples have cleaned up after themselves.")

if __name__ == "__main__":
    main()