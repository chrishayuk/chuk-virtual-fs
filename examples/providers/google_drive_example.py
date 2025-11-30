#!/usr/bin/env python3
"""Google Drive Provider Example

Demonstrates using GoogleDriveProvider to store files in user's Google Drive.

Prerequisites:
1. Run google_drive_oauth_setup.py first to get credentials
2. Credentials will be loaded from google_drive_credentials.json

Usage:
    python google_drive_example.py

    # Or with custom credentials file
    python google_drive_example.py --credentials /path/to/credentials.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

try:
    from chuk_virtual_fs.node_info import EnhancedNodeInfo
    from chuk_virtual_fs.providers import GoogleDriveProvider
except ImportError:
    print("ERROR: chuk-virtual-fs not installed!")
    print()
    print("Install with:")
    print("  pip install chuk-virtual-fs[google_drive]")
    sys.exit(1)


async def demonstrate_google_drive(credentials_file: Path):
    """Demonstrate Google Drive provider capabilities.

    Args:
        credentials_file: Path to credentials JSON file
    """
    print("=" * 70)
    print("Google Drive Provider Example")
    print("=" * 70)
    print()

    # Load credentials
    if not credentials_file.exists():
        print(f"ERROR: Credentials file not found: {credentials_file}")
        print()
        print("Run google_drive_oauth_setup.py first to create credentials:")
        print("  python google_drive_oauth_setup.py")
        print()
        sys.exit(1)

    with open(credentials_file) as f:
        credentials = json.load(f)

    # Validate credentials format
    required_fields = ["client_id", "client_secret", "refresh_token"]
    missing_fields = [field for field in required_fields if field not in credentials]

    if missing_fields:
        print("ERROR: Invalid credentials file format")
        print()
        print(f"Missing required fields: {', '.join(missing_fields)}")
        print()
        print("This looks like a client_secret.json file (from Google Cloud Console).")
        print("You need to run the OAuth setup to get actual user credentials:")
        print()
        print(
            "  python google_drive_oauth_setup.py --client-secrets google_drive_credentials.json"
        )
        print()
        print("This will:")
        print("  1. Open a browser for Google authorization")
        print(
            "  2. Create a NEW file with your tokens (defaults to google_drive_credentials.json)"
        )
        print()
        sys.exit(1)

    print(f"✓ Loaded credentials from: {credentials_file}")
    print()

    # Create provider
    print("Creating Google Drive provider...")
    provider = GoogleDriveProvider(
        credentials=credentials,
        root_folder="CHUK_EXAMPLE",  # Will create /CHUK_EXAMPLE/ in Drive
        cache_ttl=60,
    )

    try:
        # Initialize
        print("Initializing connection to Google Drive...")
        success = await provider.initialize()
        if not success:
            print("ERROR: Failed to initialize Google Drive provider")
            sys.exit(1)

        print("✓ Connected to Google Drive")
        print(f"  Root folder ID: {provider._root_folder_id}")
        print()

        # Create directory structure
        print("=" * 70)
        print("Creating Directory Structure")
        print("=" * 70)
        print()

        # Create /projects directory
        projects_dir = EnhancedNodeInfo(
            name="projects",
            is_dir=True,
            parent_path="/",
            custom_meta={"description": "Example projects directory"},
            tags={"type": "directory", "env": "example"},
        )

        print("Creating /projects directory...")
        success = await provider.create_node(projects_dir)
        if success:
            print("✓ Created /projects")
        else:
            print("⚠️  /projects may already exist")
        print()

        # Create /projects/demo directory
        demo_dir = EnhancedNodeInfo(
            name="demo",
            is_dir=True,
            parent_path="/projects",
            custom_meta={"description": "Demo project"},
        )

        print("Creating /projects/demo directory...")
        success = await provider.create_node(demo_dir)
        if success:
            print("✓ Created /projects/demo")
        else:
            print("⚠️  /projects/demo may already exist")
        print()

        # Write files
        print("=" * 70)
        print("Writing Files")
        print("=" * 70)
        print()

        # Write README
        readme_content = b"""# Demo Project

This file was created by chuk-virtual-fs Google Drive provider!

## Features

- Files stored in YOUR Google Drive
- Accessible from Google Drive UI
- Built-in sharing via Drive
- Cross-device sync
- You own your data!

## Location

This file is in your Google Drive under:
/CHUK_EXAMPLE/projects/demo/README.md

You can:
- View it in Drive web UI
- Edit it directly in Drive
- Share it with collaborators
- Download it to any device
"""

        print("Writing /projects/demo/README.md...")
        success = await provider.write_file("/projects/demo/README.md", readme_content)
        if success:
            print("✓ Wrote README.md")
            print(f"  Size: {len(readme_content)} bytes")
        print()

        # Write data file
        data_content = json.dumps(
            {
                "project": "demo",
                "created_by": "chuk-virtual-fs",
                "provider": "google_drive",
                "features": [
                    "User owns data",
                    "Natural discoverability",
                    "Built-in sharing",
                    "Cross-device sync",
                ],
            },
            indent=2,
        ).encode()

        print("Writing /projects/demo/data.json...")
        success = await provider.write_file("/projects/demo/data.json", data_content)
        if success:
            print("✓ Wrote data.json")
            print(f"  Size: {len(data_content)} bytes")
        print()

        # Read files back
        print("=" * 70)
        print("Reading Files")
        print("=" * 70)
        print()

        print("Reading /projects/demo/README.md...")
        content = await provider.read_file("/projects/demo/README.md")
        if content:
            print("✓ Read README.md")
            print(f"  Size: {len(content)} bytes")
            print()
            print("First 200 characters:")
            print("-" * 70)
            print(content[:200].decode())
            print("...")
            print("-" * 70)
        print()

        # List directory
        print("=" * 70)
        print("Listing Directories")
        print("=" * 70)
        print()

        print("Listing /projects/demo:")
        children = await provider.list_directory("/projects/demo")
        for child in children:
            node_info = await provider.get_node_info(f"/projects/demo/{child}")
            type_icon = "📁" if node_info.is_dir else "📄"
            print(f"  {type_icon} {child}")
            if not node_info.is_dir:
                print(f"      Size: {node_info.size} bytes")
                print(f"      MIME: {node_info.mime_type}")
        print()

        # Metadata operations
        print("=" * 70)
        print("Metadata Operations")
        print("=" * 70)
        print()

        print("Setting custom metadata on README.md...")
        metadata = {
            "version": "1.0",
            "author": "chuk-virtual-fs",
            "category": "documentation",
        }
        success = await provider.set_metadata("/projects/demo/README.md", metadata)
        if success:
            print("✓ Set custom metadata")
        print()

        print("Getting custom metadata...")
        retrieved_metadata = await provider.get_metadata("/projects/demo/README.md")
        print(f"✓ Retrieved metadata: {retrieved_metadata}")
        print()

        # Get node info
        print("Getting detailed node info for README.md...")
        node_info = await provider.get_node_info("/projects/demo/README.md")
        if node_info:
            print("✓ Node Information:")
            print(f"    Name: {node_info.name}")
            print(f"    Size: {node_info.size} bytes")
            print(f"    MIME Type: {node_info.mime_type}")
            print(f"    MD5: {node_info.md5}")
            print(f"    Created: {node_info.created_at}")
            print(f"    Modified: {node_info.modified_at}")
            print(f"    Custom Meta: {node_info.custom_meta}")
            print(f"    Tags: {node_info.tags}")
        print()

        # Statistics
        print("=" * 70)
        print("Storage Statistics")
        print("=" * 70)
        print()

        stats = await provider.get_storage_stats()
        print("Provider Statistics:")
        print(f"  Provider: {stats['provider']}")
        print(f"  Root Folder: {stats['root_folder']}")
        print()
        print("Operations:")
        for key, value in stats["operations"].items():
            print(f"  {key}: {value}")
        print()
        print("Cache:")
        for key, value in stats["cache"].items():
            print(f"  {key}: {value}")
        print()

        # Success message
        print("=" * 70)
        print("✅ Example Complete!")
        print("=" * 70)
        print()
        print("Your files are now in Google Drive!")
        print()
        print("To view them:")
        print("  1. Open Google Drive in your browser")
        print("  2. Look for 'CHUK_EXAMPLE' folder")
        print("  3. Navigate to projects/demo/")
        print()
        print("You can:")
        print("  • View and edit files in Drive UI")
        print("  • Share the folder with collaborators")
        print("  • Access files from any device")
        print("  • Download files locally")
        print()
        print("Files created:")
        print("  📁 /CHUK_EXAMPLE/")
        print("    📁 projects/")
        print("      📁 demo/")
        print("        📄 README.md")
        print("        📄 data.json")
        print()

    finally:
        # Cleanup
        print("Closing connection...")
        await provider.close()
        print("✓ Connection closed")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Demonstrate Google Drive provider for chuk-virtual-fs"
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("google_drive_credentials.json"),
        help="Path to Google Drive credentials JSON (default: google_drive_credentials.json)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(demonstrate_google_drive(args.credentials))
    except KeyboardInterrupt:
        print()
        print("Cancelled by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
