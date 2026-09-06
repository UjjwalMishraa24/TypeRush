"""Local state under ``~/.typerush``: user config and run history."""

from __future__ import annotations

from ..theme import Theme
from .config import Config, ConfigError, config_path, load_config, save_config, typerush_home
from .history import (
    HistoryEntry,
    HistoryError,
    append_result,
    best_entry,
    history_path,
    load_history,
    recent_entries,
)

__all__ = [
    "Config",
    "ConfigError",
    "HistoryEntry",
    "HistoryError",
    "Theme",
    "append_result",
    "best_entry",
    "config_path",
    "history_path",
    "load_config",
    "load_history",
    "recent_entries",
    "save_config",
    "typerush_home",
]
