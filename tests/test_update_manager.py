"""Tests for the PyPI update check error contract."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from semver import Version

from parllama.update_manager import UpdateManager


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    """Route every httpx.AsyncClient created by update_manager through a mock transport."""
    real_client = httpx.AsyncClient

    def factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "AsyncClient", factory)


@pytest.mark.anyio
async def test_returns_parsed_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """A well-formed PyPI response yields the published version."""
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json={"info": {"version": "9.8.7"}}))

    assert await UpdateManager().get_latest_version() == Version.parse("9.8.7")


@pytest.mark.anyio
async def test_httpx_network_error_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An httpx transport error surfaces as the documented ValueError, not an httpx exception."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_transport(monkeypatch, handler)

    with pytest.raises(ValueError, match="Could not fetch version info") as exc_info:
        await UpdateManager().get_latest_version()
    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)


@pytest.mark.anyio
async def test_http_error_status_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-2xx PyPI response surfaces as ValueError instead of a KeyError on the missing payload."""
    _patch_transport(monkeypatch, lambda request: httpx.Response(503, json={"message": "unavailable"}))

    with pytest.raises(ValueError, match="Could not fetch version info"):
        await UpdateManager().get_latest_version()


@pytest.mark.anyio
async def test_malformed_payload_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 response without the expected keys surfaces as ValueError."""
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json={"unexpected": True}))

    with pytest.raises(ValueError, match="Could not fetch version info"):
        await UpdateManager().get_latest_version()
