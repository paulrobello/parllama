"""Chat manager class"""
from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from typing import Any
from typing import Literal

import simplejson as json
from ollama import Message as OMessage
from ollama import Options as OllamaOptions
from textual.app import App
from textual.message_pump import MessagePump

from parllama.messages.main import ChatGenerationAborted
from parllama.messages.main import ChatMessage
from parllama.messages.main import SessionChanges
from parllama.messages.main import SessionListChanged
from parllama.messages.main import SessionMessage
from parllama.messages.main import SessionSelected
from parllama.messages.main import SessionUpdated
from parllama.models.settings_data import settings


# ---------------------- OllamaMessage ---------------------------- #
@dataclass
class OllamaMessage:
    """
    Chat message.
    """

    message_id: str
    "Unique identifier of the message."

    role: Literal["user", "assistant", "system"]
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."

    _session: ChatSession | None = None

    def __init__(
        self,
        *,
        role: Literal["user", "assistant", "system"],
        content: str = "",
        message_id: str | None = None,
        session: ChatSession | None = None,
    ) -> None:
        """Initialize the chat message"""
        self.message_id = message_id or uuid.uuid4().hex
        self.role = role
        self.content = content
        self._session = session

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        return OMessage(role=self.role, content=self.content)

    def save(self) -> bool:
        """Save the chat session to a file"""
        if self._session:
            return self._session.save()
        return False

    @property
    def session(self) -> ChatSession | None:
        """Get the chat session"""
        return self._session

    @session.setter
    def session(self, value: ChatSession) -> None:
        """Set the chat session"""
        self._session = value

    def to_json(self, indent: int = 4) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {"message_id": self.message_id, "role": self.role, "content": self.content},
            default=str,
            indent=indent,
        )

    def __dict__(
        self,
    ):
        """Convert the chat message to a dictionary"""
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
        }

    @staticmethod
    def from_json(json_data: str) -> OllamaMessage:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        return OllamaMessage(
            message_id=data["message_id"], role=data["role"], content=data["content"]
        )


# ---------------------- ChatSession ---------------------------- #


@dataclass
class ChatSession:
    """Chat session class"""

    session_id: str
    llm_model_name: str
    options: OllamaOptions
    session_name: str
    messages: list[OllamaMessage]
    last_updated: datetime.datetime
    _manager: ChatManager
    _subs: set[MessagePump]
    _id_to_msg: dict[str, OllamaMessage]
    _name_generated: bool = False
    _abort: bool = False
    _generating: bool = False

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        manager: ChatManager,
        session_id: str | None = None,
        llm_model_name: str,
        options: OllamaOptions | None = None,
        session_name: str,
        messages: list[OllamaMessage] | list[dict] | None = None,
        last_updated: datetime.datetime | None = None,
    ):
        """Initialize the chat session"""
        self._id_to_msg = {}
        self._subs = set()
        self._manager = manager
        self.session_id = session_id or uuid.uuid4().hex
        self.llm_model_name = llm_model_name
        self.options = options or {}
        self.session_name = session_name
        self.messages = []
        msgs = messages or []
        for m in msgs:
            if isinstance(m, OllamaMessage):
                self.messages.append(m)
            else:
                self.messages.append(OllamaMessage(session=self, **m))

        self.last_updated = last_updated or datetime.datetime.now()

        for m in self.messages:
            m._session = self
            self._id_to_msg[m.message_id] = m

    def add_sub(self, sub: MessagePump) -> None:
        """Add a subscription"""
        self._subs.add(sub)

    def remove_sub(self, sub: MessagePump) -> None:
        """Remove a subscription"""
        self._subs.discard(sub)

    def _notify_subs(self, event: SessionMessage) -> None:
        """Notify all subscriptions"""
        for sub in self._subs:
            sub.post_message(event)

    def _notify_changed(self, changed: SessionChanges) -> None:
        """Notify changed"""
        self.last_updated = datetime.datetime.now()
        self._notify_subs(SessionUpdated(session_id=self.session_id, changed=changed))
        if "name" in changed or "temperature" in changed or "model" in changed:
            self._manager.notify_changed()

    def get_message_by_id(self, message_id: str) -> OllamaMessage | None:
        """Get a message"""
        return self._id_to_msg.get(message_id)

    def add_message(self, msg: OllamaMessage, prepend: bool = False) -> None:
        """Add a message"""
        msg.session = self
        if prepend:
            self.messages.insert(0, msg)
        else:
            self.messages.append(msg)
        self._id_to_msg[msg.message_id] = msg
        self._notify_changed({"messages"})
        self.save()

    def set_name(self, name: str) -> None:
        """Set the name of the chat session"""
        name = name.strip()
        if self.session_name == name:
            return
        self.session_name = self._manager.mk_session_name(name)
        self._notify_changed({"name"})
        self.save()

    def set_llm_model(self, llm_model_name: str) -> None:
        """Set the LLM model name"""
        llm_model_name = llm_model_name.strip()
        if self.llm_model_name == llm_model_name:
            return
        self.llm_model_name = llm_model_name
        self._notify_changed({"model"})
        self.save()

    def set_temperature(self, temperature: float | None) -> None:
        """Set the temperature"""
        if temperature is not None:
            if (
                "temperature" in self.options
                and self.options["temperature"] == temperature
            ):
                return
            self.options["temperature"] = temperature
        else:
            if "temperature" not in self.options:
                return
            del self.options["temperature"]
        self._notify_changed({"temperature"})
        self.save()

    async def set_system_prompt(self, system_prompt: str) -> None:
        """Set system prompt for session"""
        msg: OllamaMessage
        if len(self.messages) > 0 and self.messages[0].role == "system":
            msg = self.messages[0]
            if msg.content == system_prompt:
                return
            msg.content = system_prompt
            self._notify_changed({"messages"})
        else:
            msg = OllamaMessage(content=system_prompt, role="system")
            self.add_message(msg, True)

        self._notify_subs(
            ChatMessage(session_id=self.session_id, message_id=msg.message_id)
        )
        self.save()

    async def send_chat(self, from_user: str) -> bool:
        """Send a chat message to LLM"""
        self._generating = True
        try:
            msg: OllamaMessage = OllamaMessage(role="user", content=from_user)
            self.add_message(msg)
            self._notify_subs(
                ChatMessage(session_id=self.session_id, message_id=msg.message_id)
            )

            msg = OllamaMessage(role="assistant")
            self.add_message(msg)
            self._notify_subs(
                ChatMessage(session_id=self.session_id, message_id=msg.message_id)
            )

            stream: Iterator[Mapping[str, Any]] = settings.ollama_client.chat(  # type: ignore
                model=self.llm_model_name,
                messages=[m.to_ollama_native() for m in self.messages],
                options=self.options,
                stream=True,
            )
            is_aborted = False
            for chunk in stream:
                if "content" in chunk["message"]:
                    msg.content += chunk["message"]["content"]
                if self._abort:
                    is_aborted = True
                    try:
                        msg.content += "\n\nAborted..."
                        self._notify_subs(ChatGenerationAborted(self.session_id))
                        stream.close()  # type: ignore
                    except Exception:  # pylint:disable=broad-except
                        pass
                    finally:
                        self._abort = False
                    break
                self._notify_subs(
                    ChatMessage(session_id=self.session_id, message_id=msg.message_id)
                )

            self.save()

            if (
                not is_aborted
                and settings.auto_name_session
                and not self._name_generated
            ):
                self._name_generated = True
                user_msg = self.get_first_user_message()
                if user_msg:
                    new_name = self.llm_session_name(user_msg.content)
                    if new_name:
                        self.set_name(new_name)
                self._notify_subs(
                    SessionUpdated(session_id=self.session_id, changed={"name"})
                )
                self.save()
        finally:
            self._generating = False

        return not is_aborted

    def get_system_message(self) -> OllamaMessage | None:
        """Get the system message"""
        for msg in self.messages:
            if msg.role == "system":
                return msg
        return None

    def get_first_user_message(self) -> OllamaMessage | None:
        """Get the first user message"""
        for msg in self.messages:
            if msg.role == "user":
                return msg
        return None

    def new_session(self, session_name: str = "My Chat"):
        """Start new session"""
        self.session_id = uuid.uuid4().hex
        self.session_name = session_name
        self.messages.clear()
        self._id_to_msg.clear()

    def llm_session_name(self, text: str) -> str | None:
        """Generate a session name from the given text using llm"""
        if not settings.auto_name_session_llm and not self.llm_model_name:
            return None
        ret = settings.ollama_client.generate(
            model=settings.auto_name_session_llm or self.llm_model_name,
            options={"temperature": 0.1},
            prompt=text,
            system="""
You are a helpful assistant.
You will be given text to summarize.
You must follow all the following instructions:
* Generate a descriptive session name of no more than a 4 words.
* Only output the session name.
* Do not answer any questions or explain anything.
* Do not output any preamble.
Examples:
* "Why is grass green" -> "Green Grass"
* "Why is the sky blue?" -> "Blue Sky"
* "What is the tallest mountain?" -> "Tallest Mountain"
* "What is the meaning of life?" -> "Meaning of Life"
        """,
        )
        return ret["response"].strip()  # type: ignore

    def __iter__(self):
        """Iterate over messages"""
        return iter(self.messages)

    def __len__(self) -> int:
        """Get the number of messages"""
        return len(self.messages)

    def __getitem__(self, msg_id: str) -> OllamaMessage:
        """Get a message"""
        return self._id_to_msg[msg_id]

    def __setitem__(self, msg_id: str, value: OllamaMessage) -> None:
        """Set a message"""
        self._id_to_msg[msg_id] = value
        for i, msg in enumerate(self.messages):
            if msg.message_id == msg_id:
                self.messages[i] = value
                return
        self.messages.append(value)

    def __delitem__(self, key: str) -> None:
        """Delete a message"""
        del self._id_to_msg[key]
        for i, msg in enumerate(self.messages):
            if msg.message_id == key:
                self.messages.pop(i)
                return

    def __contains__(self, item: OllamaMessage) -> bool:
        """Check if a message exists"""
        return item.message_id in self._id_to_msg

    def __eq__(self, other: object) -> bool:
        """Check if two sessions are equal"""
        if not isinstance(other, ChatSession):
            return NotImplemented
        return self.session_id == other.session_id

    def __ne__(self, other: object) -> bool:
        """Check if two sessions are not equal"""
        if not isinstance(other, ChatSession):
            return NotImplemented
        return self.session_id != other.session_id

    def __str__(self) -> str:
        """Get a string representation of the chat session"""
        ret = StringIO()
        ret.write(f"# {self.session_name}\n\n")
        for msg in self.messages:
            ret.write(str(msg))
        return ret.getvalue()

    def to_json(self, indent: int = 4) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {
                "session_id": self.session_id,
                "last_updated": self.last_updated.isoformat(),
                "llm_model_name": self.llm_model_name,
                "options": self.options,
                "session_name": self.session_name,
                "messages": [m.__dict__() for m in self.messages],
            },
            default=str,
            indent=indent,
        )

    @staticmethod
    def from_json(manager: ChatManager, json_data: str) -> ChatSession:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        return ChatSession(
            manager=manager,
            session_id=data["session_id"],
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
            llm_model_name=data["llm_model_name"],
            options=data.get("options"),
            session_name=data["session_name"],
            messages=[OllamaMessage(**m) for m in data["messages"]],
        )

    @staticmethod
    def load_from_file(manager: ChatManager, filename: str) -> ChatSession | None:
        """Load a chat session from a file"""
        try:
            with open(
                os.path.join(settings.chat_dir, filename), "rt", encoding="utf-8"
            ) as f:
                return ChatSession.from_json(manager, f.read())
        except (OSError, IOError):
            return None

    def is_valid(self) -> bool:
        """return true if session is valid"""
        return (
            len(self.session_name) > 0
            and len(self.llm_model_name) > 0
            and self.llm_model_name not in ["Select.BLANK", "None"]
            and len(self.messages) > 0
        )

    def save(self) -> bool:
        """Save the chat session to a file"""
        if not self.is_valid():
            return False  # Cannot save without session name, LLM model name and at least one message
        if settings.no_save_chat:
            return False  # Do not save if no_save_chat is set in settings
        file_name = (
            f"{self.session_id}.json"  # Use session ID as filename to avoid over
        )
        try:
            with open(
                os.path.join(settings.chat_dir, file_name), "wt", encoding="utf-8"
            ) as f:
                f.write(self.to_json())
            return True
        except (OSError, IOError):
            return False

    def export_as_markdown(self, filename: str) -> bool:
        """Save the chat session to markdown file"""
        try:
            with open(
                os.path.join(settings.chat_dir, filename), "w", encoding="utf-8"
            ) as f:
                f.write(str(self))
            return True
        except (OSError, IOError):
            return False

    def stop_generation(self) -> None:
        """Stop LLM model generation"""
        self._abort = True

    @property
    def abort_pending(self) -> bool:
        """Check if LLM model generation is pending"""
        return self._abort

    @property
    def is_generating(self) -> bool:
        """Check if LLM model generation is in progress"""
        return self._generating

    @property
    def context_length(self) -> int:
        """Return current message context length"""
        total: int = 0
        for msg in self.messages:
            total += len(msg.content)
        return total


# ---------------------- ChatManager ---------------------------- #


class ChatManager:
    """Chat manager class"""

    app: App[Any]
    sessions: list[ChatSession] = []
    options: OllamaOptions = {}

    def __init__(self) -> None:
        """Initialize the chat manager"""

    def set_app(self, app: App[Any]) -> None:
        """Set the app and load existing sessions from storage"""
        self.app = app
        self.load_sessions()

    def mk_session_name(self, base_name: str) -> str:
        """Generate a unique session name"""
        session_name = base_name
        good = self.get_session_by_name(session_name) is None
        i = 0
        while not good:
            if good:
                break
            i += 1
            session_name = f"{base_name} {i}"
            good = self.get_session_by_name(session_name) is None
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
        session = ChatSession(
            manager=self,
            session_name=self.mk_session_name(session_name),
            llm_model_name=model_name,
            options=options or self.options,
        )
        session.add_sub(widget)
        self.sessions.append(session)
        self.sort_sessions()
        self.notify_changed()
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a chat session"""
        for session in self.sessions:
            if session.session_id == session_id:
                return session
        return None

    def get_session_by_name(self, session_name: str) -> ChatSession | None:
        """Get a chat session by name"""
        for session in self.sessions:
            if session.session_name == session_name:
                return session
        return None

    def delete_session(self, session_id: str) -> None:
        """Delete a chat session"""
        for session in self.sessions:
            if session.session_id == session_id:
                self.sessions.remove(session)
                p = os.path.join(settings.chat_dir, f"{session_id}.json")
                if os.path.exists(p):
                    os.remove(p)
                self.notify_changed()
                return

    def notify_changed(self) -> None:
        """Notify changed"""
        self.app.post_message(SessionListChanged())

    def get_or_create_session_name(
        self,
        *,
        session_name: str,
        model_name: str,
        options: OllamaOptions | None,
        widget: MessagePump,
    ) -> ChatSession:
        """Get or create a chat session"""
        session = self.get_session_by_name(session_name)
        if not session:
            session = self.new_session(
                session_name=session_name,
                model_name=model_name,
                options=options,
                widget=widget,
            )
        session.add_sub(widget)
        return session

    def set_current_session(self, session_id: str) -> None:
        """Set the current chat session"""
        self.app.post_message(SessionSelected(session_id))

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
                        manager=self,
                        session_name=data["session_name"],
                        llm_model_name=data["llm_model_name"],
                        session_id=data["session_id"],
                        messages=data["messages"],
                        options=data.get("options"),
                        last_updated=datetime.datetime.fromisoformat(
                            data["last_updated"]
                        ),
                    )
                    self.sessions.append(session)
            except:  # pylint: disable=bare-except
                self.app.notify(f"Error loading session {f}", severity="error")
        self.sort_sessions()

    def sort_sessions(self) -> None:
        """Sort sessions by last_updated field in descending order."""
        self.sessions.sort(key=lambda x: x.last_updated, reverse=True)


chat_manager = ChatManager()
