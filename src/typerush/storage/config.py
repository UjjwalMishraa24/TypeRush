"""User configuration stored at ``~/.typerush/config.json``.

Set ``TYPERUSH_HOME`` to relocate the whole directory (tests rely on this).
Unknown keys in the file are ignored, so a config written by a newer typerush
never breaks an older one.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

DEFAULT_HOME = "~/.typerush"
HOME_ENV_VAR = "TYPERUSH_HOME"
CONFIG_FILENAME = "config.json"


class ConfigError(RuntimeError):
    """Raised when the config file exists but cannot be understood."""


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


@dataclass(frozen=True, slots=True)
class Config:
    """Everything the user can pre-set so the bare ``typerush`` command fits them."""

    default_mode: str = "time"
    default_time: int = 30
    default_words: int = 25
    show_banner: bool = True
    save_history: bool = True
    wordlist_path: str | None = None
    quotes_path: str | None = None
    theme: Theme = field(default_factory=Theme)

    @property
    def wordlist(self) -> Path | None:
        return Path(self.wordlist_path).expanduser() if self.wordlist_path else None

    @property
    def quotes(self) -> Path | None:
        return Path(self.quotes_path).expanduser() if self.quotes_path else None


def typerush_home() -> Path:
    """Directory holding config and history."""
    return Path(os.environ.get(HOME_ENV_VAR, DEFAULT_HOME)).expanduser()


def config_path() -> Path:
    return typerush_home() / CONFIG_FILENAME


def _theme_from_mapping(data: Any, base: Theme) -> Theme:
    if not isinstance(data, dict):
        return base
    known = {f: v for f, v in data.items() if f in Theme.__dataclass_fields__}
    colours = {name: str(value) for name, value in known.items() if isinstance(value, str)}
    return replace(base, **colours)


def config_from_mapping(data: Any, base: Config | None = None) -> Config:
    """Overlay a raw mapping onto defaults, ignoring unknown or ill-typed keys."""
    current = base or Config()
    if not isinstance(data, dict):
        return current

    updates: dict[str, Any] = {}
    for name in ("default_mode", "wordlist_path", "quotes_path"):
        value = data.get(name)
        if isinstance(value, str) and value.strip():
            updates[name] = value.strip()
    for name in ("default_time", "default_words"):
        value = data.get(name)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            updates[name] = value
    for name in ("show_banner", "save_history"):
        value = data.get(name)
        if isinstance(value, bool):
            updates[name] = value
    if "theme" in data:
        updates["theme"] = _theme_from_mapping(data["theme"], current.theme)
    return replace(current, **updates)


def load_config(path: Path | None = None) -> Config:
    """Read the config file, or return defaults when it does not exist.

    Raises :class:`ConfigError` if the file is present but malformed, so the CLI
    can warn instead of silently ignoring the user's settings.
    """
    target = path or config_path()
    if not target.exists():
        return Config()
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"could not read {target}: {exc.strerror or exc}") from exc
    if not raw.strip():
        return Config()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{target} is not valid JSON: {exc.msg} (line {exc.lineno})") from exc
    return config_from_mapping(payload)


def save_config(config: Config, path: Path | None = None) -> Path:
    """Write ``config`` as pretty JSON, creating ``~/.typerush`` if needed."""
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target
