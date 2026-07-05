"""Composable per-provider settings panel for the Options view.

Each AI provider's settings subsection (base URL, API key, disable toggle,
model-cache controls) is near-identical boilerplate that previously lived as one
hand-written ``_compose_<provider>_provider_section`` method per provider on
``OptionsView``. This module collapses that into a single spec-driven
``ProviderSettingsPanel`` widget: adding a provider becomes one
:class:`ProviderPanelSpec` entry in :data:`PROVIDER_PANELS` (plus the existing
``_PROVIDER_BY_WIDGET_NAME`` entry that drives ``OptionsView``'s input dispatch).

Widget ids are unchanged from the original inline sections so ``OptionsView``'s
declarative input/checkbox dispatch tables continue to route events by id. The
panel owns only the self-contained model-refresh feature (the refresh button and
its cache-status display); all input/checkbox persistence stays centralized on
``OptionsView`` and reaches it via normal Textual event bubbling.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from par_ai_core.llm_providers import LlmProvider, provider_base_urls
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.validation import Integer
from textual.widgets import Button, Checkbox, Label, Static

from parllama.provider_manager import provider_manager
from parllama.settings_manager import settings
from parllama.validators.http_validator import HttpValidator
from parllama.widgets.input_blur_submit import InputBlurSubmit


def provider_cache_status_text(provider: LlmProvider) -> str:
    """Return the human-readable model-cache status line for a provider.

    Args:
        provider: The provider whose cache status to describe.

    Returns:
        A one-line status string, or ``"No cache"`` if the provider has never
        been refreshed.
    """
    cache_info = provider_manager.get_cache_info(provider)
    if cache_info["last_refresh"]:
        last_refresh = datetime.fromtimestamp(cache_info["last_refresh"]).strftime("%m/%d %H:%M")
        status = "Expired" if cache_info["cache_expired"] else "Fresh"
        return f"{status} | Age: {cache_info['cache_age_hours']}h | Models: {cache_info['model_count']} | Last: {last_refresh}"
    return "No cache"


@dataclass(frozen=True)
class ExtraInputSpec:
    """A provider-specific extra integer input rendered after the base URL.

    Used for the handful of provider fields that are not the standard base
    URL / API key (currently only Ollama's PS poll interval).
    """

    label: str
    widget_id: str
    value: Callable[[], str]
    minimum: int
    maximum: int
    max_length: int = 5


@dataclass(frozen=True)
class ProviderPanelSpec:
    """Declarative description of one provider's settings subsection."""

    provider: LlmProvider
    title: str
    has_base_url: bool = True
    base_url_default: str = ""
    has_api_key: bool = False
    api_key_id: str = ""
    extra_inputs: tuple[ExtraInputSpec, ...] = field(default_factory=tuple)


class ProviderSettingsPanel(Vertical):
    """A composable settings subsection for a single AI provider.

    Renders the provider's base URL, optional API key, any extra inputs, a
    disable toggle, and model-cache controls, and handles its own model-refresh
    button. Widget ids match the provider's canonical lowercase name so the
    parent view's input dispatch continues to work unchanged.
    """

    def __init__(self, spec: ProviderPanelSpec, **kwargs) -> None:
        """Initialise the panel.

        Args:
            spec: The declarative description of the provider subsection.
            **kwargs: Forwarded to the underlying :class:`~textual.containers.Vertical`.
        """
        super().__init__(**kwargs)
        self.spec = spec

    @property
    def _provider_name(self) -> str:
        """The provider's canonical lowercase name used to build widget ids."""
        return self.spec.provider.value.lower()

    def compose(self) -> ComposeResult:
        """Compose the provider's settings subsection."""
        spec = self.spec
        with Vertical(classes="section") as section:
            section.border_title = spec.title
            if spec.has_base_url:
                yield Label("Base URL")
                yield InputBlurSubmit(
                    value=settings.provider_base_urls[spec.provider] or spec.base_url_default,
                    valid_empty=True,
                    validators=HttpValidator(),
                    id=f"{self._provider_name}_base_url",
                )
            for extra in spec.extra_inputs:
                yield Label(extra.label)
                yield InputBlurSubmit(
                    value=extra.value(),
                    max_length=extra.max_length,
                    type="integer",
                    validators=[Integer(minimum=extra.minimum, maximum=extra.maximum)],
                    id=extra.widget_id,
                )
            if spec.has_api_key:
                yield Label("API Key")
                yield InputBlurSubmit(
                    value=settings.provider_api_keys[spec.provider] or "",
                    valid_empty=True,
                    password=True,
                    id=spec.api_key_id or f"{self._provider_name}_api_key",
                )
            yield from self._compose_disable_checkbox()
            yield from self._compose_cache_controls()

    def _compose_disable_checkbox(self) -> ComposeResult:
        """Compose the provider disable checkbox."""
        yield Checkbox(
            label=f"Disable {self.spec.provider.value} Provider",
            value=settings.disabled_providers.get(self.spec.provider, False),
            id=f"disable_{self._provider_name}_provider",
        )

    def _compose_cache_controls(self) -> ComposeResult:
        """Compose the model-cache duration, status, and refresh controls."""
        yield Label("Cache Duration (hours)")
        yield InputBlurSubmit(
            value=str(settings.provider_cache_hours[self.spec.provider]),
            max_length=5,
            type="integer",
            validators=[Integer(minimum=1, maximum=8760)],
            id=f"{self._provider_name}_cache_hours",
        )

        yield Label("Cache Status")
        yield Static(
            provider_cache_status_text(self.spec.provider),
            id=f"{self._provider_name}_cache_status",
        )

        with Horizontal():
            yield Button(
                f"Refresh {self.spec.provider.value} Models",
                id=f"refresh_{self._provider_name}_models",
                variant="primary",
            )

    @on(Button.Pressed)
    def _on_refresh_pressed(self, event: Button.Pressed) -> None:
        """Refresh this provider's model list and update its cache status."""
        event.stop()
        provider_manager.refresh_provider_models(self.spec.provider)
        self.query_one(f"#{self._provider_name}_cache_status", Static).update(
            provider_cache_status_text(self.spec.provider)
        )


# Ordered exactly as the provider subsections appeared in the original
# OptionsView.compose. Adding a provider is a single entry here (plus the
# matching _PROVIDER_BY_WIDGET_NAME entry in options_view for input dispatch).
PROVIDER_PANELS: tuple[ProviderPanelSpec, ...] = (
    ProviderPanelSpec(
        provider=LlmProvider.OLLAMA,
        title="Ollama",
        extra_inputs=(
            ExtraInputSpec(
                label="PS poll interval in seconds. 0 to disable.",
                widget_id="ollama_ps_poll_interval",
                value=lambda: str(settings.ollama_ps_poll_interval),
                minimum=0,
                maximum=300,
            ),
        ),
    ),
    ProviderPanelSpec(provider=LlmProvider.OPENAI, title="OpenAI", has_api_key=True),
    ProviderPanelSpec(provider=LlmProvider.GROQ, title="Groq", has_api_key=True),
    ProviderPanelSpec(provider=LlmProvider.ANTHROPIC, title="Anthropic", has_api_key=True),
    ProviderPanelSpec(
        provider=LlmProvider.GEMINI,
        title="Gemini",
        has_base_url=False,
        has_api_key=True,
        api_key_id="google_api_key",
    ),
    ProviderPanelSpec(provider=LlmProvider.XAI, title="xAI", has_api_key=True),
    ProviderPanelSpec(provider=LlmProvider.OPENROUTER, title="OpenRouter", has_api_key=True),
    ProviderPanelSpec(provider=LlmProvider.DEEPSEEK, title="Deepseek", has_api_key=True),
    ProviderPanelSpec(provider=LlmProvider.LITELLM, title="LiteLLM", has_api_key=True),
    ProviderPanelSpec(
        provider=LlmProvider.LLAMACPP,
        title="LlamaCPP",
        base_url_default=provider_base_urls[LlmProvider.LLAMACPP] or "",
    ),
)
