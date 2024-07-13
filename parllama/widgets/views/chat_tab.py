"""Chat tab"""
from __future__ import annotations

from ollama import Options
from textual import on
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.containers import VerticalScroll
from textual.events import Focus
from textual.events import Show
from textual.reactive import Reactive
from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import Select
from textual.widgets import TabbedContent
from textual.widgets import TabPane

from parllama.chat_manager import chat_manager
from parllama.data_manager import dm
from parllama.messages.main import ChatMessage
from parllama.messages.main import DeleteSession
from parllama.messages.main import LocalModelListLoaded
from parllama.messages.main import RegisterForUpdates
from parllama.messages.main import SessionSelected
from parllama.messages.main import UpdateChatControlStates
from parllama.messages.main import UpdateTabLabel
from parllama.models.chat import ChatSession
from parllama.models.chat import OllamaMessage
from parllama.models.settings_data import settings
from parllama.screens.save_session import SaveSession
from parllama.utils import str_ellipsis
from parllama.widgets.chat_message import ChatMessageWidget
from parllama.widgets.input_tab_complete import InputTabComplete
from parllama.widgets.session_list import SessionList

MAX_TAB_TITLE_LENGTH = 12


class ChatTab(TabPane):
    """Chat tab"""

    BINDINGS = [
        Binding(key="ctrl+b", action="new_session", description="New Chat", show=True),
    ]
    DEFAULT_CSS = """
    ChatTab {
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
        #new_button {
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

    # BINDINGS = []
    session: ChatSession
    busy: Reactive[bool] = Reactive(False)

    def __init__(
        self, user_input: InputTabComplete, session_list: SessionList, **kwargs
    ) -> None:
        """Initialise the view."""
        session_name = chat_manager.mk_session_name("New Chat")
        super().__init__(
            title=str_ellipsis(session_name, MAX_TAB_TITLE_LENGTH),
            **kwargs,
        )
        self.session_list = session_list
        self.user_input = user_input
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
            restrict=r"^\d?\.?\d?$",
        )
        self.session_name_input: Input = Input(
            id="session_name_input",
            value=session_name,
        )

        self.vs: VerticalScroll = VerticalScroll(id="messages")
        self.vs.can_focus = False
        self.busy = False

        self.session = chat_manager.get_or_create_session_name(
            session_name=session_name,
            model_name=str(self.model_select.value),
            options=self.get_session_options(),
        )

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
        with Vertical(id="main"):
            with Horizontal(id="tool_bar"):
                yield self.model_select
                yield Label("Temp")
                yield self.temperature_input
                yield Label("Session")
                yield self.session_name_input
                yield Button("New", id="new_button", variant="warning")
            with self.vs:
                yield from [
                    ChatMessageWidget.mk_msg_widget(msg=m)
                    for m in self.session.messages
                ]

    async def on_mount(self) -> None:
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
        self.set_timer(0.1, self.update_session_select)
        self.update_control_states()

    def update_session_select(self) -> None:
        """Update session select on show"""
        self.session_list.post_message(
            SessionSelected(session_id=self.session.session_id)
        )

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
        self.session.set_temperature(settings.last_chat_temperature)
        settings.save_settings_to_file()
        chat_manager.notify_changed()

    @on(Input.Changed, "#session_name_input")
    def on_session_name_input_changed(self) -> None:
        """Handle session name input change"""
        session_name: str = self.session_name_input.value.strip()
        if not session_name:
            return
        settings.last_chat_session_name = session_name
        settings.save_settings_to_file()
        self.session.set_name(settings.last_chat_session_name)
        self.notify_tab_label_changed()
        chat_manager.notify_changed()

    def update_control_states(self):
        """Update disabled state of controls based on model and user input values"""
        self.post_message(UpdateChatControlStates())

    @on(Select.Changed)
    def on_model_select_changed(self) -> None:
        """Model select changed, update control states and save model name"""
        self.update_control_states()
        if self.model_select.value not in (Select.BLANK, settings.last_chat_model):
            settings.last_chat_model = str(self.model_select.value)
            settings.save_settings_to_file()
        self.session.set_llm_model(self.model_select.value)  # type: ignore

    def set_model_name(self, model_name: str) -> None:
        """ "Set model names"""
        for _, v in dm.get_model_select_options():
            if v == model_name:
                self.model_select.value = model_name
                return
        self.model_select.value = Select.BLANK

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

        # if self.model_select.value != Select.BLANK:
        #     self.session.set_llm_model(self.model_select.value)  # type: ignore
        #     #  TODO fix this smell
        #     if (
        #         self.parent
        #         and self.parent.parent
        #         and self.parent.parent.parent
        #         and cast(TabbedContent, self.parent.parent.parent).active == "Chat"
        #     ):
        #         self.user_input.focus()

    @on(Button.Pressed, "#new_button")
    async def on_new_button_pressed(self, event: Button.Pressed) -> None:
        """New button pressed"""
        event.stop()
        await self.action_new_session()

    def get_session_options(self) -> Options | None:
        """Get session options"""
        if not self.temperature_input.value:
            return None
        return {"temperature": (float(self.temperature_input.value))}

    async def action_new_session(self, session_name: str = "New Chat") -> None:
        """Start new session"""
        self.notify("new session")
        with self.prevent(Input.Changed):
            self.session = chat_manager.new_session(
                session_name=session_name,
                model_name=str(self.model_select.value),
                options=self.get_session_options(),
            )
            self.session_name_input.value = self.session.session_name
        self.notify_tab_label_changed()
        await self.vs.remove_children("*")
        self.update_control_states()
        model = dm.get_model_by_name(str(self.model_select.value))
        if model:
            msgs = model.get_messages()
            for msg in msgs:
                self.session.add_message(
                    OllamaMessage(role=msg["role"], content=msg["content"])
                )
        self.user_input.focus()

    def notify_tab_label_changed(self) -> None:
        """Notify tab label changed"""
        self.post_message(
            UpdateTabLabel(
                str(self.id),
                str_ellipsis(self.session.session_name, MAX_TAB_TITLE_LENGTH),
            )
        )

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
            if w.msg.message_id == msg.message_id:
                await w.update("")
                msg_widget = w
                break
        if not msg_widget:
            msg_widget = ChatMessageWidget.mk_msg_widget(msg=msg)
            await self.vs.mount(msg_widget)
        msg_widget.loading = len(msg_widget.msg.content) == 0
        if self.user_input.has_focus:
            self.set_timer(0.05, self.scroll_to_bottom)
        chat_manager.notify_changed()

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the chat window."""
        self.vs.scroll_to(y=self.vs.scroll_y + self.vs.size.height)

    @work
    async def save_conversation_text(self) -> None:
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

    def load_session(self, session_id: str) -> None:
        """Load a session"""
        session = chat_manager.get_session(session_id)
        if not session:
            self.notify("Chat session not found", severity="error")
            return
        self.session = session
        self.vs.remove_children("*")
        self.vs.mount(
            *[ChatMessageWidget.mk_msg_widget(msg=m) for m in self.session.messages]
        )
        with self.prevent(Focus, Input.Changed, Select.Changed):
            self.set_model_name(self.session.llm_model_name)
            self.temperature_input.value = str(
                self.session.options.get("temperature", "")
            )
            self.session_name_input.value = self.session.session_name
        self.update_control_states()
        self.notify_tab_label_changed()
        self.set_timer(0.05, self.scroll_to_bottom)
        self.user_input.focus()

    @on(SessionSelected)
    def on_session_selected(self, event: SessionSelected) -> None:
        """Session selected event"""
        event.stop()
        self.load_session(event.session_id)

    @on(DeleteSession)
    async def on_delete_session(self, event: DeleteSession) -> None:
        """Delete session event"""
        event.stop()
        chat_manager.delete_session(event.session_id)
        self.notify("Chat session deleted")
        if self.session.session_id == event.session_id:
            await self.action_new_session()
