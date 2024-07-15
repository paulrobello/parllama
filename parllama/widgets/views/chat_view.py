"""Widget for chatting with LLM."""
from __future__ import annotations

import re
from typing import cast

from textual import on
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.message import Message
from textual.suggester import SuggestFromList
from textual.widgets import Button
from textual.widgets import ContentSwitcher
from textual.widgets import Input
from textual.widgets import Select
from textual.widgets import TabbedContent

from parllama.chat_manager import chat_manager
from parllama.data_manager import dm
from parllama.dialogs.information import InformationDialog
from parllama.messages.main import ChatMessage
from parllama.messages.main import ChatMessageSent
from parllama.messages.main import DeleteSession
from parllama.messages.main import LocalModelListLoaded
from parllama.messages.main import RegisterForUpdates
from parllama.messages.main import SessionSelected
from parllama.messages.main import SessionUpdated
from parllama.messages.main import UpdateChatControlStates
from parllama.messages.main import UpdateTabLabel
from parllama.models.chat import ChatSession
from parllama.widgets.input_tab_complete import InputTabComplete
from parllama.widgets.session_list import SessionList
from parllama.widgets.views.chat_tab import ChatTab

valid_commands: list[str] = [
    "/help",
    "/?",
    "/tab.",
    "/tab.remove",
    "/tabs.clear",
    "/session.model",
    "/session.temp",
    "/session.new",
    "/session.name",
    "/session.delete",
    "/session.export",
]


class ChatView(Vertical, can_focus=False, can_focus_children=True):
    """Widget for viewing application logs."""

    DEFAULT_CSS = """
    ChatView {
      layers: left;
      SessionList {
        width: 40;
        height: 1fr;
        dock: left;
        padding: 1;
      }
      #chat_tabs {
        height: 1fr;
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
    }
    """

    BINDINGS = [
        Binding(
            key="ctrl+s",
            action="toggle_session_list",
            description="Sessions",
            show=True,
            priority=True,
        ),
        Binding(
            key="ctrl+b",
            action="new_session",
            description="New Session",
            show=True,
            priority=True,
        ),
        Binding(
            key="ctrl+n",
            action="new_tab",
            description="New Tab",
            show=True,
        ),
        Binding(
            key="ctrl+delete",
            action="remove_tab",
            description="Remove Tab",
            show=True,
        ),
        Binding(
            key="ctrl+e",
            action="export",
            description="Export",
            show=True,
            priority=True,
        ),
    ]
    chat_tabs: TabbedContent

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)

        self.session_list = SessionList()
        self.session_list.display = False

        self.chat_tabs = TabbedContent(id="chat_tabs")
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

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        yield self.session_list
        with self.chat_tabs:
            yield ChatTab(user_input=self.user_input, session_list=self.session_list)
        with Horizontal(id="send_bar"):
            yield self.user_input
            yield self.send_button

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(RegisterForUpdates(widget=self))

    @on(Input.Changed, "#user_input")
    def on_user_input_changed(self) -> None:
        """Handle max lines input change"""
        self.update_control_states()

    def update_control_states(self):
        """Update disabled state of controls based on model and user input values"""
        self.send_button.disabled = (
            self.active_tab.busy
            or self.active_tab.model_select.value == Select.BLANK
            or len(self.user_input.value.strip()) == 0
        )

    @on(LocalModelListLoaded)
    def on_local_model_list_loaded(self, evt: LocalModelListLoaded) -> None:
        """Model list changed"""
        evt.stop()
        for tab in self.chat_tabs.query(ChatTab):
            tab.on_local_model_list_loaded(evt)

        self.user_input.suggester = SuggestFromList(
            valid_commands + [f"/session.model {m.model.name}" for m in dm.models],
            case_sensitive=False,
        )

    @on(Button.Pressed, "#new_button")
    def on_new_button_pressed(self, event: Button.Pressed) -> None:
        """New button pressed"""
        event.stop()
        # TODO Add new tab

    @on(Button.Pressed, "#send_button")
    @on(Input.Submitted, "#user_input")
    async def action_send_message(self, event: Message) -> None:
        """Send the message."""
        event.stop()

        self.user_input.focus()

        if self.send_button.disabled:
            return

        user_msg: str = self.user_input.value.strip()
        if not user_msg:
            return

        if self.active_tab.busy:
            self.notify("LLM Busy...", severity="error")
            return

        self.update_control_states()
        self.user_input.value = ""
        if user_msg.startswith("/"):
            return await self.handle_command(user_msg[1:].lower().strip())
        self.active_tab.busy = True
        self.do_send_message(user_msg)

    # pylint: disable=too-many-branches
    async def handle_command(self, cmd: str) -> None:
        """Handle a command"""
        if cmd in ("?", "help"):
            await self.app.push_screen(
                InformationDialog(
                    title="Chat Commands",
                    message="""
Chat Commands:
/tab.# - Switch to the tab with the given number
/tab.new - Create new tab and switch to it
/tab.remove - Remove the active tab
/tabs.clear - Clear / remove all tabs
/session.new [session_name] - Start new chat session in current tab with optional name
/session.name [session_name] - Select session name input or set the session name in current tab
/session.model [model_name] - Select model dropdown or set model name in current tab
/session.temp [temperature] - Select temperature input or set temperature in current tab
/session.delete - Delete the chat session for current tab
/session.export - Export the conversation in current tab to a Markdown file
                    """,
                )
            )
            return

        tab_number_re = re.compile(r"^t(?:ab)?\.(\d+)$")
        if match := tab_number_re.match(cmd):
            (tab_number,) = match.groups()
            tab_number = int(tab_number) - 1
            if 0 <= tab_number <= len(self.chat_tabs.children):
                self.focus_tab(tab_number)
            else:
                self.notify(f"Tab {tab_number + 1} does not exist", severity="error")
            return
        if cmd == "tab.new":
            await self.action_new_tab()
        elif cmd == "tab.remove":
            await self.remove_active_tab()
        elif cmd == "tabs.clear":
            await self.remove_all_tabs()
        elif cmd == "session.new":
            await self.active_tab.action_new_session()
        elif cmd.startswith("session.new "):
            (_, v) = cmd.split(" ", 1)
            await self.active_tab.action_new_session(v)
        elif cmd == "session.delete":
            self.app.post_message(DeleteSession(session_id=self.session.session_id))
        elif cmd == "session.model":
            self.set_timer(0.1, self.active_tab.model_select.focus)
            return
        elif cmd.startswith("session.model "):
            (_, v) = cmd.split(" ", 1)
            if v not in [m.model.name for m in dm.models]:
                self.notify(f"Model {v} not found", severity="error")
                return
            self.active_tab.model_select.value = v
            self.set_timer(0.1, self.user_input.focus)
        elif cmd == "session.temp":
            self.set_timer(0.1, self.active_tab.temperature_input.focus)
        elif cmd.startswith("session.temp "):
            (_, v) = cmd.split(" ", 1)
            self.active_tab.temperature_input.value = v
            self.set_timer(0.1, self.user_input.focus)
        elif cmd == "session.name":
            self.set_timer(0.1, self.active_tab.session_name_input.focus)
        elif cmd.startswith("session.name "):
            (_, v) = cmd.split(" ", 1)
            self.active_tab.session_name_input.value = v
            self.set_timer(0.1, self.user_input.focus)
        elif cmd.startswith("session.export"):
            self.active_tab.save_conversation_text()
        else:
            self.notify(f"Unknown command: {cmd}", severity="error")

    @work(thread=True)
    async def do_send_message(self, msg: str) -> None:
        """Send the message."""
        await self.session.send_chat(msg, self)
        self.post_message(ChatMessageSent(self.session.session_id))

    @on(ChatMessageSent)
    def on_chat_message_sent(self, event: ChatMessageSent) -> None:
        """Handle a chat message sent"""
        event.stop()
        for tab in self.chat_tabs.query(ChatTab):
            if tab.session.session_id == event.session_id:
                tab.busy = False

    @on(SessionUpdated)
    async def on_session_updated(self, event: SessionUpdated) -> None:
        """Session updated event"""

        event.stop()
        session = chat_manager.get_session(event.session_id)
        if not session:
            return
        session.set_name(chat_manager.mk_session_name(session.session_name))
        for tab in self.chat_tabs.query(ChatTab):
            if tab.session.session_id == event.session_id:
                await tab.on_session_updated()

    def action_toggle_session_list(self) -> None:
        """Toggle the session list."""
        self.session_list.display = not self.session_list.display
        if self.session_list.display:
            self.set_timer(0.1, self.session_list.list_view.focus)
        else:
            self.set_timer(0.1, self.user_input.focus)

    @on(SessionSelected)
    async def on_session_selected(self, event: SessionSelected) -> None:
        """Session selected event"""
        event.stop()
        if event.new_tab:
            await self.action_new_tab()
            await self.active_tab.load_session(event.session_id)
        else:
            await self.active_tab.load_session(event.session_id)

    @on(UpdateChatControlStates)
    def on_update_chat_control_states(self, event: UpdateChatControlStates) -> None:
        """Update chat control states event"""
        event.stop()
        self.update_control_states()

    @property
    def active_tab(self) -> ChatTab:
        """Return the active chat tab."""
        return cast(ChatTab, self.chat_tabs.get_pane(self.chat_tabs.active))

    @property
    def session(self) -> ChatSession:
        """Return the active chat session."""
        return self.active_tab.session

    @on(ChatMessage)
    async def on_chat_message(self, event: ChatMessage) -> None:
        """Route chat message to correct tab"""
        event.stop()
        for tab in self.chat_tabs.query(ChatTab):
            if tab.session.session_id == event.session_id:
                await tab.on_chat_message(event)

    @on(UpdateTabLabel)
    def on_update_tab_label(self, event: UpdateTabLabel) -> None:
        """Update tab label event"""
        event.stop()
        tab = self.chat_tabs.get_tab(event.tab_id)
        tab_num = self.chat_tabs.get_child_by_type(ContentSwitcher).children.index(
            self.chat_tabs.get_pane(event.tab_id)
        )
        tab.label = f"[{tab_num + 1}] " + event.tab_label  # type: ignore

    def re_index_labels(self) -> None:
        """Re-index tab labels"""
        for ctab in self.chat_tabs.query(ChatTab):
            tab = self.chat_tabs.get_tab(str(ctab.id))
            tab_num = self.chat_tabs.get_child_by_type(ContentSwitcher).children.index(
                self.chat_tabs.get_pane(str(ctab.id))
            )
            tab.label = f"[{tab_num + 1}] " + tab.label.plain.split(" ", 1)[1]  # type: ignore

    @on(DeleteSession)
    async def on_delete_session(self, event: DeleteSession) -> None:
        """Delete session event"""
        event.stop()
        for tab in self.chat_tabs.query(ChatTab):
            if tab.session.session_id == event.session_id:
                await self.chat_tabs.remove_pane(str(tab.id))
                self.re_index_labels()
                break
        chat_manager.delete_session(event.session_id)
        if len(self.chat_tabs.query(ChatTab)) == 0:
            await self.action_new_tab()
        self.notify("Chat session deleted")
        self.user_input.focus()

    async def action_new_tab(self) -> None:
        """New tab action"""
        tab = ChatTab(user_input=self.user_input, session_list=self.session_list)
        await self.chat_tabs.add_pane(tab)
        tab.on_local_model_list_loaded(LocalModelListLoaded())
        self.chat_tabs.active = str(tab.id)

    async def remove_active_tab(self) -> None:
        """Remove the active tab"""
        await self.chat_tabs.remove_pane(self.chat_tabs.active)
        if len(self.chat_tabs.query(ChatTab)) == 0:
            await self.action_new_tab()
        else:
            self.re_index_labels()

    async def remove_all_tabs(self) -> None:
        """Remove all tabs"""
        for tab in self.chat_tabs.query(ChatTab):
            await self.chat_tabs.remove_pane(str(tab.id))
        await self.action_new_tab()

    def action_export(self) -> None:
        """Export chat to Markdown file"""
        self.active_tab.save_conversation_text()

    async def action_new_session(self) -> None:
        """Start a new chat session"""
        await self.active_tab.action_new_session()

    async def action_remove_tab(self) -> None:
        """Remove the active tab"""
        await self.remove_active_tab()

    def focus_tab(self, tab_num: int) -> None:
        """Focus requested tab"""
        tabs = self.chat_tabs.query(ChatTab)
        if len(tabs) > tab_num:
            self.chat_tabs.active = str(tabs[tab_num].id)
