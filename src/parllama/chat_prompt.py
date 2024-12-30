"""Prompt manager class"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import orjson as json
import pytz
import rich.repr

from parllama.chat_message import ParllamaChatMessage
from parllama.chat_message_container import ChatMessageContainer
from parllama.messages.par_prompt_messages import ParPromptDelete, ParPromptUpdated
from parllama.messages.shared import PromptChanges, prompt_change_list
from parllama.settings_manager import settings


@rich.repr.auto
@dataclass
class ChatPrompt(ChatMessageContainer):
    """Chat prompt class"""

    _description: str
    messages: list[ParllamaChatMessage]
    last_updated: datetime
    source: str | None

    _submit_on_load: bool
    _id_to_msg: dict[str, ParllamaChatMessage]

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str,
        description: str,
        messages: list[ParllamaChatMessage] | list[dict] | None = None,
        submit_on_load: bool = False,
        last_updated: datetime | None = None,
        source: str | None = None,
    ):
        """Initialize the chat prompt"""
        super().__init__(id=id, name=name, messages=messages, last_updated=last_updated)
        self._description = description
        self._submit_on_load = submit_on_load
        self.source = source

    def load(self) -> None:
        """Load chat prompts from files"""
        if self._loaded:
            return
        self._batching = True

        file_path = Path(settings.prompt_dir) / f"{self.id}.json"
        if not file_path.exists():
            return

        try:
            data: dict = json.loads(file_path.read_bytes())
            self.clear_messages()
            msgs = data["messages"] or []
            for m in msgs:
                self.add_message(ParllamaChatMessage(**m))
            self._loaded = True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log_it(f"Error loading prompt {e}", notify=True, severity="error")
        finally:
            self._batching = False

    def delete(self) -> None:
        """Delete the prompt"""
        self.post_message(ParPromptDelete(prompt_id=self.id))

    def _notify_changed(self, changed: PromptChanges) -> None:
        """Notify changed"""
        self.post_message(ParPromptUpdated(prompt_id=self.id, changed=changed))

    @property
    def description(self) -> str:
        """Get the description of the chat prompt"""
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        """Set the description of the chat prompt"""
        value = value.strip()
        if self._description == value:
            return
        self._description = value
        self._changes.add("description")
        self.save()

    @property
    def submit_on_load(self) -> bool:
        """Get whether the prompt should be submitted on load"""
        return self._submit_on_load

    @submit_on_load.setter
    def submit_on_load(self, value: bool) -> None:
        """Set whether the prompt should be submitted on load"""
        if self._submit_on_load == value:
            return
        self._submit_on_load = value
        self._changes.add("submit_on_load")
        self.save()

    def new_prompt(self, prompt_name: str = "My Prompt"):
        """Start new session"""
        self.id = uuid.uuid4().hex
        self._name = prompt_name
        self._description = ""
        self.source = ""
        self.messages.clear()
        self._id_to_msg.clear()
        self._loaded = False
        self.batching = False
        self.clear_changes()

    def __eq__(self, other: object) -> bool:
        """Check if two sessions are equal"""
        if not isinstance(other, ChatPrompt):
            return NotImplemented
        return self.id == other.id

    def __ne__(self, other: object) -> bool:
        """Check if two sessions are not equal"""
        if not isinstance(other, ChatPrompt):
            return NotImplemented
        return self.id != other.id

    def to_json(self) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {
                "id": self.id,
                "name": self.name,
                "last_updated": self.last_updated.isoformat(),
                "description": self._description,
                "submit_on_load": self._submit_on_load,
                "messages": [m.to_dict() for m in self.messages],
                "source": self.source,
            },
            str,
            json.OPT_INDENT_2,
        ).decode("utf-8")

    @staticmethod
    def from_json(json_data: str, load_messages: bool = False) -> ChatPrompt:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        utc = pytz.UTC

        return ChatPrompt(
            id=data["id"],
            name=data["name"],
            last_updated=datetime.fromisoformat(data["last_updated"]).replace(tzinfo=utc),
            description=data.get("description", ""),
            messages=([ParllamaChatMessage(**m) for m in data["messages"]] if load_messages else None),
            submit_on_load=data.get("submit_on_load", False),
            source=data.get("source"),
        )

    @staticmethod
    def load_from_file(filename: str) -> ChatPrompt | None:
        """Load a chat prompt from a file"""
        try:
            with open(os.path.join(settings.prompt_dir, filename), encoding="utf-8") as f:
                return ChatPrompt.from_json(f.read())
        except OSError:
            return None

    @property
    def is_valid(self) -> bool:
        """return true if session is valid"""
        return len(self.name) > 0

    def save(self) -> bool:
        """Save the chat prompt to a file"""
        if self._batching:
            # self.log_it(f"CP is batching, not notifying: {self.name}")
            return False
        if not self._loaded:
            self.load()
        if not self.is_dirty:
            # self.log_it(f"CP is not dirty, not notifying: {self.name}")
            return False  # No need to save if no changes
        self.last_updated = datetime.now(UTC)
        nc: PromptChanges = PromptChanges()
        for change in self._changes:
            if change in prompt_change_list:
                nc.add(change)  # type: ignore

        self._notify_changed(nc)
        self.clear_changes()

        if not self.is_valid:
            # self.log_it(f"CP not valid, not saving: {self.id}")
            return False  # Cannot save without name

        file_name = f"{self.id}.json"  # Use prompt ID as filename
        try:
            with open(os.path.join(settings.prompt_dir, file_name), "w", encoding="utf-8") as f:
                f.write(self.to_json())
            return True
        except OSError:
            return False

    def replace_messages(self, new_messages: list[ParllamaChatMessage]) -> None:
        """Replace all messages with new ones"""
        self.messages = new_messages
        self._id_to_msg = {m.id: m for m in new_messages}
        self._changes.add("messages")

    def clone(self, new_id: bool = False) -> ChatPrompt:
        """Clone the chat prompt"""
        return ChatPrompt(
            id=uuid.uuid4().hex if new_id else self.id,
            name=self.name,
            description=self._description,
            messages=[m.clone() for m in self.messages],
            submit_on_load=self._submit_on_load,
            last_updated=self.last_updated,
            source=self.source,
        )
