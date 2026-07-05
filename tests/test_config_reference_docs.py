"""Guard against drift between the config groups and the configuration reference doc.

Every field defined on a Pydantic config group in
``src/parllama/settings/config_groups.py`` must be documented in
``docs/reference/configuration.md``. This test fails if a new config key is
added without a corresponding doc entry, keeping the hand-maintained reference
from silently going stale.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from parllama.settings import config_groups as cg

_DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "reference" / "configuration.md"


def _config_group_models() -> list[type[BaseModel]]:
    """Return every Pydantic config-group model defined in config_groups.py."""
    return [
        obj
        for obj in vars(cg).values()
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == cg.__name__
    ]


def test_all_config_group_fields_are_documented() -> None:
    """Assert each config-group field name appears in the configuration reference."""
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    groups = _config_group_models()
    assert groups, "No config-group models discovered — check config_groups.py import."

    undocumented: dict[str, list[str]] = {}
    for group in groups:
        for field_name in group.model_fields:
            if field_name not in doc_text:
                undocumented.setdefault(group.__name__, []).append(field_name)

    assert not undocumented, (
        "Config keys missing from docs/reference/configuration.md: "
        f"{undocumented}. Document them (or update this test) to fix the drift."
    )
