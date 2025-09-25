"""Widget for managing user memory."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Static, TextArea

from parllama.messages.messages import MemoryUpdated, RegisterForUpdates
from parllama.settings_manager import settings


class MemoryView(Vertical):
    """Widget for managing user memory."""

    DEFAULT_CSS = """
    MemoryView {
        width: 1fr;
        height: 1fr;
        overflow: auto;

        .memory-section {
            background: $panel;
            height: auto;
            width: 1fr;
            border: solid $primary;
            border-title-color: $primary;
            margin: 0;
        }

        .memory-controls {
            height: auto;
            padding: 1;
        }

        .memory-textarea {
            height: 1fr;
            min-height: 20;
        }

        .status-text {
            height: auto;
            padding: 0 1;
            color: $text-muted;
        }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialize the memory view."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the memory view."""
        with Vertical(classes="memory-section") as section:
            section.border_title = "User Memory"

            with Horizontal(classes="memory-controls"):
                yield Checkbox(
                    label="Enable memory injection", value=settings.memory_enabled, id="memory_enabled_checkbox"
                )
                yield Button("Clear Memory", id="clear_memory_button", variant="error")
                yield Button("Save Memory", id="save_memory_button", variant="success")

            yield TextArea(
                text=settings.user_memory,
                placeholder="Enter information about yourself that you want the AI to remember across all conversations...",
                classes="memory-textarea",
                id="memory_textarea",
            )

            with Vertical(classes="status-text"):
                yield Static(
                    "This memory will be injected as the first message in every new conversation when enabled.\n"
                    "Use slash commands like '/remember I like pizza' or '/forget my address' to update memory with AI assistance.",
                    id="memory_status",
                )

    @on(Checkbox.Changed, "#memory_enabled_checkbox")
    def on_memory_enabled_changed(self, event: Checkbox.Changed) -> None:
        """Handle memory enabled checkbox change."""
        settings.memory_enabled = event.checkbox.value
        settings.save()
        status_text = "enabled" if settings.memory_enabled else "disabled"
        self.notify(f"Memory injection {status_text}")

    @on(TextArea.Changed, "#memory_textarea")
    def on_memory_text_changed(self, event: TextArea.Changed) -> None:
        """Handle memory text area change."""
        settings.user_memory = event.text_area.text
        # Don't save on every keystroke, only when user stops typing
        # We'll save when they click save button or leave the field

    @on(Button.Pressed, "#save_memory_button")
    def on_save_memory_button_pressed(self) -> None:
        """Handle save memory button press."""
        memory_textarea = self.query_one("#memory_textarea", TextArea)
        settings.user_memory = memory_textarea.text
        settings.save()
        self.notify("Memory saved successfully")

    @on(Button.Pressed, "#clear_memory_button")
    async def on_clear_memory_button_pressed(self) -> None:
        """Handle clear memory button press."""
        from parllama.dialogs.yes_no_dialog import YesNoDialog

        result = await self.app.push_screen_wait(
            YesNoDialog(
                title="Clear Memory",
                question="Are you sure you want to clear all memory content?\nThis action cannot be undone.",
                yes_label="Clear",
                no_label="Cancel",
            )
        )

        if result:
            memory_textarea = self.query_one("#memory_textarea", TextArea)
            memory_textarea.text = ""
            settings.user_memory = ""
            settings.save()
            self.notify("Memory cleared")

    @on(MemoryUpdated)
    def on_memory_updated(self, event: MemoryUpdated) -> None:
        """Handle memory updated event."""
        event.stop()
        # Update the textarea with the new memory content
        memory_textarea = self.query_one("#memory_textarea", TextArea)
        # Only update if the content is different to avoid cursor jumping
        if memory_textarea.text != event.new_content:
            memory_textarea.text = event.new_content

    async def on_mount(self) -> None:
        """Called when the widget is mounted."""
        # Register to receive memory updates
        self.app.post_message(RegisterForUpdates(widget=self, event_names=["MemoryUpdated"]))

        # Update the textarea with current memory content
        memory_textarea = self.query_one("#memory_textarea", TextArea)
        memory_textarea.text = settings.user_memory
