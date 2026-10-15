"""Image cache SSRF guard: remote image fetches must refuse non-public hosts on every hop."""

from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from parllama.image_cache import fetch_and_cache_image
from parllama.settings_manager import settings


def _resolve_to(address: str):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (address, port or 0))]

    return fake_getaddrinfo


class _FakeResponse:
    def __init__(self, body: bytes = b"", location: str | None = None) -> None:
        self._body = body
        self.headers = {"Location": location} if location else {}
        self.is_redirect = location is not None

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 1):
        yield self._body


@pytest.fixture
def image_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(settings, "image_cache_dir", tmp_path)
    return tmp_path


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1"])
def test_non_public_image_host_is_refused(image_cache_dir: Path, address: str) -> None:
    with (
        patch("parllama.net_guard.socket.getaddrinfo", _resolve_to(address)),
        patch("parllama.image_cache.requests.get") as mock_get,
    ):
        with pytest.raises(FileNotFoundError, match="non-public address"):
            fetch_and_cache_image("http://internal.example/pic.png")
    mock_get.assert_not_called()
    assert not list(image_cache_dir.iterdir())


def test_redirect_to_private_image_host_is_refused(image_cache_dir: Path) -> None:
    def fake_getaddrinfo(host, port, *args, **kwargs):
        address = "93.184.216.34" if host == "public.example" else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 0))]

    redirect = _FakeResponse(location="http://localhost/admin.png")
    with (
        patch("parllama.net_guard.socket.getaddrinfo", fake_getaddrinfo),
        patch("parllama.image_cache.requests.get", return_value=redirect) as mock_get,
    ):
        with pytest.raises(FileNotFoundError, match="non-public address"):
            fetch_and_cache_image("http://public.example/pic.png")
    assert mock_get.call_count == 1
    assert mock_get.call_args.kwargs["allow_redirects"] is False


def test_oversized_image_download_is_refused(image_cache_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.file_validation, "max_image_size_mb", 0.001)
    with (
        patch("parllama.net_guard.socket.getaddrinfo", _resolve_to("93.184.216.34")),
        patch("parllama.image_cache.requests.get", return_value=_FakeResponse(b"x" * 4096)),
    ):
        with pytest.raises(FileNotFoundError, match="too large"):
            fetch_and_cache_image("http://public.example/big.png")
