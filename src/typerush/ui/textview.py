"""Turning engine state into styled Rich renderables.

Kept free of Textual imports so the wrapping maths and the status bars can be
unit-tested without a terminal. Wrapping is computed from the *target* text alone
— it never depends on what has been typed — so the words never reflow mid-test.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.style import Style
from rich.table import Table
from rich.text import Text

from ..game.engine import CharState, TestMode, TypingEngine
from ..storage.config import Theme

TYPING_HINT = "esc quit  ·  tab restart"


def wrap_indices(target: str, width: int) -> list[list[int]]:
    """Word-wrap ``target`` into lines of global character indices.

    Every index of ``target`` appears exactly once, in order, so the caller can
    render each line without losing the spaces between words. A word longer than
    ``width`` is hard-split rather than allowed to overflow.
    """
    if width < 1:
        width = 1
    if not target:
        return [[]]

    spans: list[tuple[int, int]] = []
    index = 0
    length = len(target)
    while index < length:
        if target[index] == " ":
            index += 1
            continue
        start = index
        while index < length and target[index] != " ":
            index += 1
        spans.append((start, index))

    lines: list[list[int]] = []
    current: list[int] = []
    previous_end = 0

    for start, end in spans:
        gap = list(range(previous_end, start))
        word = list(range(start, end))
        previous_end = end

        # Hard-split words that cannot fit on a line by themselves.
        if len(word) > width:
            current.extend(gap)
            if current:
                lines.append(current)
                current = []
            for offset in range(0, len(word), width):
                chunk = word[offset : offset + width]
                if len(chunk) == width:
                    lines.append(chunk)
                else:
                    current = chunk
            continue

        if current and len(current) + len(gap) + len(word) > width:
            current.extend(gap)  # trailing space closes the line
            lines.append(current)
            current = list(word)
        else:
            current.extend(gap)
            current.extend(word)

    if previous_end < length:  # trailing whitespace
        current.extend(range(previous_end, length))
    if current or not lines:
        lines.append(current)
    return lines


def line_for_cursor(lines: Sequence[Sequence[int]], cursor: int) -> int:
    """Index of the line the cursor sits on (the last line once past the end)."""
    for number, line in enumerate(lines):
        if line and cursor <= line[-1]:
            return number
    return max(len(lines) - 1, 0)


def visible_slice(total_lines: int, cursor_line: int, max_lines: int) -> tuple[int, int]:
    """``(start, end)`` window of lines to draw, keeping the cursor line centred."""
    if max_lines <= 0 or total_lines <= 0:
        return (0, 0)
    if total_lines <= max_lines:
        return (0, total_lines)
    start = cursor_line - (max_lines - 1) // 2
    start = max(0, min(start, total_lines - max_lines))
    return (start, start + max_lines)


def _style_for(char: str, state: CharState, theme: Theme) -> Style:
    if state is CharState.CORRECT:
        return Style(color=theme.correct)
    if state is CharState.INCORRECT:
        # A mistyped space has nothing to colour, so flag it with a background.
        if char == " ":
            return Style(bgcolor=theme.incorrect)
        return Style(color=theme.incorrect, underline=True)
    return Style(color=theme.pending)


def render_target(
    target: str,
    states: Sequence[CharState],
    cursor: int,
    lines: Sequence[Sequence[int]],
    window: tuple[int, int],
    theme: Theme,
    *,
    show_cursor: bool = True,
) -> Text:
    """Build the styled text block for the visible window of lines."""
    cursor_style = Style(color=theme.cursor, underline=True, bold=True)
    start, end = window
    block = Text(no_wrap=True, overflow="crop")
    for row, line in enumerate(lines[start:end]):
        for index in line:
            char = target[index]
            state = states[index] if index < len(states) else CharState.PENDING
            style = _style_for(char, state, theme)
            if show_cursor and index == cursor:
                style += cursor_style
            block.append(char, style=style)
        if row < (end - start) - 1:
            block.append("\n")
    return block


def _bar(left: Text, centre: Text, right: Text) -> Table:
    """A three-column full-width grid, used for the top and bottom bars."""
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right", ratio=1)
    grid.add_row(left, centre, right)
    return grid


def render_progress(engine: TypingEngine, theme: Theme) -> Text:
    """Whichever limit ends this test: a countdown, a word count or a char count."""
    style = f"bold {theme.accent}"
    if engine.mode is TestMode.TIME:
        remaining = engine.remaining or 0.0
        # Round up so a fresh 30s test shows 00:30 rather than 00:29.
        minutes, seconds = divmod(int(-(-remaining // 1)), 60)
        return Text(f"{minutes:02d}:{seconds:02d}", style=style)
    if engine.mode is TestMode.WORDS:
        return Text(f"{engine.words_completed}/{engine.word_total} words", style=style)
    return Text(f"{engine.cursor}/{len(engine.target)} chars", style=style)


def render_topbar(engine: TypingEngine, theme: Theme) -> Table:
    """Title and mode on the left, the limit in the middle, live WPM on the right."""
    title = Text("typerush", style=f"bold {theme.secondary}")
    title.append(f"  {engine.result().label}", style=theme.muted)
    live = (
        Text(f"{engine.stats().wpm_display} wpm", style=f"bold {theme.good}")
        if engine.started
        else Text("start typing", style=theme.muted)
    )
    return _bar(title, render_progress(engine, theme), live)


def render_footer(engine: TypingEngine, theme: Theme) -> Table:
    """Secondary stats on the left, key hints on the right."""
    stats = engine.stats()
    left = Text()
    left.append("raw ", style=theme.muted)
    left.append(str(stats.raw_wpm_display), style=theme.correct)
    left.append("   acc ", style=theme.muted)
    left.append(f"{stats.accuracy_display:.0f}%", style=theme.correct)
    left.append("   err ", style=theme.muted)
    left.append(
        str(stats.errors),
        style=theme.incorrect if stats.errors else theme.correct,
    )
    return _bar(left, Text(""), Text(TYPING_HINT, style=theme.muted))
