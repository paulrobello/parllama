"""Import Fabric prompts from fabric repo."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable

import requests

from parllama.chat_manager import chat_manager
from parllama.chat_message import ParllamaChatMessage
from parllama.chat_prompt import ChatPrompt
from parllama.par_event_system import ParEventSystemBase
from parllama.secure_file_ops import SecureFileOperations, SecureFileOpsError
from parllama.settings_manager import settings
from parllama.validators import FileValidationError, FileValidator


class ImportFabricManager(ParEventSystemBase):
    """Import Fabric prompts from fabric repo."""

    id_to_prompt: dict[str, ChatPrompt]
    prompts: list[ChatPrompt]
    import_ids: set[str]

    def __init__(self) -> None:
        """Initialize the import manager."""
        super().__init__(id="import_fabric_manager")
        self.prompts = []
        self.id_to_prompt = {}
        self.import_ids = set()
        self.repo_zip_url = "https://github.com/danielmiessler/fabric/archive/refs/heads/main.zip"
        self._cache_folder = os.path.join(settings.cache_dir, "fabric_prompts")
        self._last_folder: str | None = None

        # Initialize secure file operations for Fabric imports
        self._secure_ops = SecureFileOperations(
            max_file_size_mb=settings.max_zip_size_mb,
            allowed_extensions=settings.allowed_zip_extensions + settings.allowed_markdown_extensions,
            validate_content=settings.validate_file_content,
            sanitize_filenames=settings.sanitize_filenames,
        )

        # Create ZIP file validator with stricter settings for external downloads
        self._zip_validator = FileValidator(
            max_size_mb=settings.max_zip_size_mb,
            allowed_extensions=settings.allowed_zip_extensions,
            check_content=True,
        )

    def import_patterns(self, progress_callback: Callable[[int, str, str], None] | None = None) -> None:
        """Import requested Fabric prompts."""
        if progress_callback:
            progress_callback(90, "Importing selected patterns...", f"Importing {len(self.import_ids)} patterns")

        total_patterns = len(self.import_ids)
        for i, prompt_id in enumerate(self.import_ids):
            prompt = self.id_to_prompt.get(prompt_id)
            if not prompt:
                continue
            prompt.source = "fabric"
            chat_manager.add_prompt(prompt)
            prompt.is_dirty = True
            prompt.save()

            if progress_callback and total_patterns > 0:
                progress_percent = 90 + int((i + 1) / total_patterns * 10)
                progress_callback(
                    progress_percent, "Importing patterns...", f"Imported {i + 1} of {total_patterns}: {prompt.name}"
                )

        if progress_callback:
            progress_callback(100, "Import complete!", f"Successfully imported {total_patterns} patterns")

    def fetch_patterns(
        self, force: bool = False, progress_callback: Callable[[int, str, str], None] | None = None
    ) -> None:
        """Create prompts from GitHub zip file with comprehensive security validation."""
        from pathlib import Path

        if progress_callback:
            progress_callback(5, "Checking cache...", "Verifying if patterns need to be downloaded")

        if os.path.exists(self._cache_folder):
            if force:
                if progress_callback:
                    progress_callback(10, "Clearing cache...", "Removing existing cached patterns")
                shutil.rmtree(self._cache_folder)
            else:
                if progress_callback:
                    progress_callback(100, "Using cached patterns", "Patterns already available in cache")
                return

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                self._last_folder = temp_dir
                zip_path = os.path.join(temp_dir, "repo.zip")

                # Download with security validation (0-30% progress)
                if progress_callback:
                    progress_callback(15, "Starting download...", "Connecting to GitHub repository")
                self.download_zip(self.repo_zip_url, zip_path, progress_callback)

                # Extract with security validation (30-50% progress)
                if progress_callback:
                    progress_callback(30, "Download complete", "Starting extraction and validation")
                extracted_folder_path = self.extract_zip(zip_path, temp_dir, progress_callback)

                # Validate expected structure
                if progress_callback:
                    progress_callback(45, "Validating structure...", "Checking for patterns folder")
                patterns_source_path = os.path.join(extracted_folder_path, "fabric-main", "patterns")
                if not os.path.exists(patterns_source_path):
                    raise FileNotFoundError("Patterns folder not found in the downloaded zip.")

                # Securely copy patterns to cache (50-60% progress)
                if progress_callback:
                    progress_callback(50, "Setting up cache...", "Copying patterns to local cache")
                self._secure_ops.create_directory(Path(self._cache_folder).parent, parents=True, exist_ok=True)
                shutil.copytree(patterns_source_path, self._cache_folder)

                if progress_callback:
                    progress_callback(60, "Cache setup complete", "Fabric patterns cached successfully")

        except RuntimeError as e:
            error_msg = str(e)
            recovery_suggestion = self._get_recovery_suggestion(error_msg)
            if progress_callback:
                progress_callback(0, "Download failed", f"{error_msg}\n\nSuggestion: {recovery_suggestion}")
            self.log_it(f"Failed to fetch Fabric patterns: {e}", notify=True, severity="error")
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            recovery_suggestion = "Please try again. If the problem persists, check your internet connection and ensure GitHub is accessible."
            if progress_callback:
                progress_callback(0, "Unexpected error occurred", f"{error_msg}\n\nSuggestion: {recovery_suggestion}")
            self.log_it(f"Unexpected error fetching Fabric patterns: {e}", notify=True, severity="error")
            raise RuntimeError(f"Failed to fetch patterns: {e}") from e

    def read_patterns(
        self, force: bool = False, progress_callback: Callable[[int, str, str], None] | None = None
    ) -> list[ChatPrompt]:
        """Read prompts from cache."""
        if progress_callback:
            progress_callback(0, "Initializing...", "Clearing existing patterns")

        self.prompts.clear()
        self.id_to_prompt.clear()
        self.import_ids.clear()

        try:
            if not os.path.exists(self._cache_folder) or force:
                self.fetch_patterns(force, progress_callback)
        except FileNotFoundError:
            if progress_callback:
                progress_callback(0, "Error: Patterns not found", "Failed to locate pattern files")
            return []

        if not os.path.exists(self._cache_folder):
            if progress_callback:
                progress_callback(0, "Error: Cache folder missing", "Pattern cache directory not found")
            return []

        # Start parsing patterns (60-90% progress)
        if progress_callback:
            progress_callback(60, "Reading patterns...", "Loading pattern definitions from cache")

        pattern_folder_list = os.listdir(self._cache_folder)
        total_patterns = len(pattern_folder_list)
        processed_patterns = 0

        for i, pattern_name in enumerate(pattern_folder_list):
            src_prompt_path = os.path.join(self._cache_folder, pattern_name, "system.md")
            if not os.path.exists(src_prompt_path):
                continue

            # Update progress for each pattern
            if progress_callback and total_patterns > 0:
                progress_percent = 60 + int((i + 1) / total_patterns * 30)
                progress_callback(
                    progress_percent,
                    "Processing patterns...",
                    f"Reading pattern {i + 1} of {total_patterns}: {pattern_name}",
                )

            # Use secure file operations to read prompt content
            try:
                from pathlib import Path

                src_path = Path(src_prompt_path)

                # Validate file before reading
                if settings.validate_file_content:
                    # Create markdown validator for prompt files
                    md_validator = FileValidator(
                        max_size_mb=settings.max_file_size_mb,
                        allowed_extensions=settings.allowed_markdown_extensions,
                        check_content=False,  # Skip content validation for markdown
                    )
                    md_validator.validate_file_path(src_path)

                # Read securely with size limits
                full_content = self._secure_ops.read_text_file(src_path)

                # Process content to extract prompt (stop at INPUT section)
                prompt_content = ""
                for line in full_content.split("\n"):
                    if line.upper().startswith("# INPUT") or line.upper().startswith("INPUT:"):
                        break
                    prompt_content += line + "\n"
                prompt_content = prompt_content.strip()

                # Create prompt from validated content
                prompt: ChatPrompt = self.markdown_to_prompt(pattern_name, prompt_content)
                self.prompts.append(prompt)
                self.id_to_prompt[prompt.id] = prompt
                processed_patterns += 1

            except (SecureFileOpsError, FileValidationError) as e:
                error_details = f"Security validation failed for {pattern_name}: {str(e)}"
                self.log_it(error_details, severity="warning")
                if progress_callback:
                    progress_callback(
                        60 + int((i + 1) / total_patterns * 30),
                        "Skipping invalid pattern",
                        f"Skipped {pattern_name}: validation failed",
                    )
                continue

        if progress_callback:
            progress_callback(
                90,
                "Pattern loading complete",
                f"Successfully loaded {processed_patterns} patterns from {total_patterns} folders",
            )

        return self.prompts

    def markdown_to_prompt(self, pattern_name: str, prompt_content: str) -> ChatPrompt:
        """Convert markdown to ChatPrompt."""
        description = self.get_description(prompt_content)
        prompt = ChatPrompt(
            id=hashlib.md5(prompt_content.encode()).hexdigest(),
            name=pattern_name,
            description=description,
            messages=[ParllamaChatMessage(role="system", content=prompt_content)],
            source="fabric",
        )
        return prompt

    @staticmethod
    def get_description(prompt_data: str) -> str:
        """Extract description from prompt data."""
        started = False
        for line in prompt_data.split("\n"):
            line = line.strip()
            if line.startswith("# IDENTITY and PURPOSE"):
                started = True
                continue
            if not started or not line:
                continue
            return line
        return ""

    def _get_recovery_suggestion(self, error_msg: str) -> str:
        """Get recovery suggestion based on error message."""
        if "network" in error_msg.lower() or "connection" in error_msg.lower():
            return "Check your internet connection and try again."
        elif "timeout" in error_msg.lower():
            return "The download timed out. Check your internet speed and try again."
        elif "size" in error_msg.lower():
            return "The file is too large. Check your storage space."
        elif "permission" in error_msg.lower():
            return "Permission denied. Check file/folder permissions."
        else:
            return "Try refreshing the import. If the problem persists, restart the application."

    def _get_network_recovery_suggestion(self, error_msg: str) -> str:
        """Get network-specific recovery suggestion."""
        if "timeout" in error_msg.lower():
            return "Check your internet connection speed and try again."
        elif "connection refused" in error_msg.lower():
            return "GitHub may be temporarily unavailable. Try again in a few minutes."
        elif "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
            return "SSL/Certificate issue. Check your system date/time and network settings."
        elif "proxy" in error_msg.lower():
            return "Check your proxy settings or try from a different network."
        else:
            return "Check your internet connection and ensure GitHub.com is accessible."

    def _get_validation_recovery_suggestion(self, error_msg: str) -> str:
        """Get validation-specific recovery suggestion."""
        if "too large" in error_msg.lower():
            return "The file exceeds size limits. Contact support if this seems incorrect."
        elif "unauthorized" in error_msg.lower():
            return "URL validation failed. This should not happen - please report this issue."
        else:
            return "File validation failed. Try refreshing to re-download the file."

    def _get_extraction_recovery_suggestion(self, error_msg: str) -> str:
        """Get extraction-specific recovery suggestion."""
        if "compression ratio" in error_msg.lower():
            return "The file appears to be a zip bomb. This is a security measure."
        elif "too many files" in error_msg.lower():
            return "The archive contains too many files. This is a security measure."
        elif "unsafe path" in error_msg.lower():
            return "The archive contains unsafe file paths. This is a security measure."
        elif "filename too long" in error_msg.lower():
            return "The archive contains files with very long names. This is a security measure."
        else:
            return "Archive extraction failed. Try refreshing to re-download the file."

    def download_zip(
        self, url: str, save_path: str, progress_callback: Callable[[int, str, str], None] | None = None
    ) -> None:
        """Download the zip file from the specified URL with security validation."""
        try:
            # Validate the URL is from expected domain for security
            if not url.startswith("https://github.com/danielmiessler/fabric/"):
                raise ValueError(f"Unauthorized download URL: {url}")

            if progress_callback:
                progress_callback(15, "Connecting...", "Establishing connection to GitHub")

            response = requests.get(url, timeout=settings.http_request_timeout, stream=True)
            response.raise_for_status()

            # Check content length before downloading
            content_length = response.headers.get("content-length")
            total_size = 0
            if content_length:
                total_size = int(content_length)
                size_mb = total_size / (1024 * 1024)
                if size_mb > settings.max_zip_size_mb:
                    raise ValueError(
                        f"ZIP file too large: {size_mb:.2f}MB exceeds limit of {settings.max_zip_size_mb}MB"
                    )
                if progress_callback:
                    progress_callback(18, "Download starting...", f"File size: {size_mb:.2f}MB")

            # Download with size checking and progress updates
            downloaded_size = 0
            max_size_bytes = settings.max_zip_size_mb * 1024 * 1024

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size_bytes:
                            raise ValueError(f"Download exceeded size limit of {settings.max_zip_size_mb}MB")
                        f.write(chunk)

                        # Update progress based on download progress
                        if progress_callback and total_size > 0:
                            # Download progress maps to 18-30% of total progress
                            download_percent = (downloaded_size / total_size) * 100
                            overall_progress = 18 + int(download_percent * 0.12)  # 18-30%
                            mb_downloaded = downloaded_size / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            progress_callback(
                                overall_progress,
                                "Downloading...",
                                f"{mb_downloaded:.1f}MB / {mb_total:.1f}MB ({download_percent:.1f}%)",
                            )

            final_size_mb = downloaded_size / (1024 * 1024)
            self.log_it(f"Downloaded Fabric ZIP: {final_size_mb:.2f}MB")

            if progress_callback:
                progress_callback(30, "Download complete", f"Downloaded {final_size_mb:.2f}MB successfully")

        except requests.RequestException as e:
            error_msg = str(e)
            recovery_suggestion = self._get_network_recovery_suggestion(error_msg)
            if progress_callback:
                progress_callback(
                    0, "Network error occurred", f"Connection failed: {error_msg}\n\nSuggestion: {recovery_suggestion}"
                )
            raise RuntimeError(f"Network error downloading ZIP file: {error_msg}\n\nTry: {recovery_suggestion}") from e
        except ValueError as e:
            # Clean up partial download on validation failure
            if os.path.exists(save_path):
                os.remove(save_path)
            error_msg = str(e)
            recovery_suggestion = self._get_validation_recovery_suggestion(error_msg)
            if progress_callback:
                progress_callback(0, "Download validation failed", f"{error_msg}\n\nSuggestion: {recovery_suggestion}")
            raise RuntimeError(f"Download validation failed: {error_msg}\n\nTry: {recovery_suggestion}") from e

    def extract_zip(
        self, zip_path: str, extract_to: str, progress_callback: Callable[[int, str, str], None] | None = None
    ) -> str:
        """Extract the zip file to the specified directory with security validation."""
        from pathlib import Path

        try:
            if progress_callback:
                progress_callback(30, "Validating ZIP file...", "Checking ZIP file integrity")

            # First validate the ZIP file using our secure validator
            zip_path_obj = Path(zip_path)
            self._zip_validator.validate_file_path(zip_path_obj)

            if progress_callback:
                progress_callback(35, "Analyzing ZIP contents...", "Scanning for security issues")

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Validate ZIP contents for security issues
                total_size = 0
                compressed_size = 0
                file_list = zip_ref.infolist()
                total_files = len(file_list)

                for i, info in enumerate(file_list):
                    # Update progress during validation
                    if progress_callback and total_files > 0:
                        validation_progress = 35 + int((i + 1) / total_files * 5)  # 35-40%
                        progress_callback(
                            validation_progress,
                            "Validating files...",
                            f"Checking file {i + 1} of {total_files}: {info.filename[:30]}...",
                        )

                    # Check for directory traversal attempts
                    if ".." in info.filename or info.filename.startswith("/") or "\\" in info.filename:
                        raise ValueError(f"Unsafe path in ZIP: {info.filename}")

                    # Check for suspiciously long filenames
                    if len(info.filename) > 255:
                        raise ValueError(f"Filename too long in ZIP: {info.filename}")

                    # Track sizes for zip bomb detection
                    total_size += info.file_size
                    compressed_size += info.compress_size

                    # Check individual file size
                    if info.file_size > settings.max_file_size_mb * 1024 * 1024:
                        raise ValueError(
                            f"File too large in ZIP: {info.filename} ({info.file_size / (1024 * 1024):.2f}MB)"
                        )

                # Check compression ratio (zip bomb detection)
                if compressed_size > 0:
                    ratio = total_size / compressed_size
                    if ratio > settings.max_zip_compression_ratio:
                        raise ValueError(
                            f"Suspicious compression ratio: {ratio:.1f}:1 exceeds limit of {settings.max_zip_compression_ratio}:1"
                        )

                # Check total uncompressed size
                max_uncompressed = settings.max_zip_size_mb * 10  # Allow 10x expansion
                if total_size > max_uncompressed * 1024 * 1024:
                    raise ValueError(f"ZIP uncompressed size too large: {total_size / (1024 * 1024):.2f}MB")

                if progress_callback:
                    progress_callback(40, "Security validation passed", f"Extracting {total_files} files...")

                # Extract safely with progress updates
                zip_ref.extractall(extract_to)

                if progress_callback:
                    progress_callback(45, "Extraction complete", "Validating extracted files...")

                # Validate extracted files don't exceed expected patterns
                extracted_files = 0
                for root, dirs, files in os.walk(extract_to):
                    extracted_files += len(files)
                    if extracted_files > 10000:  # Reasonable limit for Fabric patterns
                        raise ValueError(f"Too many files extracted: {extracted_files}")

                final_size_mb = total_size / (1024 * 1024)
                self.log_it(f"Extracted Fabric ZIP: {extracted_files} files, {final_size_mb:.2f}MB uncompressed")

                if progress_callback:
                    progress_callback(
                        50,
                        "Extraction validated",
                        f"Successfully extracted {extracted_files} files ({final_size_mb:.1f}MB)",
                    )

        except zipfile.BadZipFile as e:
            error_msg = f"Downloaded file is corrupted or not a valid ZIP archive: {str(e)}"
            recovery_suggestion = (
                "Try refreshing to download the file again. If the problem persists, GitHub may be experiencing issues."
            )
            if progress_callback:
                progress_callback(0, "Invalid ZIP file", f"{error_msg}\n\nSuggestion: {recovery_suggestion}")
            raise RuntimeError(f"{error_msg}\n\nTry: {recovery_suggestion}") from e
        except FileValidationError as e:
            error_msg = f"Security validation failed: {str(e)}"
            recovery_suggestion = "The downloaded file failed security checks. Try refreshing to download again."
            if progress_callback:
                progress_callback(0, "Security check failed", f"{error_msg}\n\nSuggestion: {recovery_suggestion}")
            raise RuntimeError(f"{error_msg}\n\nTry: {recovery_suggestion}") from e
        except ValueError as e:
            # Clean up extracted files on validation failure
            if os.path.exists(extract_to):
                shutil.rmtree(extract_to, ignore_errors=True)
            error_msg = str(e)
            recovery_suggestion = self._get_extraction_recovery_suggestion(error_msg)
            if progress_callback:
                progress_callback(
                    0, "Extraction validation failed", f"{error_msg}\n\nSuggestion: {recovery_suggestion}"
                )
            raise RuntimeError(f"Extraction failed: {error_msg}\n\nTry: {recovery_suggestion}") from e

        return extract_to

    def test_import(self) -> None:
        """Test importing fabric prompts."""
        with open(
            "d:/repos/parllama/fabric_samples/extract_wisdom/system.md",
            encoding="utf-8",
        ) as f:
            prompt_content = ""
            for line in f.readlines():
                if line.upper().startswith("# INPUT") or line.upper().startswith("INPUT:"):
                    break
                prompt_content += line + "\n"
            prompt_content = prompt_content.strip()
            prompt: ChatPrompt = self.markdown_to_prompt("extract_wisdom", prompt_content)
        chat_manager.add_prompt(prompt)
        prompt.is_dirty = True
        prompt.save()
        self.log_it("Prompt imported: extract_wisdom", notify=True)


import_fabric_manager = ImportFabricManager()
