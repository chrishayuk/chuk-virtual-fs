"""
Example demonstrating binary file support in the virtual filesystem

This example shows:
1. Working with binary files (images, PDFs, PowerPoint, etc.)
2. Automatic binary detection
3. MIME type detection
4. Path utilities
5. Exception handling
"""

import asyncio
from chuk_virtual_fs import AsyncVirtualFileSystem, path_utils, exceptions


async def main():
    print("=" * 60)
    print("Binary File Support Example")
    print("=" * 60)

    # Create filesystem
    async with AsyncVirtualFileSystem(provider="memory") as fs:

        # 1. Binary File Operations
        print("\n1. Binary File Operations")
        print("-" * 60)

        # Create directories first
        await fs.mkdir("/documents")
        await fs.mkdir("/images")
        await fs.mkdir("/presentations")

        # Create a fake PDF file (just for demonstration)
        pdf_content = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n'
        await fs.write_binary("/documents/report.pdf", pdf_content)

        # Create a fake PNG image
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        await fs.write_binary("/images/logo.png", png_content)

        # Create a fake PowerPoint file (PPTX is a ZIP file)
        pptx_content = b'PK\x03\x04' + b'\x00' * 100 + b'ppt/slides/'
        await fs.write_binary("/presentations/slides.pptx", pptx_content)

        # Create a text file for comparison
        await fs.write_text("/documents/notes.txt", "This is a text file")

        print("Created files:")
        print("  - /documents/report.pdf (binary PDF)")
        print("  - /images/logo.png (binary PNG)")
        print("  - /presentations/slides.pptx (binary PowerPoint)")
        print("  - /documents/notes.txt (text)")

        # 2. Check file metadata and MIME types
        print("\n2. File Metadata and MIME Type Detection")
        print("-" * 60)

        files_to_check = [
            "/documents/report.pdf",
            "/images/logo.png",
            "/presentations/slides.pptx",
            "/documents/notes.txt"
        ]

        for file_path in files_to_check:
            node_info = await fs.get_node_info(file_path)
            if node_info:
                # Detect MIME type from content
                content = await fs.read_binary(file_path)
                if content:
                    node_info.detect_mime_from_content(content)

                    print(f"\n{file_path}:")
                    print(f"  MIME Type: {node_info.mime_type}")
                    print(f"  Size: {node_info.size} bytes")
                    print(f"  MD5: {node_info.md5 or 'Not calculated'}")

        # 3. Path Utilities
        print("\n3. Path Utilities")
        print("-" * 60)

        test_path = "/documents/presentations/Q4/report.pdf"

        print(f"Path: {test_path}")
        print(f"  dirname: {path_utils.dirname(test_path)}")
        print(f"  basename: {path_utils.basename(test_path)}")
        print(f"  extension: {path_utils.extension(test_path)}")
        print(f"  stem: {path_utils.stem(test_path)}")
        print(f"  depth: {path_utils.depth(test_path)}")
        print(f"  parts: {path_utils.parts(test_path)}")

        # Join paths
        joined = path_utils.join("/home", "user", "documents", "file.txt")
        print(f"\nJoined path: {joined}")

        # Change extension
        new_path = path_utils.change_extension(test_path, ".docx")
        print(f"Changed extension: {new_path}")

        # Check extension
        is_pdf = path_utils.has_extension(test_path, ".pdf", ".doc")
        print(f"Is PDF or DOC: {is_pdf}")

        # 4. Reading Binary Files
        print("\n4. Reading Binary Files")
        print("-" * 60)

        # Read as bytes explicitly
        pdf_bytes = await fs.read_binary("/documents/report.pdf")
        if pdf_bytes:
            print(f"PDF file size: {len(pdf_bytes)} bytes")
            print(f"First 20 bytes: {pdf_bytes[:20]}")

        # Read text file explicitly
        text_content = await fs.read_text("/documents/notes.txt")
        if text_content:
            print(f"\nText file content: {text_content}")

        # 5. Exception Handling
        print("\n5. Exception Handling")
        print("-" * 60)

        try:
            # Try to read non-existent file
            await fs.read_file("/nonexistent/file.txt")
        except Exception as e:
            print(f"Caught exception: {type(e).__name__}")
            print(f"  (Note: Providers currently return None instead of raising)")

        # Test path utilities error
        try:
            # This should raise an error - attempting path traversal
            path_utils.safe_join("/home/user", "../../etc/passwd")
        except (exceptions.VirtualFSError, ValueError) as e:
            print(f"\nPath traversal blocked!")
            print(f"  Error: {e}")

        # 6. Binary Detection and Clean API
        print("\n6. Binary Detection and Clean API")
        print("-" * 60)

        from chuk_virtual_fs.file import File

        # Create File objects with clean API (following pathlib.Path pattern)
        pdf_file = File("report.pdf", content=pdf_content)
        text_file = File("notes.txt", content="Hello World")

        print(f"PDF file is binary: {pdf_file.is_binary()}")
        print(f"PDF file encoding: {pdf_file.get_encoding()}")
        print(f"\nText file is binary: {text_file.is_binary()}")
        print(f"Text file encoding: {text_file.get_encoding()}")

        # Clean read/write API (no awkward as_text parameter!)
        print("\nClean API examples:")
        print("  Binary: file.read() → bytes")
        print("  Binary: file.read_bytes() → bytes")
        print("  Text: file.read_text() → str")
        print("  Write binary: file.write(b'...')")
        print("  Write text: file.write_text('...')")

        # 7. Working with Different File Formats
        print("\n7. Supported File Formats")
        print("-" * 60)

        formats = {
            "PowerPoint": [".ppt", ".pptx", ".pptm", ".ppsx"],
            "Word": [".doc", ".docx"],
            "Excel": [".xls", ".xlsx"],
            "PDF": [".pdf"],
            "Images": [".jpg", ".png", ".gif", ".bmp", ".webp"],
            "Archives": [".zip", ".tar", ".gz", ".7z"],
            "Audio": [".mp3", ".wav", ".flac", ".ogg"],
            "Video": [".mp4", ".avi", ".mkv", ".mov"]
        }

        print("All file formats now have proper MIME type support:")
        for category, exts in formats.items():
            print(f"  {category}: {', '.join(exts)}")

        # 8. Storage Stats
        print("\n8. Storage Statistics")
        print("-" * 60)

        stats = await fs.get_storage_stats()
        print(f"Total files: {stats.get('total_files', 'N/A')}")
        print(f"Total size: {stats.get('total_size_bytes', 0)} bytes")

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
