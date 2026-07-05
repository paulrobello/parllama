"""The main entry point for the application."""

from __future__ import annotations

from parllama.settings_manager import initialize_settings
from parllama.utils import get_args

# if os.environ.get("DEBUG"):
#     import pydevd_pycharm  # type: ignore
#
#     pydevd_pycharm.settrace(
#         "localhost", port=12345, suspend=False, patch_multiprocessing=True
#     )


def run() -> None:
    """Run the application."""
    # Parse real CLI args and initialize the Settings singleton BEFORE importing
    # parllama.app: importing the app eagerly triggers the lazy `settings`
    # singleton, so the explicit args must be applied first or CLI flags are lost.
    settings = initialize_settings(get_args())
    print(f"Settings folder {settings.data_dir}")

    from parllama.app import ParLlamaApp

    ParLlamaApp().run()


if __name__ == "__main__":
    run()
