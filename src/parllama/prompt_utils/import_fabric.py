"""Import Fabric prompts from fabric repo."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import zipfile

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

    def import_patterns(self) -> None:
        """Import requested Fabric prompts."""
        for prompt_id in self.import_ids:
            prompt = self.id_to_prompt.get(prompt_id)
            if not prompt:
                continue
            prompt.source = "fabric"
            chat_manager.add_prompt(prompt)
            prompt.is_dirty = True
            prompt.save()

    def fetch_patterns(self, force: bool = False) -> None:
        """Create prompts from GitHub zip file with comprehensive security validation."""
        from pathlib import Path

        if os.path.exists(self._cache_folder):
            if force:
                shutil.rmtree(self._cache_folder)
            else:
                return

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                self._last_folder = temp_dir
                zip_path = os.path.join(temp_dir, "repo.zip")

                # Download with security validation
                self.log_it("Downloading Fabric patterns...", notify=True)
                self.download_zip(self.repo_zip_url, zip_path)

                # Extract with security validation
                self.log_it("Extracting and validating Fabric patterns...", notify=True)
                extracted_folder_path = self.extract_zip(zip_path, temp_dir)

                # Validate expected structure
                patterns_source_path = os.path.join(extracted_folder_path, "fabric-main", "patterns")
                if not os.path.exists(patterns_source_path):
                    raise FileNotFoundError("Patterns folder not found in the downloaded zip.")

                # Securely copy patterns to cache
                self._secure_ops.create_directory(Path(self._cache_folder).parent, parents=True, exist_ok=True)
                shutil.copytree(patterns_source_path, self._cache_folder)

                self.log_it("Fabric patterns downloaded and cached successfully", notify=True)

        except RuntimeError as e:
            self.log_it(f"Failed to fetch Fabric patterns: {e}", notify=True, severity="error")
            raise
        except Exception as e:
            self.log_it(f"Unexpected error fetching Fabric patterns: {e}", notify=True, severity="error")
            raise RuntimeError(f"Failed to fetch patterns: {e}") from e

    def read_patterns(self, force: bool = False) -> list[ChatPrompt]:
        """Read prompts from cache."""

        self.prompts.clear()
        self.id_to_prompt.clear()
        self.import_ids.clear()

        try:
            if not os.path.exists(self._cache_folder) or force:
                self.fetch_patterns(force)
        except FileNotFoundError:
            return []

        if not os.path.exists(self._cache_folder):
            return []

        pattern_folder_list = os.listdir(self._cache_folder)
        for pattern_name in pattern_folder_list:
            src_prompt_path = os.path.join(self._cache_folder, pattern_name, "system.md")
            if not os.path.exists(src_prompt_path):
                continue
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

            except (SecureFileOpsError, FileValidationError) as e:
                self.log_it(f"Failed to read prompt {pattern_name}: {e}", severity="warning")
                continue
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

    def download_zip(self, url: str, save_path: str) -> None:
        """Download the zip file from the specified URL with security validation."""
        try:
            # Validate the URL is from expected domain for security
            if not url.startswith("https://github.com/danielmiessler/fabric/"):
                raise ValueError(f"Unauthorized download URL: {url}")

            response = requests.get(url, timeout=settings.http_request_timeout, stream=True)
            response.raise_for_status()

            # Check content length before downloading
            content_length = response.headers.get("content-length")
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > settings.max_zip_size_mb:
                    raise ValueError(
                        f"ZIP file too large: {size_mb:.2f}MB exceeds limit of {settings.max_zip_size_mb}MB"
                    )

            # Download with size checking
            downloaded_size = 0
            max_size_bytes = settings.max_zip_size_mb * 1024 * 1024

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size_bytes:
                            raise ValueError(f"Download exceeded size limit of {settings.max_zip_size_mb}MB")
                        f.write(chunk)

            self.log_it(f"Downloaded Fabric ZIP: {downloaded_size / (1024 * 1024):.2f}MB")

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download ZIP file: {e}") from e
        except ValueError as e:
            # Clean up partial download on validation failure
            if os.path.exists(save_path):
                os.remove(save_path)
            raise RuntimeError(str(e)) from e

    def extract_zip(self, zip_path: str, extract_to: str) -> str:
        """Extract the zip file to the specified directory with security validation."""
        from pathlib import Path

        try:
            # First validate the ZIP file using our secure validator
            zip_path_obj = Path(zip_path)
            self._zip_validator.validate_file_path(zip_path_obj)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Validate ZIP contents for security issues
                total_size = 0
                compressed_size = 0

                for info in zip_ref.infolist():
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

                # Extract safely
                zip_ref.extractall(extract_to)

                # Validate extracted files don't exceed expected patterns
                extracted_files = 0
                for root, dirs, files in os.walk(extract_to):
                    extracted_files += len(files)
                    if extracted_files > 10000:  # Reasonable limit for Fabric patterns
                        raise ValueError(f"Too many files extracted: {extracted_files}")

                self.log_it(
                    f"Extracted Fabric ZIP: {extracted_files} files, {total_size / (1024 * 1024):.2f}MB uncompressed"
                )

        except zipfile.BadZipFile as e:
            raise RuntimeError(f"Invalid ZIP file: {e}") from e
        except FileValidationError as e:
            raise RuntimeError(f"ZIP validation failed: {e}") from e
        except ValueError as e:
            # Clean up extracted files on validation failure
            if os.path.exists(extract_to):
                shutil.rmtree(extract_to, ignore_errors=True)
            raise RuntimeError(str(e)) from e

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
