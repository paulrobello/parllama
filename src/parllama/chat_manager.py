"""Chat manager class"""

from __future__ import annotations

import os
from typing import Any

from ollama import Options as OllamaOptions
from par_ai_core.llm_config import LlmConfig
from textual.app import App
from textual.message_pump import MessagePump

from parllama.chat_message import ParllamaChatMessage
from parllama.chat_prompt import ChatPrompt
from parllama.chat_session import ChatSession
from parllama.llm_session_name import llm_session_name
from parllama.messages.messages import ChangeTab, PromptListChanged, PromptListLoaded, SessionListChanged
from parllama.messages.par_prompt_messages import ParPromptDelete, ParPromptUpdated
from parllama.messages.par_session_messages import ParSessionAutoName, ParSessionDelete, ParSessionUpdated
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings


class ChatManager(ParEventSystemBase):
    """Chat manager class"""

    _id_to_session: dict[str, ChatSession]
    _id_to_prompt: dict[str, ChatPrompt]

    options: OllamaOptions
    prompt_temperature: float
    prompt_llm_name: str | None

    def __init__(self) -> None:
        """Initialize the chat manager"""
        super().__init__(id="chat_manager")
        self._id_to_session = {}
        self._id_to_prompt = {}
        self.options = OllamaOptions()
        self.prompt_temperature = 0.5
        self.prompt_llm_name = None

    def set_app(self, app: App[Any] | None) -> None:
        """Set the app and load existing sessions and prompts from storage"""
        super().set_app(app)
        self.load_sessions()
        self.load_prompts()

    ############ Sessions #################
    @property
    def sessions(self) -> list[ChatSession]:
        """Return a list of chat sessions"""
        return list(self._id_to_session.values())

    @property
    def valid_sessions(self) -> list[ChatSession]:
        """Return a list of valid sessions"""
        return [session for session in self._id_to_session.values() if session.is_valid]

    @property
    def sorted_sessions(self) -> list[ChatSession]:
        """Sort sessions by last_updated field in descending order."""
        sessions = self.valid_sessions
        sessions.sort(key=lambda x: x.last_updated, reverse=True)
        return sessions

    @property
    def session_ids(self) -> list[str]:
        """Return a list of session IDs"""
        return list(self._id_to_session.keys())

    @property
    def session_names(self) -> list[str]:
        """Return a list of session names"""
        return [session.name for session in self._id_to_session.values()]

    def mk_session_name(self, base_name: str) -> str:
        """Generate a unique session name"""
        session_name = base_name
        good = self.get_session_by_name(session_name) is None
        # self.log_it(f"mk_session_name: {base_name}: {good}")

        i = 0
        while not good:
            i += 1
            session_name = f"{base_name} {i}"
            good = self.get_session_by_name(session_name) is None
            if good:
                break
        return session_name

    def mk_llm_session_name(self, text: str) -> str | None:
        """Generate a unique LLM session name"""
        if not settings.auto_name_session_llm_config:
            return None
        base_name = llm_session_name(text, LlmConfig.from_json(settings.auto_name_session_llm_config))
        if not base_name:
            return None
        return self.mk_session_name(base_name)

    def new_session(
        self,
        *,
        session_name: str,
        llm_config: LlmConfig,
        widget: MessagePump,
    ) -> ChatSession:
        """Create a new chat session"""
        # self.log_it("CM new_session")

        session = ChatSession(
            name=self.mk_session_name(session_name),
            messages=[],
            llm_config=llm_config,
        )
        self._id_to_session[session.id] = session
        self.mount(session)
        session.add_sub(widget)
        self.notify_sessions_changed()
        return session

    def get_session(self, session_id: str, widget: MessagePump | None = None) -> ChatSession | None:
        """Get a chat session"""
        # self.log_it("get_session: " + session_id)

        session = self._id_to_session.get(session_id)

        if session is not None and widget:
            session.add_sub(widget)
        return session

    def get_prompt(self, prompt_id: str) -> ChatPrompt | None:
        """Get a chat prompt"""
        # self.log_it("get_prompt: " + prompt_id)
        return self._id_to_prompt.get(prompt_id)

    def get_session_by_name(self, session_name: str, widget: MessagePump | None = None) -> ChatSession | None:
        """Get a chat session by name"""
        for session in self._id_to_session.values():
            if session.name == session_name:
                if widget:
                    session.add_sub(widget)
                return session
        return None

    def delete_session(self, session_id: str) -> None:
        """Delete a chat session"""
        session = self._id_to_session.get(session_id)
        if session is None:
            return
        del self._id_to_session[session_id]
        p = os.path.join(settings.chat_dir, f"{session_id}.json")
        if os.path.exists(p):
            os.remove(p)
        self.notify_sessions_changed()
        # self.log_it(f"CM Session {session_id} deleted")

    def notify_sessions_changed(self) -> None:
        """Notify changed"""
        # self.log_it("CM Notify session changed")
        if self.app:
            self.app.post_message(SessionListChanged())

    def get_or_create_session(  # pylint: disable=too-many-arguments
        self,
        *,
        session_id: str | None,
        session_name: str | None,
        llm_config: LlmConfig,
        widget: MessagePump,
    ) -> ChatSession:
        """Get or create a chat session"""
        session: ChatSession | None = None
        if session_id:
            session = self.get_session(session_id)
        if session is None:
            if not session_name:
                session_name = self.mk_session_name("New Chat")
            session = self.new_session(
                session_name=session_name,
                llm_config=llm_config,
                widget=widget,
            )
        session.add_sub(widget)
        # session.batching = False
        return session

    def load_sessions(self) -> None:
        """Load chat sessions from files"""
        for f in os.listdir(settings.chat_dir):
            f = f.lower()
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(settings.chat_dir, f), encoding="utf-8") as fh:
                    data = fh.read()
                    # self.log_it(data)
                    session = ChatSession.from_json(data, load_messages=False)
                    session.name_generated = True
                    self._id_to_session[session.id] = session
                    self.mount(session)
            except Exception as e:
                self.log_it(f"Error loading session {e}", notify=True, severity="error")

    def on_par_session_updated(self, event: ParSessionUpdated) -> None:
        """Handle a ParSessionUpdated event"""
        event.stop()
        # self.log_it(
        #     f"CM Session {event.session_id} updated. [{','.join(event.changed)}]"
        # )
        if "name" in event.changed or "model" in event.changed or "temperature" in event.changed:
            self.notify_sessions_changed()

    def on_par_session_auto_name(self, event: ParSessionAutoName) -> None:
        """Handle a ParSessionAutoName event"""
        event.stop()
        session = self.get_session(event.session_id)
        if not session:
            return
        new_name = llm_session_name(event.context, event.llm_config)
        if not new_name:
            return
        self.log_it(f"CM Session auto name {event.session_id} context: {event.context} named: {new_name}")
        session.name = self.mk_session_name(new_name)
        # self.log_it(f"CM Session {event.session_id} auto-named: {new_name}")

    def on_par_session_delete(self, event: ParSessionDelete) -> None:
        """Handle a ParDeleteSession event"""
        event.stop()
        self.delete_session(event.session_id)

    def session_to_prompt(
        self, session_id: str, submit_on_load: bool, prompt_name: str | None = None
    ) -> ChatPrompt | None:
        """Copy a session to a new custom prompt"""
        session = self.get_session(session_id)
        if session is None:
            self.log_it(f"Chat session {session_id} not found", severity="error", notify=True)
            return None
        prompt_name = prompt_name or session.name
        messages = [
            ParllamaChatMessage(role=m.role, content=m.content, images=m.images, tool_calls=m.tool_calls)
            for m in session.messages
        ]
        prompt = ChatPrompt(
            name=prompt_name,
            description="",
            messages=messages,
            submit_on_load=submit_on_load,
            source="session",
        )
        self._id_to_prompt[prompt.id] = prompt
        self.mount(prompt)
        self.notify_prompts_changed()
        prompt.description = "-"
        prompt.save()
        self.log_it(f"Session {session.name or session.id} copied to prompt", notify=True)
        if self.app:
            self.app.post_message(ChangeTab(tab="Prompts"))
        return prompt

    ############ Prompts #################
    @property
    def prompts(self) -> list[ChatPrompt]:
        """Return a list of chat sessions"""
        return list(self._id_to_prompt.values())

    @property
    def sorted_prompts(self) -> list[ChatPrompt]:
        """Sort sessions by last_updated field in descending order."""
        prompts = self.prompts
        prompts.sort(key=lambda x: x.last_updated, reverse=True)
        return prompts

    @property
    def prompt_ids(self) -> list[str]:
        """Return a list of session IDs"""
        return list(self._id_to_prompt.keys())

    @property
    def prompt_names(self) -> list[str]:
        """Return a list of session names"""
        return [prompt.name for prompt in self._id_to_prompt.values()]

    def get_prompt_by_name(self, name: str) -> ChatPrompt | None:
        """Get a custom prompt by name"""
        name = name.strip().lower()
        for prompt in self._id_to_prompt.values():
            if prompt.name.lower() == name:
                return prompt
        return None

    def load_prompts(self) -> None:
        """Load custom prompts from files"""
        for f in os.listdir(settings.prompt_dir):
            f = f.lower()
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(settings.prompt_dir, f), encoding="utf-8") as fh:
                    prompt = ChatPrompt.from_json(fh.read())
                    self._id_to_prompt[prompt.id] = prompt
                    self.mount(prompt)
                    # self.log_it(prompt)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.log_it(f"Error loading prompt {e}", notify=True, severity="error")
        if self.app:
            self.app.post_message(PromptListLoaded())

    def add_prompt(self, prompt: ChatPrompt) -> None:
        """Add a custom prompt"""
        self._id_to_prompt[prompt.id] = prompt
        self.mount(prompt)
        self.notify_prompts_changed()

    def delete_prompt(self, prompt_id: str) -> None:
        """Delete a custom prompt"""
        prompt = self._id_to_prompt.get(prompt_id)
        if prompt is None:
            return
        del self._id_to_prompt[prompt_id]
        p = os.path.join(settings.prompt_dir, f"{prompt_id}.json")
        if os.path.exists(p):
            os.remove(p)
        self.notify_prompts_changed()
        self.log_it(f"Prompt {prompt.name or prompt.id} deleted", notify=True)

    def notify_prompts_changed(self) -> None:
        """Notify changed"""
        # self.log_it("CM Notify prompts changed")
        if self.app:
            self.app.post_message(PromptListChanged())

    def on_par_prompt_updated(self, event: ParPromptUpdated) -> None:
        """Handle a ParSessionUpdated event"""
        event.stop()
        # self.log_it(f"CM Prompt {event.prompt_id} updated. [{','.join(event.changed)}]")
        self.notify_prompts_changed()

    def on_par_prompt_delete(self, event: ParPromptDelete) -> None:
        """Handle a ParDeleteSession event"""
        event.stop()
        self.delete_prompt(event.prompt_id)


chat_manager = ChatManager()
