"""Widget to select provider and model"""

from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Select

from parllama.llm_providers import LlmProvider, provider_config
from parllama.llm_providers import provider_select_options
from parllama.messages.messages import LogIt, ProviderModelSelected
from parllama.messages.messages import ProviderModelsChanged
from parllama.messages.messages import RegisterForUpdates
from parllama.messages.messages import UnRegisterForUpdates
from parllama.provider_manager import provider_manager
from parllama.settings_manager import settings
from parllama.widgets.deferred_select import DeferredSelect


class ProviderModelSelect(Container):
    """Widget to select provider and model"""

    DEFAULT_CSS = """
       ProviderModelSelect {
           width: 1fr;
           height: auto;
           layout: vertical;
           overflow: hidden hidden;
           &.horizontal {
               layout: horizontal;
               width: 60;
               margin-right: 1;
               #provider_name{
                   width: 20;
               }
               #model_name{
                   max-width: 40;
               }
           }
       }
       """
    provider_select: DeferredSelect[LlmProvider]
    model_select: DeferredSelect[str]

    def __init__(
        self,
        *,
        provider: Optional[LlmProvider] = None,
        model_name: Optional[str] = None,
        update_settings: bool = False,
        **kwargs,
    ) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)

        self.update_settings = update_settings

        lp: LlmProvider = (
            provider or settings.last_llm_config.provider or LlmProvider.OLLAMA
        )
        self.provider_select = DeferredSelect[LlmProvider](
            id="provider_name",
            options=provider_select_options,
            allow_blank=False,
            value=lp,
        )

        self.model_select = DeferredSelect[str](
            id="model_name",
            options=provider_manager.get_model_select_options(lp),
            allow_blank=True,
            value=(
                model_name
                or settings.last_llm_config.model_name
                or provider_config[lp].default_model
            ),
        )

    @property
    def provider_name(self) -> LlmProvider:
        """Get provider name"""
        return (  # pyright: ignore [reportReturnType]
            self.provider_select.value
            if self.provider_select.value != Select.BLANK
            else LlmProvider.OLLAMA
        )

    @property
    def model_name(self) -> str:
        """Get model name"""
        return (  # pyright: ignore [reportReturnType]
            self.model_select.value if self.model_select.value != Select.BLANK else ""
        )

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "ProviderModelsChanged",
                    "SessionUpdated",
                ],
            )
        )

    async def on_unmount(self) -> None:
        """Remove dialog from updates when unmounted."""
        self.app.post_message(UnRegisterForUpdates(widget=self))

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        yield self.provider_select
        yield self.model_select

    def set_model_name(self, model_name: str) -> None:
        """Set model names"""
        if self.provider_select.value == Select.BLANK:
            self.notify("Please select a provider first", severity="warning")
            return
        if model_name:
            for _, v in provider_manager.get_model_select_options(
                self.provider_select.value  # type: ignore
            ):
                if v == model_name:
                    self.model_select.deferred_value = model_name
                    return
            self.notify(f"Model not found: {model_name}", severity="warning")
        self.model_select.value = Select.BLANK

    @on(Select.Changed, "#provider_name")
    def provider_select_changed(self) -> None:
        """Provider select changed, update control states and save provider name"""
        if self.provider_select.value != Select.BLANK:
            if self.update_settings:
                settings.last_llm_config.provider = self.provider_select.value  # type: ignore
                settings.save()
            opts = provider_manager.get_model_select_options(self.provider_select.value)  # type: ignore
            self.model_select.set_options(opts)
            if self.model_select.value == Select.BLANK:
                msv = provider_config[  # pyright: ignore [reportArgumentType]
                    self.provider_select.value
                ].default_model
                if msv in provider_manager.get_model_names(self.provider_select.value):  # type: ignore
                    self.model_select.deferred_value = msv
        else:
            self.model_select.set_options([])
        self.notify_changed()

    def notify_changed(self) -> None:
        """Notify changed"""
        self.post_message(
            ProviderModelSelected(
                provider=self.provider_select.value,  # pyright: ignore [reportArgumentType]
                model_name=(  # pyright: ignore [reportArgumentType]
                    self.model_select.value
                    if self.model_select.value != Select.BLANK
                    else ""
                ),
            )
        )

    @on(Select.Changed, "#model_name")
    def model_select_changed(self, event: Select.Changed) -> None:
        """Model select changed, update control states and save model name"""
        event.stop()
        if self.model_select.value not in (
            Select.BLANK,
            settings.last_llm_config.model_name,
        ):
            if self.update_settings:
                settings.last_llm_config.model_name = self.model_select.value  # type: ignore
                settings.save()
        self.notify_changed()

    @on(ProviderModelsChanged)
    def on_provider_models_refreshed(self, event: ProviderModelsChanged) -> None:
        """Handle provider models refreshed event"""
        event.stop()
        # self.app.post_message(LogIt("ProviderModelsChanged", notify=True))
        if self.provider_select.value == Select.BLANK:
            self.post_message(
                LogIt(
                    "Got refresh with no provider selected",
                    severity="warning",
                )
            )
            return
        opts = provider_manager.get_model_select_options(self.provider_select.value)  # type: ignore
        self.model_select.set_options(opts)

    def is_valid(self) -> bool:
        """Check if valid"""
        return (
            self.provider_select.value != Select.BLANK
            and len(str(self.provider_select.value)) > 0
            and self.model_select.value != Select.BLANK
            and len(str(self.model_select.value)) > 0
        )
