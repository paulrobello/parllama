"""The main entry point for the application."""

from __future__ import annotations

import os

from parllama.app import ParLlamaApp
from parllama.models.settings_data import settings

if os.environ.get("DEBUG"):
    import pydevd_pycharm  # type: ignore

    pydevd_pycharm.settrace(
        "localhost", port=12345, suspend=False, patch_multiprocessing=True
    )


def run() -> None:
    """Run the application."""
    print(f"Settings folder {settings.data_dir}")
    ParLlamaApp().run()


if __name__ == "__main__":
    run()
