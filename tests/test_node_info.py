"""
tests/chuk_virtual_fs/filesystem/test_node_info.py
"""

import time

from chuk_virtual_fs.node_info import FSNodeInfo


def test_get_path_no_parent():
    # When parent_path is empty and name is provided, path should be "/<name>"
    node = FSNodeInfo(name="file.txt", is_dir=False, parent_path="")
    assert node.get_path() == "/file.txt"


def test_get_path_root():
    # When name is empty, it is considered root
    node = FSNodeInfo(name="", is_dir=True, parent_path="")
    assert node.get_path() == "/"


def test_get_path_with_root_parent():
    # When parent_path is "/" the result should be "/<name>"
    node = FSNodeInfo(name="folder", is_dir=True, parent_path="/")
    assert node.get_path() == "/folder"


def test_get_path_nested():
    # When parent_path is non-root, the path should be "parent_path/name"
    node = FSNodeInfo(name="document.txt", is_dir=False, parent_path="/home/user")
    assert node.get_path() == "/home/user/document.txt"


def test_to_dict():
    # Create a node and convert to dictionary.
    node = FSNodeInfo(name="data", is_dir=True, parent_path="/var")
    info_dict = node.to_dict()

    # Check essential keys exist (EnhancedNodeInfo has many more fields)
    expected_keys = {"name", "is_dir", "parent_path", "modified_at"}
    assert expected_keys <= set(info_dict.keys())

    # Validate values are correctly mapped
    assert info_dict["name"] == "data"
    assert info_dict["is_dir"] is True
    assert info_dict["parent_path"] == "/var"
    # Check that modified_at is a non-empty string
    assert isinstance(info_dict["modified_at"], str) and info_dict["modified_at"]


def test_from_dict():
    # Create a node, convert it to a dict, then create a new node from that dict.
    original = FSNodeInfo(name="config.json", is_dir=False, parent_path="/etc")
    # Set some custom metadata
    original.custom_meta = {"size": 1024}
    data = original.to_dict()
    # Simulate a time delay to ensure the new node's modified_at isn't accidentally updated
    time.sleep(0.01)
    recreated = FSNodeInfo.from_dict(data)

    # Check that all attributes match
    assert recreated.name == original.name
    assert recreated.is_dir == original.is_dir
    assert recreated.parent_path == original.parent_path
    assert recreated.get_path() == original.get_path()
    assert recreated.modified_at == original.modified_at
    assert recreated.custom_meta == original.custom_meta


def test_unique_timestamps():
    # Ensure that multiple instances have different timestamps when created at different times.
    node1 = FSNodeInfo(name="a", is_dir=False)
    time.sleep(0.001)  # Small delay
    node2 = FSNodeInfo(name="b", is_dir=False)
    # Both should have timestamps, and they should be different if created at different times
    assert (
        node1.created_at != node2.created_at or node1.modified_at != node2.modified_at
    )


# New tests for enhanced MIME detection


def test_mime_office_formats():
    """Test MIME detection for Microsoft Office formats"""
    # PowerPoint
    pptx_node = FSNodeInfo(name="presentation.pptx", is_dir=False, parent_path="/")
    pptx_node.set_mime_type()
    assert (
        pptx_node.mime_type
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

    # Word
    docx_node = FSNodeInfo(name="document.docx", is_dir=False, parent_path="/")
    docx_node.set_mime_type()
    assert (
        docx_node.mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    # Excel
    xlsx_node = FSNodeInfo(name="spreadsheet.xlsx", is_dir=False, parent_path="/")
    xlsx_node.set_mime_type()
    assert (
        xlsx_node.mime_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_mime_pdf():
    """Test MIME detection for PDF"""
    pdf_node = FSNodeInfo(name="document.pdf", is_dir=False, parent_path="/")
    pdf_node.set_mime_type()
    assert pdf_node.mime_type == "application/pdf"


def test_mime_images():
    """Test MIME detection for images"""
    # JPEG
    jpg_node = FSNodeInfo(name="photo.jpg", is_dir=False, parent_path="/")
    jpg_node.set_mime_type()
    assert jpg_node.mime_type == "image/jpeg"

    # PNG
    png_node = FSNodeInfo(name="image.png", is_dir=False, parent_path="/")
    png_node.set_mime_type()
    assert png_node.mime_type == "image/png"

    # WebP
    webp_node = FSNodeInfo(name="image.webp", is_dir=False, parent_path="/")
    webp_node.set_mime_type()
    assert webp_node.mime_type == "image/webp"


def test_mime_programming_languages():
    """Test MIME detection for programming languages"""
    # Python
    py_node = FSNodeInfo(name="script.py", is_dir=False, parent_path="/")
    py_node.set_mime_type()
    assert py_node.mime_type == "text/x-python"

    # TypeScript
    ts_node = FSNodeInfo(name="app.ts", is_dir=False, parent_path="/")
    ts_node.set_mime_type()
    assert ts_node.mime_type == "text/typescript"

    # Rust
    rs_node = FSNodeInfo(name="main.rs", is_dir=False, parent_path="/")
    rs_node.set_mime_type()
    assert rs_node.mime_type == "text/x-rust"


def test_mime_from_content_pdf():
    """Test MIME detection from PDF content"""
    node = FSNodeInfo(name="unknown", is_dir=False, parent_path="/")
    pdf_content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    node.detect_mime_from_content(pdf_content)
    assert node.mime_type == "application/pdf"


def test_mime_from_content_png():
    """Test MIME detection from PNG content"""
    node = FSNodeInfo(name="unknown", is_dir=False, parent_path="/")
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    node.detect_mime_from_content(png_content)
    assert node.mime_type == "image/png"


def test_mime_from_content_jpeg():
    """Test MIME detection from JPEG content"""
    node = FSNodeInfo(name="unknown", is_dir=False, parent_path="/")
    jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    node.detect_mime_from_content(jpeg_content)
    assert node.mime_type == "image/jpeg"


def test_mime_from_content_powerpoint():
    """Test MIME detection from PowerPoint content"""
    node = FSNodeInfo(name="unknown", is_dir=False, parent_path="/")
    # ZIP with ppt/ marker
    pptx_content = b"PK\x03\x04" + b"\x00" * 100 + b"ppt/slides/"
    node.detect_mime_from_content(pptx_content)
    assert (
        node.mime_type
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )


def test_mime_from_content_word():
    """Test MIME detection from Word content"""
    node = FSNodeInfo(name="unknown", is_dir=False, parent_path="/")
    # ZIP with word/ marker
    docx_content = b"PK\x03\x04" + b"\x00" * 100 + b"word/document.xml"
    node.detect_mime_from_content(docx_content)
    assert (
        node.mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_mime_from_content_excel():
    """Test MIME detection from Excel content"""
    node = FSNodeInfo(name="unknown", is_dir=False, parent_path="/")
    # ZIP with xl/ marker
    xlsx_content = b"PK\x03\x04" + b"\x00" * 100 + b"xl/workbook.xml"
    node.detect_mime_from_content(xlsx_content)
    assert (
        node.mime_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_mime_from_content_zip():
    """Test MIME detection from generic ZIP content"""
    node = FSNodeInfo(name="unknown", is_dir=False, parent_path="/")
    # ZIP without Office markers
    zip_content = b"PK\x03\x04" + b"\x00" * 100 + b"data.txt"
    node.detect_mime_from_content(zip_content)
    assert node.mime_type == "application/zip"


def test_mime_directory():
    """Test MIME type for directory"""
    dir_node = FSNodeInfo(name="folder", is_dir=True, parent_path="/")
    dir_node.set_mime_type()
    assert dir_node.mime_type == "inode/directory"


def test_mime_case_insensitive():
    """Test MIME detection is case insensitive"""
    # Uppercase extension
    node = FSNodeInfo(name="FILE.TXT", is_dir=False, parent_path="/")
    node.set_mime_type()
    assert node.mime_type == "text/plain"

    # Mixed case
    node2 = FSNodeInfo(name="Photo.JpG", is_dir=False, parent_path="/")
    node2.set_mime_type()
    assert node2.mime_type == "image/jpeg"
