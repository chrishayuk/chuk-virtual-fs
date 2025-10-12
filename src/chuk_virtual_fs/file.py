"""
chuk_virtual_fs/file.py - File node implementation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chuk_virtual_fs.node_base import FSNode

if TYPE_CHECKING:
    from chuk_virtual_fs.directory import Directory


class File(FSNode):
    """File node that contains content (text or binary)"""

    def __init__(
        self, name: str, parent: Directory | None = None, content: str | bytes = ""
    ) -> None:
        super().__init__(name, parent)
        self._content = (
            content if isinstance(content, bytes) else content.encode("utf-8")
        )
        self._was_string = isinstance(
            content, str
        )  # Track original type for backwards compatibility
        self.size = len(self._content)
        self._is_binary = self._detect_binary()

    def _detect_binary(self) -> bool:
        """Detect if content is binary based on null bytes and non-text characters"""
        if not self._content:
            return False

        # Check for null bytes (strong indicator of binary)
        if b"\x00" in self._content:
            return True

        # Sample first 8KB for detection
        sample_size = min(8192, len(self._content))
        sample = self._content[:sample_size]

        # Count non-text bytes
        non_text_bytes = sum(
            1 for byte in sample if byte < 0x20 and byte not in (0x09, 0x0A, 0x0D)
        )

        # If more than 30% non-text, consider binary
        return (non_text_bytes / len(sample)) > 0.3 if sample else False

    @property
    def content(self) -> str | bytes:
        """
        Get the content (backwards compatible)

        Returns string if original content was string, bytes if it was bytes.
        This maintains backwards compatibility with existing code.
        """
        if self._was_string and not self._is_binary:
            try:
                return self._content.decode("utf-8")
            except UnicodeDecodeError:
                return self._content
        return self._content

    @content.setter
    def content(self, value: str | bytes) -> None:
        """Set content (accepts str or bytes)"""
        self._content = value if isinstance(value, bytes) else value.encode("utf-8")
        self._was_string = isinstance(value, str)
        self.size = len(self._content)
        self._is_binary = self._detect_binary()
        self.modified_at = "2025-03-27T12:00:00Z"

    def is_binary(self) -> bool:
        """Check if the file contains binary data"""
        return self._is_binary

    def write(self, content: bytes) -> None:
        """
        Write bytes to the file (replaces existing content)

        For text content, use write_text() instead.
        This matches Python's pathlib.Path pattern.

        Args:
            content: Bytes to write

        Example:
            >>> file.write(b'binary data')
        """
        if not isinstance(content, bytes):
            raise TypeError(
                f"write() requires bytes, not {type(content).__name__}. "
                "Use write_text() for strings."
            )
        self._content = content
        self._was_string = False
        self.size = len(self._content)
        self._is_binary = self._detect_binary()
        self.modified_at = "2025-03-27T12:00:00Z"

    def write_text(self, content: str, encoding: str = "utf-8") -> None:
        """
        Write text to the file (replaces existing content)

        This matches Python's pathlib.Path.write_text() signature.

        Args:
            content: Text string to write
            encoding: Text encoding (default: utf-8)

        Example:
            >>> file.write_text('Hello World')
            >>> file.write_text('Café', encoding='latin-1')
        """
        if not isinstance(content, str):
            raise TypeError(
                f"write_text() requires str, not {type(content).__name__}. "
                "Use write() or write_bytes() for bytes."
            )
        self._content = content.encode(encoding)
        self._was_string = True
        self.size = len(self._content)
        self._is_binary = self._detect_binary()
        self.modified_at = "2025-03-27T12:00:00Z"

    def write_bytes(self, content: bytes) -> None:
        """
        Write bytes to the file (replaces existing content)

        This matches Python's pathlib.Path.write_bytes() signature.
        Alias for write() for consistency with pathlib.

        Args:
            content: Bytes to write

        Example:
            >>> file.write_bytes(b'binary data')
        """
        self.write(content)

    def append(self, content: bytes) -> None:
        """
        Append bytes to the file

        For text content, use append_text() instead.

        Args:
            content: Bytes to append
        """
        if not isinstance(content, bytes):
            raise TypeError(
                f"append() requires bytes, not {type(content).__name__}. "
                "Use append_text() for strings."
            )
        self._content += content
        self._was_string = False
        self.size = len(self._content)
        self._is_binary = self._detect_binary()
        self.modified_at = "2025-03-27T12:00:00Z"

    def append_text(self, content: str, encoding: str = "utf-8") -> None:
        """
        Append text to the file

        Args:
            content: Text string to append
            encoding: Text encoding (default: utf-8)

        Example:
            >>> file.append_text('\\nMore content')
        """
        if not isinstance(content, str):
            raise TypeError(
                f"append_text() requires str, not {type(content).__name__}. "
                "Use append() for bytes."
            )
        self._content += content.encode(encoding)
        self.size = len(self._content)
        self._is_binary = self._detect_binary()
        self.modified_at = "2025-03-27T12:00:00Z"

    def read(self) -> bytes:
        """
        Read the content of the file as bytes

        For text content, use read_text() instead.
        This matches Python's pathlib.Path pattern.

        Returns:
            Raw bytes content
        """
        return self._content

    def read_text(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        """
        Read content as text with specified encoding

        This matches Python's pathlib.Path.read_text() signature.

        Args:
            encoding: The encoding to use (default: utf-8)
            errors: How to handle decode errors ('strict', 'ignore', 'replace')

        Returns:
            Decoded text content

        Example:
            >>> file.read_text()
            'Hello World'
            >>> file.read_text(encoding='latin-1')
            'Café'
        """
        return self._content.decode(encoding, errors=errors)

    def read_bytes(self) -> bytes:
        """
        Read content as raw bytes

        This matches Python's pathlib.Path.read_bytes() signature.

        Returns:
            Raw bytes content

        Example:
            >>> file.read_bytes()
            b'Hello World'
        """
        return self._content

    def get_encoding(self) -> str:
        """
        Attempt to detect the file encoding

        Returns:
            Detected encoding or 'binary' if not text
        """
        if self._is_binary:
            return "binary"

        # Try UTF-8 first
        try:
            self._content.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass

        # Try common encodings
        for encoding in ["latin-1", "cp1252", "ascii"]:
            try:
                self._content.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue

        return "unknown"
