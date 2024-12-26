"""Chat tab"""

from __future__ import annotations

import uuid
from functools import partial
from typing import cast

import humanize
from par_ai_core.utils import str_ellipsis
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Show
from textual.reactive import Reactive
from textual.widgets import Static, TabbedContent, TabPane

from parllama.chat_manager import ChatSession, chat_manager
from parllama.chat_message import ParllamaChatMessage
from parllama.messages.messages import (
    ChatMessage,
    ChatMessageDeleted,
    ChatMessageSent,
    DeleteSession,
    PromptSelected,
    SessionSelected,
    SessionUpdated,
    UnRegisterForUpdates,
    UpdateChatControlStates,
    UpdateChatStatus,
    UpdateTabLabel,
)
from parllama.models.ollama_data import FullModel
from parllama.ollama_data_manager import ollama_dm
from parllama.provider_manager import provider_manager
from parllama.screens.save_session import SaveSession
from parllama.settings_manager import settings
from parllama.widgets.chat_message_list import ChatMessageList
from parllama.widgets.chat_message_widget import ChatMessageWidget
from parllama.widgets.session_config import SessionConfig
from parllama.widgets.session_list import SessionList
from parllama.widgets.user_input import UserInput


class ChatTab(TabPane):
    """Chat tab"""

    BINDINGS = [
        Binding(
            key="ctrl+p",
            action="toggle_session_config",
            description="Config",
            show=True,
            priority=True,
        ),
    ]
    DEFAULT_CSS = """
    """

    busy: Reactive[bool] = Reactive(False)

    def __init__(self, user_input: UserInput, session_list: SessionList, **kwargs) -> None:
        """Initialise the view."""
        self.session_config = SessionConfig(id="session_config")

        session_name = self.session_config.session.name
        super().__init__(
            id=f"tp_{uuid.uuid4().hex}",
            title=str_ellipsis(session_name, settings.chat_tab_max_length),
            **kwargs,
        )
        self.session_list = session_list
        self.user_input = user_input

        self.vs: ChatMessageList = ChatMessageList(id="messages")
        self.busy = False

        self.session_status_bar = Static("", id="SessionStatusBar")

    @property
    def session(self) -> ChatSession:
        """Get the current session"""
        return self.session_config.session

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
        yield self.session_config
        with Vertical(id="main"):
            yield self.session_status_bar
            with self.vs:
                yield from [
                    ChatMessageWidget.mk_msg_widget(msg=m, session=self.session, is_final=True)
                    for m in self.session.messages
                ]

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        # self.app.post_message(
        #     RegisterForUpdates(
        #         widget=self,
        #         event_names=[
        #             "ChatMessageDeleted",
        #         ],
        #     )
        # )
        self.notify_tab_label_changed()

    async def on_unmount(self) -> None:
        """Remove dialog from updates when unmounted."""
        self.app.post_message(UnRegisterForUpdates(widget=self))

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self._watch_busy(self.busy)
        with self.screen.prevent(TabbedContent.TabActivated):
            self.user_input.focus()
        self.set_timer(0.1, self.update_session_select)
        self.update_control_states()

    def update_session_select(self) -> None:
        """Update session select on show"""
        self.session_list.post_message(SessionSelected(session_id=self.session.id))

    def update_control_states(self):
        """Update disabled state of controls based on model and user input values"""
        self.post_message(UpdateChatControlStates())

    def set_model_name(self, model_name: str) -> None:
        """Set model names"""
        self.session_config.set_model_name(model_name)

    async def action_new_session(self, session_name: str = "New Chat") -> None:
        """Start new session"""
        # self.notify("New session")
        await self.session_config.action_new_session(session_name)
        await self.vs.remove_children(ChatMessageWidget)
        self.update_control_states()
        self.on_update_chat_status()
        self.notify_tab_label_changed()
        self.user_input.focus()

    def notify_tab_label_changed(self) -> None:
        """Notify tab label changed"""
        # self.notify("notify tab label changed")
        self.post_message(
            UpdateTabLabel(
                str(self.id),
                str_ellipsis(self.session.name, settings.chat_tab_max_length),
            )
        )

    @on(ChatMessageDeleted)
    async def on_chat_message_deleted(self, event: ChatMessageDeleted) -> None:
        """Handle a chat message deleted"""
        event.stop()

        if self.session.id != event.parent_id:
            self.notify("Chat session id missmatch", severity="error")
            return

        for w in cast(list[ChatMessageWidget], self.query(f"#cm_{event.message_id}")):
            await w.remove()
            self.on_update_chat_status()
            break

    @on(ChatMessage)
    async def on_chat_message(self, event: ChatMessage) -> None:
        """Handle a chat message"""

        if self.session.id != event.parent_id:
            self.notify("Chat session id missmatch", severity="error")
            return
        msg: ParllamaChatMessage | None = self.session[event.message_id]
        if not msg:
            self.notify("Chat message not found", severity="error")
            return

        msg_widget: ChatMessageWidget | None = None
        for w in cast(list[ChatMessageWidget], self.query(f"#cm_{msg.id}")):
            msg_widget = w
            w.is_final = event.is_final or w.role == "system"
            await w.update()
            break
        if not msg_widget:
            msg_widget = ChatMessageWidget.mk_msg_widget(msg=msg, session=self.session, is_final=event.is_final)
            if msg.role == "system":
                await self.vs.mount(msg_widget, before=0)
            else:
                await self.vs.mount(msg_widget)
        msg_widget.loading = len(msg_widget.msg.content) == 0

        if self.user_input.child_has_focus:
            self.set_timer(0.1, self.scroll_to_bottom)

        # chat_manager.notify_sessions_changed()
        self.on_update_chat_status()

    def scroll_to_bottom(self, animate: bool = True) -> None:
        """Scroll to the bottom of the chat window."""
        self.vs.scroll_to(y=self.vs.max_scroll_y, animate=animate)
        # self.vs.scroll_end(force=True)

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

    async def load_session(self, session_id: str) -> None:
        """Load a session"""
        # self.app.post_message(LogIt("CT load_session: " + session_id))

        if not await self.session_config.load_session(session_id):
            return
        await self.vs.remove_children(ChatMessageWidget)
        await self.vs.mount(
            *[
                ChatMessageWidget.mk_msg_widget(msg=m, session=self.session, is_final=True)
                for m in self.session.messages
            ]
        )
        self.set_timer(0.25, partial(self.scroll_to_bottom, False))
        self.update_control_states()
        self.notify_tab_label_changed()
        self.on_update_chat_status()
        self.user_input.focus()

    async def load_prompt(self, event: PromptSelected) -> None:
        """Load a session"""
        if not await self.session_config.load_prompt(event):
            return

        prompt = chat_manager.get_prompt(event.prompt_id)
        if not prompt:
            return

        with self.session.batch_changes():
            for m in prompt.messages:
                self.session.add_message(
                    ParllamaChatMessage(
                        role=m.role,
                        content=m.content,
                        images=m.images,
                        tool_calls=m.tool_calls,
                    )
                )
        await self.vs.remove_children(ChatMessageWidget)
        await self.vs.mount(
            *[
                ChatMessageWidget.mk_msg_widget(msg=m, session=self.session, is_final=True)
                for m in self.session.messages
            ]
        )

        self.set_timer(0.25, partial(self.scroll_to_bottom, False))
        self.session_config.display = False
        self.update_control_states()
        self.notify_tab_label_changed()
        self.on_update_chat_status()
        self.user_input.focus()
        if prompt.submit_on_load:
            self.do_send_message("")

    @on(SessionSelected)
    async def on_session_selected(self, event: SessionSelected) -> None:
        """Session selected event"""
        event.stop()
        await self.load_session(event.session_id)

    @on(DeleteSession)
    async def on_delete_session(self, event: DeleteSession) -> None:
        """Delete session event"""
        event.stop()
        chat_manager.delete_session(event.session_id)
        self.notify("Chat session deleted")
        if self.session.id == event.session_id:
            await self.action_new_session()

    @on(SessionUpdated)
    def session_updated(self, event: SessionUpdated) -> None:
        """Handle a session updated event"""
        # self.notify(f"Chat tab updated: {event.changed}")
        # Allow event to propagate to parent
        # event.stop()
        if "name" in event.changed:
            self.notify_tab_label_changed()
        if "model_name" in event.changed or "messages" in event.changed or "num_ctx" in event.changed:
            self.on_update_chat_status()

    @work(group="get_details", thread=True)
    async def get_model_details(self, model: FullModel) -> None:
        """Fetch model details"""
        ollama_dm.enrich_model_details(model)
        if not model.modelinfo:
            return
        self.post_message(UpdateChatStatus())

    def on_update_chat_status(self) -> None:
        """Update session status bar"""
        parts = [
            self.session.llm_provider_name,
            " : ",
            str_ellipsis(self.session.llm_model_name, 25, ""),
            " : CTX Len: ",
            humanize.intcomma(int(self.session.context_length / 3)),
            " / ",
            humanize.intcomma(
                self.session.llm_config.num_ctx
                or (
                    provider_manager.get_model_context_length(
                        self.session.llm_provider_name, self.session.llm_model_name
                    )
                )
            ),
        ]

        stats = self.session.stats
        if stats:
            if stats.eval_count:
                parts.append(f" | Res Tkns / Sec: {stats.eval_count / (stats.eval_duration or 1):.1f}")

        self.session_status_bar.update(Text.assemble(*parts))
        self.update_control_states()

    async def action_delete_msg(self) -> None:
        """Handle the delete message action."""
        ret = self.vs.query("ChatMessageWidget:focus")
        if len(ret) != 1:
            return
        msg: ChatMessageWidget = cast(ChatMessageWidget, ret[0])
        del self.session[msg.msg.id]
        await msg.remove()
        self.session.save()
        self.on_update_chat_status()
        if len(self.session) == 0:
            self.user_input.focus()

    @work(thread=True, name="msg_send_worker")
    async def do_send_message(self, msg: str) -> None:
        """Send the message."""
        self.busy = True
        await self.session.send_chat(msg)
        self.post_message(ChatMessageSent(self.session.id))

    @on(ChatMessageSent)
    def on_chat_message_sent(self) -> None:
        """Handle a chat message sent"""
        self.busy = False

    def action_toggle_session_config(self) -> None:
        """Toggle session configuration panel"""
        self.session_config.display = not self.session_config.display
