"""The guarded stream helper must never follow redirects itself; callers re-check every hop."""

from __future__ import annotations

import httpx

from parllama import net_guard


def test_open_guarded_stream_does_not_follow_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "public.example"
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/admin"})

    original = net_guard._guarded_client
    net_guard._guarded_client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    try:
        response = net_guard.open_guarded_stream("http://public.example/pic.png", timeout=1.0)
        try:
            assert response.is_redirect
            assert response.headers["Location"] == "http://127.0.0.1/admin"
        finally:
            response.close()
    finally:
        net_guard._guarded_client.close()
        net_guard._guarded_client = original
