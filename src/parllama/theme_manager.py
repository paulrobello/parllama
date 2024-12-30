"""Theme manager for Textual"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Literal, TypeAlias

import orjson as json
from textual.app import App
from textual.theme import Theme

from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings

ThemeMode: TypeAlias = Literal["dark", "light"]
ThemeModes: list[ThemeMode] = ["dark", "light"]
Themes: TypeAlias = dict[str, Theme]


class InvalidThemeError(Exception):
    """Raised when an invalid theme is provided."""

    def __init__(self, theme_name: str):
        """Initialize the exception with the invalid theme name."""
        self.theme_name = theme_name
        super().__init__(f"Invalid theme: {theme_name}")


class ThemeModeError(InvalidThemeError):
    """Raised when a theme does not have at least one of 'dark' or 'light' modes."""

    def __init__(self, theme_name: str):
        """Initialize the exception with the invalid theme name."""
        super().__init__(f"Theme '{theme_name}' does not have at least one of 'dark' or 'light' modes.")


class ThemeManager(ParEventSystemBase):
    """Theme manager for Textual"""

    theme_folder: Path

    def __init__(self) -> None:
        """Initialize the theme manager"""
        super().__init__(id="theme_manager")
        self.theme_folder = Path(settings.data_dir) / "themes"

    def set_app(self, app: App[Any] | None) -> None:
        """Set the app and load existing sessions and prompts from storage"""
        super().set_app(app)
        self.load_themes()

    def ensure_default_theme(self) -> None:
        """Ensure that the default theme exists."""
        default_theme_file: Path = Path(os.path.dirname(Path(__file__))) / "themes" / "par.json"

        if not self.theme_folder.exists():
            self.theme_folder.mkdir(parents=True, exist_ok=True)
        theme_file: Path = self.theme_folder / "par.json"

        if not theme_file.exists():
            shutil.copy(default_theme_file, theme_file)

    def load_theme(self, theme_name: str) -> None:
        """Load textual theme from json file"""
        if not self.app:
            raise Exception("App is not initialized")

        theme_name = os.path.basename(theme_name)
        theme_file: Path = Path(self.theme_folder) / (theme_name + ".json")
        theme_def = json.loads(theme_file.read_bytes())
        if "dark" not in theme_def and "light" not in theme_def:
            raise ThemeModeError(theme_name)

        for mode in ThemeModes:
            if mode in theme_def:
                self.app.register_theme(
                    Theme(
                        name=f"{theme_name}_{mode}",
                        **theme_def[mode],
                    )
                )

    def load_themes(self) -> None:
        """Load textual themes from json files"""
        self.ensure_default_theme()

        for file in os.listdir(self.theme_folder):
            if file.lower().endswith(".json"):
                self.load_theme(f"{self.theme_folder}/{os.path.splitext(file)[0]}")

    def get_theme(self, theme_name: str) -> Theme:
        """Get theme by name"""
        if not self.app:
            raise Exception("App is not initialized")
        return self.app.available_themes[theme_name]

    def list_themes(self) -> list[str]:
        """Get list of themes"""
        if not self.app:
            raise Exception("App is not initialized")

        return list(self.app.available_themes.keys())

    def theme_select_options(self) -> list[tuple[str, str]]:
        """Get select options for theme"""
        return [(theme, theme) for theme in self.list_themes()]

    def change_theme(self, theme_name: str) -> None:
        """Change the theme"""
        if not self.app:
            raise Exception("App is not initialized")
        self.app.theme = theme_name


theme_manager = ThemeManager()
