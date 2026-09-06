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

from ..theme import DEFAULT_THEME_NAME, Theme, resolve_theme

DEFAULT_HOME = "~/.typerush"
HOME_ENV_VAR = "TYPERUSH_HOME"
CONFIG_FILENAME = "config.json"


class ConfigError(RuntimeError):
    """Raised when the config file exists but cannot be understood."""


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
    #: Name of the bundled palette to use (see :mod:`typerush.theme`).
    theme_name: str = DEFAULT_THEME_NAME
    #: Per-field colours applied on top of the named preset.
    theme_overrides: dict[str, str] = field(default_factory=dict)

    @property
    def wordlist(self) -> Path | None:
        return Path(self.wordlist_path).expanduser() if self.wordlist_path else None

    @property
    def quotes(self) -> Path | None:
        return Path(self.quotes_path).expanduser() if self.quotes_path else None

    @property
    def theme(self) -> Theme:
        """The resolved palette: the named preset plus any overrides."""
        return resolve_theme(self.theme_name, self.theme_overrides)


def typerush_home() -> Path:
    """Directory holding config and history."""
    return Path(os.environ.get(HOME_ENV_VAR, DEFAULT_HOME)).expanduser()


def config_path() -> Path:
    return typerush_home() / CONFIG_FILENAME


def _theme_overrides_from_mapping(data: Any, base: dict[str, str]) -> dict[str, str]:
    if not isinstance(data, dict):
        return base
    overrides = dict(base)
    for colour, value in data.items():
        if colour in Theme.__dataclass_fields__ and isinstance(value, str) and value.strip():
            overrides[colour] = value.strip()
    return overrides


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
    theme_name = data.get("theme_name")
    if isinstance(theme_name, str) and theme_name.strip():
        updates["theme_name"] = theme_name.strip()
    for name in ("default_time", "default_words"):
        value = data.get(name)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            updates[name] = value
    for name in ("show_banner", "save_history"):
        value = data.get(name)
        if isinstance(value, bool):
            updates[name] = value
    if "theme" in data:
        updates["theme_overrides"] = _theme_overrides_from_mapping(
            data["theme"], current.theme_overrides
        )
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
    """Write ``config`` as pretty JSON, creating ``~/.typerush`` if needed.

    Overrides are written under the legacy ``"theme"`` key so files stay
    readable by (and interchangeable with) older typerush versions.
    """
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    payload["theme"] = payload.pop("theme_overrides")
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target
