"""Characterization tests for ChatPrompt notification behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from textual.message import Message

from parllama.chat_manager import ChatManager
from parllama.chat_prompt import ChatPrompt
from parllama.messages.prompt_messages import DeletePrompt, PromptListChanged
from parllama.messages.ui_messages import LogIt
from parllama.settings_manager import settings


@dataclass
class RecordingApp:
    """Minimal app double that records Textual messages and bus broadcasts."""

    messages: list[Message] = field(default_factory=list)

    def post_message(self, message: Message) -> None:
        """Record a posted Textual message."""
        self.messages.append(message)

    def post_message_all(self, message: Message) -> None:
        """Record a broadcast Textual message."""
        self.messages.append(message)


@pytest.fixture
def isolated_prompt_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep prompt tests from reading or writing user data."""
    chat_dir = tmp_path / "chats"
    prompt_dir = tmp_path / "prompts"
    chat_dir.mkdir()
    prompt_dir.mkdir()
    monkeypatch.setattr(settings, "chat_dir", chat_dir)
    monkeypatch.setattr(settings, "prompt_dir", prompt_dir)


def test_prompt_save_notifies_manager_and_invalidates_prompt_list(
    isolated_prompt_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ChatPrompt._notify_changed notifies the chat manager directly."""
    from parllama.chat_manager import chat_manager as singleton

    manager = ChatManager()
    app = RecordingApp()
    manager.app = app  # type: ignore[assignment]
    monkeypatch.setattr(singleton, "notify_prompts_changed", manager.notify_prompts_changed)
    prompt = ChatPrompt(name="Prompt", description="before", messages=[])
    manager.add_prompt(prompt)
    app.messages.clear()

    prompt.description = "after"

    assert prompt.save() is False
    assert any(isinstance(message, PromptListChanged) for message in app.messages)


def test_prompt_delete_deletes_via_manager_and_broadcasts(
    isolated_prompt_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ChatPrompt.delete deletes via the chat manager and broadcasts DeletePrompt."""
    from parllama.chat_manager import chat_manager as singleton

    manager = ChatManager()
    app = RecordingApp()
    manager.app = app  # type: ignore[assignment]
    monkeypatch.setattr(singleton, "delete_prompt", manager.delete_prompt)
    prompt = ChatPrompt(name="Prompt", description="description", messages=[])
    manager.add_prompt(prompt)
    app.messages.clear()

    prompt.delete()

    assert prompt.id not in manager.prompt_ids
    assert any(isinstance(message, DeletePrompt) for message in app.messages)
    assert any(isinstance(message, PromptListChanged) for message in app.messages)
    assert any(isinstance(message, LogIt) for message in app.messages)
