"""Widget to select provider and model"""

from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Select
from textual.widgets._select import NoSelection

from parllama.llm_providers import LlmProvider
from parllama.llm_providers import provider_select_options
from parllama.messages.messages import LogIt, ProviderModelSelected
from parllama.messages.messages import ProviderModelsChanged
from parllama.messages.messages import RegisterForUpdates
from parllama.messages.messages import UnRegisterForUpdates
from parllama.provider_manager import provider_manager
from parllama.settings_manager import settings


class ProviderModelSelect(Container):
    """Widget to select provider and model"""

    DEFAULT_CSS = """
       ProviderModelSelect {
           width: 1fr;
           height: 1fr;
           layout: vertical;
           overflow: hidden hidden;
           &.horizontal {
               layout: horizontal;
           }
       }
       """
    _deferred_model_value: str | NoSelection
    provider_select: Select[LlmProvider]
    model_select: Select[str]

    def __init__(
        self,
        *,
        provider: Optional[LlmProvider] = None,
        model_name: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)

        lp: LlmProvider = provider or settings.last_chat_provider or LlmProvider.OLLAMA
        self.provider_select = Select[LlmProvider](
            id="provider_name",
            options=provider_select_options,
            allow_blank=False,
            value=lp,
        )

        opts = provider_manager.get_model_select_options(lp)
        models = provider_manager.get_model_names(lp)
        v: NoSelection | str = Select.BLANK
        cm = model_name or settings.last_chat_model
        if cm:
            if len(models) == 0:
                self._deferred_model_value = cm
            elif settings.last_chat_model not in models:
                self._deferred_model_value = cm
            else:
                self._deferred_model_value = settings.last_chat_model
                v = settings.last_chat_model

        # self.app.post_message(
        #     LogIt(
        #         f"dv={self._deferred_model_value}, cv={settings.last_chat_model}, v={v}"
        #     )
        # )

        self.model_select = Select(
            id="model_name",
            options=opts,
            allow_blank=True,
            value=v,
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
                    self.model_select.value = model_name
                    return
            self.notify("Model not found", severity="warning")
        self.model_select.value = Select.BLANK

    @on(Select.Changed, "#provider_name")
    def provider_select_changed(self) -> None:
        """Provider select changed, update control states and save provider name"""
        if self.provider_select.value != Select.BLANK:
            settings.last_chat_provider = self.provider_select.value  # type: ignore
            settings.save()
            self.model_select.set_options(
                provider_manager.get_model_select_options(self.provider_select.value)  # type: ignore
            )
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
        if self.model_select.value not in (Select.BLANK, settings.last_chat_model):
            settings.last_chat_model = self.model_select.value  # type: ignore
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

        old_value = self.model_select.value
        # self.app.post_message(LogIt(f"dv={self._deferred_model_value}, ov={old_value}"))
        models = provider_manager.get_model_names(self.provider_select.value)  # type: ignore
        # self.post_message(LogIt(models))
        if old_value == Select.BLANK or old_value not in models:
            old_value = Select.BLANK

        if (
            self._deferred_model_value != Select.BLANK
            and self._deferred_model_value in models
        ):
            old_value = self._deferred_model_value
            self._deferred_model_value = Select.BLANK

        self.model_select.set_options(opts)
        if old_value != Select.BLANK:
            with self.prevent(Select.Changed):
                self.model_select.value = old_value
            self.notify_changed()
