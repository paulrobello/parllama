"""Tests for OllamaDataManager.refresh_site_models (ollama.com catalog scrape + cache)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import orjson as json
import pytest

from parllama.models.ollama_data import SiteModel, SiteModelData
from parllama.ollama_data_manager import OllamaDataManager
from parllama.settings_manager import settings


def _card(name: str, pulls: str = "1.2M", tags: int = 68, updated: str = "2 months ago") -> str:
    """Render one catalog card in the shape the scraper parses."""
    return (
        '<li class="items-baseline">'
        f'<a href="/library/{name}">'
        f"<h2>{name}</h2>"
        f"<p>{name} description</p>"
        '<span class="text-blue-600">tools</span>'
        '<span class="text-blue-600">8b</span>'
        f'<span class="flex items-center">{pulls}\nPulls</span>'
        f'<span class="flex items-center">{tags}\xa0Tags</span>'
        f'<span class="flex items-center">Updated\xa0{updated}</span>'
        "</a>"
        "</li>"
    )


def _page(*cards: str) -> httpx.Response:
    return httpx.Response(200, content=f"<ul>{''.join(cards)}</ul>".encode())


class _FakeFetch:
    """Stand-in for the network page fetch that records every requested URL."""

    def __init__(self, pages: dict[str, httpx.Response] | None = None, default: httpx.Response | None = None) -> None:
        self.pages = pages or {}
        self.default = default if default is not None else _page()
        self.urls: list[str] = []

    def __call__(self, url: str) -> httpx.Response:
        self.urls.append(url)
        return self.pages.get(url, self.default)


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give each test its own site-model cache directory with saving enabled."""
    monkeypatch.setattr(settings, "ollama_cache_dir", tmp_path)
    monkeypatch.setattr(settings, "no_save", False)
    return tmp_path


@pytest.fixture
def manager() -> OllamaDataManager:
    return OllamaDataManager()


def _install(manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch, fetch: _FakeFetch) -> _FakeFetch:
    monkeypatch.setattr(manager, "_fetch_site_models_page", fetch)
    return fetch


def _write_cache(cache_dir: Path, namespace: str, data: SiteModelData) -> Path:
    path = cache_dir / f"site_models-{namespace}.json"
    path.write_bytes(json.dumps(data.model_dump(), str))
    return path


def _site_model(name: str) -> SiteModel:
    return SiteModel(name=name, description="", url="", num_pulls="", num_tags="", tags=[], updated="")


def test_card_fields_are_parsed(cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(manager, monkeypatch, _FakeFetch(default=_page(_card("llama3"))))

    items = manager.refresh_site_models("library")

    assert [item.model for item in items] == [
        SiteModel(
            name="llama3",
            description="llama3 description",
            url="https://ollama.com/library/library/llama3",
            num_pulls="1.2M",
            num_tags="68",
            tags=["tools", "8b"],
            updated="2 months ago",
        )
    ]
    assert manager.site_models == items


def test_successful_refresh_writes_cache(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(manager, monkeypatch, _FakeFetch(default=_page(_card("llama3"), _card("qwen"))))

    manager.refresh_site_models("library")

    cached = SiteModelData(**json.loads((cache_dir / "site_models-library.json").read_bytes()))
    assert [m.name for m in cached.models] == ["llama3", "qwen"]


def test_non_models_namespace_fetches_once(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = _install(manager, monkeypatch, _FakeFetch(default=_page(_card("llama3"))))

    manager.refresh_site_models("library")

    assert fetch.urls == ["https://ollama.com/library"]


def test_empty_namespace_defaults_to_library(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = _install(manager, monkeypatch, _FakeFetch())

    manager.refresh_site_models("")

    assert fetch.urls == ["https://ollama.com/library"]


def test_namespace_is_reduced_to_its_basename(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = _install(manager, monkeypatch, _FakeFetch(default=_page(_card("llama3"))))

    manager.refresh_site_models("../../evil")

    assert fetch.urls == ["https://ollama.com/evil"]
    assert (cache_dir / "site_models-evil.json").exists()
    assert not (cache_dir.parent / "site_models-evil.json").exists()


def test_models_namespace_fetches_every_category_and_dedupes(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "https://ollama.com/models"
    fetch = _install(
        manager,
        monkeypatch,
        _FakeFetch(
            pages={
                f"{base}?sort=popular": _page(_card("llama3"), _card("qwen")),
                f"{base}?sort=featured": _page(_card("qwen"), _card("phi")),
                f"{base}?sort=newest": _page(_card("llama3"), _card("gemma")),
            }
        ),
    )

    items = manager.refresh_site_models("models")

    assert fetch.urls == [f"{base}?sort=popular", f"{base}?sort=featured", f"{base}?sort=newest"]
    assert [item.model.name for item in items] == ["llama3", "qwen", "phi", "gemma"]


def test_category_filter_fetches_only_that_category(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = _install(manager, monkeypatch, _FakeFetch(default=_page(_card("phi"))))

    manager.refresh_site_models("models", category="featured")

    assert fetch.urls == ["https://ollama.com/models?sort=featured"]


def test_empty_page_returns_no_models_and_writes_no_cache(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(manager, monkeypatch, _FakeFetch())

    assert manager.refresh_site_models("library") == []
    assert not (cache_dir / "site_models-library.json").exists()


def test_no_save_suppresses_cache_write(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "no_save", True)
    _install(manager, monkeypatch, _FakeFetch(default=_page(_card("llama3"))))

    assert [item.model.name for item in manager.refresh_site_models("library")] == ["llama3"]
    assert not (cache_dir / "site_models-library.json").exists()


def test_fresh_cache_is_served_without_fetching(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_cache(cache_dir, "library", SiteModelData(models=[_site_model("cached")], last_update=datetime.now(UTC)))
    fetch = _install(manager, monkeypatch, _FakeFetch(default=_page(_card("live"))))

    items = manager.refresh_site_models("library", force=False)

    assert [item.model.name for item in items] == ["cached"]
    assert fetch.urls == []


def test_stale_cache_is_refetched(cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch) -> None:
    stale = datetime.now(UTC) - timedelta(days=2)
    _write_cache(cache_dir, "library", SiteModelData(models=[_site_model("cached")], last_update=stale))
    fetch = _install(manager, monkeypatch, _FakeFetch(default=_page(_card("live"))))

    items = manager.refresh_site_models("library", force=False)

    assert [item.model.name for item in items] == ["live"]
    assert fetch.urls == ["https://ollama.com/library"]


def test_force_refetches_even_with_fresh_cache(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_cache(cache_dir, "library", SiteModelData(models=[_site_model("cached")], last_update=datetime.now(UTC)))
    _install(manager, monkeypatch, _FakeFetch(default=_page(_card("live"))))

    items = manager.refresh_site_models("library", force=True)

    assert [item.model.name for item in items] == ["live"]


def test_corrupt_cache_is_logged_and_refetched(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    (cache_dir / "site_models-library.json").write_text("{not json", encoding="utf-8")
    logged: list[str] = []
    monkeypatch.setattr(manager, "log_it", lambda msg, **_: logged.append(str(msg)) or True)
    _install(manager, monkeypatch, _FakeFetch(default=_page(_card("live"))))

    items = manager.refresh_site_models("library", force=False)

    assert [item.model.name for item in items] == ["live"]
    assert any("site models cache" in msg for msg in logged)


def test_network_error_propagates_to_caller(
    cache_dir: Path, manager: OllamaDataManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app worker owns user notification, so the manager must not swallow fetch failures."""

    def fail(url: str) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    monkeypatch.setattr(manager, "_fetch_site_models_page", fail)
    manager.site_models = []

    with pytest.raises(httpx.ConnectError):
        manager.refresh_site_models("library")
    assert manager.site_models == []
