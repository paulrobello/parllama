"""Prompt manager class"""

from __future__ import annotations

import datetime
import os
import uuid
from dataclasses import dataclass

import simplejson as json
import rich.repr

from parllama.chat_message import OllamaMessage
from parllama.chat_message_container import ChatMessageContainer
from parllama.messages.par_messages import ParLogIt
from parllama.messages.par_prompt_messages import ParPromptDelete, ParPromptUpdated
from parllama.messages.shared import PromptChanges
from parllama.models.settings_data import settings


@rich.repr.auto
@dataclass
class ChatPrompt(ChatMessageContainer):
    """Chat prompt class"""

    description: str
    messages: list[OllamaMessage]
    last_updated: datetime.datetime
    _id_to_msg: dict[str, OllamaMessage]
    _loaded: bool = False

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str,
        description: str,
        messages: list[OllamaMessage] | list[dict] | None = None,
        last_updated: datetime.datetime | None = None,
    ):
        """Initialize the chat prompt"""
        super().__init__(id=id, name=name, messages=messages, last_updated=last_updated)
        self._loading = True
        self.description = description
        self._loaded = messages is not None and len(messages) > 0
        self._loading = False

    def load(self) -> None:
        """Load chat prompts from files"""
        if self._loaded:
            return
        self._loading = True

        file_path = os.path.join(settings.prompt_dir, self.id + ".json")
        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, mode="rt", encoding="utf-8") as fh:
                data: dict = json.load(fh)

            msgs = data["messages"] or []
            for m in msgs:
                self.add_message(OllamaMessage(**m))
            self._loaded = True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.post_message(
                ParLogIt(f"Error loading prompt {e}", notify=True, severity="error")
            )
        finally:
            self._loading = False

    def delete(self) -> None:
        """Delete the prompt"""
        self.post_message(ParPromptDelete(prompt_id=self.id))

    def _notify_changed(self, changed: PromptChanges) -> None:
        """Notify changed"""
        self.last_updated = datetime.datetime.now()
        self.post_message(ParPromptUpdated(prompt_id=self.id, changed=changed))

    def set_description(self, description: str) -> None:
        """Set the description of the chat prompt"""
        description = description.strip()
        if self.description == description:
            return
        self.description = description
        self._notify_changed({"description"})
        self.save()

    def new_prompt(self, prompt_name: str = "My Prompt"):
        """Start new session"""
        self.id = uuid.uuid4().hex
        self.name = prompt_name
        self.description = ""
        self.messages.clear()
        self._id_to_msg.clear()

    @property
    def is_loaded(self):
        """Check if the prompt is loaded"""
        return self._loaded

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

    def to_json(self, indent: int = 4) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {
                "id": self.id,
                "name": self.name,
                "last_updated": self.last_updated.isoformat(),
                "description": self.description,
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
            id=data["id"],
            name=data["name"],
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
            description=data.get("description", ""),
            messages=[OllamaMessage(**m) for m in data["messages"]],
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
        return len(self.name) > 0

    def save(self) -> bool:
        """Save the chat prompt to a file"""
        if not self._loaded:
            self.load()
        if not self.is_valid:
            return False  # Cannot save without session name, LLM model name and at least one message

        file_name = f"{self.id}.json"  # Use prompt ID as filename
        try:
            with open(
                os.path.join(settings.prompt_dir, file_name), "wt", encoding="utf-8"
            ) as f:
                f.write(self.to_json())
            return True
        except (OSError, IOError):
            return False
