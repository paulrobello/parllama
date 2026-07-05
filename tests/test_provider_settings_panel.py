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

from parllama.settings_manager import settings
from parllama.theme_manager import theme_manager
from parllama.widgets.provider_settings_panel import PROVIDER_PANELS, ProviderSettingsPanel
from parllama.widgets.views.options_view import OptionsView


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


class _OptionsHostApp(App[None]):
    """Mounts the real OptionsView, wiring the theme manager as ParLlamaApp does."""

    def __init__(self) -> None:
        super().__init__()
        # OptionsView._compose_theme_section queries theme_manager, which needs
        # its app reference set before composing (mirrors ParLlamaApp.__init__).
        theme_manager.set_app(self)

    def compose(self) -> ComposeResult:
        yield OptionsView()


@pytest.mark.anyio
async def test_provider_panels_stack_without_overlap_in_options_view() -> None:
    """Each provider panel is its own bordered .section so they stack, not overlap.

    Regression guard: wrapping each panel in an extra plain ``Vertical`` (default
    ``height: 1fr``) instead of making the panel itself the ``.section`` caused
    every provider panel to collapse onto the same vertical position.
    """
    # Use a built-in Textual theme: a bare host app (unlike ParLlamaApp) does not
    # register parllama's custom "par" theme, so OptionsView's theme Select would
    # reject the default value.
    original_theme = settings.theme_name
    settings.theme_name = "textual-dark"
    try:
        app = _OptionsHostApp()
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            panels = list(app.query(ProviderSettingsPanel))
            assert panels, "no provider panels mounted"
            # Every panel must be a bordered section that sizes to its content.
            assert all("section" in panel.classes for panel in panels)
            assert all(panel.region.height > 3 for panel in panels), "a panel collapsed"
            rects = sorted((panel.region for panel in panels), key=lambda r: r.y)
            for upper, lower in zip(rects, rects[1:]):
                assert upper.bottom <= lower.y, "provider panels overlap vertically"
    finally:
        settings.theme_name = original_theme
