"""Colour themes.

``Theme`` is the palette dataclass every renderer consumes (banner, typing
screen, results card, history table). It lives here, next to the named
presets, so ``storage`` can resolve a saved theme name without importing
anything from ``ui`` — and so ``ui`` code can grab a palette without going
through the config machinery.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

#: The key ``config.json`` and ``--theme`` fall back to when a name is unknown.
DEFAULT_THEME_NAME = "default"


@dataclass(frozen=True, slots=True)
class Theme:
    """Colours used by the typing screen and results card."""

    #: Characters typed correctly.
    correct: str = "#e5e7eb"
    #: Characters typed incorrectly.
    incorrect: str = "#f87171"
    #: Text not reached yet.
    pending: str = "#4b5563"
    #: The caret.
    cursor: str = "#22d3ee"
    #: Primary accent (banner start, live WPM, highlights).
    accent: str = "#22d3ee"
    #: Banner mid-stop.
    mid: str = "#3b82f6"
    #: Secondary accent (banner end, attributions).
    secondary: str = "#a855f7"
    #: Positive numbers, e.g. accuracy.
    good: str = "#4ade80"
    #: Low-emphasis chrome and hints.
    muted: str = "#6b7280"

    @property
    def gradient(self) -> tuple[str, str, str]:
        """Colour stops for the ASCII banner sweep."""
        return (self.accent, self.mid, self.secondary)


#: Bundled palettes, in the order the ``--ui`` picker shows them.
THEMES: dict[str, Theme] = {
    "default": Theme(),
    # Catppuccin Mocha
    "catppuccin": Theme(
        correct="#cdd6f4",
        incorrect="#f38ba8",
        pending="#6c7086",
        cursor="#94e2d5",
        accent="#94e2d5",
        mid="#89b4fa",
        secondary="#cba6f7",
        good="#a6e3a1",
        muted="#a6adc8",
    ),
    # Tokyo Night
    "tokyo-night": Theme(
        correct="#c0caf5",
        incorrect="#f7768e",
        pending="#565f89",
        cursor="#7dcfff",
        accent="#7dcfff",
        mid="#7aa2f7",
        secondary="#bb9af7",
        good="#9ece6a",
        muted="#a9b1d6",
    ),
    # Gruvbox Dark
    "gruvbox": Theme(
        correct="#ebdbb2",
        incorrect="#fb4934",
        pending="#928374",
        cursor="#fabd2f",
        accent="#fabd2f",
        mid="#fe8019",
        secondary="#d3869b",
        good="#b8bb26",
        muted="#bdae93",
    ),
}


def theme_names() -> tuple[str, ...]:
    """Available theme names, picker order."""
    return tuple(THEMES)


def resolve_theme(name: str, overrides: Mapping[str, str] | None = None) -> Theme:
    """The named preset with any per-field overrides applied on top.

    Unknown names fall back to the default theme; unknown override fields
    are ignored, so a config written by a newer typerush never breaks.
    """
    base = THEMES.get(name) or THEMES[DEFAULT_THEME_NAME]
    if not overrides:
        return base
    known = {
        field: str(value)
        for field, value in overrides.items()
        if field in Theme.__dataclass_fields__ and isinstance(value, str)
    }
    return replace(base, **known)
