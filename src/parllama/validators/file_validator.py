"""Comprehensive file validation utilities for PAR LLAMA."""

from __future__ import annotations

import json
import mimetypes
import os
import zipfile
from pathlib import Path

from textual.validation import ValidationResult, Validator


class FileValidationError(Exception):
    """Exception raised when file validation fails."""

    def __init__(self, message: str, path: str | Path | None = None) -> None:
        """Initialize the FileValidationError.

        Args:
            message: The error message
            path: The file path that caused the error
        """
        super().__init__(message)
        self.path = path


class FileValidator(Validator):
    """Comprehensive file validator for PAR LLAMA."""

    def __init__(
        self,
        max_size_mb: float = 10.0,
        allowed_extensions: list[str] | None = None,
        check_content: bool = True,
    ) -> None:
        """Initialize the FileValidator.

        Args:
            max_size_mb: Maximum file size in MB
            allowed_extensions: List of allowed file extensions (e.g., ['.txt', '.json'])
            check_content: Whether to perform content validation
        """
        super().__init__()
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.allowed_extensions = allowed_extensions or []
        self.check_content = check_content

    def validate(self, value: str) -> ValidationResult:
        """Validate a file path.

        Args:
            value: The file path to validate

        Returns:
            ValidationResult indicating success or failure
        """
        try:
            path = Path(value)
            self.validate_file_path(path)
            return ValidationResult.success()
        except FileValidationError as e:
            return self.failure(description=str(e), value=value)

    def validate_file_path(self, path: Path) -> None:
        """Validate a file path comprehensively.

        Args:
            path: The file path to validate

        Raises:
            FileValidationError: If validation fails
        """
        # Check if path exists
        if not path.exists():
            raise FileValidationError(f"File does not exist: {path}")

        # Check if it's actually a file
        if not path.is_file():
            raise FileValidationError(f"Path is not a file: {path}")

        # Validate path security
        self._validate_path_security(path)

        # Validate file size
        self._validate_file_size(path)

        # Validate file extension
        if self.allowed_extensions:
            self._validate_file_extension(path)

        # Validate file content if requested
        if self.check_content:
            self._validate_file_content(path)

    def _validate_path_security(self, path: Path) -> None:
        """Validate path security to prevent directory traversal attacks.

        Args:
            path: The file path to validate

        Raises:
            FileValidationError: If path is unsafe
        """
        # Convert to absolute path for security checks
        abs_path = path.resolve()

        # Check for directory traversal attempts
        path_str = str(abs_path)
        if ".." in path_str:
            raise FileValidationError(f"Path contains directory traversal: {path}")

        # Check for suspicious characters
        suspicious_chars = ["<", ">", ":", '"', "|", "?", "*"]
        for char in suspicious_chars:
            if char in path.name:
                raise FileValidationError(f"Filename contains suspicious character '{char}': {path.name}")

        # Check for reserved names on Windows
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }
        if path.stem.upper() in reserved_names:
            raise FileValidationError(f"Filename uses reserved name: {path.name}")

    def _validate_file_size(self, path: Path) -> None:
        """Validate file size is within limits.

        Args:
            path: The file path to validate

        Raises:
            FileValidationError: If file is too large
        """
        try:
            file_size = path.stat().st_size
            if file_size > self.max_size_bytes:
                size_mb = file_size / (1024 * 1024)
                max_mb = self.max_size_bytes / (1024 * 1024)
                raise FileValidationError(f"File too large: {size_mb:.2f}MB exceeds limit of {max_mb:.2f}MB")
        except OSError as e:
            raise FileValidationError(f"Cannot access file size: {e}") from e

    def _validate_file_extension(self, path: Path) -> None:
        """Validate file extension is allowed.

        Args:
            path: The file path to validate

        Raises:
            FileValidationError: If extension is not allowed
        """
        extension = path.suffix.lower()
        if extension not in [ext.lower() for ext in self.allowed_extensions]:
            raise FileValidationError(
                f"File extension '{extension}' not allowed. Allowed extensions: {', '.join(self.allowed_extensions)}"
            )

    def _validate_file_content(self, path: Path) -> None:
        """Validate file content based on extension.

        Args:
            path: The file path to validate

        Raises:
            FileValidationError: If content is invalid
        """
        extension = path.suffix.lower()

        if extension == ".json":
            self._validate_json_content(path)
        elif extension in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]:
            self._validate_image_content(path)
        elif extension == ".zip":
            self._validate_zip_content(path)

    def _validate_json_content(self, path: Path) -> None:
        """Validate JSON file content.

        Args:
            path: The JSON file path to validate

        Raises:
            FileValidationError: If JSON is invalid
        """
        try:
            with path.open("r", encoding="utf-8") as f:
                # Read in chunks to handle large files
                content = f.read(self.max_size_bytes)
                json.loads(content)
        except json.JSONDecodeError as e:
            raise FileValidationError(f"Invalid JSON content: {e}") from e
        except UnicodeDecodeError as e:
            raise FileValidationError(f"Invalid UTF-8 encoding in JSON file: {e}") from e
        except OSError as e:
            raise FileValidationError(f"Cannot read JSON file: {e}") from e

    def _validate_image_content(self, path: Path) -> None:
        """Validate image file content.

        Args:
            path: The image file path to validate

        Raises:
            FileValidationError: If image is invalid
        """
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type and not mime_type.startswith("image/"):
            raise FileValidationError(f"File is not an image: MIME type is {mime_type}")

        # Basic image header validation
        try:
            with path.open("rb") as f:
                header = f.read(16)
                if not header:
                    raise FileValidationError("Empty image file")

                # Check for common image signatures
                if not self._is_valid_image_header(header):
                    raise FileValidationError("Invalid image file header")

        except OSError as e:
            raise FileValidationError(f"Cannot read image file: {e}") from e

    def _validate_zip_content(self, path: Path) -> None:
        """Validate ZIP file content and check for zip bombs.

        Args:
            path: The ZIP file path to validate

        Raises:
            FileValidationError: If ZIP is invalid or dangerous
        """
        try:
            with zipfile.ZipFile(path, "r") as zip_file:
                # Check for zip bomb (excessive compression ratio)
                total_size = 0
                compressed_size = 0

                for info in zip_file.infolist():
                    total_size += info.file_size
                    compressed_size += info.compress_size

                    # Check for directory traversal in zip entries
                    if ".." in info.filename or info.filename.startswith("/"):
                        raise FileValidationError(f"ZIP contains unsafe path: {info.filename}")

                # Check compression ratio (zip bomb detection)
                if compressed_size > 0:
                    ratio = total_size / compressed_size
                    if ratio > 100:  # More than 100:1 compression ratio is suspicious
                        raise FileValidationError(f"ZIP file has suspicious compression ratio: {ratio:.1f}:1")

                # Check total uncompressed size
                max_uncompressed = self.max_size_bytes * 10  # Allow 10x expansion
                if total_size > max_uncompressed:
                    raise FileValidationError(f"ZIP uncompressed size too large: {total_size / (1024 * 1024):.2f}MB")

        except zipfile.BadZipFile as e:
            raise FileValidationError(f"Invalid ZIP file: {e}") from e
        except OSError as e:
            raise FileValidationError(f"Cannot read ZIP file: {e}") from e

    def _is_valid_image_header(self, header: bytes) -> bool:
        """Check if the header bytes indicate a valid image file.

        Args:
            header: First 16 bytes of the file

        Returns:
            True if header indicates a valid image format
        """
        # JPEG signatures
        if header.startswith(b"\xff\xd8\xff"):
            return True

        # PNG signature
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return True

        # GIF signatures
        if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
            return True

        # WebP signature
        if header.startswith(b"RIFF") and b"WEBP" in header:
            return True

        # BMP signature
        if header.startswith(b"BM"):
            return True

        return False


def validate_directory_path(path: Path, must_exist: bool = True, must_be_writable: bool = False) -> None:
    """Validate a directory path.

    Args:
        path: The directory path to validate
        must_exist: Whether the directory must already exist
        must_be_writable: Whether the directory must be writable

    Raises:
        FileValidationError: If validation fails
    """
    if must_exist and not path.exists():
        raise FileValidationError(f"Directory does not exist: {path}")

    if path.exists() and not path.is_dir():
        raise FileValidationError(f"Path is not a directory: {path}")

    if must_be_writable:
        if path.exists():
            if not os.access(path, os.W_OK):
                raise FileValidationError(f"Directory is not writable: {path}")
        else:
            # Check if parent directory is writable
            parent = path.parent
            if not parent.exists() or not os.access(parent, os.W_OK):
                raise FileValidationError(f"Cannot create directory (parent not writable): {path}")


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to make it safe for filesystem use.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename
    """
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "_")

    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[: 255 - len(ext)] + ext

    # Ensure it's not empty
    if not filename.strip():
        filename = "untitled"

    return filename.strip()


def get_safe_file_size(path: Path) -> int:
    """Safely get file size with error handling.

    Args:
        path: The file path

    Returns:
        File size in bytes, or 0 if cannot be determined
    """
    try:
        return path.stat().st_size
    except OSError:
        return 0


def is_text_file(path: Path, max_check_bytes: int = 8192) -> bool:
    """Check if a file appears to be a text file.

    Args:
        path: The file path to check
        max_check_bytes: Maximum bytes to read for checking

    Returns:
        True if file appears to be text
    """
    try:
        with path.open("rb") as f:
            chunk = f.read(max_check_bytes)
            if not chunk:
                return True  # Empty file is considered text

            # Check for null bytes (binary indicator)
            if b"\x00" in chunk:
                return False

            # Try to decode as UTF-8
            try:
                chunk.decode("utf-8")
                return True
            except UnicodeDecodeError:
                return False

    except OSError:
        return False
