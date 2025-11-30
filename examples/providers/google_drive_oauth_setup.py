#!/usr/bin/env python3
"""Google Drive OAuth Setup Helper

This script helps you set up OAuth2 credentials for Google Drive integration.

Steps:
1. Create a Google Cloud Project
2. Enable Google Drive API
3. Create OAuth 2.0 credentials
4. Download client_secret.json
5. Run this script to authorize
6. Save the credentials for later use

Usage:
    python google_drive_oauth_setup.py

    # Or with custom client secrets file
    python google_drive_oauth_setup.py --client-secrets /path/to/client_secret.json

    # Save credentials to specific file
    python google_drive_oauth_setup.py --output-file credentials.json
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("ERROR: Google Auth libraries not installed!")
    print()
    print("Install with:")
    print("  pip install chuk-virtual-fs[google_drive]")
    print()
    print("Or manually:")
    print("  pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)


# Required OAuth scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",  # Only access files created by app
]


def setup_oauth(client_secrets_file: Path, output_file: Path | None = None) -> dict:
    """Run OAuth flow and return credentials.

    Args:
        client_secrets_file: Path to client_secret.json from Google Cloud Console
        output_file: Optional path to save credentials JSON

    Returns:
        Credentials dictionary suitable for GoogleDriveProvider
    """
    print("=" * 70)
    print("Google Drive OAuth Setup")
    print("=" * 70)
    print()

    # Check client secrets file exists
    if not client_secrets_file.exists():
        print(f"ERROR: Client secrets file not found: {client_secrets_file}")
        print()
        print("To get client_secret.json:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project or select existing")
        print("  3. Enable Google Drive API")
        print("  4. Go to 'Credentials' → Create OAuth 2.0 Client ID")
        print("  5. Choose 'Desktop app' as application type")
        print("  6. Download the JSON file and save as client_secret.json")
        print()
        sys.exit(1)

    print(f"✓ Found client secrets: {client_secrets_file}")
    print()

    # Run OAuth flow
    print("Starting OAuth authorization flow...")
    print("Your browser will open for Google authorization.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_file), scopes=SCOPES
    )

    try:
        # This will open a browser window
        creds = flow.run_local_server(port=0)
    except Exception as e:
        print(f"ERROR: OAuth flow failed: {e}")
        sys.exit(1)

    print()
    print("✓ Authorization successful!")
    print()

    # Convert credentials to dict
    creds_dict = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }

    # Save to file if requested
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(creds_dict, f, indent=2)
        print(f"✓ Credentials saved to: {output_file}")
        print()

    # Show credentials (for copying to config)
    print("=" * 70)
    print("Credentials (use in your application)")
    print("=" * 70)
    print()
    print("Python code:")
    print()
    print("from chuk_virtual_fs.providers import GoogleDriveProvider")
    print()
    print("credentials = {")
    for key, value in creds_dict.items():
        if isinstance(value, str):
            print(f"    '{key}': '{value}',")
        else:
            print(f"    '{key}': {value},")
    print("}")
    print()
    print("provider = GoogleDriveProvider(credentials=credentials)")
    print("await provider.initialize()")
    print()

    # Show Claude Desktop config
    print("=" * 70)
    print("Claude Desktop Configuration")
    print("=" * 70)
    print()
    print("Add to claude_desktop_config.json:")
    print()
    config_snippet = {
        "mcpServers": {
            "vfs": {
                "command": "uvx",
                "args": ["chuk-virtual-fs"],
                "env": {
                    "VFS_PROVIDER": "google_drive",
                    "GOOGLE_DRIVE_CREDENTIALS": json.dumps(creds_dict),
                },
            }
        }
    }
    print(json.dumps(config_snippet, indent=2))
    print()

    print("=" * 70)
    print("Setup Complete!")
    print("=" * 70)
    print()
    print("Your files will be stored in Google Drive under:")
    print("  /CHUK/")
    print()
    print("You can:")
    print("  • View files in Google Drive UI")
    print("  • Share folders with collaborators")
    print("  • Access files on any device")
    print("  • Revoke access anytime")
    print()

    return creds_dict


def main():
    parser = argparse.ArgumentParser(
        description="Set up Google Drive OAuth credentials for chuk-virtual-fs"
    )
    parser.add_argument(
        "--client-secrets",
        type=Path,
        default=Path("client_secret.json"),
        help="Path to client_secret.json from Google Cloud Console (default: client_secret.json)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("google_drive_credentials.json"),
        help="Where to save credentials (default: google_drive_credentials.json)",
    )

    args = parser.parse_args()

    try:
        setup_oauth(args.client_secrets, args.output_file)
    except KeyboardInterrupt:
        print()
        print("Cancelled by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
