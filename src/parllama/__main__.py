"""The main entry point for the application."""

from __future__ import annotations

from parllama.app import ParLlamaApp
from parllama.settings_manager import initialize_settings

# if os.environ.get("DEBUG"):
#     import pydevd_pycharm  # type: ignore
#
#     pydevd_pycharm.settrace(
#         "localhost", port=12345, suspend=False, patch_multiprocessing=True
#     )


def run() -> None:
    """Run the application."""
    settings = initialize_settings()
    print(f"Settings folder {settings.data_dir}")
    ParLlamaApp().run()


if __name__ == "__main__":
    run()
