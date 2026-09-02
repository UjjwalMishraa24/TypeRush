"""Shared fixtures.

``isolated_home`` is autouse so no test can ever read or write the developer's
real ``~/.typerush``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


class FakeClock:
    """A monotonic clock the tests advance by hand instead of sleeping."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    home = tmp_path / "typerush-home"
    monkeypatch.setenv("TYPERUSH_HOME", str(home))
    yield home


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
