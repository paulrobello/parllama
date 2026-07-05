"""Tests for the composable ProviderSettingsPanel used by the Options view.

These mount the panels in a headless Textual app so that construction and
compose are actually exercised — the kind of runtime failure (e.g. a property
shadowing a Textual internal) that type-checking and non-mounting unit tests
cannot catch.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.containers import Vertical

from parllama.widgets.provider_settings_panel import PROVIDER_PANELS, ProviderSettingsPanel


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _PanelHostApp(App[None]):
    """Minimal app that mounts every provider settings panel."""

    def compose(self) -> ComposeResult:
        with Vertical():
            for spec in PROVIDER_PANELS:
                yield ProviderSettingsPanel(spec)


def _expected_ids() -> set[str]:
    """Compute the widget ids every panel is expected to mount."""
    ids: set[str] = set()
    for spec in PROVIDER_PANELS:
        name = spec.provider.value.lower()
        if spec.has_base_url:
            ids.add(f"{name}_base_url")
        for extra in spec.extra_inputs:
            ids.add(extra.widget_id)
        if spec.has_api_key:
            ids.add(spec.api_key_id or f"{name}_api_key")
        ids.update(
            {
                f"disable_{name}_provider",
                f"{name}_cache_hours",
                f"{name}_cache_status",
                f"refresh_{name}_models",
            }
        )
    return ids


@pytest.mark.anyio
async def test_all_provider_panels_mount_with_expected_ids() -> None:
    """Every provider panel constructs, composes, and mounts its expected widget ids."""
    app = _PanelHostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        mounted_ids = {widget.id for widget in app.query("*") if widget.id}
        missing = _expected_ids() - mounted_ids
        assert not missing, f"Provider panels did not mount expected ids: {sorted(missing)}"


@pytest.mark.anyio
async def test_special_case_provider_ids_present() -> None:
    """The non-uniform provider fields (Ollama PS poll, Gemini google_api_key, LlamaCPP base URL) mount correctly."""
    app = _PanelHostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        mounted_ids = {widget.id for widget in app.query("*") if widget.id}
        for special in ("ollama_ps_poll_interval", "google_api_key", "llamacpp_base_url"):
            assert special in mounted_ids, f"expected special-case id {special} not mounted"
        # Gemini has no base URL field.
        assert "gemini_base_url" not in mounted_ids
