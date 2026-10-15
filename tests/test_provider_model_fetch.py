"""ARC-005: provider model-list fetch adapter registry, shared filter/sort, and timeouts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from par_ai_core.llm_providers import LlmProvider

from parllama import provider_manager as pm
from parllama.settings_manager import settings


def test_every_known_provider_with_a_fetch_branch_has_an_adapter() -> None:
    """The registry covers every provider the old if/elif chain handled."""
    expected = {
        LlmProvider.OLLAMA,
        LlmProvider.LLAMACPP,
        LlmProvider.OPENAI,
        LlmProvider.OPENROUTER,
        LlmProvider.XAI,
        LlmProvider.DEEPSEEK,
        LlmProvider.GROQ,
        LlmProvider.ANTHROPIC,
        LlmProvider.LITELLM,
        LlmProvider.GEMINI,
    }
    assert expected <= set(pm.MODEL_LIST_FETCHERS)


def test_sort_newest_first_when_every_model_has_created() -> None:
    with patch.object(pm, "get_model_mode", return_value="chat"):
        result = pm._filter_and_sort_models(LlmProvider.GROQ, [("old", 1.0), ("new", 3.0), ("mid", 2.0)])
    assert result == ["new", "mid", "old"]


def test_missing_created_falls_back_to_id_order_without_raising() -> None:
    """GROQ/ANTHROPIC used to sort on created unconditionally and crash on None."""
    with patch.object(pm, "get_model_mode", return_value="chat"):
        result = pm._filter_and_sort_models(LlmProvider.GROQ, [("b", 2.0), ("a", None), ("c", 1.0)])
    assert result == ["a", "b", "c"]


def test_non_chat_models_are_filtered_except_for_local_providers() -> None:
    modes = {"chat-model": "chat", "embed-model": "embedding"}
    with patch.object(pm, "get_model_mode", side_effect=lambda p, m: modes[m]):
        cloud = pm._filter_and_sort_models(LlmProvider.OPENAI, [("chat-model", None), ("embed-model", None)])
    assert cloud == ["chat-model"]
    local = pm._filter_and_sort_models(LlmProvider.LLAMACPP, [("embed-model", 1.0), ("chat-model", 2.0)])
    assert local == ["chat-model", "embed-model"]


def test_gemini_filter_sees_full_resource_name_and_result_is_stripped() -> None:
    seen: list[str] = []

    def mode(p: LlmProvider, name: str) -> str:
        seen.append(name)
        return "chat"

    with patch.object(pm, "get_model_mode", side_effect=mode):
        result = pm._filter_and_sort_models(LlmProvider.GEMINI, [("models/gemini-b", None), ("models/gemini-a", None)])
    assert seen == ["models/gemini-b", "models/gemini-a"]
    assert result == ["gemini-a", "gemini-b"]


def test_ollama_keeps_local_order() -> None:
    assert pm._filter_and_sort_models(LlmProvider.OLLAMA, [("z", None), ("a", None)]) == ["z", "a"]


def test_anthropic_adapter_normalizes_datetime_and_passes_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.http, "provider_model_request_timeout", 7.0)
    created = datetime(2026, 1, 1, tzinfo=UTC)
    client = MagicMock()
    client.models.list.return_value = [SimpleNamespace(id="claude-x", created_at=created)]
    with patch("anthropic.Anthropic", return_value=client) as ctor:
        entries = pm._fetch_anthropic(LlmProvider.ANTHROPIC)
    assert ctor.call_args.kwargs["timeout"] == 7.0
    assert entries == [("claude-x", created.timestamp())]


def test_groq_adapter_passes_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.http, "provider_model_request_timeout", 9.0)
    client = MagicMock()
    client.models.list.return_value.data = [SimpleNamespace(id="llama", created=None)]
    with patch("groq.Groq", return_value=client) as ctor:
        assert pm._fetch_groq(LlmProvider.GROQ) == [("llama", None)]
    assert ctor.call_args.kwargs["timeout"] == 9.0


def test_openai_compatible_adapter_passes_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.http, "provider_model_request_timeout", 4.0)
    client = MagicMock()
    client.models.list.return_value.data = [SimpleNamespace(id="gpt-x", created=5)]
    with patch("openai.OpenAI", return_value=client) as ctor:
        assert pm._fetch_openai_compatible(LlmProvider.OPENAI) == [("gpt-x", 5)]
    assert ctor.call_args.kwargs["timeout"] == 4.0


def test_litellm_payload_without_data_raises_value_error() -> None:
    """The old branch indexed ['data'] unguarded and surfaced a bare KeyError."""
    response = MagicMock()
    response.json.return_value = {"error": "unauthorized"}
    with patch.object(pm.requests, "get", return_value=response):
        with pytest.raises(ValueError, match="no 'data' list"):
            pm._fetch_litellm(LlmProvider.LITELLM)


def test_litellm_adapter_tolerates_missing_created() -> None:
    response = MagicMock()
    response.json.return_value = {"data": [{"id": "m1"}, {"id": "m2", "created": 3}]}
    with patch.object(pm.requests, "get", return_value=response) as get:
        assert pm._fetch_litellm(LlmProvider.LITELLM) == [("m1", None), ("m2", 3)]
    assert get.call_args.kwargs["timeout"] == settings.http.provider_model_request_timeout


def test_fetch_dispatches_through_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(settings.provider.disabled_providers, LlmProvider.GROQ, False)
    monkeypatch.setitem(pm.MODEL_LIST_FETCHERS, LlmProvider.GROQ, lambda p: [("a", 1.0), ("b", 2.0)])
    with (
        patch.object(pm, "is_provider_api_key_set", return_value=True),
        patch.object(pm, "get_model_mode", return_value="chat"),
    ):
        assert pm.ProviderManager()._fetch_provider_model_list(LlmProvider.GROQ) == ["b", "a"]


def test_disabled_provider_is_not_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(settings.provider.disabled_providers, LlmProvider.GROQ, True)
    fetcher = MagicMock()
    monkeypatch.setitem(pm.MODEL_LIST_FETCHERS, LlmProvider.GROQ, fetcher)
    assert pm.ProviderManager()._fetch_provider_model_list(LlmProvider.GROQ) is None
    fetcher.assert_not_called()
