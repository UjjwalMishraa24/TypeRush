from __future__ import annotations

import pytest

from typerush.game.stats import (
    build_stats,
    calculate_accuracy,
    calculate_raw_wpm,
    calculate_wpm,
    empty_stats,
)


def test_wpm_uses_five_characters_per_word():
    # 250 correct chars in 60s = 50 words per minute.
    assert calculate_wpm(250, 60.0) == pytest.approx(50.0)


def test_wpm_scales_with_elapsed_time():
    assert calculate_wpm(250, 30.0) == pytest.approx(100.0)
    assert calculate_wpm(250, 120.0) == pytest.approx(25.0)


def test_wpm_is_zero_before_any_time_passes():
    assert calculate_wpm(100, 0.0) == 0.0
    assert calculate_wpm(100, -5.0) == 0.0


def test_raw_wpm_counts_incorrect_characters_too():
    assert calculate_raw_wpm(300, 60.0) == pytest.approx(60.0)
    assert calculate_raw_wpm(300, 60.0) > calculate_wpm(250, 60.0)


@pytest.mark.parametrize(
    ("correct", "total", "expected"),
    [
        (0, 0, 100.0),  # nothing typed yet is not a failure
        (50, 50, 100.0),
        (45, 50, 90.0),
        (0, 10, 0.0),
    ],
)
def test_accuracy(correct, total, expected):
    assert calculate_accuracy(correct, total) == pytest.approx(expected)


def test_accuracy_is_clamped_to_100():
    assert calculate_accuracy(20, 10) == 100.0


def test_build_stats_derives_errors_from_keystrokes():
    stats = build_stats(
        correct_chars=48,
        incorrect_chars=2,
        keystrokes=55,
        correct_keystrokes=50,
        elapsed=30.0,
    )
    assert stats.typed_chars == 50
    assert stats.errors == 5
    assert stats.wpm == pytest.approx((48 / 5) / 0.5)
    assert stats.raw_wpm == pytest.approx((50 / 5) / 0.5)
    assert stats.accuracy == pytest.approx(50 / 55 * 100)


def test_display_helpers_round():
    stats = build_stats(
        correct_chars=41,
        incorrect_chars=0,
        keystrokes=41,
        correct_keystrokes=40,
        elapsed=30.0,
    )
    assert stats.wpm_display == round(stats.wpm)
    assert isinstance(stats.wpm_display, int)
    assert stats.accuracy_display == pytest.approx(round(stats.accuracy, 1))


def test_empty_stats_is_all_zero_but_perfect_accuracy():
    stats = empty_stats()
    assert (stats.wpm, stats.raw_wpm, stats.errors, stats.typed_chars) == (0.0, 0.0, 0, 0)
    assert stats.accuracy == 100.0
