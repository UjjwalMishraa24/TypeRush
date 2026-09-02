"""The typing-test state machine.

Comparison model
----------------
Typed characters are compared to the target strictly by index: ``typed[i]`` is
correct only if it equals ``target[i]``. Keystrokes past the end of the target
are ignored rather than appended, which keeps the on-screen line wrapping stable
for the whole run. Backspace removes a character (improving net WPM) but never
erases the fact that a wrong key was pressed (so accuracy still remembers it).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, StrEnum

from .stats import Stats, build_stats


class CharState(Enum):
    """How a single target character should be drawn."""

    PENDING = "pending"
    CORRECT = "correct"
    INCORRECT = "incorrect"


class TestMode(StrEnum):
    """The three ways a test can end."""

    TIME = "time"
    WORDS = "words"
    QUOTE = "quote"


@dataclass(frozen=True, slots=True)
class TestResult:
    """Everything needed to render a results card or write a history entry."""

    mode: TestMode
    target: str
    typed: str
    stats: Stats
    completed: bool
    duration_limit: float | None = None
    word_limit: int | None = None
    source: str | None = None

    @property
    def label(self) -> str:
        """Human-readable mode summary, e.g. ``time 30s`` or ``words 25``."""
        if self.mode is TestMode.TIME and self.duration_limit is not None:
            return f"time {int(self.duration_limit)}s"
        if self.mode is TestMode.WORDS and self.word_limit is not None:
            return f"words {self.word_limit}"
        return self.mode.value


class TypingEngine:
    """Tracks a single typing attempt.

    The engine is driven entirely by the caller: :meth:`type_char`,
    :meth:`backspace` and :meth:`tick`. It never reads from stdin and never
    looks at the wall clock except through ``time_fn``, which tests replace with
    a fake clock.
    """

    def __init__(
        self,
        target: str,
        *,
        mode: TestMode = TestMode.WORDS,
        duration: float | None = None,
        word_limit: int | None = None,
        source: str | None = None,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        if not target:
            raise ValueError("target text must not be empty")
        if mode is TestMode.TIME and (duration is None or duration <= 0):
            raise ValueError("time mode requires a positive duration")

        self.target = target
        self.mode = mode
        self.duration = duration
        self.word_limit = word_limit
        self.source = source

        self._time_fn = time_fn
        self._typed: list[str] = []
        self._correct_chars = 0
        self._incorrect_chars = 0
        self._keystrokes = 0
        self._correct_keystrokes = 0
        self._started_at: float | None = None
        self._ended_at: float | None = None
        self._completed = False

    # ------------------------------------------------------------------ state

    @property
    def started(self) -> bool:
        """True once the first character has been typed (the clock starts then)."""
        return self._started_at is not None

    @property
    def finished(self) -> bool:
        return self._ended_at is not None

    @property
    def completed(self) -> bool:
        """True if the test reached its natural end rather than being abandoned."""
        return self._completed

    @property
    def cursor(self) -> int:
        """Index of the next target character to be typed."""
        return len(self._typed)

    @property
    def typed_text(self) -> str:
        return "".join(self._typed)

    @property
    def elapsed(self) -> float:
        """Seconds spent typing, clamped to the time limit in timed mode."""
        if self._started_at is None:
            return 0.0
        end = self._ended_at if self._ended_at is not None else self._time_fn()
        elapsed = max(end - self._started_at, 0.0)
        if self.mode is TestMode.TIME and self.duration is not None:
            return min(elapsed, self.duration)
        return elapsed

    @property
    def remaining(self) -> float | None:
        """Seconds left in timed mode, or ``None`` in the other modes."""
        if self.mode is not TestMode.TIME or self.duration is None:
            return None
        return max(self.duration - self.elapsed, 0.0)

    @property
    def word_total(self) -> int:
        """Number of whitespace-separated words in the target."""
        return len(self.target.split())

    @property
    def words_completed(self) -> int:
        """Words fully passed by the cursor (a crossed space completes a word)."""
        return self.target[: self.cursor].count(" ")

    @property
    def progress(self) -> float:
        """Completion ratio in ``0.0..1.0`` for whichever limit ends this test."""
        if self.mode is TestMode.TIME and self.duration:
            return min(self.elapsed / self.duration, 1.0)
        return min(self.cursor / len(self.target), 1.0)

    # ------------------------------------------------------------------ input

    def type_char(self, char: str) -> bool:
        """Register one printable keystroke. Returns True if it was accepted."""
        if self.finished or len(char) != 1:
            return False
        if char != " " and not char.isprintable():
            return False
        if self._started_at is None:
            self._started_at = self._time_fn()
        if self._expired():
            self._finish(completed=True)
            return False
        index = len(self._typed)
        if index >= len(self.target):
            return False

        self._typed.append(char)
        self._keystrokes += 1
        if char == self.target[index]:
            self._correct_chars += 1
            self._correct_keystrokes += 1
        else:
            self._incorrect_chars += 1

        if len(self._typed) >= len(self.target) and self.mode is not TestMode.TIME:
            self._finish(completed=True)
        else:
            self.tick()
        return True

    def backspace(self) -> bool:
        """Delete the last typed character. Returns True if anything was removed."""
        if self.finished or not self._typed:
            return False
        index = len(self._typed) - 1
        char = self._typed.pop()
        if char == self.target[index]:
            self._correct_chars -= 1
        else:
            self._incorrect_chars -= 1
        return True

    def tick(self) -> bool:
        """Let the clock end a timed test. Returns :attr:`finished`."""
        if not self.finished and self._expired():
            self._finish(completed=True)
        return self.finished

    def abandon(self) -> None:
        """End the test early (the user pressed escape); marks it incomplete."""
        if not self.finished:
            self._finish(completed=False)

    # ----------------------------------------------------------------- output

    def char_states(self) -> list[CharState]:
        """Per-target-character draw state, aligned with :attr:`target`."""
        states = [CharState.PENDING] * len(self.target)
        for index, char in enumerate(self._typed):
            states[index] = CharState.CORRECT if char == self.target[index] else CharState.INCORRECT
        return states

    def stats(self) -> Stats:
        """Current score; safe to call on every UI frame."""
        return build_stats(
            correct_chars=self._correct_chars,
            incorrect_chars=self._incorrect_chars,
            keystrokes=self._keystrokes,
            correct_keystrokes=self._correct_keystrokes,
            elapsed=self.elapsed,
        )

    def result(self) -> TestResult:
        """Freeze the attempt into a :class:`TestResult`."""
        return TestResult(
            mode=self.mode,
            target=self.target,
            typed=self.typed_text,
            stats=self.stats(),
            completed=self._completed,
            duration_limit=self.duration,
            word_limit=self.word_limit,
            source=self.source,
        )

    # --------------------------------------------------------------- internal

    def _expired(self) -> bool:
        if self.mode is not TestMode.TIME or self.duration is None:
            return False
        if self._started_at is None:
            return False
        return (self._time_fn() - self._started_at) >= self.duration

    def _finish(self, *, completed: bool) -> None:
        if self._started_at is None:
            self._started_at = self._time_fn()
        if self.mode is TestMode.TIME and self.duration is not None and completed:
            # Pin the end exactly to the limit so 30s tests report 30.0s.
            self._ended_at = self._started_at + self.duration
        else:
            self._ended_at = self._time_fn()
        self._completed = completed
