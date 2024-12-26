"""Chat message container base class"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO

import orjson as json
import rich.repr

from parllama.chat_message import ParllamaChatMessage
from parllama.messages.par_chat_messages import ParChatMessageDeleted
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings


@rich.repr.auto
@dataclass
class ChatMessageContainer(ParEventSystemBase):
    """Chat message container base class"""

    _name: str
    """Name of the chat message container"""
    messages: list[ParllamaChatMessage]
    """Messages in the chat message container"""
    last_updated: datetime
    """Last updated timestamp of the chat message container"""

    _id_to_msg: dict[str, ParllamaChatMessage]
    _changes: set[str]
    _batching: bool
    _loaded: bool

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str | None = None,
        messages: list[ParllamaChatMessage] | list[dict] | None = None,
        last_updated: datetime | None = None,
    ):
        """Initialize the chat prompt"""
        super().__init__(id=id)
        self._batching = True
        self._changes = set()
        self._id_to_msg = {}
        self._name = name or "Messages"
        self.messages = []
        msgs = messages or []
        for m in msgs:
            msg: ParllamaChatMessage
            if isinstance(m, ParllamaChatMessage):
                msg = m
            else:
                msg = ParllamaChatMessage(**m)
            self.messages.append(msg)
            self._id_to_msg[msg.id] = msg
            self.mount(msg)
        self.last_updated = last_updated or datetime.now(UTC)
        self._loaded = messages is not None
        self._batching = False

    def unload(self) -> None:
        """Unload the messages"""
        self._loaded = False
        self.messages = []

    @property
    def is_loaded(self):
        """Check if the messages have been loaded"""
        return self._loaded

    @property
    def batching(self) -> bool:
        """Check if the session is loading"""
        return self._batching

    @batching.setter
    def batching(self, value: bool) -> None:
        """Set the loading state"""
        self._batching = value

    def add_message(self, msg: ParllamaChatMessage, prepend: bool = False) -> None:
        """Add a message"""
        if prepend:
            self.messages.insert(0, msg)
        else:
            self.messages.append(msg)
        self._id_to_msg[msg.id] = msg
        self.last_updated = datetime.now(UTC)
        self.mount(msg)
        self._changes.add("messages")
        self._loaded = True
        # self.log_it(f"Added {msg.role} message to: {self.name}")
        self.save()

    @property
    def name(self) -> str:
        """Get the name of the chat container"""
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        """Set the name of the chat container"""
        name = name.strip()
        if self._name == name:
            return
        self._name = name
        self._changes.add("name")

        self.save()

    @property
    def system_prompt(self) -> ParllamaChatMessage | None:
        """Get the system message"""
        if len(self.messages) > 0 and self.messages[0].role == "system":
            return self.messages[0]
        return None

    # system prompt setter
    @system_prompt.setter
    def system_prompt(self, value: ParllamaChatMessage | None) -> None:
        """Set system prompt"""
        if not value:
            if len(self.messages) == 0 or self.messages[0].role != "system":
                return
            msg = self.messages.pop(0)
            self.last_updated = datetime.now(UTC)
            self._changes.add("messages")
            self._changes.add("system_prompt")
            self.save()
            if msg.parent:
                self.post_message(ParChatMessageDeleted(parent_id=msg.parent.id, message_id=msg.id))
            return

        if len(self.messages) > 0 and self.messages[0].role == "system":
            msg: ParllamaChatMessage = self.messages[0]
            if msg.content == value.content:
                return
            msg.content = value.content
            self.last_updated = datetime.now(UTC)
            self._changes.add("messages")
            self._changes.add("system_prompt")
            self.save()
        else:
            self.add_message(value, True)

    def get_first_user_message(self) -> ParllamaChatMessage | None:
        """Get the first user message"""
        for msg in self.messages:
            if msg.role == "user":
                return msg
        return None

    def get_last_user_message(self) -> ParllamaChatMessage | None:
        """Get the last user message"""
        if len(self.messages) == 0:
            return None
        msg = self.messages[-1]
        if msg.role == "user":
            return msg
        return None

    def __iter__(self):
        """Iterate over messages"""
        return iter(self.messages)

    def __len__(self) -> int:
        """Get the number of messages"""
        return len(self.messages)

    def __getitem__(self, msg_id: str) -> ParllamaChatMessage | None:
        """Get a message"""
        return self._id_to_msg.get(msg_id)

    def __setitem__(self, msg_id: str, value: ParllamaChatMessage) -> None:
        """Set a message"""
        for i, msg in enumerate(self.messages):
            if msg.id == msg_id:
                self._id_to_msg[msg_id] = value
                self.messages[i] = value
                self.last_updated = datetime.now(UTC)
                self._changes.add("messages")
                self.save()
                return
        self.add_message(value)

    def __delitem__(self, key: str) -> None:
        """Delete a message"""
        del self._id_to_msg[key]
        for i, msg in enumerate(self.messages):
            if msg.id == key:
                if msg.parent:
                    self.post_message(ParChatMessageDeleted(parent_id=msg.parent.id, message_id=msg.id))

                msg = self.messages.pop(i)
                self.last_updated = datetime.now(UTC)
                if msg.role == "system":
                    self._changes.add("system_prompt")
                self._changes.add("messages")
                self.save()
                return

    def __contains__(self, item: ParllamaChatMessage) -> bool:
        """Check if a message exists"""
        return item.id in self._id_to_msg

    def __iadd__(self, other: ParllamaChatMessage) -> ChatMessageContainer:
        """Add a message to the chat"""
        self.add_message(other)
        return self

    def __str__(self) -> str:
        """Get a string representation of the chat"""
        ret = StringIO()
        ret.write(f"# {self.name}\n\n")
        for msg in self.messages:
            ret.write(str(msg))
        return ret.getvalue()

    def to_json(self) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {
                "id": self.id,
                "name": self._name,
                "last_updated": self.last_updated.isoformat(),
                "messages": [m.to_dict() for m in self.messages],
            },
            str,
            json.OPT_INDENT_2,
        ).decode("utf-8")

    def export_as_markdown(self, filename: str) -> bool:
        """Save the chat session to markdown file"""
        try:
            with open(os.path.join(settings.export_md_dir, filename), "w", encoding="utf-8") as f:
                f.write(str(self))
            return True
        except OSError:
            return False

    @property
    def context_length(self) -> int:
        """Return current message context length"""
        total: int = 0
        for msg in self.messages:
            total += len(msg.content)
        return total

    def save(self) -> bool:
        """Save chats to file"""
        raise NotImplementedError("save not implemented in base class")

    def clear_messages(self) -> None:
        """Clear all messages"""
        self.messages.clear()
        self._id_to_msg.clear()
        self._changes.add("messages")

    def clear_changes(self) -> None:
        """Clear changes"""
        # self.log_it("Clearing changes")
        self._changes.clear()

    @property
    def is_dirty(self) -> bool:
        """Check if there are any changes"""
        # self.log_it(",".join(self._changes))
        return len(self._changes) > 0

    @is_dirty.setter
    def is_dirty(self, value: bool) -> None:
        """Set dirty status"""
        if value:
            self._changes.add("is_dirty")
        else:
            self.clear_changes()

    @contextmanager
    def batch_changes(self) -> Generator[None, None, None]:
        """Batch changes"""
        # self.log_it("Starting batch changes")
        self._batching = True
        yield
        self._batching = False
        # self.log_it("Committing batch changes")
        self.save()
