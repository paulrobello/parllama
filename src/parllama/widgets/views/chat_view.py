"""Widget for chatting with LLM."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from par_ai_core.llm_providers import (
    LlmProvider,
    get_provider_name_fuzzy,
    llm_provider_names,
)
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Show
from textual.suggester import SuggestFromList
from textual.widgets import Button, ContentSwitcher, Select, TabbedContent

from parllama.chat_manager import ChatSession, chat_manager
from parllama.chat_message import ParllamaChatMessage
from parllama.dialogs.information import InformationDialog
from parllama.messages.messages import (
    ChangeTab,
    ChatGenerationAborted,
    ChatMessage,
    ChatMessageSent,
    ClearChatInputHistory,
    DeleteSession,
    LogIt,
    PromptListChanged,
    PromptListLoaded,
    PromptSelected,
    ProviderModelsChanged,
    RegisterForUpdates,
    SessionSelected,
    SessionToPrompt,
    SessionUpdated,
    UpdateChatControlStates,
    UpdateTabLabel,
)
from parllama.provider_manager import provider_manager
from parllama.settings_manager import settings
from parllama.widgets.session_config import SessionConfig
from parllama.widgets.session_list import SessionList
from parllama.widgets.user_input import UserInput
from parllama.widgets.views.chat_tab import ChatTab

valid_commands: list[str] = [
    "/help",
    "/?",
    "/tab.",
    "/tab.remove",
    "/tabs.clear",
    "/session.",
    "/session.provider",
    "/session.model",
    "/session.temp",
    "/session.new",
    "/session.name",
    "/session.delete",
    "/session.export",
    "/session.system_prompt",
    "/session.clear_system_prompt",
    "/session.to_prompt",
    "/history.clear",
    "/add.image",
    "/prompt.load ",
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
            height: auto;
            min-height: 3;
            max-height: 15;
            background: $surface-darken-1;
            #send_button {
                min-width: 7;
                width: 7;
                margin-right: 1;
            }
            #stop_button {
                min-width: 6;
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
            key_display="^del",
            show=True,
        ),
        Binding(
            key="ctrl+e",
            action="export",
            description="Export",
            show=True,
            priority=True,
        ),
        Binding(
            key="ctrl+p",
            action="toggle_session_config",
            description="Config",
            show=True,
            priority=True,
        ),
    ]
    chat_tabs: TabbedContent
    provider_list_auto_complete_list: list[str]
    model_list_auto_complete_list: list[str]
    prompt_list_auto_complete_list: list[str]

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)

        self.session_list = SessionList()
        self.session_list.display = False

        self.chat_tabs = TabbedContent(id="chat_tabs")
        self.user_input: UserInput = UserInput(
            id="user_input",
            suggester=SuggestFromList(
                valid_commands,
                case_sensitive=False,
            ),
            history_file=Path(settings.chat_history_file),
        )

        self.send_button: Button = Button("Send", id="send_button", disabled=True, variant="success")
        self.stop_button: Button = Button("Stop", id="stop_button", disabled=True, variant="error")
        self.last_command = ""
        self.provider_list_auto_complete_list = [f"/session.provider {p}" for p in llm_provider_names]
        self.model_list_auto_complete_list = []
        self.prompt_list_auto_complete_list = []

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        yield self.session_list
        with self.chat_tabs:
            yield ChatTab(user_input=self.user_input, session_list=self.session_list)
        with Horizontal(id="send_bar"):
            yield self.user_input
            yield self.send_button
            yield self.stop_button

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "ProviderModelsChanged",
                    "DeleteSession",
                    "SessionSelected",
                    "PromptListLoaded",
                    "PromptListChanged",
                    "PromptSelected",
                ],
            )
        )
        self.prompt_list_auto_complete_list = [f"/prompt.load {prompt.name}" for prompt in chat_manager.sorted_prompts]

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.user_input.focus()

    @on(PromptListLoaded)
    def on_prompt_list_loaded(self, event: PromptListLoaded) -> None:
        """Prompt list changed"""
        event.stop()
        self.post_message(LogIt("Prompt list loaded"))
        self.prompt_list_auto_complete_list = [f"/prompt.load {prompt.name}" for prompt in chat_manager.sorted_prompts]
        self.rebuild_suggester()

    @on(UserInput.Changed)
    def on_user_input_changed(self, event: UserInput.Changed) -> None:
        """Handle max lines input change"""
        event.stop()
        self.update_control_states()

    def update_control_states(self):
        """Update disabled state of controls based on model and user input values"""
        self.send_button.disabled = (
            self.active_tab.busy
            or self.active_tab.session_config.provider_model_select.provider_select.value == Select.BLANK
            or self.active_tab.session_config.provider_model_select.model_select.value == Select.BLANK
            or len(self.user_input.value.strip()) == 0
        )
        self.stop_button.disabled = not self.active_tab.busy or self.session.abort_pending

    @on(ProviderModelsChanged)
    def model_list_changed(self, evt: ProviderModelsChanged) -> None:
        """Model list changed"""
        evt.stop()
        if not evt.provider or self.session_config.provider_model_select.provider_select.value != evt.provider:
            return
        self.post_message(LogIt("Provider models changed"))
        self.model_list_auto_complete_list = [
            f"/session.model {m}"
            for m in provider_manager.get_model_names(
                self.active_tab.session_config.provider_model_select.provider_select.value  # type: ignore
            )
        ]
        self.rebuild_suggester()
        self.update_control_states()

    @on(PromptListChanged)
    def on_prompt_list_changed(self, evt: PromptListChanged) -> None:
        """Prompt list changed"""
        evt.stop()
        self.post_message(LogIt("Prompt list changed"))
        self.prompt_list_auto_complete_list = [f"/prompt.load {prompt.name}" for prompt in chat_manager.sorted_prompts]
        self.rebuild_suggester()

    def rebuild_suggester(self) -> None:
        """Rebuild the suggester"""
        self.user_input.suggester = SuggestFromList(
            valid_commands
            + self.provider_list_auto_complete_list
            + self.model_list_auto_complete_list
            + self.prompt_list_auto_complete_list,
            case_sensitive=False,
        )

    @on(Button.Pressed, "#new_button")
    async def on_new_button_pressed(self, event: Button.Pressed) -> None:
        """New button pressed"""
        event.stop()
        await self.action_new_tab()

    @on(Button.Pressed, "#send_button")
    async def on_send_button_pressed(self, event: Button.Pressed) -> None:
        """Send button pressed"""
        event.stop()
        self.user_input.submit()

    @on(UserInput.Submitted)
    async def action_send_message(self, event: UserInput.Submitted) -> None:
        """Send the message."""
        event.stop()
        if settings.close_session_config_on_submit:
            self.active_tab.session_config.display = False

        self.user_input.focus()

        if self.send_button.disabled:
            return

        user_msg: str = event.value.strip()
        if not user_msg:
            return

        if self.active_tab.busy:
            self.notify("LLM Busy...", severity="error")
            return
        self.last_command = user_msg
        self.user_input.value = ""
        self.update_control_states()

        if user_msg.startswith("/"):
            return await self.handle_command(user_msg[1:].strip())

        self.active_tab.do_send_message(user_msg)

    # pylint: disable=too-many-statements,too-many-branches,too-many-return-statements
    async def handle_command(self, cmd_raw: str) -> None:
        """Handle a command"""
        cmd = cmd_raw.lower()
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
/session.provider [provider_name] - Select the AI provider dropdown or set provider name in current tab
/session.model [model_name] - Select model dropdown or set model name in current tab
/session.temp [temperature] - Select temperature input or set temperature in current tab
/session.delete - Delete the chat session for current tab
/session.export - Export the conversation in current tab to a Markdown file
/session.system_prompt [system_prompt] - Set system prompt in current tab
/session.clear_system_prompt - Remove system prompt in current tab
/session.to_prompt submit_on_load [prompt_name] - Copy current session to new custom prompt. submit_on_load = {0|1}
/prompt.load prompt_name - Load a custom prompt using current tabs model and temperature
/add.image image_path_or_url prompt - Add an image via path or url to the active chat session
/history.clear - Clear chat input history
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
            v = v.strip()
            await self.active_tab.action_new_session(v)
        elif cmd == "session.delete":
            self.app.post_message(DeleteSession(session_id=self.session.id))
        elif cmd == "session.provider":
            self.active_tab.session_config.display = True
            self.set_timer(
                0.1,
                self.active_tab.session_config.provider_model_select.provider_select.focus,
            )
            return
        elif cmd.startswith("session.provider "):
            (_, v) = cmd.split(" ", 1)
            v_org = v.strip()
            v = get_provider_name_fuzzy(v_org)
            if not v:
                self.notify(
                    f"Provider {v_org} not found in [{','.join(llm_provider_names)}]",
                    severity="error",
                )
                return
            self.active_tab.session_config.provider_model_select.provider_select.value = LlmProvider(v)
            self.set_timer(0.1, self.user_input.focus)
        elif cmd == "session.model":
            self.active_tab.session_config.display = True
            self.set_timer(
                0.1,
                self.active_tab.session_config.provider_model_select.model_select.focus,
            )
            return
        elif cmd.startswith("session.model "):
            (_, v) = cmd_raw.split(" ", 1)
            v = provider_manager.get_model_name_fuzzy(
                self.active_tab.session_config.provider_model_select.provider_select.value,  # type: ignore
                v.strip(),
            )
            if not v:
                self.notify(f"Model {v} not found", severity="error")
                return
            self.active_tab.session_config.provider_model_select.model_select.value = v
            self.set_timer(0.1, self.user_input.focus)
        elif cmd == "session.temp":
            self.set_timer(0.1, self.active_tab.session_config.temperature_input.focus)
            self.active_tab.session_config.display = True
        elif cmd.startswith("session.temp "):
            (_, v) = cmd.split(" ", 1)
            v = v.strip()
            self.active_tab.session_config.temperature_input.value = v
            self.set_timer(0.1, self.user_input.focus)
        elif cmd == "session.name":
            self.set_timer(0.1, self.active_tab.session_config.session_name_input.focus)
            self.active_tab.session_config.display = True
        elif cmd.startswith("session.name "):
            (_, v) = cmd.split(" ", 1)
            v = v.strip()
            self.active_tab.session_config.session_name_input.value = v
            await self.active_tab.session_config.session_name_input.action_submit()
        elif cmd.startswith("session.to_prompt "):
            vs: list[str] = cmd.split(" ", 2)
            if len(vs) == 2:
                (_, submit_on_load) = vs
                v = ""
            else:
                (_, submit_on_load, v) = vs
            v = v.strip()
            self.app.post_message(
                SessionToPrompt(
                    session_id=self.session.id,
                    submit_on_load=submit_on_load == "1",
                    prompt_name=v,
                )
            )
        elif cmd.startswith("session.export"):
            self.active_tab.save_conversation_text()
        elif cmd.startswith("session.clear_system_prompt"):
            self.session.system_prompt = None
        elif cmd.startswith("session.system_prompt "):
            (_, v) = cmd.split(" ", 1)
            v = v.strip()
            if not v:
                self.notify("System prompt cannot be empty", severity="error")
                return
            self.session.system_prompt = ParllamaChatMessage(role="system", content=v)
            self.active_tab.post_message(
                ChatMessage(
                    parent_id=self.session.id,
                    message_id=self.session.system_prompt.id,  # pyright: ignore [reportOptionalMemberAccess]
                    is_final=True,
                )
            )
        elif cmd.startswith("prompt.load "):
            (_, v) = cmd.split(" ", 1)
            v = v.strip()
            prompt = chat_manager.get_prompt_by_name(v)
            if prompt is None:
                self.notify(f"Prompt {v} not found", severity="error")
                return
            await self.active_tab.load_prompt(
                PromptSelected(
                    prompt_id=prompt.id,
                    model_name=None,
                    temperature=None,
                )
            )
        elif cmd.startswith("add.image "):
            parts = cmd.split(" ")
            if len(parts) < 3:
                self.notify("Usage add.image FILE_NAME PROMPT", severity="error")
            v = parts[1].strip()
            p = " ".join(parts[2:])
            if v.startswith("http://") or v.startswith("https://"):
                msg = ParllamaChatMessage(role="user", content=p, images=[v])
            else:
                path = Path(v)
                if not path.exists():
                    self.notify(f"Image {v} not found", severity="error")
                    return
                msg = ParllamaChatMessage(role="user", content=p, images=[str(path.absolute())])

            self.session.add_message(msg)
            self.post_message(ChatMessage(parent_id=self.session.id, message_id=msg.id))
            self.active_tab.do_send_message("")
        elif cmd == "history.clear":
            self.app.post_message(ClearChatInputHistory())
        else:
            self.notify(f"Unknown command: {cmd}", severity="error")

    @on(Button.Pressed, "#stop_button")
    def on_stop_button_pressed(self, event: Button.Pressed) -> None:
        """Stop button pressed"""
        event.stop()
        self.stop_button.disabled = True
        self.active_tab.session.stop_generation()
        # self.workers.cancel_group(self, "message_send")
        self.workers.cancel_node(self.active_tab)
        self.active_tab.busy = False

    @on(ChatMessageSent)
    def on_chat_message_sent(self, event: ChatMessageSent) -> None:
        """Handle a chat message sent"""
        event.stop()
        if self.session.id == event.session_id:
            self.stop_button.disabled = True

    @on(SessionUpdated)
    async def session_updated(self, event: SessionUpdated) -> None:
        """Session updated event"""
        event.stop()
        session = chat_manager.get_session(event.session_id)
        if session != self.session:
            return
        # self.notify(f"Chat View session updated {','.join([*event.changed])}")
        if "provider" in event.changed:
            self.model_list_changed(ProviderModelsChanged())

    def action_toggle_session_list(self) -> None:
        """Toggle the session list."""
        self.session_list.display = not self.session_list.display
        if self.session_list.display:
            self.set_timer(0.1, self.session_list.list_view.focus)
        else:
            self.set_timer(0.1, self.user_input.focus)

    @on(SessionSelected)
    async def session_selected(self, event: SessionSelected) -> None:
        """Session selected event"""
        event.stop()
        if event.new_tab:
            await self.action_new_tab()
            await self.active_tab.load_session(event.session_id)
        else:
            await self.active_tab.load_session(event.session_id)

    @on(PromptSelected)
    async def prompt_selected(self, event: PromptSelected) -> None:
        """Prompt selected event"""
        event.stop()
        await self.action_new_tab()
        await self.active_tab.load_prompt(event)
        self.app.post_message(ChangeTab(tab="Chat"))

    @on(UpdateChatControlStates)
    def update_chat_control_states(self, event: UpdateChatControlStates) -> None:
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

    @property
    def ai_provider(self) -> LlmProvider:
        """Get the AI provider"""
        v = self.session_config.provider_model_select.provider_select.value
        if v == Select.BLANK:
            return LlmProvider.OLLAMA
        return v  # type: ignore

    @property
    def ai_model(self) -> str:
        """Get the AI model"""
        v = self.session_config.provider_model_select.model_select.value
        if v == Select.BLANK:
            return ""
        return str(v)

    @property
    def session_config(self) -> SessionConfig:
        """Get the session config"""
        return self.active_tab.session_config

    @on(ChatMessage)
    async def on_chat_message(self, event: ChatMessage) -> None:
        """Route chat message to correct tab"""
        event.stop()
        for tab in self.chat_tabs.query(ChatTab):
            if tab.session.id == event.parent_id:
                await tab.on_chat_message(event)

    @on(UpdateTabLabel)
    def on_update_tab_label(self, event: UpdateTabLabel) -> None:
        """Update tab label event"""
        event.stop()
        # self.notify(f"Updated tab label: {event.tab_label}")
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
        self.app.post_message(LogIt(f"Deleted chat session {event.session_id}"))
        tab_removed: bool = False
        for tab in self.chat_tabs.query(ChatTab):
            if tab.session.id == event.session_id:
                await self.chat_tabs.remove_pane(str(tab.id))
                tab_removed = True

        chat_manager.delete_session(event.session_id)
        if len(self.chat_tabs.query(ChatTab)) == 0:
            await self.action_new_tab()
        elif tab_removed:
            self.re_index_labels()

        self.notify("Chat session deleted")
        # self.user_input.focus()

    async def action_new_tab(self) -> None:
        """New tab action"""
        tab = ChatTab(user_input=self.user_input, session_list=self.session_list)
        await self.chat_tabs.add_pane(tab)
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

    @on(ChatGenerationAborted)
    def on_chat_generation_aborted(self, event: ChatGenerationAborted) -> None:
        """Chat generation aborted event"""
        event.stop()
        self.notify("Chat Aborted", severity="warning")

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, msg: TabbedContent.TabActivated) -> None:
        """Prevent Tab activated event bubble"""
        msg.stop()

    def action_toggle_session_config(self) -> None:
        """Toggle session configuration panel"""
        self.active_tab.action_toggle_session_config()
