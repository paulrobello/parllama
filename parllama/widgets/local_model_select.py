"""A select widget for selecting a local model."""

from __future__ import annotations

from textual import on
from textual.message import Message
from textual.widgets import Select

from parllama.data_manager import dm
from parllama.messages.messages import LocalModelDeleted
from parllama.messages.messages import LocalModelListLoaded
from parllama.messages.messages import RegisterForUpdates
from parllama.settings_manager import settings


class LocalModelSelect(Select[str]):
    """A select widget for selecting a local model."""

    def __init__(self, **kwargs) -> None:
        """Initialise the widget."""
        self._deferred_value = None  # No deferred value.
        opts = dm.get_model_select_options()
        if "value" in kwargs:
            if len(kwargs["value"]) == 0:
                del kwargs["value"]  # Remove blank values

        if len(opts) == 0 and "value" in kwargs:
            if kwargs["value"]:
                self._deferred_value = kwargs["value"]
            del kwargs[
                "value"
            ]  # Remove the value from the kwargs to avoid conflicts with the Select widget's value attribute.

        super().__init__(prompt="Select Model", options=opts, **kwargs)

    async def on_mount(self) -> None:
        """Subscribe to model list changes and update the widget's options accordingly."""
        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "LocalModelDeleted",
                    "LocalModelListLoaded",
                ],
            )
        )

    @on(LocalModelListLoaded)
    @on(LocalModelDeleted)
    def on_local_model_list_loaded(self, event: Message) -> None:
        """Model list changed. Update options and preserve value if possible."""
        event.stop()
        if self._deferred_value is not None:
            old_v = self._deferred_value
            self._deferred_value = None  # Reset the deferred value.
        elif self.value != Select.BLANK:
            old_v = self.value
        elif settings.last_chat_model:
            old_v = settings.last_chat_model
        else:
            old_v = None

        opts = dm.get_model_select_options()

        if old_v is not None:
            found = False
            for _, v in opts:
                if v == old_v:
                    found = True
                    break
            if found:
                with self.prevent(Select.Changed):
                    self.set_options(opts)
                self.value = old_v
                return
        self.set_options(opts)
