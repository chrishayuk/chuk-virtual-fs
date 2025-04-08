#!/usr/bin/env python3
"""
standalone_e2b_demo.py - Simple demonstration of E2B functionality

This script tests the E2B sandbox directly without using the virtual filesystem
infrastructure. This helps verify that E2B itself is working correctly.
"""
import os
import sys
import time
import traceback

# Try to import necessary components
try:
    from e2b_code_interpreter import Sandbox
except ImportError:
    print("ERROR: Could not import e2b_code_interpreter package.")
    print("Please install it with: pip install e2b_code_interpreter")
    sys.exit(1)

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded environment variables from .env file")
except ImportError:
    print("dotenv package not installed. Using system environment variables only.")

# Get API key
E2B_API_KEY = os.environ.get('E2B_API_KEY')
if not E2B_API_KEY:
    print("\nERROR: E2B_API_KEY environment variable not set.")
    print("Please add your API key to a .env file or set it in the environment.")
    print("Example .env file content: E2B_API_KEY=your_api_key_here")
    
    # Uncomment and set your key here for direct testing
    # E2B_API_KEY = "your_api_key_here"
    
    if not E2B_API_KEY:
        sys.exit(1)
else:
    print(f"Using E2B API key: {E2B_API_KEY[:4]}...{E2B_API_KEY[-4:]}")

def print_separator(title=None):
    """Print a separator with optional title"""
    width = 80
    if title:
        print("\n" + "=" * 5 + f" {title} " + "=" * (width - len(title) - 7) + "\n")
    else:
        print("\n" + "=" * width + "\n")

def main():
    """Run a simple E2B demonstration"""
    print_separator("E2B Sandbox Demonstration")
    
    try:
        print("Initializing E2B sandbox...")
        sandbox = Sandbox(api_key=E2B_API_KEY)
        print("Sandbox initialized successfully")
        
        # Test running Python code
        print("\nRunning Python code...")
        result = sandbox.run_code("""
import os
import platform
import sys

print("Hello from E2B sandbox!")
print(f"Python version: {platform.python_version()}")
print(f"Current directory: {os.getcwd()}")
print("\\nFiles in current directory:")
for file in os.listdir("."):
    print(f"  - {file}")
""")
        print("\nExecution result:")
        print(result.logs)
        
        # Test file operations
        print("\nTesting file operations...")
        
        # Write a file
        print("Writing file...")
        sandbox.files.write("/tmp/hello.txt", "Hello from the E2B sandbox!")
        
        # Read the file
        print("Reading file...")
        content = sandbox.files.read("/tmp/hello.txt")
        print(f"File content: '{content}'")
        
        # Run a shell command
        print("\nRunning shell commands...")
        result = sandbox.run_code("""
import subprocess
result = subprocess.run("ls -la /tmp", shell=True, capture_output=True, text=True)
print(result.stdout)
""")
        print("\nCommand result:")
        print(result.logs)
        
        print_separator("Demonstration Completed")
        print("All tests completed successfully!")
        
    except Exception as e:
        print("\nERROR: An exception occurred during demonstration:")
        print(f"{type(e).__name__}: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()