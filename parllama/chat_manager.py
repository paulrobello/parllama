"""Chat manager class"""

from __future__ import annotations

import datetime
import os
from typing import Any

import simplejson as json
from ollama import Options as OllamaOptions
from textual.app import App
from textual.message_pump import MessagePump

from parllama.chat_prompt import ChatPrompt
from parllama.llm_session_name import llm_session_name
from parllama.messages.messages import SessionListChanged, LogIt, PromptListChanged
from parllama.messages.par_prompt_messages import ParPromptUpdated, ParPromptDelete
from parllama.messages.par_session_messages import (
    ParSessionUpdated,
    ParSessionDelete,
    ParSessionAutoName,
)
from parllama.models.settings_data import settings
from parllama.par_event_system import ParEventSystemBase, ParLogIt
from parllama.chat_session import ChatSession


class ChatManager(ParEventSystemBase):
    """Chat manager class"""

    _id_to_session: dict[str, ChatSession]
    _id_to_prompt: dict[str, ChatPrompt]

    app: App[Any]
    options: OllamaOptions

    def __init__(self) -> None:
        """Initialize the chat manager"""
        super().__init__()
        self._id_to_session = {}
        self._id_to_prompt = {}
        self.options = {}

    def set_app(self, app: App[Any]) -> None:
        """Set the app and load existing sessions and prompts from storage"""
        self.app = app
        self.load_sessions()
        self.load_prompts()

    def on_par_log_it(self, event: ParLogIt) -> None:
        """Handle a ParLogIt event"""
        event.stop()
        self.app.post_message(
            LogIt(event.msg, notify=event.notify, severity=event.severity)
        )

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
        self.log_it(f"mk_session_name: {base_name}: {good}")

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
        base_name = llm_session_name(text)
        if not base_name:
            return None
        return self.mk_session_name(base_name)

    def new_session(
        self,
        *,
        session_name: str,
        model_name: str,
        options: OllamaOptions | None,
        widget: MessagePump,
    ) -> ChatSession:
        """Create a new chat session"""
        self.log_it("CM new_session")

        session = ChatSession(
            name=self.mk_session_name(session_name),
            llm_model_name=model_name,
            options=options or self.options,
            messages=[],
        )
        self._id_to_session[session.id] = session
        self.mount(session)
        session.add_sub(widget)
        self.notify_sessions_changed()
        return session

    def get_session(
        self, session_id: str, widget: MessagePump | None = None
    ) -> ChatSession | None:
        """Get a chat session"""
        self.log_it("get_session: " + session_id)

        session = self._id_to_session.get(session_id)

        if session is not None and widget:
            session.add_sub(widget)
        return session

    def get_session_by_name(
        self, session_name: str, widget: MessagePump | None = None
    ) -> ChatSession | None:
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
        self.log_it(f"CM Session {session_id} deleted")

    def notify_sessions_changed(self) -> None:
        """Notify changed"""
        self.log_it("CM Notify session changed")
        self.app.post_message(SessionListChanged())

    def get_or_create_session(  # pylint: disable=too-many-arguments
        self,
        *,
        session_id: str | None,
        session_name: str | None,
        model_name: str,
        options: OllamaOptions | None,
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
                model_name=model_name,
                options=options,
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
                with open(
                    os.path.join(settings.chat_dir, f), mode="rt", encoding="utf-8"
                ) as fh:
                    data: dict = json.load(fh)
                    session = ChatSession(
                        id=data.get("id", data.get("session_id")),
                        name=data.get("name", data.get("session_name")),
                        llm_model_name=data["llm_model_name"],
                        # messages=data["messages"],
                        options=data.get("options"),
                        last_updated=datetime.datetime.fromisoformat(
                            data["last_updated"]
                        ),
                    )
                    session.name_generated = True
                    self._id_to_session[session.id] = session
                    self.mount(session)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.log_it(f"Error loading session {e}", notify=True, severity="error")

    def on_par_session_updated(self, event: ParSessionUpdated) -> None:
        """Handle a ParSessionUpdated event"""
        event.stop()
        self.log_it(
            f"CM Session {event.session_id} updated. [{','.join(event.changed)}]"
        )
        if (
            "name" in event.changed
            or "model_name" in event.changed
            or "temperature" in event.changed
        ):
            self.notify_sessions_changed()

    def on_par_session_auto_name(self, event: ParSessionAutoName) -> None:
        """Handle a ParSessionAutoName event"""
        event.stop()
        session = self.get_session(event.session_id)
        if not session:
            return
        new_name = llm_session_name(event.context, event.model_name)
        if not new_name:
            return
        session.name = self.mk_session_name(new_name)
        self.log_it(f"CM Session {event.session_id} auto-named: {new_name}")

    def on_par_session_delete(self, event: ParSessionDelete) -> None:
        """Handle a ParDeleteSession event"""
        event.stop()
        self.delete_session(event.session_id)

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

    def load_prompts(self) -> None:
        """Load custom prompts from files"""
        for f in os.listdir(settings.prompt_dir):
            f = f.lower()
            if not f.endswith(".json"):
                continue
            try:
                with open(
                    os.path.join(settings.prompt_dir, f), mode="rt", encoding="utf-8"
                ) as fh:
                    data: dict = json.load(fh)
                    prompt = ChatPrompt(
                        id=data["id"],
                        name=data.get("name", data.get("session_name")),
                        description=data["description"],
                        # messages=data["messages"],
                        last_updated=datetime.datetime.fromisoformat(
                            data["last_updated"]
                        ),
                    )
                    self._id_to_prompt[prompt.id] = prompt
                    self.mount(prompt)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.log_it(f"Error loading prompt {e}", notify=True, severity="error")

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
        self.log_it(f"CM Prompt {prompt_id} deleted")

    def notify_prompts_changed(self) -> None:
        """Notify changed"""
        self.log_it("CM Notify prompt changed")
        # self.app.notify("CM notify changed")
        self.app.post_message(PromptListChanged())

    def on_par_prompt_updated(self, event: ParPromptUpdated) -> None:
        """Handle a ParSessionUpdated event"""
        event.stop()
        self.log_it(f"CM Prompt {event.prompt_id} updated. [{','.join(event.changed)}]")
        self.notify_prompts_changed()

    def on_par_prompt_delete(self, event: ParPromptDelete) -> None:
        """Handle a ParDeleteSession event"""
        event.stop()
        self.delete_prompt(event.prompt_id)


chat_manager = ChatManager()
