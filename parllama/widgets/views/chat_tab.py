"""Chat tab"""

from __future__ import annotations

import uuid
from functools import partial
from typing import cast

import humanize
from ollama import Options
from rich.text import Text
from textual import on
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.events import Focus
from textual.events import Show
from textual.message import Message
from textual.reactive import Reactive
from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import Select
from textual.widgets import Static
from textual.widgets import TabbedContent
from textual.widgets import TabPane

from parllama.chat_manager import chat_manager
from parllama.chat_manager import ChatSession
from parllama.chat_message import OllamaMessage
from parllama.data_manager import dm
from parllama.messages.messages import ChatMessage
from parllama.messages.messages import ChatMessageSent
from parllama.messages.messages import DeleteSession
from parllama.messages.messages import LocalModelDeleted
from parllama.messages.messages import LogIt
from parllama.messages.messages import PromptSelected
from parllama.messages.messages import RegisterForUpdates
from parllama.messages.messages import SessionSelected
from parllama.messages.messages import SessionUpdated
from parllama.messages.messages import UnRegisterForUpdates
from parllama.messages.messages import UpdateChatControlStates
from parllama.messages.messages import UpdateChatStatus
from parllama.messages.messages import UpdateTabLabel
from parllama.models.ollama_data import FullModel
from parllama.settings_manager import settings
from parllama.screens.save_session import SaveSession
from parllama.utils import str_ellipsis
from parllama.widgets.chat_message_list import ChatMessageList
from parllama.widgets.chat_message_widget import ChatMessageWidget
from parllama.widgets.input_blur_submit import InputBlurSubmit
from parllama.widgets.local_model_select import LocalModelSelect
from parllama.widgets.session_list import SessionList
from parllama.widgets.user_input import UserInput


class ChatTab(TabPane):
    """Chat tab"""

    DEFAULT_CSS = """
    ChatTab {
        #tool_bar {
            height: 3;
            background: $surface-darken-1;
            #model_name {
                max-width: 40;
            }
        }
        #temperature_input {
            width: 12;
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
    """

    session: ChatSession
    busy: Reactive[bool] = Reactive(False)

    def __init__(
        self, user_input: UserInput, session_list: SessionList, **kwargs
    ) -> None:
        """Initialise the view."""
        session_name = chat_manager.mk_session_name("New Chat")
        super().__init__(
            id=f"tp_{uuid.uuid4().hex}",
            title=str_ellipsis(session_name, settings.chat_tab_max_length),
            **kwargs,
        )
        self.session_list = session_list
        self.user_input = user_input
        self.model_select: LocalModelSelect = LocalModelSelect(
            id="model_name",
        )
        self.temperature_input: InputBlurSubmit = InputBlurSubmit(
            id="temperature_input",
            value=(
                f"{settings.last_chat_temperature:.2f}"
                if settings.last_chat_temperature
                else ""
            ),
            max_length=4,
            restrict=r"^\d?\.?\d?\d?$",
            valid_empty=False,
        )
        self.session_name_input: InputBlurSubmit = InputBlurSubmit(
            id="session_name_input",
            value=session_name,
            valid_empty=False,
        )

        self.vs: ChatMessageList = ChatMessageList(id="messages")
        self.busy = False

        self.session = chat_manager.get_or_create_session(
            session_id=None,
            session_name=session_name,
            model_name=str(self.model_select.value),
            options=self.get_session_options(),
            widget=self,
        )

        self.session_status_bar = Static("", id="SessionStatusBar")

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
            yield self.session_status_bar
            with Horizontal(id="tool_bar"):
                yield self.model_select
                yield Label("Temp")
                yield self.temperature_input
                yield Label("Session")
                yield self.session_name_input
                yield Button("New", id="new_button", variant="warning")
            with self.vs:
                yield from [
                    ChatMessageWidget.mk_msg_widget(msg=m, session=self.session)
                    for m in self.session.messages
                ]

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "LocalModelDeleted",
                    "LocalModelListLoaded",
                    "SessionUpdated",
                ],
            )
        )

    async def on_unmount(self) -> None:
        """Remove dialog from updates when unmounted."""
        self.app.post_message(UnRegisterForUpdates(widget=self))

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
        self.session_list.post_message(SessionSelected(session_id=self.session.id))

    @on(Input.Submitted, "#temperature_input")
    def temperature_input_changed(self, event: Message) -> None:
        """Handle temperature input change"""
        event.stop()
        try:
            if self.temperature_input.value:
                settings.last_chat_temperature = float(self.temperature_input.value)
            else:
                settings.last_chat_temperature = None
        except ValueError:
            return
        self.session.temperature = settings.last_chat_temperature
        settings.save()
        # chat_manager.notify_sessions_changed()
        self.user_input.focus()

    @on(Input.Submitted, "#session_name_input")
    def session_name_input_changed(self, event: Input.Submitted) -> None:
        """Handle session name input change"""
        event.stop()
        event.prevent_default()
        # self.app.post_message(LogIt("CT session_name_input_changed"))
        session_name: str = self.session_name_input.value.strip()
        if not session_name:
            return
        with self.prevent(Input.Changed, Input.Submitted):
            self.session.name = chat_manager.mk_session_name(session_name)
        self.user_input.focus()
        settings.last_chat_session_id = self.session.id
        settings.save()

    def update_control_states(self):
        """Update disabled state of controls based on model and user input values"""
        self.post_message(UpdateChatControlStates())

    @on(Select.Changed, "#model_name")
    def model_select_changed(self) -> None:
        """Model select changed, update control states and save model name"""
        self.update_control_states()
        if self.model_select.value not in (Select.BLANK, settings.last_chat_model):
            settings.last_chat_model = str(self.model_select.value)
            settings.save()
        if self.model_select.value != Select.BLANK:
            self.session.llm_model_name = self.model_select.value  # type: ignore
        else:
            self.session.llm_model_name = ""
        self.on_update_chat_status()

    def set_model_name(self, model_name: str) -> None:
        """ "Set model names"""
        for _, v in dm.get_model_select_options():
            if v == model_name:
                self.model_select.value = model_name
                return
        self.model_select.value = Select.BLANK

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
        # self.notify("New session")
        with self.prevent(Input.Changed):
            old_session = self.session
            old_session.remove_sub(self)
            self.session = chat_manager.new_session(
                session_name=session_name,
                model_name=str(self.model_select.value),
                options=self.get_session_options(),
                widget=self,
            )
            self.session_name_input.value = self.session.name
            # self.session.batching = False

        await self.vs.remove_children(ChatMessageWidget)
        self.update_control_states()
        # model = dm.get_model_by_name(str(self.model_select.value))
        # if model:
        #     msgs = model.get_messages()
        #     for msg in msgs:
        #         self.session.add_message(
        #             OllamaMessage(
        #                 role=msg["role"],
        #                 content=msg["content"],
        #             )
        #         )
        self.on_update_chat_status()
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

    @on(ChatMessage)
    async def on_chat_message(self, event: ChatMessage) -> None:
        """Handle a chat message"""

        if self.session.id != event.parent_id:
            self.notify("Chat session id missmatch", severity="error")
            return
        msg: OllamaMessage | None = self.session[event.message_id]
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
            msg_widget = ChatMessageWidget.mk_msg_widget(msg=msg, session=self.session)
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
        self.app.post_message(LogIt("load_session: " + session_id))
        session = chat_manager.get_session(session_id, self)
        if session is None:
            self.notify(f"Chat session not found: {session_id}", severity="error")
            return
        session.load()
        old_session = self.session
        old_session.remove_sub(self)
        self.session = session
        await self.vs.remove_children(ChatMessageWidget)
        await self.vs.mount(
            *[
                ChatMessageWidget.mk_msg_widget(msg=m, session=self.session)
                for m in self.session.messages
            ]
        )
        with self.prevent(Focus, Input.Changed, Select.Changed):
            self.set_model_name(self.session.llm_model_name)
            if self.model_select.value == Select.BLANK:
                self.notify(
                    "Model defined in session is not installed", severity="warning"
                )
            self.temperature_input.value = str(
                self.session.options.get("temperature", "")
            )
            self.session_name_input.value = self.session.name
        self.set_timer(0.25, partial(self.scroll_to_bottom, False))
        self.update_control_states()
        self.notify_tab_label_changed()
        self.on_update_chat_status()
        self.user_input.focus()

    async def load_prompt(self, event: PromptSelected) -> None:
        """Load a session"""
        self.app.post_message(LogIt("load_prompt: " + event.prompt_id))
        self.app.post_message(
            LogIt(f"{event.prompt_id},{event.llm_model_name},{event.temperature}")
        )
        prompt = chat_manager.get_prompt(event.prompt_id)
        if prompt is None:
            self.notify(f"Prompt not found: {event.prompt_id}", severity="error")
            return
        prompt.load()
        self.app.post_message(LogIt(f"{prompt.id},{prompt.name}"))
        old_session = self.session
        old_session.remove_sub(self)
        opts = old_session.options
        if event.temperature is not None:
            opts["temperature"] = event.temperature
        self.session = chat_manager.new_session(
            session_name=prompt.name or old_session.name,
            model_name=event.llm_model_name or old_session.llm_model_name,
            options=opts,  # type: ignore
            widget=self,
        )
        with self.prevent(Focus, Input.Changed, Select.Changed):
            self.set_model_name(self.session.llm_model_name)

        with self.session.batch_changes():
            for m in prompt.messages:
                self.session.add_message(
                    OllamaMessage(
                        role=m.role,
                        content=m.content,
                        images=m.images,
                        tool_calls=m.tool_calls,
                    )
                )
        await self.vs.remove_children(ChatMessageWidget)
        await self.vs.mount(
            *[
                ChatMessageWidget.mk_msg_widget(msg=m, session=self.session)
                for m in self.session.messages
            ]
        )
        with self.prevent(Focus, Input.Changed, Select.Changed):
            self.set_model_name(self.session.llm_model_name)
            if self.model_select.value == Select.BLANK:
                self.notify(
                    "Model defined in session is not installed", severity="warning"
                )
            self.temperature_input.value = str(
                self.session.options.get("temperature", "")
            )
            self.session_name_input.value = self.session.name
        self.set_timer(0.25, partial(self.scroll_to_bottom, False))
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
        event.stop()
        # self.app.post_message(
        #     LogIt(f"CT session updated [{','.join([*event.changed])}]")
        # )
        if "name" in event.changed:
            with self.prevent(Input.Changed, Input.Submitted):
                self.session_name_input.value = self.session.name
                self.notify_tab_label_changed()
        if "model_name" in event.changed or "messages" in event.changed:
            self.on_update_chat_status()

    @work(group="get_details", thread=True)
    async def get_model_details(self, model: FullModel) -> None:
        """Fetch model details"""
        dm.enrich_model_details(model)
        if not model.model_info:
            return
        max_context_length = model.model_info.llama_context_length
        if max_context_length:
            self.post_message(UpdateChatStatus())

    # @on(UpdateChatStatus)
    def on_update_chat_status(self, event: Message | None = None) -> None:
        """Update session status bar"""
        if event:
            event.stop()
        model: FullModel | None = dm.get_model_by_name(self.session.llm_model_name)
        max_context_length = 0
        if model:
            if not model.model_info:
                self.get_model_details(model)
            elif model.model_info:
                max_context_length = model.model_info.llama_context_length or 0
        parts = [
            "Context Length: ",
            humanize.intcomma(self.session.context_length),
            " / ",
            humanize.intcomma(max_context_length),
        ]
        stats = self.session.stats
        if stats:
            if stats.eval_duration:
                parts.append(
                    f" | Tokens / Sec: {stats.eval_count / (stats.eval_duration/1_000_000_000):.1f}"
                )

        self.session_status_bar.update(Text.assemble(*parts))

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

    @on(LocalModelDeleted)
    def on_model_deleted(self, event: LocalModelDeleted) -> None:
        """Model deleted check if the currently selected model."""
        event.stop()
        self.update_control_states()
