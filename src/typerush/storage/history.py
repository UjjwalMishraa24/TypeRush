"""Run history stored at ``~/.typerush/history.json``.

The file is a small JSON document::

    {"version": 1, "entries": [{...}, {...}]}

Entries are append-only and written atomically. Anything unparseable is skipped
rather than fatal — a corrupted history should never stop you from typing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..game.engine import TestResult
from .config import typerush_home

HISTORY_FILENAME = "history.json"
HISTORY_VERSION = 1
#: Keep the file small; oldest entries are dropped past this many runs.
MAX_ENTRIES = 5000


class HistoryError(RuntimeError):
    """Raised when history cannot be written."""


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One completed (or abandoned) run, flattened for JSON."""

    timestamp: str
    mode: str
    label: str
    wpm: float
    raw_wpm: float
    accuracy: float
    errors: int
    elapsed: float
    correct_chars: int
    incorrect_chars: int
    completed: bool
    duration_limit: float | None = None
    word_limit: int | None = None
    source: str | None = None

    @property
    def when(self) -> datetime | None:
        """Parsed :attr:`timestamp`, or ``None`` if it was not valid ISO-8601."""
        try:
            return datetime.fromisoformat(self.timestamp)
        except ValueError:
            return None


def history_path() -> Path:
    return typerush_home() / HISTORY_FILENAME


def entry_from_result(result: TestResult, when: datetime | None = None) -> HistoryEntry:
    """Flatten a :class:`~typerush.game.engine.TestResult` into a history entry."""
    stamp = when or datetime.now().astimezone()
    stats = result.stats
    return HistoryEntry(
        timestamp=stamp.isoformat(timespec="seconds"),
        mode=result.mode.value,
        label=result.label,
        wpm=round(stats.wpm, 2),
        raw_wpm=round(stats.raw_wpm, 2),
        accuracy=round(stats.accuracy, 2),
        errors=stats.errors,
        elapsed=round(stats.elapsed, 2),
        correct_chars=stats.correct_chars,
        incorrect_chars=stats.incorrect_chars,
        completed=result.completed,
        duration_limit=result.duration_limit,
        word_limit=result.word_limit,
        source=result.source,
    )


def _entry_from_mapping(data: Any) -> HistoryEntry | None:
    if not isinstance(data, dict):
        return None
    fields = HistoryEntry.__dataclass_fields__
    known = {key: value for key, value in data.items() if key in fields}
    try:
        return HistoryEntry(**known)
    except TypeError:
        # Missing a required key — treat the row as unusable.
        return None


def load_history(path: Path | None = None) -> list[HistoryEntry]:
    """Read all entries, oldest first. Missing or corrupt files yield ``[]``."""
    target = path or history_path()
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    items: Any = payload.get("entries", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    return [entry for entry in (_entry_from_mapping(item) for item in items) if entry is not None]


def save_history(entries: list[HistoryEntry], path: Path | None = None) -> Path:
    """Write the whole history atomically, trimmed to :data:`MAX_ENTRIES`."""
    target = path or history_path()
    trimmed = entries[-MAX_ENTRIES:]
    payload = {"version": HISTORY_VERSION, "entries": [asdict(entry) for entry in trimmed]}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(target)
    except OSError as exc:
        raise HistoryError(f"could not write {target}: {exc.strerror or exc}") from exc
    return target


def append_result(
    result: TestResult,
    path: Path | None = None,
    when: datetime | None = None,
) -> HistoryEntry:
    """Append one run to the history file and return the stored entry."""
    entry = entry_from_result(result, when)
    target = path or history_path()
    entries = load_history(target)
    entries.append(entry)
    save_history(entries, target)
    return entry


def recent_entries(entries: list[HistoryEntry], limit: int) -> list[HistoryEntry]:
    """The last ``limit`` entries, newest first."""
    if limit <= 0:
        return []
    return list(reversed(entries[-limit:]))


def best_entry(entries: list[HistoryEntry], mode: str | None = None) -> HistoryEntry | None:
    """Highest-WPM completed run, optionally restricted to one mode."""
    candidates = [entry for entry in entries if entry.completed]
    if mode is not None:
        candidates = [entry for entry in candidates if entry.mode == mode]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: entry.wpm)


def average_wpm(entries: list[HistoryEntry]) -> float:
    """Mean WPM across completed runs (0.0 when there are none)."""
    completed = [entry.wpm for entry in entries if entry.completed]
    if not completed:
        return 0.0
    return sum(completed) / len(completed)
