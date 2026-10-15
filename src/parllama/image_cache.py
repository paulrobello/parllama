"""Fetch, validate, and cache chat images from local paths or http(s) URLs."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from urllib.parse import urljoin

import httpx
from par_ai_core.utils import md5_hash

from parllama.net_guard import UnsafeUrlError, check_public_url, open_guarded_stream
from parllama.secure_file_ops import SecureFileOperations
from parllama.settings_manager import settings
from parllama.validators.file_validator import FileValidationError

MAX_IMAGE_REDIRECTS = 5

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)


def _download_image(url: str) -> bytes:
    """Download ``url`` enforcing the SSRF guard on every redirect hop and the size cap mid-stream.

    Raises:
        FileNotFoundError: If the URL is refused, the download fails, or the image is too large.
    """
    from parllama.retry_utils import create_retry_config, retry_with_backoff

    http = settings.http
    cap = settings.file_validation.max_image_size_mb * 1024 * 1024

    @retry_with_backoff(
        config=create_retry_config(max_attempts=http.image_fetch_max_attempts, base_delay=http.image_fetch_base_delay)
    )
    def _get(current: str) -> httpx.Response:
        return open_guarded_stream(current, timeout=http.image_fetch_timeout, headers={"user-agent": _USER_AGENT})

    current = url
    for _ in range(MAX_IMAGE_REDIRECTS + 1):
        try:
            check_public_url(current, "image")
        except UnsafeUrlError as e:
            raise FileNotFoundError(str(e)) from e
        with closing(_get(current)) as response:
            if response.is_redirect:
                location = response.headers.get("Location")
                if not location:
                    raise FileNotFoundError("Image redirect without a Location header")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            chunks: list[bytes] = []
            received = 0
            for chunk in response.iter_bytes(chunk_size=64 * 1024):
                received += len(chunk)
                if received > cap:
                    raise FileNotFoundError(
                        f"Image too large: exceeds {settings.file_validation.max_image_size_mb}MB limit"
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    raise FileNotFoundError(f"Too many redirects fetching image (limit {MAX_IMAGE_REDIRECTS})")


def fetch_and_cache_image(image_path: str | Path) -> tuple[Path, bytes]:
    """Return ``(path, bytes)`` for a local image or a remote image cached under ``settings.image_cache_dir``.

    Remote URLs must resolve to public addresses; every redirect hop is re-checked.

    Raises:
        FileNotFoundError: If the image is missing, refused, fails validation, or cannot be downloaded.
    """
    fv = settings.file_validation
    image_secure_ops = SecureFileOperations(
        max_file_size_mb=fv.max_image_size_mb,
        allowed_extensions=fv.allowed_image_extensions,
        validate_content=fv.validate_file_content,
        sanitize_filenames=fv.sanitize_filenames,
    )

    if isinstance(image_path, str):
        image_path = image_path.strip()
        if image_path.startswith("http://") or image_path.startswith("https://"):
            ext = image_path.split(".")[-1].lower()
            cache_file = Path(settings.image_cache_dir) / f"{md5_hash(image_path)}.{ext}"

            if not cache_file.exists():
                try:
                    data = _download_image(image_path)

                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_bytes(data)

                    if fv.validate_file_content:
                        try:
                            image_secure_ops.validator.validate_file_path(cache_file)
                        except FileValidationError as e:
                            if cache_file.exists():
                                cache_file.unlink()
                            raise FileNotFoundError(f"Downloaded image failed validation: {e}") from e

                except (httpx.HTTPError, OSError, FileValidationError) as e:
                    raise FileNotFoundError(f"Failed to fetch image: {e}") from e
            else:
                if fv.validate_file_content:
                    try:
                        image_secure_ops.validator.validate_file_path(cache_file)
                    except FileValidationError as e:
                        if cache_file.exists():
                            cache_file.unlink()
                        raise FileNotFoundError(f"Cached image failed validation: {e}") from e

                data = cache_file.read_bytes()
            return cache_file, data

        image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if fv.validate_file_content:
        try:
            image_secure_ops.validator.validate_file_path(image_path)
        except FileValidationError as e:
            raise FileNotFoundError(f"Local image failed validation: {e}") from e

    return image_path, image_path.read_bytes()
