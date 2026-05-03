"""Characterization tests for ChatPrompt notification behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from textual.message import Message

from parllama.chat_manager import ChatManager
from parllama.chat_prompt import ChatPrompt
from parllama.messages.messages import DeletePrompt, LogIt, PromptListChanged, PromptUpdated
from parllama.settings_manager import settings


@dataclass
class PromptRoutingApp:
    """Minimal app double that records and routes prompt Textual messages."""

    manager: ChatManager
    messages: list[Message] = field(default_factory=list)

    def post_message(self, message: Message) -> None:
        """Record a posted Textual message and mimic app prompt routing."""
        self.messages.append(message)
        if isinstance(message, PromptUpdated):
            self.manager.notify_prompts_changed()
        elif isinstance(message, DeletePrompt):
            self.manager.delete_prompt(message.prompt_id)


@pytest.fixture
def isolated_prompt_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep prompt tests from reading or writing user data."""
    chat_dir = tmp_path / "chats"
    prompt_dir = tmp_path / "prompts"
    chat_dir.mkdir()
    prompt_dir.mkdir()
    monkeypatch.setattr(settings, "chat_dir", chat_dir)
    monkeypatch.setattr(settings, "prompt_dir", prompt_dir)


def test_prompt_save_emits_prompt_updated_and_invalidates_prompt_list(isolated_prompt_settings: None) -> None:
    """ChatPrompt.save should emit Textual PromptUpdated for app/controller routing."""
    manager = ChatManager()
    app = PromptRoutingApp(manager)
    manager.app = app  # type: ignore[assignment]
    prompt = ChatPrompt(name="Prompt", description="before", messages=[])
    manager.add_prompt(prompt)
    app.messages.clear()

    prompt.description = "after"

    assert prompt.save() is False
    assert any(isinstance(message, PromptUpdated) for message in app.messages)
    assert any(isinstance(message, PromptListChanged) for message in app.messages)


def test_prompt_delete_emits_delete_prompt_and_invalidates_prompt_list(isolated_prompt_settings: None) -> None:
    """ChatPrompt.delete should emit Textual DeletePrompt for app/controller routing."""
    manager = ChatManager()
    app = PromptRoutingApp(manager)
    manager.app = app  # type: ignore[assignment]
    prompt = ChatPrompt(name="Prompt", description="description", messages=[])
    manager.add_prompt(prompt)
    app.messages.clear()

    prompt.delete()

    assert prompt.id not in manager.prompt_ids
    assert any(isinstance(message, DeletePrompt) for message in app.messages)
    assert any(isinstance(message, PromptListChanged) for message in app.messages)
    assert any(isinstance(message, LogIt) for message in app.messages)
