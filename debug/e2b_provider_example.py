"""
debug/e2b_provider_example.py - Example usage of the E2B sandbox provider
"""

import os
import time

from dotenv import load_dotenv

from chuk_virtual_fs import VirtualFileSystem
from chuk_virtual_fs.template_loader import TemplateLoader

# Load environment variables (for E2B API keys if needed)
load_dotenv()


def basic_e2b_example():
    """Basic usage example with E2B sandbox provider"""
    print("===== E2B Sandbox Provider Example =====")

    # Create filesystem with E2B provider
    fs = VirtualFileSystem("e2b", root_dir="/home/user/vfs_test")
    print(f"Provider: {fs.get_provider_name()}")
    print(f"Sandbox ID: {fs.provider.sandbox_id}")

    # Create directories
    print("\nCreating directories...")
    fs.mkdir("/projects")
    fs.mkdir("/projects/python")
    fs.mkdir("/data")

    # Create and write files
    print("\nCreating files...")
    fs.write_file("/projects/python/hello.py", 'print("Hello from E2B sandbox!")')
    fs.write_file("/data/sample.txt", "This is sample data stored in the E2B sandbox.")

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

    # Execute Python code in the sandbox (using E2B provider's sandbox)
    print("\nExecuting Python code in the sandbox:")
    if hasattr(fs.provider, "sandbox") and hasattr(fs.provider.sandbox, "run_code"):
        code = fs.read_file("/projects/python/hello.py")
        execution = fs.provider.sandbox.run_code(code)
        print(f"Execution result: {execution.logs}")

    # Cleanup
    print("\nCleaning up...")
    cleanup_result = fs.provider.cleanup()
    print(f"Cleanup result: {cleanup_result}")


def working_with_files():
    """Example of working with files in the E2B sandbox"""
    print("\n===== Working with Files in E2B Sandbox =====")

    # Create filesystem with E2B provider
    fs = VirtualFileSystem("e2b", root_dir="/home/user/files_example")

    # Create a template loader
    template_loader = TemplateLoader(fs)

    # Define a simple project template
    web_project_template = {
        "directories": [
            "/web_project",
            "/web_project/css",
            "/web_project/js",
            "/web_project/images",
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
</html>""",
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
}""",
            },
            {
                "path": "/web_project/js/main.js",
                "content": """// ${project_name} main JavaScript file
document.addEventListener('DOMContentLoaded', function() {
    console.log('${project_name} loaded!');
});""",
            },
        ],
    }

    # Apply the template with variables
    print("Creating web project from template...")
    template_loader.apply_template(
        web_project_template,
        variables={
            "project_name": "E2B Web Demo",
            "project_description": "A web project running in an E2B sandbox",
        },
    )

    # List created files
    print("\nCreated files:")
    created_files = fs.find("/web_project", recursive=True)
    for file_path in sorted(created_files):
        node_info = fs.get_node_info(file_path)
        file_type = "Directory" if node_info and node_info.is_dir else "File"
        print(f"  {file_type}: {file_path}")

    # Run a command in the sandbox to serve the files
    print("\nRunning command in sandbox to list the web project:")
    if hasattr(fs.provider, "sandbox") and hasattr(fs.provider.sandbox.commands, "run"):
        result = fs.provider.sandbox.commands.run(
            f"find {fs.provider._get_sandbox_path('/web_project')} -type f | sort"
        )
        print(f"Command output:\n{result.stdout}")

    # Upload a local file to the sandbox if it exists
    local_file = "local_sample/example.txt"
    if os.path.exists(local_file):
        print(f"\nUploading local file {local_file} to sandbox...")
        with open(local_file, "rb") as file:
            fs.write_file(
                "/web_project/uploads/example.txt", file.read().decode("utf-8")
            )
        print("File uploaded to: /web_project/uploads/example.txt")

    # Create a data file and run an analysis in the sandbox
    print("\nCreating a data file and analyzing it...")
    fs.write_file(
        "/web_project/data.csv",
        """date,value
2023-01-01,10
2023-01-02,15
2023-01-03,8
2023-01-04,20
2023-01-05,12""",
    )

    if hasattr(fs.provider, "sandbox") and hasattr(fs.provider.sandbox, "run_code"):
        analysis_code = """
import pandas as pd

# Read the CSV file
df = pd.read_csv('/home/user/files_example/web_project/data.csv')

# Perform simple analysis
print("Data summary:")
print(df.describe())

# Calculate average
avg = df['value'].mean()
print(f"Average value: {avg}")
"""
        print("\nRunning data analysis:")
        execution = fs.provider.sandbox.run_code(analysis_code)
        print(f"Analysis result:\n{execution.logs}")


def e2b_sandbox_persistence():
    """Example showing sandbox persistence and reconnection"""
    print("\n===== E2B Sandbox Persistence Example =====")

    # Create first filesystem with E2B provider
    print("Creating initial sandbox...")
    fs1 = VirtualFileSystem("e2b", root_dir="/home/user/persistence_test")
    sandbox_id = fs1.provider.sandbox_id
    print(f"Created sandbox with ID: {sandbox_id}")

    # Create some files
    fs1.write_file("/test.txt", "This is a test file for persistence")
    fs1.mkdir("/persistent_data")
    fs1.write_file(
        "/persistent_data/config.json", '{"setting": "value", "enabled": true}'
    )

    print("\nCreated files in initial sandbox:")
    files = fs1.find("/", recursive=True)
    for file_path in sorted(files):
        print(f"  {file_path}")

    # Store sandbox ID and disconnect
    print("\nDisconnecting from initial sandbox...")
    fs1.provider.close()

    # Short delay to simulate disconnection
    time.sleep(2)

    # Connect to the same sandbox using its ID
    print(f"\nReconnecting to sandbox with ID: {sandbox_id}...")
    fs2 = VirtualFileSystem(
        "e2b", sandbox_id=sandbox_id, root_dir="/home/user/persistence_test"
    )

    # Check if files persist
    print("\nChecking files after reconnection:")
    reconnect_files = fs2.find("/", recursive=True)

    if reconnect_files:
        print("Files persisted successfully:")
        for file_path in sorted(reconnect_files):
            print(f"  {file_path}")

        # Read a file to confirm content persisted
        content = fs2.read_file("/test.txt")
        print(f"\nContent of /test.txt: {content}")
    else:
        print(
            "No files found after reconnection - persistence may not be working as expected"
        )

    # Add a new file to the reconnected sandbox
    print("\nAdding a new file to the reconnected sandbox...")
    fs2.write_file(
        "/persistent_data/new_after_reconnect.txt",
        "This file was added after reconnection",
    )

    print("\nFinal file list:")
    final_files = fs2.find("/", recursive=True)
    for file_path in sorted(final_files):
        print(f"  {file_path}")


def main():
    # Run the examples
    basic_e2b_example()
    working_with_files()
    e2b_sandbox_persistence()

    print("\nE2B provider examples completed.")


if __name__ == "__main__":
    main()
