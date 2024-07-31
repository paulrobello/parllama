"""Session manager class"""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import simplejson as json
from ollama import Options as OllamaOptions
from textual.message_pump import MessagePump
import rich.repr

from parllama.chat_message_container import ChatMessageContainer
from parllama.llm_session_name import llm_session_name
from parllama.messages.messages import ChatGenerationAborted
from parllama.messages.messages import ChatMessage
from parllama.messages.messages import SessionChanges
from parllama.messages.messages import SessionMessage
from parllama.messages.messages import SessionUpdated

from parllama.chat_message import OllamaMessage
from parllama.messages.par_chat_messages import ParChatUpdated
from parllama.messages.par_session_messages import (
    ParSessionDelete,
    ParSessionUpdated,
)
from parllama.messages.shared import session_change_list
from parllama.models.settings_data import settings


@rich.repr.auto
@dataclass
class ChatSession(ChatMessageContainer):
    """Chat session class"""

    _llm_model_name: str
    options: OllamaOptions
    _subs: set[MessagePump]
    _name_generated: bool
    _abort: bool
    _generating: bool
    _loaded: bool

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str,
        llm_model_name: str,
        options: OllamaOptions | None = None,
        messages: list[OllamaMessage] | list[dict] | None = None,
        last_updated: datetime.datetime | None = None,
    ):
        """Initialize the chat session"""
        super().__init__(id=id, name=name, messages=messages, last_updated=last_updated)
        self._batching = True
        self._name_generated = False
        self._abort = False
        self._generating = False
        self._subs = set()
        self._llm_model_name = llm_model_name
        self.options = options or {}
        self._loaded = messages is not None
        self._batching = False

    def load(self) -> None:
        """Load chat sessions from files"""
        if self._loaded:
            self._batching = False
            return

        self._batching = True
        try:
            file_path = os.path.join(settings.chat_dir, self.id + ".json")
            if not os.path.exists(file_path):
                return

            with open(file_path, mode="rt", encoding="utf-8") as fh:
                data: dict = json.load(fh)

            msgs = data["messages"] or []
            for m in msgs:
                if "message_id" in m:
                    m["id"] = "message_id"
                    del m["message_id"]
            for m in msgs:
                self.add_message(OllamaMessage(**m))
            self._loaded = True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log_it(f"CS Error loading session {e}", notify=True, severity="error")
        finally:
            self._batching = False
            self.clear_changes()

    @property
    def loading(self) -> bool:
        """Check if the session is loading"""
        return self._batching

    @loading.setter
    def loading(self, value: bool) -> None:
        """Set the loading state"""
        self._batching = value

    def add_sub(self, sub: MessagePump) -> None:
        """Add a subscription"""
        self._subs.add(sub)

    def remove_sub(self, sub: MessagePump) -> None:
        """Remove a subscription"""
        self._subs.discard(sub)
        if self.num_subs == 0 and not self.is_valid:
            self.delete()

    def delete(self) -> None:
        """Delete the session"""
        self.post_message(ParSessionDelete(session_id=self.id))

    def _notify_subs(self, event: SessionMessage | ChatMessage) -> None:
        """Notify all subscriptions"""
        for sub in self._subs:
            sub.post_message(event)

    def _notify_changed(self, changed: SessionChanges) -> None:
        """Notify changed"""
        self._notify_subs(SessionUpdated(session_id=self.id, changed=changed))
        self.post_message(ParSessionUpdated(session_id=self.id, changed=changed))

    @property
    def llm_model_name(self) -> str:
        """Get the LLM model name"""
        return self._llm_model_name

    @llm_model_name.setter
    def llm_model_name(self, value: str) -> None:
        """Set the LLM model name"""
        value = value.strip()
        if self._llm_model_name == value:
            return
        self._llm_model_name = value
        self._changes.add("model")
        self.save()

    @property
    def temperature(self) -> float | None:
        """Get the temperature"""
        return self.options.get("temperature")

    @temperature.setter
    def temperature(self, value: float | None) -> None:
        """Set the temperature"""
        if value is not None:
            if "temperature" in self.options and self.options["temperature"] == value:
                return
            self.options["temperature"] = value
        else:
            if "temperature" not in self.options:
                return
            del self.options["temperature"]
        self._changes.add("temperature")
        self.save()

    async def send_chat(self, from_user: str) -> bool:
        """Send a chat message to LLM"""
        self._generating = True
        try:
            self.log_it("CM adding user message")
            msg: OllamaMessage = OllamaMessage(role="user", content=from_user)
            self.add_message(msg)
            self._notify_subs(ChatMessage(parent_id=self.id, message_id=msg.id))
            self.post_message(ParChatUpdated(parent_id=self.id, message_id=msg.id))

            self.log_it("CM adding assistant message")
            msg = OllamaMessage(role="assistant")
            self.add_message(msg)
            self._notify_subs(ChatMessage(parent_id=self.id, message_id=msg.id))
            self.post_message(ParChatUpdated(parent_id=self.id, message_id=msg.id))

            self.save()

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
                        self._notify_subs(ChatGenerationAborted(self.id))
                        stream.close()  # type: ignore
                    except Exception:  # pylint:disable=broad-except
                        pass
                    finally:
                        self._abort = False
                    break
                self._notify_subs(ChatMessage(parent_id=self.id, message_id=msg.id))
                self.post_message(ParChatUpdated(parent_id=self.id, message_id=msg.id))

            self._changes.add("messages")
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
                        self.name = new_name
        finally:
            self._generating = False

        return not is_aborted

    def new_session(self, name: str = "My Chat"):
        """Start new session"""
        self._batching = True
        self.id = uuid.uuid4().hex
        self.name = name
        self.messages.clear()
        self._id_to_msg.clear()
        self.clear_changes()
        self._loaded = False
        self._batching = False

    @property
    def is_loaded(self):
        """Check if the session is loaded"""
        return self._loaded

    def __eq__(self, other: object) -> bool:
        """Check if two sessions are equal"""
        if not isinstance(other, ChatSession):
            return NotImplemented
        return self.id == other.id

    def __ne__(self, other: object) -> bool:
        """Check if two sessions are not equal"""
        if not isinstance(other, ChatSession):
            return NotImplemented
        return self.id != other.id

    def to_json(self, indent: int = 4) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {
                "id": self.id,
                "name": self.name,
                "last_updated": self.last_updated.isoformat(),
                "llm_model_name": self.llm_model_name,
                "options": self.options,
                "messages": [m.__dict__() for m in self.messages],
            },
            default=str,
            indent=indent,
        )

    @staticmethod
    def from_json(json_data: str) -> ChatSession:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        messages = data["messages"]
        for m in messages:
            if "message_id" in m:
                m["id"] = "message_id"
                del m["message_id"]
        return ChatSession(
            id=data.get("id", data.get("id", data.get("session_id"))),
            name=data.get("name", data.get("name", data.get("session_name"))),
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
            llm_model_name=data["llm_model_name"],
            options=data.get("options"),
            messages=[OllamaMessage(**m) for m in messages],
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

    @property
    def is_valid(self) -> bool:
        """return true if session is valid"""
        return (
            len(self.name) > 0
            and len(self.llm_model_name) > 0
            and self.llm_model_name not in ["Select.BLANK", "None"]
            # and len(self.messages) > 0
        )

    def save(self) -> bool:
        """Save the chat session to a file"""
        if self._batching:
            self.log_it(f"CS is batching, not notifying: {self.name}")
            return False
        if not self._loaded:
            self.load()
        if not self.is_dirty:
            self.log_it(f"CS is not dirty, not notifying: {self.name}")
            return False  # No need to save if no changes
        if "system_prompt" in self._changes:
            msg = self.system_prompt
            if msg is not None:
                self._notify_subs(ChatMessage(parent_id=self.id, message_id=msg.id))
        nc: SessionChanges = SessionChanges()
        for change in self._changes:
            if change in session_change_list:
                nc.add(change)  # type: ignore

        self._notify_changed(nc)
        self.clear_changes()

        if settings.no_save_chat:
            return False  # Do not save if no_save_chat is set in settings
        if not self.is_valid or len(self.messages) == 0:
            self.log_it(f"CS not valid, not saving: {self.name}")
            return False  # Cannot save without name, LLM model name and at least one message

        self.log_it(f"CS saving: {self.name}")

        file_name = f"{self.id}.json"  # Use session ID as filename to avoid over
        try:
            with open(
                os.path.join(settings.chat_dir, file_name), "wt", encoding="utf-8"
            ) as f:
                f.write(self.to_json())
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
    def num_subs(self):
        """Return the number of subscribers"""
        return len(self._subs)
