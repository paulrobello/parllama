"""Secure file operations utilities for PAR LLAMA."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from parllama.validators import (
    FileValidationError,
    FileValidator,
    sanitize_filename,
    validate_directory_path,
)

logger = logging.getLogger(__name__)


class SecureFileOpsError(Exception):
    """Exception raised when secure file operations fail."""

    def __init__(self, message: str, path: str | Path | None = None) -> None:
        """Initialize the SecureFileOpsError.

        Args:
            message: The error message
            path: The file path that caused the error
        """
        super().__init__(message)
        self.path = path


class SecureFileOperations:
    """Secure file operations with validation and safety checks."""

    def __init__(
        self,
        max_file_size_mb: float = 10.0,
        allowed_extensions: list[str] | None = None,
        validate_content: bool = True,
        sanitize_filenames: bool = True,
    ) -> None:
        """Initialize the SecureFileOperations.

        Args:
            max_file_size_mb: Maximum file size in MB
            allowed_extensions: List of allowed file extensions
            validate_content: Whether to validate file content
            sanitize_filenames: Whether to sanitize filenames
        """
        self.max_file_size_mb = max_file_size_mb
        self.allowed_extensions = allowed_extensions or []
        self.validate_content = validate_content
        self.sanitize_filenames = sanitize_filenames

        self.validator = FileValidator(
            max_size_mb=max_file_size_mb,
            allowed_extensions=allowed_extensions,
            check_content=validate_content,
        )

    def read_text_file(self, file_path: Path, encoding: str = "utf-8") -> str:
        """Safely read a text file with validation.

        Args:
            file_path: Path to the file to read
            encoding: File encoding to use

        Returns:
            File contents as string

        Raises:
            SecureFileOpsError: If validation or reading fails
        """
        try:
            # Validate the file
            self.validator.validate_file_path(file_path)

            # Read the file
            with file_path.open("r", encoding=encoding) as f:
                content = f.read()

            logger.debug(f"Successfully read text file: {file_path}")
            return content

        except FileValidationError as e:
            logger.error(f"File validation failed for {file_path}: {e}")
            raise SecureFileOpsError(f"File validation failed: {e}", file_path) from e
        except OSError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise SecureFileOpsError(f"Failed to read file: {e}", file_path) from e

    def read_json_file(self, file_path: Path, encoding: str = "utf-8") -> Any:
        """Safely read a JSON file with validation.

        Args:
            file_path: Path to the JSON file to read
            encoding: File encoding to use

        Returns:
            Parsed JSON data

        Raises:
            SecureFileOpsError: If validation or parsing fails
        """
        try:
            # Validate the file (will check JSON content if validation is enabled)
            self.validator.validate_file_path(file_path)

            # Read and parse JSON
            with file_path.open("r", encoding=encoding) as f:
                data = json.load(f)

            logger.debug(f"Successfully read JSON file: {file_path}")
            return data

        except FileValidationError as e:
            logger.error(f"JSON file validation failed for {file_path}: {e}")
            raise SecureFileOpsError(f"JSON validation failed: {e}", file_path) from e
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed for {file_path}: {e}")
            raise SecureFileOpsError(f"Invalid JSON format: {e}", file_path) from e
        except OSError as e:
            logger.error(f"Failed to read JSON file {file_path}: {e}")
            raise SecureFileOpsError(f"Failed to read JSON file: {e}", file_path) from e

    def write_text_file(
        self,
        file_path: Path,
        content: str,
        encoding: str = "utf-8",
        atomic: bool = True,
        create_dirs: bool = True,
    ) -> None:
        """Safely write a text file with atomic operations.

        Args:
            file_path: Path to write the file
            content: Content to write
            encoding: File encoding to use
            atomic: Whether to use atomic write operations
            create_dirs: Whether to create parent directories

        Raises:
            SecureFileOpsError: If writing fails
        """
        try:
            # Sanitize filename if requested
            if self.sanitize_filenames:
                safe_name = sanitize_filename(file_path.name)
                file_path = file_path.parent / safe_name

            # Create parent directories if requested
            if create_dirs:
                self._ensure_directory_exists(file_path.parent)

            # Validate parent directory
            validate_directory_path(file_path.parent, must_exist=True, must_be_writable=True)

            if atomic:
                self._atomic_write_text(file_path, content, encoding)
            else:
                with file_path.open("w", encoding=encoding) as f:
                    f.write(content)

            logger.debug(f"Successfully wrote text file: {file_path}")

        except FileValidationError as e:
            logger.error(f"Directory validation failed for {file_path.parent}: {e}")
            raise SecureFileOpsError(f"Directory validation failed: {e}", file_path) from e
        except OSError as e:
            logger.error(f"Failed to write text file {file_path}: {e}")
            raise SecureFileOpsError(f"Failed to write file: {e}", file_path) from e

    def write_json_file(
        self,
        file_path: Path,
        data: Any,
        encoding: str = "utf-8",
        atomic: bool = True,
        create_dirs: bool = True,
        indent: int = 2,
    ) -> None:
        """Safely write a JSON file with atomic operations.

        Args:
            file_path: Path to write the JSON file
            data: Data to serialize to JSON
            encoding: File encoding to use
            atomic: Whether to use atomic write operations
            create_dirs: Whether to create parent directories
            indent: JSON indentation level

        Raises:
            SecureFileOpsError: If writing fails
        """
        try:
            # Serialize data to JSON first to check for errors
            json_content = json.dumps(data, indent=indent, ensure_ascii=False)

            # Use the text file writer
            self.write_text_file(
                file_path=file_path,
                content=json_content,
                encoding=encoding,
                atomic=atomic,
                create_dirs=create_dirs,
            )

            logger.debug(f"Successfully wrote JSON file: {file_path}")

        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization failed for {file_path}: {e}")
            raise SecureFileOpsError(f"JSON serialization failed: {e}", file_path) from e

    def copy_file(
        self,
        source_path: Path,
        dest_path: Path,
        validate_source: bool = True,
        create_dirs: bool = True,
    ) -> None:
        """Safely copy a file with validation.

        Args:
            source_path: Source file path
            dest_path: Destination file path
            validate_source: Whether to validate the source file
            create_dirs: Whether to create destination directories

        Raises:
            SecureFileOpsError: If copying fails
        """
        try:
            # Validate source file if requested
            if validate_source:
                self.validator.validate_file_path(source_path)

            # Sanitize destination filename if requested
            if self.sanitize_filenames:
                safe_name = sanitize_filename(dest_path.name)
                dest_path = dest_path.parent / safe_name

            # Create destination directories if requested
            if create_dirs:
                self._ensure_directory_exists(dest_path.parent)

            # Validate destination directory
            validate_directory_path(dest_path.parent, must_exist=True, must_be_writable=True)

            # Copy the file
            shutil.copy2(source_path, dest_path)

            logger.debug(f"Successfully copied file from {source_path} to {dest_path}")

        except FileValidationError as e:
            logger.error(f"File validation failed during copy: {e}")
            raise SecureFileOpsError(f"Copy validation failed: {e}") from e
        except OSError as e:
            logger.error(f"Failed to copy file from {source_path} to {dest_path}: {e}")
            raise SecureFileOpsError(f"Copy operation failed: {e}") from e

    def delete_file(self, file_path: Path, require_confirmation: bool = False) -> None:
        """Safely delete a file.

        Args:
            file_path: Path to the file to delete
            require_confirmation: Whether to require explicit confirmation

        Raises:
            SecureFileOpsError: If deletion fails
        """
        try:
            if not file_path.exists():
                logger.warning(f"File does not exist for deletion: {file_path}")
                return

            if not file_path.is_file():
                raise SecureFileOpsError(f"Path is not a file: {file_path}", file_path)

            if require_confirmation:
                # In a real implementation, this would show a confirmation dialog
                # For now, we'll just log the requirement
                logger.info(f"Confirmation required for deleting: {file_path}")

            file_path.unlink()
            logger.debug(f"Successfully deleted file: {file_path}")

        except OSError as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            raise SecureFileOpsError(f"Delete operation failed: {e}", file_path) from e

    def create_directory(
        self,
        dir_path: Path,
        parents: bool = True,
        exist_ok: bool = True,
        mode: int = 0o755,
    ) -> None:
        """Safely create a directory.

        Args:
            dir_path: Path to the directory to create
            parents: Whether to create parent directories
            exist_ok: Whether it's okay if directory already exists
            mode: Directory permissions mode

        Raises:
            SecureFileOpsError: If creation fails
        """
        try:
            # Sanitize directory name if requested
            if self.sanitize_filenames:
                safe_name = sanitize_filename(dir_path.name)
                dir_path = dir_path.parent / safe_name

            dir_path.mkdir(parents=parents, exist_ok=exist_ok, mode=mode)
            logger.debug(f"Successfully created directory: {dir_path}")

        except OSError as e:
            logger.error(f"Failed to create directory {dir_path}: {e}")
            raise SecureFileOpsError(f"Directory creation failed: {e}", dir_path) from e

    def _atomic_write_text(self, file_path: Path, content: str, encoding: str) -> None:
        """Perform atomic write operation for text content.

        Args:
            file_path: Target file path
            content: Content to write
            encoding: File encoding

        Raises:
            OSError: If write operation fails
        """
        # Create temporary file in the same directory for atomic rename
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=encoding,
                dir=file_path.parent,
                prefix=f".tmp_{file_path.name}_",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure data is written to disk

            # Atomic rename
            temp_path.replace(file_path)
            temp_path = None  # Successfully renamed, don't clean up

        except Exception:
            # Clean up temporary file if something went wrong
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass  # Best effort cleanup
            raise

    def _ensure_directory_exists(self, dir_path: Path) -> None:
        """Ensure a directory exists, creating it if necessary.

        Args:
            dir_path: Path to the directory

        Raises:
            SecureFileOpsError: If directory creation fails
        """
        if not dir_path.exists():
            self.create_directory(dir_path, parents=True, exist_ok=True)

    @contextmanager
    def backup_file(self, file_path: Path) -> Generator[Path | None, None, None]:
        """Context manager that creates a backup of a file before operations.

        Args:
            file_path: Path to the file to backup

        Yields:
            Path to the backup file

        Example:
            with secure_ops.backup_file(my_file) as backup_path:
                # Perform operations on my_file
                # If something fails, backup_path contains the original content
        """
        backup_path = None

        try:
            if file_path.exists():
                # Create backup with timestamp
                backup_name = f"{file_path.name}.backup"
                backup_path = file_path.parent / backup_name

                # If backup already exists, create a unique name
                counter = 1
                while backup_path.exists():
                    backup_name = f"{file_path.name}.backup.{counter}"
                    backup_path = file_path.parent / backup_name
                    counter += 1

                shutil.copy2(file_path, backup_path)
                logger.debug(f"Created backup: {backup_path}")

            yield backup_path

        except Exception:
            # If there was an error and we have a backup, restore it
            if backup_path and backup_path.exists() and file_path.exists():
                try:
                    shutil.copy2(backup_path, file_path)
                    logger.info(f"Restored file from backup: {file_path}")
                except OSError as restore_error:
                    logger.error(f"Failed to restore backup: {restore_error}")
            raise
        finally:
            # Clean up backup file on successful completion
            if backup_path and backup_path.exists():
                try:
                    backup_path.unlink()
                    logger.debug(f"Cleaned up backup: {backup_path}")
                except OSError:
                    # Log but don't fail on cleanup
                    logger.warning(f"Could not clean up backup file: {backup_path}")


# Global instance with default settings
default_secure_ops = SecureFileOperations()


# Convenience functions using the global instance
def secure_read_text(file_path: Path, encoding: str = "utf-8") -> str:
    """Safely read a text file using default secure operations."""
    return default_secure_ops.read_text_file(file_path, encoding)


def secure_read_json(file_path: Path, encoding: str = "utf-8") -> Any:
    """Safely read a JSON file using default secure operations."""
    return default_secure_ops.read_json_file(file_path, encoding)


def secure_write_text(
    file_path: Path,
    content: str,
    encoding: str = "utf-8",
    atomic: bool = True,
) -> None:
    """Safely write a text file using default secure operations."""
    default_secure_ops.write_text_file(file_path, content, encoding, atomic)


def secure_write_json(
    file_path: Path,
    data: Any,
    encoding: str = "utf-8",
    atomic: bool = True,
    indent: int = 2,
) -> None:
    """Safely write a JSON file using default secure operations."""
    default_secure_ops.write_json_file(file_path, data, encoding, atomic, True, indent)
