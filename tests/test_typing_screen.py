"""Headless tests for the Textual app, driven through Textual's own pilot.

``asyncio.run`` is used directly so the suite needs no async plugin.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from textual.widgets import Static

from typerush.game.engine import TestMode, TestResult, TypingEngine
from typerush.ui.typing_screen import RESTART, TypingScreen

T = TypeVar("T")


def run(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    return asyncio.run(coro_factory())


def engine_for(target: str = "ab cd") -> TypingEngine:
    return TypingEngine(target, mode=TestMode.WORDS, word_limit=2)


def words_text(app: TypingScreen) -> str:
    """Plain text currently shown in the words pane.

    Reaches into Textual's ``Static.visual``, which is the one Textual-internal
    detail these tests depend on.
    """
    visual = app.query_one("#words", Static).visual
    return str(getattr(visual, "plain", visual))


def test_typing_the_whole_target_finishes_and_returns_a_result():
    async def scenario() -> object:
        app = TypingScreen(engine_for(), show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("a", "b", "space", "c", "d")
            await pilot.pause()
        return app.return_value

    result = run(scenario)
    assert isinstance(result, TestResult)
    assert result.completed
    assert result.typed == "ab cd"
    assert result.stats.errors == 0


def test_mistakes_are_recorded_and_backspace_fixes_them():
    async def scenario() -> object:
        app = TypingScreen(engine_for(), show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("a", "x")  # 'x' is wrong
            await pilot.press("backspace")
            await pilot.press("b", "space", "c", "d")
            await pilot.pause()
        return app.return_value

    result = run(scenario)
    assert isinstance(result, TestResult)
    assert result.typed == "ab cd"
    assert result.stats.errors == 1
    assert result.stats.correct_chars == 5


def test_splash_swallows_the_first_key_then_typing_begins():
    async def scenario() -> tuple[int, str]:
        engine = engine_for()
        app = TypingScreen(engine, show_banner=True)
        async with app.run_test() as pilot:
            await pilot.press("a")  # dismisses the splash only
            assert engine.cursor == 0
            await pilot.press("a", "b")
            cursor, typed = engine.cursor, engine.typed_text
            await pilot.press("escape")
        return cursor, typed

    assert run(scenario) == (2, "ab")


def test_escape_before_typing_returns_nothing():
    async def scenario() -> object:
        app = TypingScreen(engine_for(), show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("escape")
        return app.return_value

    assert run(scenario) is None


def test_escape_mid_test_reports_an_abandoned_result():
    async def scenario() -> object:
        app = TypingScreen(engine_for(), show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("a", "b")
            await pilot.press("escape")
        return app.return_value

    result = run(scenario)
    assert isinstance(result, TestResult)
    assert result.completed is False
    assert result.typed == "ab"


def test_tab_requests_a_restart():
    async def scenario() -> object:
        app = TypingScreen(engine_for(), show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("a")
            await pilot.press("tab")
        return app.return_value

    assert run(scenario) is RESTART


def test_ctrl_r_requests_a_restart():
    async def scenario() -> object:
        app = TypingScreen(engine_for(), show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("ctrl+r")
        return app.return_value

    assert run(scenario) is RESTART


def test_enter_is_not_typed_as_a_character():
    async def scenario() -> str:
        engine = engine_for()
        app = TypingScreen(engine, show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("a", "enter", "b")
            typed = engine.typed_text
            await pilot.press("escape")
        return typed

    assert run(scenario) == "ab"


def test_the_words_pane_shows_the_target_text():
    async def scenario() -> str:
        app = TypingScreen(engine_for("ab cd"), show_banner=False)
        async with app.run_test(size=(40, 24)) as pilot:
            await pilot.press("a")
            await pilot.pause()
            shown = words_text(app)
            await pilot.press("escape")
        return shown

    assert run(scenario).strip() == "ab cd"


def test_visible_window_shows_only_three_lines():
    async def scenario() -> str:
        engine = TypingEngine(" ".join(["word"] * 200), mode=TestMode.WORDS, word_limit=200)
        app = TypingScreen(engine, show_banner=False, visible_lines=3)
        async with app.run_test(size=(40, 24)) as pilot:
            await pilot.press("w")
            await pilot.pause()
            plain = words_text(app)
            await pilot.press("escape")
        return plain

    assert run(scenario).count("\n") == 2  # three lines


def test_the_window_scrolls_to_follow_the_cursor():
    async def scenario() -> tuple[str, str]:
        target = " ".join(f"w{index:02d}" for index in range(60))
        engine = TypingEngine(target, mode=TestMode.WORDS, word_limit=60)
        app = TypingScreen(engine, show_banner=False, visible_lines=3)
        async with app.run_test(size=(30, 24)) as pilot:
            await pilot.press("w")
            await pilot.pause()
            first = words_text(app)
            # Type far enough that the cursor leaves the first three lines.
            for char in target[1:100]:
                await pilot.press("space" if char == " " else char)
            await pilot.pause()
            later = words_text(app)
            await pilot.press("escape")
        return first, later

    first, later = run(scenario)
    assert first.count("\n") == 2 and later.count("\n") == 2  # still three lines
    assert "w00" in first
    assert "w00" not in later  # the window scrolled past the opening words
