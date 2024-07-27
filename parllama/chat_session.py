"""Session manager class"""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from typing import Any

import simplejson as json
from ollama import Options as OllamaOptions
from textual.message_pump import MessagePump
import rich.repr

from parllama.llm_session_name import llm_session_name
from parllama.messages.messages import ChatGenerationAborted
from parllama.messages.messages import ChatMessage
from parllama.messages.messages import SessionChanges
from parllama.messages.messages import SessionMessage
from parllama.messages.messages import SessionUpdated
from parllama.messages.par_messages import (
    ParSessionUpdated,
    ParChatUpdated,
    ParDeleteSession,
)
from parllama.chat_message import OllamaMessage
from parllama.models.settings_data import settings
from parllama.par_event_system import ParEventSystemBase


@rich.repr.auto
@dataclass
class ChatSession(ParEventSystemBase):
    """Chat session class"""

    session_id: str
    llm_model_name: str
    options: OllamaOptions
    session_name: str
    messages: list[OllamaMessage]
    last_updated: datetime.datetime
    _subs: set[MessagePump]
    _id_to_msg: dict[str, OllamaMessage]
    _name_generated: bool = False
    _abort: bool = False
    _generating: bool = False

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        session_id: str | None = None,
        llm_model_name: str,
        options: OllamaOptions | None = None,
        session_name: str,
        messages: list[OllamaMessage] | list[dict] | None = None,
        last_updated: datetime.datetime | None = None,
    ):
        """Initialize the chat session"""
        super().__init__()
        self._id_to_msg = {}
        self._subs = set()
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
                self.messages.append(OllamaMessage(**m))

        for m in self.messages:
            self._id_to_msg[m.message_id] = m

        self.last_updated = last_updated or datetime.datetime.now()

    def add_sub(self, sub: MessagePump) -> None:
        """Add a subscription"""
        self._subs.add(sub)

    def remove_sub(self, sub: MessagePump) -> None:
        """Remove a subscription"""
        self._subs.discard(sub)
        if self.num_subs == 0 and not self.is_valid():
            self.delete()

    def delete(self) -> None:
        """Delete the session"""
        self.post_message(ParDeleteSession(session_id=self.session_id))

    def _notify_subs(self, event: SessionMessage) -> None:
        """Notify all subscriptions"""
        for sub in self._subs:
            sub.post_message(event)

    def _notify_changed(self, changed: SessionChanges) -> None:
        """Notify changed"""
        self.last_updated = datetime.datetime.now()
        self._notify_subs(SessionUpdated(session_id=self.session_id, changed=changed))
        # if "name" in changed or "temperature" in changed or "model" in changed:
        self.post_message(
            ParSessionUpdated(session_id=self.session_id, changed=changed)
        )

    def add_message(self, msg: OllamaMessage, prepend: bool = False) -> None:
        """Add a message"""
        if prepend:
            self.messages.insert(0, msg)
        else:
            self.messages.append(msg)
        self._id_to_msg[msg.message_id] = msg
        self.mount(msg)

        self._notify_changed({"messages"})
        self.save()

    def set_name(self, name: str) -> None:
        """Set the name of the chat session"""
        name = name.strip()
        if self.session_name == name:
            return
        self.session_name = name
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

    def set_system_prompt(self, system_prompt: str) -> None:
        """Set system prompt for session"""
        msg: OllamaMessage
        if len(self.messages) > 0 and self.messages[0].role == "system":
            msg = self.messages[0]
            if msg.content == system_prompt:
                return
            msg.content = system_prompt
            self._notify_changed({"messages"})
        else:
            msg = OllamaMessage(
                session_id=self.session_id, content=system_prompt, role="system"
            )
            self.add_message(msg, True)

        self._notify_subs(
            ChatMessage(session_id=self.session_id, message_id=msg.message_id)
        )
        self.save()

    async def send_chat(self, from_user: str) -> bool:
        """Send a chat message to LLM"""
        self._generating = True
        try:
            msg: OllamaMessage = OllamaMessage(
                session_id=self.session_id, role="user", content=from_user
            )
            self.add_message(msg)
            self._notify_subs(
                ChatMessage(session_id=self.session_id, message_id=msg.message_id)
            )
            self.post_message(
                ParChatUpdated(session_id=self.session_id, message_id=msg.message_id)
            )

            msg = OllamaMessage(session_id=self.session_id, role="assistant")
            self.add_message(msg)
            self._notify_subs(
                ChatMessage(session_id=self.session_id, message_id=msg.message_id)
            )
            self.post_message(
                ParChatUpdated(session_id=self.session_id, message_id=msg.message_id)
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
                self.post_message(
                    ParChatUpdated(
                        session_id=self.session_id, message_id=msg.message_id
                    )
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
                    new_name = llm_session_name(user_msg.content, self.llm_model_name)
                    if new_name:
                        self.set_name(new_name)
                self._notify_subs(
                    SessionUpdated(session_id=self.session_id, changed={"name"})
                )
                self.post_message(
                    ParSessionUpdated(session_id=self.session_id, changed={"name"})
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
                self._notify_changed({"messages"})
                return
        self.messages.append(value)
        self._notify_changed({"messages"})

    def __delitem__(self, key: str) -> None:
        """Delete a message"""
        del self._id_to_msg[key]
        for i, msg in enumerate(self.messages):
            if msg.message_id == key:
                self.messages.pop(i)
                self._notify_changed({"messages"})
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
    def from_json(json_data: str) -> ChatSession:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        return ChatSession(
            session_id=data["session_id"],
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
            llm_model_name=data["llm_model_name"],
            options=data.get("options"),
            session_name=data["session_name"],
            messages=[OllamaMessage(**m) for m in data["messages"]],
        )

    @staticmethod
    def load_from_file(filename: str) -> ChatSession | None:
        """Load a chat session from a file"""
        try:
            with open(
                os.path.join(settings.chat_dir, filename), "rt", encoding="utf-8"
            ) as f:
                return ChatSession.from_json(f.read())
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
                os.path.join(settings.chat_dir, filename), "wt", encoding="utf-8"
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

    @property
    def num_subs(self):
        """Return the number of subscribers"""
        return len(self._subs)
