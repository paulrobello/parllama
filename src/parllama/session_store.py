"""Serialization and persistence of chat sessions to the chat directory."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Any

from parllama.secure_file_ops import SecureFileOperations
from parllama.settings_manager import settings

if TYPE_CHECKING:
    from parllama.chat_session import ChatSession


class SessionStore:
    """Reads and writes chat session JSON files through ``SecureFileOperations``."""

    def __init__(self) -> None:
        """Create a store whose validation limits come from the current file-validation settings."""
        self._secure_ops = SecureFileOperations(
            max_file_size_mb=settings.file_validation.max_json_size_mb,
            allowed_extensions=settings.file_validation.allowed_json_extensions,
            validate_content=settings.file_validation.validate_file_content,
            sanitize_filenames=settings.file_validation.sanitize_filenames,
        )

    @staticmethod
    def path_for(filename: str) -> Path:
        """Return the path of a session file inside the configured chat directory.

        Args:
            filename: The session file name, e.g. ``"<id>.json"``.
        """
        return Path(settings.chat_dir) / filename

    @staticmethod
    def serialize(session: ChatSession) -> dict[str, Any]:
        """Build the persisted dictionary form of a session.

        Args:
            session: The session to serialize.

        Returns:
            Session metadata, encrypted salt/key fields (if a password is set),
            cost/usage tracking, and all messages.
        """
        return {
            "id": session.id,
            "_salt": (base64.b64encode(session._salt).decode("utf-8") if session._salt else None),
            "__key__": session._key_secure,
            "name": session.name,
            "name_generated": session.name_generated,
            "last_updated": session.last_updated.isoformat(),
            "llm_config": session.llm_config.to_json(),
            "total_cost": session.total_cost,
            "total_usage": session.total_usage,
            "messages": [m.to_dict() for m in session.messages],
        }

    @staticmethod
    def normalize_legacy_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rename the legacy ``message_id`` key to ``id`` in place on each message dict.

        Args:
            messages: Raw message dictionaries as read from disk.

        Returns:
            The same list, for chaining.
        """
        for m in messages:
            if "message_id" in m:
                m["id"] = m["message_id"]
                del m["message_id"]
        return messages

    def read(self, session_id: str) -> dict[str, Any] | None:
        """Read a session's JSON file.

        Args:
            session_id: The session id; the file is ``<id>.json``.

        Returns:
            The parsed data, or None when the session has no file yet.

        Raises:
            SecureFileOpsError: If the file fails validation or cannot be parsed.
        """
        file_path = self.path_for(f"{session_id}.json")
        if not file_path.exists():
            return None
        return self._secure_ops.read_json_file(file_path)

    def read_text(self, filename: str) -> str:
        """Read a session file's raw JSON text.

        Args:
            filename: The session file name inside the chat directory.

        Raises:
            OSError: If the file cannot be read.
            SecureFileOpsError: If the file fails validation.
        """
        return self._secure_ops.read_text_file(self.path_for(filename))

    def write(self, session: ChatSession) -> None:
        """Atomically write a session to ``<id>.json``, restoring the previous file on failure.

        Args:
            session: The session to persist.

        Raises:
            OSError: If the write fails.
            SecureFileOpsError: If the data or path fails validation.
        """
        file_path = self.path_for(f"{session.id}.json")
        with self._secure_ops.backup_file(file_path):
            self._secure_ops.write_json_file(
                file_path,
                self.serialize(session),
                atomic=True,
                create_dirs=True,
                indent=2,
            )
