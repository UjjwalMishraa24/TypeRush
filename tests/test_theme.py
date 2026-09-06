from __future__ import annotations

from typing import Any

from typerush.theme import (
    DEFAULT_THEME_NAME,
    THEMES,
    Theme,
    resolve_theme,
    theme_names,
)


def test_the_default_theme_is_registered():
    assert THEMES[DEFAULT_THEME_NAME] == Theme()


def test_every_preset_defines_all_fields():
    for name, theme in THEMES.items():
        assert theme.gradient == (theme.accent, theme.mid, theme.secondary), name


def test_picker_order_leads_with_default():
    assert theme_names()[0] == DEFAULT_THEME_NAME
    assert set(theme_names()) == {"default", "catppuccin", "tokyo-night", "gruvbox"}


def test_resolve_returns_the_named_preset():
    assert resolve_theme("gruvbox") == THEMES["gruvbox"]


def test_resolve_unknown_name_falls_back_to_default():
    assert resolve_theme("nonsense") == Theme()


def test_resolve_applies_overrides_on_top():
    theme = resolve_theme("catppuccin", {"accent": "#ff0000"})
    assert theme.accent == "#ff0000"
    assert theme.correct == THEMES["catppuccin"].correct


def test_resolve_ignores_unknown_or_non_string_overrides():
    # Deliberately ill-typed: the loader must cope with junk from a config file.
    overrides: dict[str, Any] = {"bogus": 1, "accent": None, "muted": "#111111"}
    theme = resolve_theme("tokyo-night", overrides)
    assert theme.muted == "#111111"
    assert theme.accent == THEMES["tokyo-night"].accent
