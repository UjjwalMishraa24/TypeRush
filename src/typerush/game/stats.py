"""WPM / accuracy math.

Two different notions of "how much did you type" are tracked deliberately:

* **characters currently on screen** — used for net WPM, so fixing a typo with
  backspace really does improve your score.
* **keystrokes ever pressed** — used for accuracy and the error count, so a typo
  still costs you accuracy even after you correct it (this is what monkeytype
  reports, and it is the number that reflects actual finger precision).
"""

from __future__ import annotations

from dataclasses import dataclass

#: The conventional "word" length used by every typing test.
CHARS_PER_WORD = 5
SECONDS_PER_MINUTE = 60.0


def _minutes(elapsed_seconds: float) -> float:
    return max(elapsed_seconds, 0.0) / SECONDS_PER_MINUTE


def calculate_wpm(correct_chars: int, elapsed_seconds: float) -> float:
    """Net WPM: ``(correct characters / 5) / minutes``."""
    minutes = _minutes(elapsed_seconds)
    if minutes <= 0.0:
        return 0.0
    return (max(correct_chars, 0) / CHARS_PER_WORD) / minutes


def calculate_raw_wpm(typed_chars: int, elapsed_seconds: float) -> float:
    """Raw WPM: same formula as :func:`calculate_wpm` but errors still count."""
    minutes = _minutes(elapsed_seconds)
    if minutes <= 0.0:
        return 0.0
    return (max(typed_chars, 0) / CHARS_PER_WORD) / minutes


def calculate_accuracy(correct_keystrokes: int, total_keystrokes: int) -> float:
    """Percentage of keystrokes that were correct when pressed (0-100)."""
    if total_keystrokes <= 0:
        return 100.0
    ratio = max(correct_keystrokes, 0) / total_keystrokes
    return min(max(ratio, 0.0), 1.0) * 100.0


@dataclass(frozen=True, slots=True)
class Stats:
    """An immutable score snapshot; cheap enough to rebuild on every UI tick."""

    wpm: float
    raw_wpm: float
    accuracy: float
    errors: int
    correct_chars: int
    incorrect_chars: int
    typed_chars: int
    keystrokes: int
    elapsed: float

    @property
    def wpm_display(self) -> int:
        return round(self.wpm)

    @property
    def raw_wpm_display(self) -> int:
        return round(self.raw_wpm)

    @property
    def accuracy_display(self) -> float:
        return round(self.accuracy, 1)


def build_stats(
    *,
    correct_chars: int,
    incorrect_chars: int,
    keystrokes: int,
    correct_keystrokes: int,
    elapsed: float,
) -> Stats:
    """Assemble a :class:`Stats` from the engine's raw counters."""
    typed_chars = correct_chars + incorrect_chars
    return Stats(
        wpm=calculate_wpm(correct_chars, elapsed),
        raw_wpm=calculate_raw_wpm(typed_chars, elapsed),
        accuracy=calculate_accuracy(correct_keystrokes, keystrokes),
        errors=max(keystrokes - correct_keystrokes, 0),
        correct_chars=correct_chars,
        incorrect_chars=incorrect_chars,
        typed_chars=typed_chars,
        keystrokes=keystrokes,
        elapsed=elapsed,
    )


def empty_stats() -> Stats:
    """Score for a test that has not been started yet."""
    return build_stats(
        correct_chars=0,
        incorrect_chars=0,
        keystrokes=0,
        correct_keystrokes=0,
        elapsed=0.0,
    )
