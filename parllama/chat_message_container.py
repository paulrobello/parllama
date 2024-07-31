"""Chat message container base class"""

from __future__ import annotations

import datetime
import os
from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from typing import Generator

import simplejson as json
import rich.repr

from parllama.chat_message import OllamaMessage
from parllama.models.settings_data import settings
from parllama.par_event_system import ParEventSystemBase


@rich.repr.auto
@dataclass
class ChatMessageContainer(ParEventSystemBase):
    """Chat message container base class"""

    _name: str
    """Name of the chat message container"""
    messages: list[OllamaMessage]
    """Messages in the chat message container"""
    last_updated: datetime.datetime
    """Last updated timestamp of the chat message container"""

    _id_to_msg: dict[str, OllamaMessage]
    _changes: set[str]
    _batching: bool

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str | None = None,
        messages: list[OllamaMessage] | list[dict] | None = None,
        last_updated: datetime.datetime | None = None,
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
            msg: OllamaMessage
            if isinstance(m, OllamaMessage):
                msg = m
            else:
                msg = OllamaMessage(**m)
            self.messages.append(msg)
            self._id_to_msg[msg.id] = msg
            self.mount(msg)
        self.last_updated = last_updated or datetime.datetime.now()
        self._batching = False

    def add_message(self, msg: OllamaMessage, prepend: bool = False) -> None:
        """Add a message"""
        if prepend:
            self.messages.insert(0, msg)
        else:
            self.messages.append(msg)
        self._id_to_msg[msg.id] = msg
        self.last_updated = datetime.datetime.now()
        self.mount(msg)
        self._changes.add("messages")
        self.log_it(f"Added {msg.role} message to: {self.name}")
        # if len(self.messages) > 2:
        #     raise Exception(f"why! {len(self.messages)}")
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
    def system_prompt(self) -> OllamaMessage | None:
        """Get the system message"""
        if len(self.messages) > 0 and self.messages[0].role == "system":
            return self.messages[0]
        return None

    # system prompt setter
    @system_prompt.setter
    def system_prompt(self, value: OllamaMessage) -> None:
        """Set system prompt"""
        if len(self.messages) > 0 and self.messages[0].role == "system":
            msg: OllamaMessage = self.messages[0]
            if msg.content == value.content:
                return
            msg.content = value.content
            self.last_updated = datetime.datetime.now()
            self._changes.add("messages")
            self._changes.add("system_prompt")
            self.save()
        else:
            self.add_message(value, True)

    def get_first_user_message(self) -> OllamaMessage | None:
        """Get the first user message"""
        for msg in self.messages:
            if msg.role == "user":
                return msg
        return None

    def get_last_user_message(self) -> OllamaMessage | None:
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

    def __getitem__(self, msg_id: str) -> OllamaMessage:
        """Get a message"""
        return self._id_to_msg[msg_id]

    def __setitem__(self, msg_id: str, value: OllamaMessage) -> None:
        """Set a message"""
        for i, msg in enumerate(self.messages):
            if msg.id == msg_id:
                self._id_to_msg[msg_id] = value
                self.messages[i] = value
                self.last_updated = datetime.datetime.now()
                self._changes.add("messages")
                self.save()
                return
        self.add_message(value)

    def __delitem__(self, key: str) -> None:
        """Delete a message"""
        del self._id_to_msg[key]
        for i, msg in enumerate(self.messages):
            if msg.id == key:
                self.messages.pop(i)
                self.last_updated = datetime.datetime.now()
                self._changes.add("messages")
                self.save()
                return

    def __contains__(self, item: OllamaMessage) -> bool:
        """Check if a message exists"""
        return item.id in self._id_to_msg

    def __iadd__(self, other: OllamaMessage) -> ChatMessageContainer:
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

    def to_json(self, indent: int = 4) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {
                "id": self.id,
                "name": self._name,
                "last_updated": self.last_updated.isoformat(),
                "messages": [m.__dict__() for m in self.messages],
            },
            default=str,
            indent=indent,
        )

    def export_as_markdown(self, filename: str) -> bool:
        """Save the chat session to markdown file"""
        try:
            with open(
                os.path.join(settings.export_md_dir, filename), "wt", encoding="utf-8"
            ) as f:
                f.write(str(self))
            return True
        except (OSError, IOError):
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

    def clear_changes(self) -> None:
        """Clear changes"""
        self.log_it("Clearing changes")
        self._changes.clear()

    @property
    def is_dirty(self) -> bool:
        """Check if there are any changes"""
        self.log_it(",".join(self._changes))
        return len(self._changes) > 0

    @contextmanager
    def batch_changes(self) -> Generator[None, None, None]:
        """Batch changes"""
        self.log_it("Starting batch changes")
        self._batching = True
        yield
        self._batching = False
        self.log_it("Committing batch changes")
        self.save()
