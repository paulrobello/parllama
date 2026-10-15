"""ARC-003: importing every parllama module and touching every manager singleton performs no I/O.

Runs in a subprocess because this test process has already imported and bootstrapped parllama.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCRIPT = """
import importlib
import pkgutil

import parllama

skipped = []
for mod in pkgutil.walk_packages(parllama.__path__, "parllama."):
    if mod.name == "parllama.__main__":
        continue
    importlib.import_module(mod.name)

from parllama.chat_manager import chat_manager
from parllama.memory_manager import memory_manager
from parllama.ollama_data_manager import ollama_dm
from parllama.prompt_utils.import_fabric import import_fabric_manager
from parllama.provider_manager import provider_manager
from parllama.secrets_manager import secrets_manager
from parllama.settings_manager import settings
from parllama.theme_manager import theme_manager
from parllama.update_manager import update_manager

for singleton in (chat_manager, memory_manager, ollama_dm, import_fabric_manager, provider_manager,
                  secrets_manager, settings, theme_manager, update_manager):
    assert singleton is not None
assert settings._initialized is False, "settings bootstrapped as a side effect of import"
print("OK")
"""


def test_import_and_singleton_access_touch_no_files(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_CACHE_HOME": str(home / "cache"),
        "XDG_CONFIG_HOME": str(home / "config"),
        "PARLLAMA_DATA_DIR": str(home / "data" / "parllama"),
    }
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")
    assert list(home.iterdir()) == [], f"import created files: {sorted(p.name for p in home.rglob('*'))}"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["home"], "import wrote into the working directory"
