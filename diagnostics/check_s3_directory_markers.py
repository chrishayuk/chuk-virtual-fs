#!/usr/bin/env python3
"""
Check S3 directory markers
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import aioboto3
from dotenv import load_dotenv


async def check_directory_markers():
    """Check for directory markers in S3"""
    
    # Load environment variables
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print("✓ Loaded environment variables from .env file")
    
    # Configuration
    BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "my-virtual-fs-bucket")
    PREFIX = "virtual-fs-demo/"
    
    print("\n" + "=" * 60)
    print("Checking S3 Directory Markers")
    print("=" * 60)
    print(f"\nBucket: {BUCKET_NAME}")
    print(f"Prefix: {PREFIX}")
    
    # Create S3 client
    session = aioboto3.Session()
    
    async with session.client(
        's3',
        endpoint_url=os.environ.get('AWS_ENDPOINT_URL_S3'),
        region_name=os.environ.get('AWS_REGION', 'us-east-1')
    ) as client:
        
        print("\nAll objects in prefix:")
        print("-" * 40)
        
        # List all objects (including directory markers)
        paginator = client.get_paginator('list_objects_v2')
        
        directory_markers = []
        regular_files = []
        
        async for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=PREFIX):
            for obj in page.get('Contents', []):
                key = obj['Key']
                size = obj['Size']
                
                # Remove prefix for display
                display_key = key[len(PREFIX):] if key.startswith(PREFIX) else key
                
                if key.endswith('/'):
                    directory_markers.append((display_key, size))
                    print(f"  📁 {display_key} (size: {size} bytes) [DIRECTORY MARKER]")
                else:
                    regular_files.append((display_key, size))
                    print(f"  📄 {display_key} (size: {size} bytes)")
        
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  - Directory markers found: {len(directory_markers)}")
        print(f"  - Regular files found: {len(regular_files)}")
        
        if directory_markers:
            print("\nDirectory markers:")
            for path, size in directory_markers:
                print(f"  - {path} ({size} bytes)")
        else:
            print("\n⚠️ No directory markers found (objects ending with '/')")
        
        # Now test creating a directory marker
        print("\n" + "=" * 60)
        print("Testing directory marker creation...")
        
        test_dir = PREFIX + "test-dir/"
        try:
            await client.put_object(
                Bucket=BUCKET_NAME,
                Key=test_dir,
                Body=b"",
                ContentType="application/x-directory",
                Metadata={
                    "type": "directory",
                    "mode": "755",
                    "owner": "1000",
                    "group": "1000",
                },
            )
            print(f"✓ Created test directory marker: {test_dir}")
            
            # Verify it exists
            response = await client.head_object(Bucket=BUCKET_NAME, Key=test_dir)
            print(f"  - ContentLength: {response.get('ContentLength', 0)} bytes")
            print(f"  - ContentType: {response.get('ContentType', 'N/A')}")
            print(f"  - Metadata: {response.get('Metadata', {})}")
            
            # Clean up
            await client.delete_object(Bucket=BUCKET_NAME, Key=test_dir)
            print("✓ Cleaned up test directory marker")
            
        except Exception as e:
            print(f"❌ Error testing directory marker: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(check_directory_markers())
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()