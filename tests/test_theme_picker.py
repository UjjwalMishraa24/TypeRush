"""Headless tests for the ``--ui`` theme picker, driven through Textual's pilot."""

from __future__ import annotations

import asyncio
import io
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from rich.console import Console

from typerush.ui.theme_picker import ThemePicker

T = TypeVar("T")


def run(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    return asyncio.run(coro_factory())


def picker_text(app: ThemePicker) -> str:
    """The picker's current render as plain, unstyled text.

    The picker shows a rich render group (banner + panel), so unlike the typing
    screen's ``Text`` panes there is no ``.plain`` to read; render it instead.
    """
    buffer = io.StringIO()
    console = Console(file=buffer, width=100, no_color=True, legacy_windows=False)
    console.print(app._render())
    return buffer.getvalue()


def test_enter_returns_the_highlighted_theme():
    async def scenario() -> object:
        app = ThemePicker("default", show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
        return app.return_value

    assert run(scenario) == "catppuccin"


def test_escape_returns_none_without_saving():
    async def scenario() -> object:
        app = ThemePicker("default", show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("down")
            await pilot.press("escape")
            await pilot.pause()
        return app.return_value

    assert run(scenario) is None


def test_navigation_wraps_around_both_ends():
    async def scenario() -> object:
        app = ThemePicker("default", show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("up")  # wraps from the first row to the last
            await pilot.press("enter")
            await pilot.pause()
        return app.return_value

    assert run(scenario) == "gruvbox"


def test_j_and_k_move_the_selection():
    async def scenario() -> str:
        app = ThemePicker("default", show_banner=False)
        async with app.run_test() as pilot:
            await pilot.press("j")  # down
            await pilot.press("k")  # back up
            await pilot.press("j", "j")  # down twice
            await pilot.pause()
            return picker_text(app)

    # The highlight bullet now sits in front of the third theme.
    assert "●  tokyo-night" in run(scenario)


def test_current_theme_starts_highlighted():
    async def scenario() -> str:
        app = ThemePicker("tokyo-night", show_banner=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            return picker_text(app)

    assert "●  tokyo-night" in run(scenario)


def test_unknown_current_theme_falls_back_to_the_first_row():
    async def scenario() -> str:
        app = ThemePicker("nonsense", show_banner=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            return picker_text(app)

    assert "●  default" in run(scenario)


def test_the_banner_previews_the_highlighted_palette():
    async def scenario() -> str:
        app = ThemePicker("default", show_banner=True)
        async with app.run_test() as pilot:
            await pilot.press("down")  # catppuccin
            await pilot.pause()
            return picker_text(app)

    # The banner block and its hint render above the list, which now
    # highlights the second theme.
    text = run(scenario)
    assert "press enter to save this theme" in text
    assert "terminal typing speed test" in text
    assert "●  catppuccin" in text
