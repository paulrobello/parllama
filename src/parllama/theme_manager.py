"""Theme manager for Textual"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict
from typing import Literal
from typing import Tuple
from typing import TypeAlias

import orjson as json
from textual.design import ColorSystem

from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings

ThemeMode: TypeAlias = Literal["dark", "light"]
ThemeModes: list[ThemeMode] = ["dark", "light"]
Theme: TypeAlias = Dict[ThemeMode, ColorSystem]
Themes: TypeAlias = Dict[str, Theme]


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
        super().__init__(
            f"Theme '{theme_name}' does not have at least one of 'dark' or 'light' modes."
        )


class ThemeManager(ParEventSystemBase):
    """Theme manager for Textual"""

    themes: Themes
    theme_folder: Path

    def __init__(self) -> None:
        """Initialize the theme manager"""
        super().__init__(id="theme_manager")
        self.theme_folder = Path(settings.data_dir) / "themes"
        self.themes = self.load_themes()

    def ensure_default_theme(self) -> None:
        """Ensure that the default theme exists."""
        default_theme_file: Path = (
            Path(os.path.dirname(Path(__file__))) / "themes" / "par.json"
        )

        if not self.theme_folder.exists():
            self.theme_folder.mkdir(parents=True, exist_ok=True)
        theme_file: Path = self.theme_folder / "par.json"

        if not theme_file.exists():
            shutil.copy(default_theme_file, theme_file)

    def load_theme(self, theme_name: str) -> Theme:
        """Load textual theme from json file"""

        theme: Theme = {}
        theme_name = os.path.basename(theme_name)
        theme_file: Path = Path(self.theme_folder) / theme_name
        theme_def = json.loads(theme_file.read_bytes())
        if "dark" not in theme_def and "light" not in theme_def:
            raise ThemeModeError(theme_name)

        for mode in ThemeModes:
            if mode in theme_def:
                theme[mode] = ColorSystem(**theme_def[mode])
        return theme

    def load_themes(self) -> Themes:
        """Load textual themes from json files"""
        self.ensure_default_theme()

        themes: Themes = {}
        for file in os.listdir(self.theme_folder):
            if file.lower().endswith(".json"):
                theme_name = os.path.splitext(file)[0]
                themes[theme_name] = self.load_theme(f"{self.theme_folder}/{file}")
        return themes

    def get_theme(self, theme_name: str) -> Theme:
        """Get theme by name"""
        return self.themes[theme_name]

    def list_themes(self) -> list[str]:
        """Get list of themes"""
        return list(self.themes.keys())

    def theme_select_options(self) -> list[Tuple[str, str]]:
        """Get select options for theme"""
        return [(theme, theme) for theme in self.list_themes()]

    def theme_has_dark(self, theme_name: str) -> bool:
        """Check if theme has dark mode"""
        return "dark" in self.themes[theme_name]

    def theme_has_light(self, theme_name: str) -> bool:
        """Check if theme has light mode"""
        return "light" in self.themes[theme_name]

    def get_color_system_for_theme_mode(
        self, theme_name: str, dark: bool
    ) -> ColorSystem:
        """Get color system for theme mode"""
        theme = self.themes[theme_name]

        if dark:
            if "dark" in theme:
                return theme["dark"]
            return theme["light"]

        if "light" in theme:
            return theme["light"]
        return theme["dark"]

    def change_theme(self, theme_name: str, dark: bool) -> None:
        """Change the theme"""
        if not self.app:
            return
        self.app.design = self.get_theme(theme_name)  # type: ignore
        self.app.dark = dark


theme_manager = ThemeManager()
