"""A select widget for selecting a local model."""

from textual import on
from textual.message import Message
from textual.widgets import Select

from parllama.data_manager import dm
from parllama.messages.messages import (
    LocalModelListLoaded,
    LocalModelDeleted,
    RegisterForUpdates,
)
from parllama.models.settings_data import settings


class LocalModelSelect(Select[str]):
    """A select widget for selecting a local model."""

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(
            prompt="Select Model", options=dm.get_model_select_options(), **kwargs
        )

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
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
        """Model list changed"""
        event.stop()
        if self.value != Select.BLANK:
            old_v = self.value
        elif settings.last_chat_model:
            old_v = settings.last_chat_model
        else:
            old_v = Select.BLANK
        opts = dm.get_model_select_options()
        with self.prevent(Select.Changed):
            self.set_options(opts)
        for _, v in opts:
            if v == old_v:
                self.value = old_v
                return
        self.value = Select.BLANK
