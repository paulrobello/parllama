"""Salt round-trip between session serialization and ``from_json`` reconstruction.

``SessionStore.serialize`` writes the salt under ``_salt``; ``from_json`` must
read the same key so a session-list load followed by a re-save cannot destroy
the salt of a password-protected session.
"""

from __future__ import annotations

import base64

import orjson
from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider

from parllama.chat_session import ChatSession
from parllama.session_store import SessionStore

SALT = b"0123456789abcdef"


def _session_with_salt() -> ChatSession:
    session = ChatSession(
        name="Session",
        llm_config=LlmConfig(provider=LlmProvider.OLLAMA, model_name="llama3.2", temperature=0.5),
        messages=[],
    )
    session._salt = SALT
    return session


def test_from_json_preserves_salt_written_by_serialize() -> None:
    """from_json reads the _salt key the store actually writes."""
    session = _session_with_salt()

    rebuilt = ChatSession.from_json(session.to_json())

    assert rebuilt._salt == SALT


def test_from_json_tolerates_legacy_salt_key() -> None:
    """Session-list loading still accepts the legacy __salt__ spelling."""
    session = _session_with_salt()
    data = SessionStore.serialize(session)
    data["__salt__"] = data.pop("_salt")

    rebuilt = ChatSession.from_json(orjson.dumps(data).decode("utf-8"))

    assert rebuilt._salt == SALT


def test_resave_after_list_load_keeps_salt() -> None:
    """Loading a session for the list and re-saving it must not null the salt on disk."""
    session = _session_with_salt()

    listed = ChatSession.from_json(session.to_json())
    resaved = SessionStore.serialize(listed)

    assert resaved["_salt"] == base64.b64encode(SALT).decode("utf-8")
