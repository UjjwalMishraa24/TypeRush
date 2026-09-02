"""Where the text to type comes from.

A common-English word list and a quote collection ship inside the package, so
typerush works offline on a fresh install. Either can be replaced at runtime by
pointing ``--wordlist`` / ``--quotes`` at your own file.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from .engine import TestMode

DATA_PACKAGE = "typerush.data"
WORDS_RESOURCE = "words_common.txt"
QUOTES_RESOURCE = "quotes.json"

#: Words generated per minute for timed tests. Far above any human ceiling, so
#: nobody ever reaches the end of the text before the clock runs out.
WORDS_PER_MINUTE_HEADROOM = 240
#: Extra words appended on top of the headroom estimate.
WORDS_TAIL_PADDING = 40


class WordSourceError(RuntimeError):
    """Raised when a word list or quote file is missing, unreadable or empty."""


@dataclass(frozen=True, slots=True)
class Quote:
    """A single quote plus optional attribution."""

    text: str
    author: str | None = None
    source: str | None = None

    @property
    def attribution(self) -> str | None:
        """``"Author, Source"`` — or whichever half is present."""
        parts = [part for part in (self.author, self.source) if part]
        return ", ".join(parts) if parts else None


@dataclass(frozen=True, slots=True)
class TargetText:
    """The text for one attempt, with the attribution to show afterwards."""

    text: str
    source: str | None = None


def _read_resource(name: str) -> str:
    try:
        return resources.files(DATA_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:  # pragma: no cover - packaging bug
        raise WordSourceError(f"bundled data file {name!r} is missing from the install") from exc


def _read_path(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WordSourceError(f"could not read {path}: {exc.strerror or exc}") from exc


def load_words(path: Path | None = None) -> list[str]:
    """Load a word list: one word per line, ``#`` comments and blanks ignored.

    Duplicates are dropped while preserving order so a hand-written list cannot
    accidentally weight one word more heavily than the rest.
    """
    raw = _read_path(path) if path is not None else _read_resource(WORDS_RESOURCE)
    words: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        word = line.strip()
        if not word or word.startswith("#"):
            continue
        # A "word" with spaces would break word counting, so take the first token.
        word = word.split()[0]
        if word not in seen:
            seen.add(word)
            words.append(word)
    if not words:
        origin = str(path) if path is not None else f"bundled {WORDS_RESOURCE}"
        raise WordSourceError(f"no usable words found in {origin}")
    return words


def _coerce_quote(item: Any) -> Quote | None:
    if isinstance(item, str):
        text = item.strip()
        return Quote(text=text) if text else None
    if isinstance(item, dict):
        text = str(item.get("text", "")).strip()
        if not text:
            return None
        author = item.get("author")
        source = item.get("source")
        return Quote(
            text=text,
            author=str(author).strip() if author else None,
            source=str(source).strip() if source else None,
        )
    return None


def load_quotes(path: Path | None = None) -> list[Quote]:
    """Load quotes from JSON.

    Accepts ``{"quotes": [...]}`` or a bare ``[...]`` list; each item may be a
    string or an object with ``text`` / ``author`` / ``source`` keys.
    """
    raw = _read_path(path) if path is not None else _read_resource(QUOTES_RESOURCE)
    origin = str(path) if path is not None else f"bundled {QUOTES_RESOURCE}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WordSourceError(f"{origin} is not valid JSON: {exc.msg} (line {exc.lineno})") from exc

    items: Any = payload.get("quotes", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise WordSourceError(f"{origin} must contain a list of quotes")

    quotes = [quote for quote in (_coerce_quote(item) for item in items) if quote is not None]
    if not quotes:
        raise WordSourceError(f"no usable quotes found in {origin}")
    return quotes


def pick_words(words: list[str], count: int, rng: random.Random) -> list[str]:
    """Sample ``count`` words with replacement (short lists still work)."""
    if count <= 0:
        raise ValueError("count must be positive")
    if not words:
        raise WordSourceError("word list is empty")
    return rng.choices(words, k=count)


def pick_quote(quotes: list[Quote], rng: random.Random) -> Quote:
    if not quotes:
        raise WordSourceError("quote list is empty")
    return rng.choice(quotes)


def words_for_duration(duration: float) -> int:
    """How many words to generate so a timed test never runs out of text."""
    minutes = max(duration, 0.0) / 60.0
    return int(minutes * WORDS_PER_MINUTE_HEADROOM) + WORDS_TAIL_PADDING


def build_target(
    mode: TestMode,
    *,
    rng: random.Random,
    duration: float | None = None,
    word_count: int | None = None,
    wordlist_path: Path | None = None,
    quotes_path: Path | None = None,
) -> TargetText:
    """Build the text for one attempt in the requested mode."""
    if mode is TestMode.QUOTE:
        quote = pick_quote(load_quotes(quotes_path), rng)
        return TargetText(text=quote.text, source=quote.attribution)

    if mode is TestMode.TIME:
        if duration is None or duration <= 0:
            raise ValueError("time mode requires a positive duration")
        count = words_for_duration(duration)
    else:
        if word_count is None or word_count <= 0:
            raise ValueError("words mode requires a positive word count")
        count = word_count

    words = pick_words(load_words(wordlist_path), count, rng)
    return TargetText(text=" ".join(words))
