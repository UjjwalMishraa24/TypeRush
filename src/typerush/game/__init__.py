"""Core typing-test logic: state machine, text sources, and score math.

Nothing in this package imports ``rich``, ``textual`` or touches a terminal, so
every rule here can be exercised from a plain unit test.
"""

from __future__ import annotations

from .engine import CharState, TestMode, TestResult, TypingEngine
from .stats import Stats, calculate_accuracy, calculate_raw_wpm, calculate_wpm
from .wordlist import Quote, WordSourceError, build_target

__all__ = [
    "CharState",
    "Quote",
    "Stats",
    "TestMode",
    "TestResult",
    "TypingEngine",
    "WordSourceError",
    "build_target",
    "calculate_accuracy",
    "calculate_raw_wpm",
    "calculate_wpm",
]
