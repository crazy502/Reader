"""Reading-theme definitions without filesystem configuration side effects."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_READING_THEME = "classic"


@dataclass(frozen=True)
class ReadingTheme:
    """A fixed pair of colors for the continuous reading surface."""

    background: str
    foreground: str


READING_THEMES: dict[str, ReadingTheme] = {
    "classic": ReadingTheme("#F6F1E7", "#2B2A28"),
    "white": ReadingTheme("#FFFFFF", "#222222"),
    "eye_care": ReadingTheme("#EAF4DF", "#2A2A2A"),
    "parchment": ReadingTheme("#F3E7C9", "#3A3026"),
    "light_gray": ReadingTheme("#F3F3F3", "#222222"),
}


def normalize_reading_theme(value: object) -> str:
    """Return a supported theme name, falling back to the legacy colors."""
    if isinstance(value, str) and value in READING_THEMES:
        return value
    return DEFAULT_READING_THEME


def get_reading_theme(value: object) -> ReadingTheme:
    """Resolve a possibly invalid stored value to its fixed color pair."""
    return READING_THEMES[normalize_reading_theme(value)]
