"""Chat manager class"""

from __future__ import annotations

import datetime
import os
from typing import Any

import simplejson as json
from ollama import Options as OllamaOptions
from textual.app import App
from textual.message_pump import MessagePump

from parllama.messages.messages import SessionListChanged, LogIt
from parllama.messages.par_messages import ParSessionUpdated, ParLogIt, ParDeleteSession
from parllama.models.settings_data import settings
from parllama.par_event_system import ParEventSystemBase
from parllama.chat_session import ChatSession


class ChatManager(ParEventSystemBase):
    """Chat manager class"""

    _id_to_session: dict[str, ChatSession]
    app: App[Any]
    sessions: list[ChatSession]
    options: OllamaOptions

    def __init__(self) -> None:
        """Initialize the chat manager"""
        super().__init__()
        self._id_to_session = {}
        self.sessions = []
        self.options = {}

    @property
    def valid_sessions(self) -> list[ChatSession]:
        """Return a list of valid sessions"""
        return [session for session in self.sessions if session.is_valid]

    @property
    def session_ids(self) -> list[str]:
        """Return a list of session IDs"""
        return list(self._id_to_session.keys())

    @property
    def session_names(self) -> list[str]:
        """Return a list of session names"""
        return [session.session_name for session in self.sessions]

    def set_app(self, app: App[Any]) -> None:
        """Set the app and load existing sessions from storage"""
        self.app = app
        self.load_sessions()

    def mk_session_name(self, base_name: str) -> str:
        """Generate a unique session name"""
        session_name = base_name
        good = self.get_session_by_name(session_name) is None
        self.app.post_message(LogIt(f"mk_session_name: {base_name}: {good}"))
        self.app.post_message(LogIt(json.dumps(self.session_names)))

        # self.app.post_message(
        #     LogIt(
        #         json.dumps(
        #             self.get_session_by_name(session_name), indent=2, default=str
        #         )
        #     )
        # )

        i = 0
        while not good:
            i += 1
            session_name = f"{base_name} {i}"
            good = self.get_session_by_name(session_name) is None
            self.app.post_message(LogIt(f"mk_session_name: {session_name}: {good}"))

            if good:
                break
        return session_name

    def new_session(
        self,
        *,
        session_name: str,
        model_name: str,
        options: OllamaOptions | None,
        widget: MessagePump,
    ) -> ChatSession:
        """Create a new chat session"""
        self.app.post_message(LogIt("CM new_session"))

        session = ChatSession(
            session_name=self.mk_session_name(session_name),
            llm_model_name=model_name,
            options=options or self.options,
        )
        self._id_to_session[session.session_id] = session
        self.sessions.append(session)
        self.mount(session)
        session.add_sub(widget)

        self.notify_changed()
        return session

    def get_session(
        self, session_id: str, widget: MessagePump | None = None
    ) -> ChatSession | None:
        """Get a chat session"""
        self.app.post_message(LogIt("get_session: " + session_id))

        session = self._id_to_session.get(session_id)

        if session is not None and widget:
            session.add_sub(widget)
        return session

    def get_session_by_name(
        self, session_name: str, widget: MessagePump | None = None
    ) -> ChatSession | None:
        """Get a chat session by name"""
        for session in self.sessions:
            if session.session_name == session_name:
                if widget:
                    session.add_sub(widget)
                return session
        return None

    def delete_session(self, session_id: str) -> None:
        """Delete a chat session"""
        self.app.post_message(LogIt(f"CM Delete session: {session_id}"))

        del self._id_to_session[session_id]
        for session in self.sessions:
            if session.session_id == session_id:
                self.sessions.remove(session)
                p = os.path.join(settings.chat_dir, f"{session_id}.json")
                if os.path.exists(p):
                    os.remove(p)
                self.notify_changed()
                self.app.post_message(LogIt(f"CM Session {session_id} deleted"))
                return

    def notify_changed(self) -> None:
        """Notify changed"""
        self.app.post_message(LogIt("CM Notify changed"))
        # self.app.notify("CM notify changed")
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
                        session_name=data["session_name"],
                        llm_model_name=data["llm_model_name"],
                        session_id=data["session_id"],
                        # messages=data["messages"],
                        options=data.get("options"),
                        last_updated=datetime.datetime.fromisoformat(
                            data["last_updated"]
                        ),
                    )
                    self._id_to_session[session.session_id] = session
                    self.sessions.append(session)
                    self.mount(session)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.app.post_message(LogIt(f"Error loading session {e}"))
                self.app.notify(f"Error loading session {f}", severity="error")
        self.sort_sessions()

    def sort_sessions(self) -> None:
        """Sort sessions by last_updated field in descending order."""
        self.sessions.sort(key=lambda x: x.last_updated, reverse=True)

    def on_par_session_updated(self, event: ParSessionUpdated) -> None:
        """Handle a ParSessionUpdated event"""
        event.stop()
        self.app.post_message(
            LogIt(f"CM Session {event.session_id} updated. [{','.join(event.changed)}]")
        )
        self.notify_changed()

    def on_par_delete_session(self, event: ParDeleteSession) -> None:
        """Handle a ParDeleteSession event"""
        event.stop()
        self.delete_session(event.session_id)
        # self.app.notify(f"CM Session {event.session_id} deleted")
        self.notify_changed()

    def on_par_log_it(self, event: ParLogIt) -> None:
        """Handle a ParLogIt event"""
        event.stop()
        self.app.post_message(LogIt(event.msg, notify=event.notify))


chat_manager = ChatManager()
