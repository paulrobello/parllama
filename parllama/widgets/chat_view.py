"""Widget for chatting with LLM."""
from __future__ import annotations

from textual import on
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.containers import VerticalScroll
from textual.events import Focus
from textual.events import Show
from textual.message import Message
from textual.reactive import Reactive
from textual.suggester import SuggestFromList
from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import Select
from textual.widgets import TabbedContent

from parllama.chat_manager import chat_manager
from parllama.data_manager import dm
from parllama.dialogs.information import InformationDialog
from parllama.messages.main import ChatMessage
from parllama.messages.main import ChatMessageSent
from parllama.messages.main import LocalModelListLoaded
from parllama.messages.main import RegisterForUpdates
from parllama.models.chat import ChatSession
from parllama.models.chat import OllamaMessage
from parllama.models.settings_data import settings
from parllama.screens.save_session import SaveSession
from parllama.widgets.chat_message import ChatMessageWidget
from parllama.widgets.input_tab_complete import InputTabComplete
from parllama.widgets.session_list import SessionList

valid_commands: list[str] = [
    "/clear",
    "/save",
    "/model",
    "/temp",
    "/session",
    "/help",
    "/?",
]


class ChatView(Container, can_focus=False, can_focus_children=True):
    """Widget for viewing application logs."""

    DEFAULT_CSS = """
    ChatView {
      layers: left;
      #tool_bar {
        height: 3;
        background: $surface-darken-1;
        #model_name {
          max-width: 40;
        }
        #temperature_input {
          width: 11;
        }
        #session_name_input {
          min-width: 15;
          max-width: 40;
          width: auto;
        }
        #clear_button {
          margin-left: 2;
          min-width: 9;
          background: $warning-darken-2;
          border-top: tall $warning-lighten-1;
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

    BINDINGS = [
        Binding(
            key="ctrl+s",
            action="toggle_session_list",
            description="Sessions",
            show=True,
        ),
    ]
    session: ChatSession | None = None
    busy: Reactive[bool] = Reactive(False)

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)

        self.model_select: Select[str] = Select(
            id="model_name", options=[], prompt="Select Model"
        )
        self.temperature_input: Input = Input(
            id="temperature_input",
            value=(
                f"{settings.last_chat_temperature:.2f}"
                if settings.last_chat_temperature
                else ""
            ),
            max_length=4,
            restrict=r"^\d(?:\.\d+)?$",
        )
        self.session_name_input: Input = Input(id="session_name_input", value="My Chat")
        self.user_input: InputTabComplete = InputTabComplete(
            id="user_input",
            placeholder="Type a message...",
            suggester=SuggestFromList(
                valid_commands,
                case_sensitive=False,
            ),
            submit_on_tab=False,
            submit_on_complete=False,
        )

        self.send_button: Button = Button("Send", id="send_button", disabled=True)
        self.vs: VerticalScroll = VerticalScroll(id="messages")
        self.vs.can_focus = False
        self.busy = False
        self.session_list = SessionList()
        self.session_list.display = False

    def _watch_busy(self, value: bool) -> None:
        """Update controls when busy changes"""
        self.update_control_states()
        if value:
            self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
                "Chat - Thinking..."
            )
        else:
            self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
                "Chat"
            )

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        yield self.session_list
        with Vertical(id="main"):
            with Horizontal(id="tool_bar"):
                yield self.model_select
                yield Label("Temp")
                yield self.temperature_input
                yield Label("Session")
                yield self.session_name_input
                yield Button("Clear", id="clear_button", variant="warning")
            yield self.vs
            with Horizontal(id="send_bar"):
                yield self.user_input
                yield self.send_button

    def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(RegisterForUpdates(widget=self))

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self._watch_busy(self.busy)
        with self.screen.prevent(TabbedContent.TabActivated):
            if self.model_select.value == Select.BLANK:
                self.model_select.focus()
            else:
                self.user_input.focus()

    @on(Input.Changed, "#user_input")
    def on_user_input_changed(self) -> None:
        """Handle max lines input change"""
        self.update_control_states()

    @on(Input.Changed, "#temperature_input")
    def on_temperature_input_changed(self) -> None:
        """Handle temperature input change"""
        try:
            if self.temperature_input.value:
                settings.last_chat_temperature = float(self.temperature_input.value)
            else:
                settings.last_chat_temperature = None
        except ValueError:
            return
        settings.save_settings_to_file()

    @on(Input.Changed, "#session_name_input")
    def on_session_name_input_changed(self) -> None:
        """Handle session name input change"""
        session_name: str = self.session_name_input.value.strip()
        if not session_name:
            return
        if self.session is not None:
            self.session.session_name = session_name

        settings.last_chat_session_name = session_name

    def update_control_states(self):
        """Update disabled state of controls based on model and user input values"""
        self.send_button.disabled = (
            self.busy
            or self.model_select.value == Select.BLANK
            or len(self.user_input.value.strip()) == 0
        )

    @on(Select.Changed)
    def on_model_select_changed(self) -> None:
        """Model select changed, update control states and save model name"""
        self.update_control_states()
        if self.model_select.value not in (Select.BLANK, settings.last_chat_model):
            settings.last_chat_model = str(self.model_select.value)
            settings.save_settings_to_file()

    @on(LocalModelListLoaded)
    def on_local_model_list_loaded(self, evt: LocalModelListLoaded) -> None:
        """Model list changed"""
        evt.stop()
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
        if self.model_select.value != Select.BLANK:
            with self.screen.prevent(Focus):
                self.user_input.focus()

        self.user_input.suggester = SuggestFromList(
            valid_commands + [f"/model {m.model.name}" for m in dm.models],
            case_sensitive=False,
        )

    @on(Button.Pressed, "#clear_button")
    def on_clear_button_pressed(self) -> None:
        """Clear button pressed"""
        self.action_clear_messages()

    def action_clear_messages(self) -> None:
        """Clear messages."""
        if self.session:
            self.session.new_session(self.session_name_input.value.strip() or "My Chat")
            self.vs.remove_children("*")
            self.update_control_states()
        self.user_input.focus()

    @on(Button.Pressed, "#send_button")
    @on(Input.Submitted, "#user_input")
    async def action_send_message(self, event: Message) -> None:
        """Send the message."""
        event.stop()
        if self.model_select.value == Select.BLANK:
            self.model_select.focus()
            return

        self.user_input.focus()

        if self.send_button.disabled:
            return

        user_msg: str = self.user_input.value.strip()
        if not user_msg:
            return

        if self.busy:
            self.notify("LLM Busy...", severity="error")
            return

        self.update_control_states()
        if not self.session:
            self.session = chat_manager.get_or_create_session(
                self.session_name_input.value or "My Chat",
                str(self.model_select.value),
                {
                    "temperature": (
                        float(self.temperature_input.value)
                        if self.temperature_input.value
                        else None
                    )
                },
            )
        else:
            self.session.llm_model_name = str(self.model_select.value)
            if self.temperature_input.value:
                self.session.options["temperature"] = float(
                    self.temperature_input.value
                )
            else:
                del self.session.options["temperature"]
        self.user_input.value = ""
        if user_msg.startswith("/"):
            return self.handle_command(user_msg[1:].lower().strip())
        self.busy = True
        self.do_send_message(user_msg)

    def handle_command(self, cmd: str) -> None:
        """Handle a command"""
        if cmd in ("?", "help"):
            self.app.push_screen(
                InformationDialog(
                    title="Chat Commands",
                    message="""
Chat Commands:
/clear - Clear the chat
/model [model_name] - Select a model
/temp [temperature] - Set the temperature
/session [session_name] - Set the session name
/save - Save the conversation to a file
                    """,
                )
            )
            return

        if self.session is None:
            return
        if cmd == "clear":
            self.action_clear_messages()
        elif cmd == "model":
            self.set_timer(0.1, self.model_select.focus)
            return
        elif cmd.startswith("model "):
            (_, v) = cmd.split(" ", 1)
            if v not in [m.model.name for m in dm.models]:
                self.notify(f"Model {v} not found", severity="error")
                return
            self.model_select.value = v
            self.set_timer(0.1, self.user_input.focus)
        elif cmd == "temp":
            self.set_timer(0.1, self.temperature_input.focus)
        elif cmd.startswith("temp "):
            (_, v) = cmd.split(" ", 1)
            self.temperature_input.value = v
            self.set_timer(0.1, self.user_input.focus)
        elif cmd == "session":
            self.set_timer(0.1, self.session_name_input.focus)
        elif cmd.startswith("session "):
            (_, v) = cmd.split(" ", 1)
            self.session_name_input.value = v
            self.set_timer(0.1, self.user_input.focus)
        elif cmd.startswith("save"):
            self._save_conversation_text()
            # filename: str = "chat_test.md"
            # if self.session.save(filename):
            #     self.notify(f"Saved: {filename}")
            # else:
            #     self.notify(f"Failed to save: {filename}", severity="error")
        else:
            self.notify(f"Unknown command: {cmd}", severity="error")

    @work(thread=True)
    async def do_send_message(self, msg: str) -> None:
        """Send the message."""

        if self.session is None:
            return
        await self.session.send_chat(msg, self)
        self.post_message(ChatMessageSent())

    @on(ChatMessageSent)
    def on_chat_message_sent(self, msg: ChatMessageSent) -> None:
        """Handle a chat message sent"""
        msg.stop()
        self.busy = False

    @on(ChatMessage)
    async def on_chat_message(self, event: ChatMessage) -> None:
        """Handle a chat message"""
        event.stop()

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
            if w.msg.id == msg.id:
                await w.update("")
                msg_widget = w
                break
        if not msg_widget:
            msg_widget = ChatMessageWidget.mk_msg_widget(msg=msg)
            await self.vs.mount(msg_widget)
        msg_widget.loading = len(msg_widget.msg.content) == 0
        if self.user_input.has_focus:
            self.set_timer(0.05, self.scroll_to_bottom)

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the chat window."""
        self.vs.scroll_to(y=self.vs.scroll_y + self.vs.size.height)

    @work
    async def _save_conversation_text(self) -> None:
        """Save the conversation as a Markdown document."""
        # Prompt the user with a save dialog, to get the name of a file to
        # save to.
        if (target := await SaveSession.get_filename(self.app)) is None:
            return

        # If the user didn't give an extension, add a default.
        if not target.suffix:
            target = target.with_suffix(".md")

        # Save the Markdown to the target file.
        target.write_text(str(self.session), encoding="utf-8")

        # Let the user know the save happened.
        self.notify(str(target), title="Saved")

    def action_toggle_session_list(self) -> None:
        """Toggle the session list."""
        self.session_list.display = not self.session_list.display
