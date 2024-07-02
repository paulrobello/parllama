"""Widget for chatting with LLM."""
from __future__ import annotations

from textual import on
from textual import work
from textual.app import ComposeResult
from textual.containers import Container
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.containers import VerticalScroll
from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import Select
from textual.widgets import TabbedContent

from parllama.chat_manager import chat_manager
from parllama.data_manager import dm
from parllama.messages.main import ChatMessage
from parllama.messages.main import ChatMessageSent
from parllama.messages.main import LocalModelListLoaded
from parllama.messages.main import RegisterForUpdates
from parllama.models.chat import ChatSession
from parllama.models.chat import OllamaMessage
from parllama.models.settings_data import settings
from parllama.widgets.chat_message import ChatMessageWidget


class ChatView(Container, can_focus=False, can_focus_children=True):
    """Widget for viewing application logs."""

    DEFAULT_CSS = """
    ChatView {
      #tool_bar {
        height: 3;
        background: $surface-darken-1;
        #model_name {
          width: 40;
        }
        #temperature_input {
          width: 11;
        }
        #clear_button {
          margin-left: 2;
        }
        Label {
          margin: 1;
          background: transparent;
        }
      }
      #send_bar {
        height: 3;
        background: $surface-darken-1;
        #user_input {
          width: 1fr;
        }

        #send_button {
          width: 6;
        }
      }
      #messages {
        background: $primary-background;
        ChatMessageWidget{
            padding: 1;
            border: none;
            border-left: blank;
            &:focus {
                border-left: thick $primary;
            }
        }
        MarkdownH2 {
          margin: 0;
          padding: 0;
        }
      }
    }
    """

    model_select: Select[str]
    send_button: Button
    session: ChatSession | None = None
    busy: bool = False

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
        self.sub_title = "Application Logs"
        self.user_input = Input(
            id="user_input", placeholder="Type a message...", disabled=True
        )
        self.temperature_input = Input(
            id="temperature_input",
            value=f"{settings.last_chat_temperature:.2f}",
            max_length=4,
            restrict=r"^\d(?:\.\d+)?$",
        )

        self.send_button = Button("Send", id="send_button", disabled=True)
        self.model_select = Select(id="model_name", options=[])
        self.vs = VerticalScroll(id="messages")
        self.vs.can_focus = False
        self.busy = False

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with Vertical(id="main"):
            with Horizontal(id="tool_bar"):
                yield Label("Model")
                yield self.model_select
                yield Label("Temperature")
                yield self.temperature_input
                yield Button("Clear", id="clear_button", variant="warning")
            yield self.vs
            with Horizontal(id="send_bar"):
                yield self.user_input
                yield self.send_button

    def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(RegisterForUpdates(widget=self))
        with self.screen.prevent(TabbedContent.TabActivated):
            self.model_select.focus()

    @on(Input.Changed, "#user_input")
    def on_user_input_changed(self) -> None:
        """Handle max lines input change"""
        self.update_control_states()

    @on(Input.Changed, "#temperature_input")
    def on_temperature_input_changed(self) -> None:
        """Handle temperature input change"""
        try:
            settings.last_chat_temperature = float(self.temperature_input.value)
        except ValueError:
            return
        settings.save_settings_to_file()

    def update_control_states(self):
        """Update disabled state of controls based on model and user input values"""
        self.user_input.disabled = self.busy or self.model_select.value == Select.BLANK
        self.send_button.disabled = (
            self.user_input.disabled or len(self.user_input.value) == 0
        )
        if self.model_select.value != Select.BLANK:
            with self.screen.prevent(TabbedContent.TabActivated):
                self.user_input.focus()

    @on(Select.Changed)
    def on_model_select_changed(self) -> None:
        """Model select changed, update control states and save model name"""
        self.update_control_states()
        if (
            not self.user_input.disabled
            and settings.last_chat_model != self.model_select.value
        ):
            settings.last_chat_model = str(self.model_select.value)
            settings.save_settings_to_file()

    @on(LocalModelListLoaded)
    def on_local_model_list_loaded(self) -> None:
        """Model list changed"""

        if self.model_select.value != Select.BLANK:
            old_v = self.model_select.value
        elif settings.last_chat_model:
            old_v = settings.last_chat_model
        else:
            old_v = Select.BLANK
        opts = dm.get_model_select_options()
        self.model_select.set_options(opts)
        for _, v in opts:
            if v == old_v:
                self.model_select.value = old_v
        self.update_control_states()

    @on(Button.Pressed, "#clear_button")
    def on_clear_button_pressed(self) -> None:
        """Clear button pressed"""
        if self.session:
            self.session.new_session()
            self.vs.remove_children("*")
            self.update_control_states()

    @on(Button.Pressed, "#send_button")
    @on(Input.Submitted, "#user_input")
    async def action_send_message(self) -> None:
        """Send the message."""
        if not self.model_select.value or self.model_select.value == Select.BLANK:
            return
        if not self.user_input.value:
            return

        if not self.temperature_input.value:
            self.temperature_input.value = "0.5"

        if self.busy:
            return
        self.busy = True
        self.update_control_states()
        try:
            if not self.session:
                self.session = chat_manager.get_or_create_session(
                    "Default",
                    str(self.model_select.value),
                    {"temperature": float(self.temperature_input.value)},
                )
            else:
                self.session.llm_model_name = str(self.model_select.value)
                self.session.options["temperature"] = float(
                    self.temperature_input.value
                )
            self.do_send_message(self.user_input.value)
        finally:
            self.user_input.value = ""
            self.busy = False
            self.update_control_states()

    @work(thread=True)
    async def do_send_message(self, msg: str) -> None:
        """Send the message."""
        if not self.session:
            return
        await self.session.send_chat(msg, self)
        self.post_message(ChatMessageSent())

    @on(ChatMessageSent)
    def on_chat_message_sent(self, msg: ChatMessageSent) -> None:
        """Handle a chat message sent"""
        msg.stop()
        if not self.user_input.disabled:
            self.user_input.focus()

    @on(ChatMessage)
    async def on_chat_message(self, event: ChatMessage) -> None:
        """Handle a chat message"""
        ses = chat_manager.get_session(event.session_id)
        if not ses:
            self.notify("Chat session not found", severity="error")
            return
        msg: OllamaMessage | None = ses.get_message(event.message_id)
        if not msg:
            self.notify("Chat message not found", severity="error")
            return

        msg_widget: ChatMessageWidget | None = None
        for w in self.query(ChatMessageWidget):
            if w.msg["id"] == msg["id"]:
                await w.update("")
                msg_widget = w
                break
        if not msg_widget:
            msg_widget = ChatMessageWidget.mk_msg_widget(msg=msg)
            await self.vs.mount(msg_widget)
        self.vs.scroll_to_widget(msg_widget)
