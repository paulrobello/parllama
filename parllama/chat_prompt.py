"""Prompt manager class"""

from __future__ import annotations

import datetime
import os
import uuid
from dataclasses import dataclass
from io import StringIO

import simplejson as json
import rich.repr

from parllama.messages.par_messages import ParLogIt
from parllama.messages.par_prompt_messages import ParPromptDelete, ParPromptUpdated
from parllama.messages.shared import PromptChanges
from parllama.models.settings_data import settings
from parllama.par_event_system import ParEventSystemBase
from parllama.prompt_message import PromptMessage


@rich.repr.auto
@dataclass
class ChatPrompt(ParEventSystemBase):
    """Chat prompt class"""

    prompt_id: str
    prompt_name: str
    prompt_description: str
    messages: list[PromptMessage]
    last_updated: datetime.datetime
    _id_to_msg: dict[str, PromptMessage]
    _loaded: bool = False

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        prompt_id: str | None = None,
        prompt_name: str,
        prompt_description: str,
        messages: list[PromptMessage] | list[dict] | None = None,
        last_updated: datetime.datetime | None = None,
    ):
        """Initialize the chat prompt"""
        super().__init__()
        self._id_to_msg = {}
        self.prompt_id = prompt_id or uuid.uuid4().hex
        self.prompt_name = prompt_name
        self.prompt_description = prompt_description
        self.messages = []
        self._loaded = messages is not None and len(messages) > 0
        msgs = messages or []
        for m in msgs:
            if isinstance(m, PromptMessage):
                self.messages.append(m)
            else:
                self.messages.append(PromptMessage(prompt_id=self.prompt_id, **m))

        for m in self.messages:
            self._id_to_msg[m.message_id] = m

        self.last_updated = last_updated or datetime.datetime.now()

    def load(self) -> None:
        """Load chat prompts from files"""
        if self._loaded:
            return
        file_path = os.path.join(settings.prompt_dir, self.prompt_id + ".json")
        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, mode="rt", encoding="utf-8") as fh:
                data: dict = json.load(fh)

            msgs = data["messages"] or []
            for m in msgs:
                msg = PromptMessage(prompt_id=self.prompt_id, **m)
                self.messages.append(msg)
                self._id_to_msg[msg.message_id] = msg
            self._loaded = True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.post_message(
                ParLogIt(f"Error loading prompt {e}", notify=True, severity="error")
            )

    def delete(self) -> None:
        """Delete the prompt"""
        self.post_message(ParPromptDelete(prompt_id=self.prompt_id))

    def _notify_changed(self, changed: PromptChanges) -> None:
        """Notify changed"""
        self.last_updated = datetime.datetime.now()
        self.post_message(ParPromptUpdated(prompt_id=self.prompt_id, changed=changed))

    def add_message(self, msg: PromptMessage, prepend: bool = False) -> None:
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
        """Set the name of the chat prompt"""
        name = name.strip()
        if self.prompt_name == name:
            return
        self.prompt_name = name
        self._notify_changed({"name"})
        self.save()

    def set_description(self, description: str) -> None:
        """Set the description of the chat prompt"""
        description = description.strip()
        if self.prompt_description == description:
            return
        self.prompt_description = description
        self._notify_changed({"description"})
        self.save()

    def set_system_prompt(self, system_prompt: str) -> None:
        """Set system prompt for session"""
        msg: PromptMessage
        if len(self.messages) > 0 and self.messages[0].role == "system":
            msg = self.messages[0]
            if msg.content == system_prompt:
                return
            msg.content = system_prompt
            self._notify_changed({"messages"})
        else:
            msg = PromptMessage(
                prompt_id=self.prompt_id, content=system_prompt, role="system"
            )
            self.add_message(msg, True)

        self.save()

    def get_system_message(self) -> PromptMessage | None:
        """Get the system message"""
        for msg in self.messages:
            if msg.role == "system":
                return msg
        return None

    def get_first_user_message(self) -> PromptMessage | None:
        """Get the first user message"""
        for msg in self.messages:
            if msg.role == "user":
                return msg
        return None

    def new_prompt(self, prompt_name: str = "My Prompt"):
        """Start new session"""
        self.prompt_id = uuid.uuid4().hex
        self.prompt_name = prompt_name
        self.prompt_description = ""
        self.messages.clear()
        self._id_to_msg.clear()

    @property
    def is_loaded(self):
        """Check if the prompt is loaded"""
        return self._loaded

    def __iter__(self):
        """Iterate over messages"""
        return iter(self.messages)

    def __len__(self) -> int:
        """Get the number of messages"""
        return len(self.messages)

    def __getitem__(self, msg_id: str) -> PromptMessage:
        """Get a message"""
        return self._id_to_msg[msg_id]

    def __setitem__(self, msg_id: str, value: PromptMessage) -> None:
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

    def __contains__(self, item: PromptMessage) -> bool:
        """Check if a message exists"""
        return item.message_id in self._id_to_msg

    def __eq__(self, other: object) -> bool:
        """Check if two sessions are equal"""
        if not isinstance(other, ChatPrompt):
            return NotImplemented
        return self.prompt_id == other.prompt_id

    def __ne__(self, other: object) -> bool:
        """Check if two sessions are not equal"""
        if not isinstance(other, ChatPrompt):
            return NotImplemented
        return self.prompt_id != other.prompt_id

    def __str__(self) -> str:
        """Get a string representation of the chat session"""
        ret = StringIO()
        ret.write(f"# {self.prompt_name}\n\n")
        for msg in self.messages:
            ret.write(str(msg))
        return ret.getvalue()

    def to_json(self, indent: int = 4) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {
                "prompt_id": self.prompt_id,
                "last_updated": self.last_updated.isoformat(),
                "prompt_description": self.prompt_description,
                "prompt_name": self.prompt_name,
                "messages": [m.__dict__() for m in self.messages],
            },
            default=str,
            indent=indent,
        )

    @staticmethod
    def from_json(json_data: str) -> ChatPrompt:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        return ChatPrompt(
            prompt_id=data["prompt_id"],
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
            prompt_description=data.get("prompt_description", ""),
            prompt_name=data["prompt_name"],
            messages=[PromptMessage(**m) for m in data["messages"]],
        )

    @staticmethod
    def load_from_file(filename: str) -> ChatPrompt | None:
        """Load a chat prompt from a file"""
        try:
            with open(
                os.path.join(settings.prompt_dir, filename), "rt", encoding="utf-8"
            ) as f:
                return ChatPrompt.from_json(f.read())
        except (OSError, IOError):
            return None

    @property
    def is_valid(self) -> bool:
        """return true if session is valid"""
        return len(self.prompt_name) > 0

    def save(self) -> bool:
        """Save the chat prompt to a file"""
        if not self._loaded:
            self.load()
        if not self.is_valid or len(self.messages) == 0:
            return False  # Cannot save without session name, LLM model name and at least one message

        file_name = f"{self.prompt_id}.json"  # Use prompt ID as filename
        try:
            with open(
                os.path.join(settings.prompt_dir, file_name), "wt", encoding="utf-8"
            ) as f:
                f.write(self.to_json())
            return True
        except (OSError, IOError):
            return False

    def export_as_markdown(self, filename: str) -> bool:
        """Save the prompt to markdown file"""
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
