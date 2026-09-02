from __future__ import annotations

import pytest
from rich.console import Console, RenderableType

from typerush.game.engine import CharState, TestMode, TypingEngine
from typerush.storage.config import Theme
from typerush.ui.textview import (
    line_for_cursor,
    render_footer,
    render_progress,
    render_target,
    render_topbar,
    visible_slice,
    wrap_indices,
)


def to_text(renderable: RenderableType, width: int = 80) -> str:
    console = Console(width=width, no_color=True, legacy_windows=False)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


def rendered_lines(target: str, width: int) -> list[str]:
    return ["".join(target[i] for i in line) for line in wrap_indices(target, width)]


def test_every_index_appears_exactly_once_and_in_order():
    target = "the quick brown fox jumps over the lazy dog"
    flat = [index for line in wrap_indices(target, 12) for index in line]
    assert flat == list(range(len(target)))


def test_lines_fit_the_width_ignoring_trailing_spaces():
    target = "alpha beta gamma delta epsilon"
    for line in rendered_lines(target, 12):
        assert len(line.rstrip()) <= 12


def test_wrapping_breaks_between_words():
    assert rendered_lines("alpha beta gamma", 11) == ["alpha beta ", "gamma"]


def test_short_text_stays_on_one_line():
    assert rendered_lines("hello there", 40) == ["hello there"]


def test_word_longer_than_the_width_is_hard_split():
    lines = rendered_lines("abcdefghij", 4)
    assert lines == ["abcd", "efgh", "ij"]


def test_long_word_after_a_short_one():
    target = "hi abcdefghij"
    flat = [index for line in wrap_indices(target, 4) for index in line]
    assert flat == list(range(len(target)))


def test_empty_target_yields_one_empty_line():
    assert wrap_indices("", 10) == [[]]


def test_non_positive_width_is_treated_as_one():
    assert rendered_lines("ab", 0) == ["a", "b"]


def test_trailing_space_is_preserved():
    flat = [index for line in wrap_indices("hi ", 10) for index in line]
    assert flat == [0, 1, 2]


def test_line_for_cursor_follows_the_cursor():
    lines = wrap_indices("alpha beta gamma", 11)  # ["alpha beta ", "gamma"]
    assert line_for_cursor(lines, 0) == 0
    assert line_for_cursor(lines, 10) == 0
    assert line_for_cursor(lines, 11) == 1
    # Past the end clamps to the final line.
    assert line_for_cursor(lines, 999) == 1


@pytest.mark.parametrize(
    ("total", "cursor_line", "expected"),
    [
        (2, 0, (0, 2)),  # fewer lines than the window
        (10, 0, (0, 3)),  # clamped at the top
        (10, 5, (4, 7)),  # cursor centred
        (10, 9, (7, 10)),  # clamped at the bottom
    ],
)
def test_visible_slice_keeps_the_cursor_centred(total, cursor_line, expected):
    assert visible_slice(total, cursor_line, 3) == expected


def test_visible_slice_handles_degenerate_input():
    assert visible_slice(0, 0, 3) == (0, 0)
    assert visible_slice(5, 0, 0) == (0, 0)


def test_render_target_only_draws_the_visible_window():
    target = "alpha beta gamma delta"
    lines = wrap_indices(target, 11)
    engine = TypingEngine(target)
    text = render_target(
        target,
        engine.char_states(),
        engine.cursor,
        lines,
        (0, 1),
        Theme(),
    )
    assert "\n" not in text.plain
    assert text.plain == "alpha beta "


def test_render_target_styles_correct_and_incorrect_characters():
    target = "cat"
    engine = TypingEngine(target)
    engine.type_char("c")
    engine.type_char("x")
    theme = Theme()
    text = render_target(
        target,
        engine.char_states(),
        engine.cursor,
        wrap_indices(target, 20),
        (0, 1),
        theme,
    )
    assert text.plain == "cat"
    styles = [str(span.style) for span in text.spans]
    assert any(theme.correct in style for style in styles)
    assert any(theme.incorrect in style for style in styles)
    # The cursor sits on the third character.
    assert any(theme.cursor in style for style in styles)


def test_render_target_can_hide_the_cursor():
    target = "ab"
    theme = Theme()
    text = render_target(
        target,
        [CharState.PENDING, CharState.PENDING],
        0,
        wrap_indices(target, 20),
        (0, 1),
        theme,
        show_cursor=False,
    )
    assert all(theme.cursor not in str(span.style) for span in text.spans)


def test_mistyped_space_gets_a_background_so_it_is_visible():
    target = "a b"
    engine = TypingEngine(target)
    engine.type_char("a")
    engine.type_char("x")  # should have been a space
    text = render_target(
        target,
        engine.char_states(),
        engine.cursor,
        wrap_indices(target, 20),
        (0, 1),
        Theme(),
    )
    assert any("on " in str(span.style) for span in text.spans)


# ----------------------------------------------------------------- status bars


def test_progress_counts_down_in_time_mode(clock):
    engine = TypingEngine("a" * 50, mode=TestMode.TIME, duration=30.0, time_fn=clock)
    assert render_progress(engine, Theme()).plain == "00:30"
    engine.type_char("a")
    clock.advance(18.0)
    assert render_progress(engine, Theme()).plain == "00:12"


def test_progress_shows_minutes_for_long_tests(clock):
    engine = TypingEngine("a" * 50, mode=TestMode.TIME, duration=120.0, time_fn=clock)
    assert render_progress(engine, Theme()).plain == "02:00"


def test_progress_counts_words_in_word_mode():
    engine = TypingEngine("one two three", mode=TestMode.WORDS, word_limit=3)
    assert render_progress(engine, Theme()).plain == "0/3 words"
    for char in "one ":
        engine.type_char(char)
    assert render_progress(engine, Theme()).plain == "1/3 words"


def test_progress_counts_characters_in_quote_mode():
    engine = TypingEngine("hello", mode=TestMode.QUOTE)
    engine.type_char("h")
    assert render_progress(engine, Theme()).plain == "1/5 chars"


def test_topbar_prompts_before_the_first_keystroke():
    engine = TypingEngine("one two", mode=TestMode.WORDS, word_limit=2)
    rendered = to_text(render_topbar(engine, Theme()))
    assert "typerush" in rendered
    assert "words 2" in rendered
    assert "start typing" in rendered


def test_topbar_shows_live_wpm_once_typing_starts(clock):
    engine = TypingEngine("one two", mode=TestMode.WORDS, word_limit=2, time_fn=clock)
    engine.type_char("o")
    clock.advance(6.0)
    rendered = to_text(render_topbar(engine, Theme()))
    assert "wpm" in rendered
    assert "start typing" not in rendered


def test_footer_shows_secondary_stats_and_hints():
    engine = TypingEngine("cat sat")
    engine.type_char("c")
    engine.type_char("z")
    rendered = to_text(render_footer(engine, Theme()))
    assert "raw" in rendered
    assert "acc" in rendered
    assert "err" in rendered
    assert "esc quit" in rendered
    assert "tab restart" in rendered
