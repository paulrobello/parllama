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
from textual.widget import Widget

from parllama.messages.main import ChatGenerationAborted
from parllama.messages.main import ChatMessage
from parllama.messages.main import SessionUpdated
from parllama.models.settings_data import settings


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

    session: ChatSession | None = None

    def __init__(
        self,
        *,
        role: Literal["user", "assistant", "system"],
        content: str,
        message_id: str | None = None,
        session: ChatSession | None = None,
    ) -> None:
        """Initialize the chat message"""
        self.message_id = message_id or uuid.uuid4().hex
        self.role = role
        self.content = content
        self.session = session
        self.id_to_msg = {self.message_id: self}

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        return OMessage(role=self.role, content=self.content)

    def save(self) -> None:
        """Save the chat session to a file"""
        if self.session:
            self.session.save()

    def to_json(self) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {"message_id": self.message_id, "role": self.role, "content": self.content},
            default=str,
            indent=4,
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


@dataclass
class ChatSession:
    """Chat session class"""

    session_id: str
    llm_model_name: str
    options: OllamaOptions
    session_name: str
    messages: list[OllamaMessage]
    id_to_msg: dict[str, OllamaMessage]
    last_updated: datetime.datetime
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

        self.id_to_msg = {}
        self.last_updated = last_updated or datetime.datetime.now()

        for m in self.messages:
            m.session = self
            self.id_to_msg[m.message_id] = m

    def get_message(self, message_id: str) -> OllamaMessage | None:
        """Get a message"""
        return self.id_to_msg.get(message_id)

    def add_message(self, msg: OllamaMessage) -> None:
        """Add a message"""
        msg.session = self
        self.messages.append(msg)
        self.id_to_msg[msg.message_id] = msg
        self.last_updated = datetime.datetime.now()
        self.save()

    def set_name(self, name: str) -> None:
        """Set the name of the chat session"""
        self.session_name = name
        self.last_updated = datetime.datetime.now()
        self.save()

    def set_llm_model(self, llm_model_name: str) -> None:
        """Set the LLM model name"""
        self.llm_model_name = llm_model_name
        self.last_updated = datetime.datetime.now()
        self.save()

    def set_temperature(self, temperature: float | None) -> None:
        """Set the temperature"""
        if temperature:
            self.options["temperature"] = temperature
        else:
            del self.options["temperature"]
        self.last_updated = datetime.datetime.now()
        self.save()

    async def send_chat(self, from_user: str, widget: Widget) -> bool:
        """Send a chat message to LLM"""
        self._generating = True
        try:
            msg: OllamaMessage = OllamaMessage(content=from_user, role="user")
            self.add_message(msg)
            widget.post_message(
                ChatMessage(session_id=self.session_id, message_id=msg.message_id)
            )

            msg = OllamaMessage(content="", role="assistant")
            self.add_message(msg)
            widget.post_message(
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
                msg.content += chunk["message"]["content"]
                if self._abort:
                    is_aborted = True
                    try:
                        msg.content += "\n\nAborted..."
                        widget.post_message(ChatGenerationAborted(self.session_id))
                        stream.close()  # type: ignore
                    except Exception:  # pylint:disable=broad-except
                        pass
                    finally:
                        self._abort = False
                    break
                widget.post_message(
                    ChatMessage(session_id=self.session_id, message_id=msg.message_id)
                )

            msg.save()

            if (
                not is_aborted
                and settings.auto_name_session
                and not self._name_generated
            ):
                self._name_generated = True
                self.set_name(self.gen_session_name(self.messages[0].content))
                widget.post_message(SessionUpdated(session_id=self.session_id))
        finally:
            self._generating = False

        return not is_aborted

    def new_session(self, session_name: str = "My Chat"):
        """Start new session"""
        self.session_id = uuid.uuid4().hex
        self.session_name = session_name
        self.messages.clear()
        self.id_to_msg.clear()

    def gen_session_name(self, text: str) -> str:
        """Generate a session name from the given text using llm"""
        ret = settings.ollama_client.generate(
            model=settings.auto_name_session_llm or self.llm_model_name,
            options={"temperature": 0.1},
            prompt=text,
            system="""You are a helpful assistant.
            You will be given some text to summarize.
            You must follow these instructions:
            * Generate a descriptive session name of no more than a 4 words.
            * Only output the session name.
            * Do not answer any questions or explain anything.
            * Do not output any preamble.
            Examples:
            "Why is grass green" -> "Green Grass"
            "Why is the sky blue?" -> "Blue Sky"
            "What is the tallest mountain?" -> "Tallest Mountain"
            "What is the meaning of life?" -> "Meaning of Life"
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
        return self.id_to_msg[msg_id]

    def __setitem__(self, msg_id: str, value: OllamaMessage) -> None:
        """Set a message"""
        self.id_to_msg[msg_id] = value
        for i, msg in enumerate(self.messages):
            if msg.message_id == msg_id:
                self.messages[i] = value
                return
        self.messages.append(value)

    def __delitem__(self, key: str) -> None:
        """Delete a message"""
        del self.id_to_msg[key]
        for i, msg in enumerate(self.messages):
            if msg.message_id == key:
                self.messages.pop(i)
                return

    def __contains__(self, item: OllamaMessage) -> bool:
        """Check if a message exists"""
        return item.message_id in self.id_to_msg

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

    def to_json(self) -> str:
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
            indent=4,
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
            and self.llm_model_name not in ["Select.BLANK", "None", ""]
            and len(self.messages) > 0
        )

    def save(self) -> bool:
        """Save the chat session to a file"""
        if settings.no_save_chat:
            return False  # Do not save if no_save_chat is set in settings
        if not self.is_valid():
            return False  # Cannot save without session name, LLM model name and at least one message

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
