"""Tests for provider refresh startup behavior."""

from __future__ import annotations

from pathlib import Path

import orjson as json

from par_ai_core.llm_providers import LlmProvider

from parllama.messages.messages import RefreshProviderModelsRequested
from parllama.provider_manager import ProviderManager


class RecordingApp:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def post_message(self, message: object) -> bool:
        self.messages.append(message)
        return True


def test_load_models_refresh_request_does_not_refresh_synchronously(tmp_path: Path) -> None:
    """Startup should use cached provider models and request refresh asynchronously."""
    cache_file = tmp_path / "provider_models.json"
    cache_file.write_bytes(json.dumps({LlmProvider.OPENAI.value: ["gpt-5.1"]}))

    manager = ProviderManager()
    manager.cache_file = cache_file
    app = RecordingApp()
    manager.app = app  # type: ignore[assignment]
    refreshed = False

    def refresh_models() -> None:
        nonlocal refreshed
        refreshed = True

    manager.refresh_models = refresh_models  # type: ignore[method-assign]

    manager.load_models(refresh=True)

    assert refreshed is False
    assert manager.provider_models[LlmProvider.OPENAI] == ["gpt-5.1"]
    assert any(isinstance(message, RefreshProviderModelsRequested) for message in app.messages)


def test_app_mount_does_not_unconditionally_request_provider_refresh() -> None:
    """ProviderManager.load_models owns startup refresh decisions based on cache state."""
    app_source = Path("src/parllama/app.py").read_text(encoding="utf-8")

    assert "self.post_message(RefreshProviderModelsRequested(None))" not in app_source
