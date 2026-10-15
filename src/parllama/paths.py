"""User data / cache directory layout, legacy-location migration, and purge flags."""

from __future__ import annotations

import os
import shutil
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from xdg_base_dirs import xdg_cache_home, xdg_data_home

from parllama import __application_binary__

if TYPE_CHECKING:
    from parllama.settings_manager import Settings

old_data_dir = Path("~/.parllama").expanduser()


def purge_folder(folder: Path) -> None:
    """Delete ``folder`` and recreate it empty, if it exists."""
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)


def setup_directories(settings_obj: Settings, args: Namespace) -> None:
    """Resolve, migrate, and create the data / cache layout on ``settings_obj``, then apply purge flags."""
    if args.no_save:
        settings_obj.no_save = True

    if args.no_chat_save:
        settings_obj.no_save_chat = True

    data_dir = Path(
        args.data_dir or os.environ.get("PARLLAMA_DATA_DIR") or str(xdg_data_home() / __application_binary__)
    )
    settings_obj.data_dir = data_dir
    if old_data_dir.exists():
        shutil.move(old_data_dir, data_dir)

    old_cache_dir = data_dir / "cache"
    cache_dir = xdg_cache_home() / __application_binary__
    settings_obj.cache_dir = cache_dir
    if old_cache_dir.exists():
        shutil.move(old_cache_dir, cache_dir)

    settings_obj.image_cache_dir = cache_dir / "image"
    settings_obj.ollama_cache_dir = cache_dir / "ollama"
    settings_obj.provider_models_file = cache_dir / "provider_models.json"

    settings_obj.chat_dir = data_dir / "chats"
    settings_obj.prompt_dir = data_dir / "prompts"
    settings_obj.export_md_dir = data_dir / "md_exports"
    settings_obj.chat_history_file = data_dir / "chat_history.json"
    settings_obj.secrets_file = data_dir / "secrets.json"

    execution_dir = data_dir / "execution"
    execution = settings_obj.execution
    execution.execution_temp_dir = cache_dir / "execution" / "temp"
    execution.execution_templates_file = execution_dir / "templates.json"
    execution.execution_history_file = execution_dir / "history.json"

    for folder in (
        cache_dir,
        settings_obj.image_cache_dir,
        settings_obj.ollama_cache_dir,
        settings_obj.chat_dir,
        settings_obj.prompt_dir,
        settings_obj.export_md_dir,
        execution_dir,
        execution.execution_temp_dir,
    ):
        folder.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        raise FileNotFoundError(f"Par Llama data directory does not exist: {data_dir}")

    settings_obj.settings_file = data_dir / "settings.json"
    if args.restore_defaults:
        settings_obj.settings_file.unlink(missing_ok=True)
        (data_dir / "themes" / "par.json").unlink(missing_ok=True)

    if args.purge_cache:
        purge_folder(cache_dir)

    if args.purge_chats:
        purge_folder(settings_obj.chat_dir)

    if args.purge_prompts:
        purge_folder(settings_obj.prompt_dir)
