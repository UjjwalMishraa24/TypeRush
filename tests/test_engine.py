from __future__ import annotations

import pytest

from typerush.game.engine import CharState, TestMode, TypingEngine


def type_text(engine: TypingEngine, text: str) -> None:
    for char in text:
        engine.type_char(char)


def test_rejects_empty_target():
    with pytest.raises(ValueError, match="must not be empty"):
        TypingEngine("")


def test_time_mode_requires_a_duration():
    with pytest.raises(ValueError, match="positive duration"):
        TypingEngine("abc", mode=TestMode.TIME)


def test_clock_starts_on_first_keystroke_not_construction(clock):
    engine = TypingEngine("hello", time_fn=clock)
    clock.advance(10.0)
    assert not engine.started
    assert engine.elapsed == 0.0

    engine.type_char("h")
    assert engine.started
    clock.advance(6.0)
    assert engine.elapsed == pytest.approx(6.0)


def test_correct_typing_completes_the_test(clock):
    engine = TypingEngine("ab cd", mode=TestMode.WORDS, word_limit=2, time_fn=clock)
    type_text(engine, "ab c")
    clock.advance(30.0)
    assert not engine.finished

    engine.type_char("d")
    assert engine.finished
    assert engine.completed
    assert engine.stats().errors == 0
    assert engine.stats().accuracy == pytest.approx(100.0)


def test_wrong_character_counts_as_an_error_and_stays_counted(clock):
    engine = TypingEngine("cat sat", time_fn=clock)
    type_text(engine, "cxt")
    stats = engine.stats()
    assert stats.errors == 1
    assert stats.correct_chars == 2
    assert stats.incorrect_chars == 1

    engine.backspace()
    engine.backspace()
    type_text(engine, "at")
    stats = engine.stats()
    # The text is now perfect, so net WPM recovers...
    assert stats.correct_chars == 3
    assert stats.incorrect_chars == 0
    # ...but the mistake is still remembered by accuracy.
    assert stats.errors == 1
    assert stats.keystrokes == 5
    assert stats.accuracy == pytest.approx(4 / 5 * 100)


def test_finishing_the_text_locks_out_further_editing():
    engine = TypingEngine("cat")
    type_text(engine, "cat")
    assert engine.finished
    assert engine.backspace() is False


def test_backspace_on_empty_input_is_a_no_op():
    engine = TypingEngine("abc")
    assert engine.backspace() is False
    assert engine.cursor == 0


def test_keystrokes_past_the_end_are_ignored():
    engine = TypingEngine("hi", mode=TestMode.QUOTE)
    type_text(engine, "hi")
    assert engine.finished
    assert engine.type_char("x") is False
    assert engine.typed_text == "hi"


def test_control_characters_are_rejected():
    engine = TypingEngine("abc")
    assert engine.type_char("\n") is False
    assert engine.type_char("\t") is False
    assert engine.type_char("ab") is False
    assert engine.cursor == 0
    assert not engine.started


def test_space_is_accepted_as_a_character():
    engine = TypingEngine("a b")
    type_text(engine, "a b")
    assert engine.typed_text == "a b"
    assert engine.stats().errors == 0


def test_time_mode_ends_when_the_clock_runs_out(clock):
    engine = TypingEngine("a" * 200, mode=TestMode.TIME, duration=30.0, time_fn=clock)
    engine.type_char("a")
    clock.advance(29.0)
    assert engine.tick() is False

    clock.advance(2.0)
    assert engine.tick() is True
    assert engine.completed
    # Elapsed is pinned to the limit so a 30s test never reports 31s.
    assert engine.elapsed == pytest.approx(30.0)


def test_time_mode_ignores_input_after_expiry(clock):
    engine = TypingEngine("a" * 50, mode=TestMode.TIME, duration=5.0, time_fn=clock)
    engine.type_char("a")
    clock.advance(10.0)
    assert engine.type_char("a") is False
    assert engine.finished
    assert engine.typed_text == "a"


def test_time_mode_does_not_finish_on_reaching_the_end_of_text(clock):
    engine = TypingEngine("ab", mode=TestMode.TIME, duration=30.0, time_fn=clock)
    type_text(engine, "ab")
    assert not engine.finished  # the clock decides, not the text


def test_remaining_counts_down_only_in_time_mode(clock):
    timed = TypingEngine("a" * 20, mode=TestMode.TIME, duration=10.0, time_fn=clock)
    timed.type_char("a")
    clock.advance(4.0)
    assert timed.remaining == pytest.approx(6.0)

    words = TypingEngine("abc", mode=TestMode.WORDS, word_limit=1)
    assert words.remaining is None


def test_abandon_marks_the_run_incomplete(clock):
    engine = TypingEngine("hello world", time_fn=clock)
    type_text(engine, "hello")
    clock.advance(5.0)
    engine.abandon()
    assert engine.finished
    assert engine.completed is False
    assert engine.result().completed is False


def test_abandon_after_finish_is_a_no_op():
    engine = TypingEngine("hi", mode=TestMode.QUOTE)
    type_text(engine, "hi")
    engine.abandon()
    assert engine.completed is True


def test_char_states_track_each_character():
    engine = TypingEngine("cat")
    type_text(engine, "cx")
    assert engine.char_states() == [
        CharState.CORRECT,
        CharState.INCORRECT,
        CharState.PENDING,
    ]


def test_word_counters():
    engine = TypingEngine("one two three", mode=TestMode.WORDS, word_limit=3)
    assert engine.word_total == 3
    assert engine.words_completed == 0
    type_text(engine, "one ")
    assert engine.words_completed == 1
    type_text(engine, "two ")
    assert engine.words_completed == 2


def test_progress_follows_the_clock_in_time_mode(clock):
    engine = TypingEngine("a" * 100, mode=TestMode.TIME, duration=10.0, time_fn=clock)
    engine.type_char("a")
    clock.advance(5.0)
    assert engine.progress == pytest.approx(0.5)


def test_progress_follows_the_cursor_in_word_mode():
    engine = TypingEngine("abcd", mode=TestMode.WORDS, word_limit=1)
    type_text(engine, "ab")
    assert engine.progress == pytest.approx(0.5)


def test_result_captures_metadata(clock):
    engine = TypingEngine(
        "be brave",
        mode=TestMode.QUOTE,
        source="Someone",
        time_fn=clock,
    )
    type_text(engine, "be brav")
    clock.advance(4.0)
    engine.type_char("e")
    result = engine.result()
    assert result.mode is TestMode.QUOTE
    assert result.source == "Someone"
    assert result.typed == "be brave"
    assert result.completed
    assert result.label == "quote"


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"mode": TestMode.TIME, "duration": 30.0}, "time 30s"),
        ({"mode": TestMode.WORDS, "word_limit": 25}, "words 25"),
        ({"mode": TestMode.QUOTE}, "quote"),
    ],
)
def test_result_labels(kwargs, expected):
    engine = TypingEngine("a b c", **kwargs)
    assert engine.result().label == expected
