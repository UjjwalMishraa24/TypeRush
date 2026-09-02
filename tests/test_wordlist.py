from __future__ import annotations

import json
import random

import pytest

from typerush.game.engine import TestMode
from typerush.game.wordlist import (
    Quote,
    WordSourceError,
    build_target,
    load_quotes,
    load_words,
    pick_quote,
    pick_words,
    words_for_duration,
)


def test_bundled_word_list_loads():
    words = load_words()
    assert len(words) > 200
    assert all(word == word.strip() for word in words)
    assert all(" " not in word for word in words)


def test_bundled_word_list_has_no_duplicates():
    words = load_words()
    assert len(words) == len(set(words))


def test_bundled_quotes_load():
    quotes = load_quotes()
    assert len(quotes) > 10
    assert all(quote.text for quote in quotes)


def test_custom_word_list_skips_blanks_and_comments(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# a comment\n\nalpha\nbeta\nalpha\n  gamma  \n", encoding="utf-8")
    assert load_words(path) == ["alpha", "beta", "gamma"]


def test_multi_word_lines_are_reduced_to_one_token(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("hello world\n", encoding="utf-8")
    assert load_words(path) == ["hello"]


def test_empty_word_list_is_an_error(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(WordSourceError, match="no usable words"):
        load_words(path)


def test_missing_word_list_is_an_error(tmp_path):
    with pytest.raises(WordSourceError, match="could not read"):
        load_words(tmp_path / "nope.txt")


def test_quotes_accept_a_bare_list_of_strings(tmp_path):
    path = tmp_path / "quotes.json"
    path.write_text(json.dumps(["first quote", "second quote"]), encoding="utf-8")
    quotes = load_quotes(path)
    assert [quote.text for quote in quotes] == ["first quote", "second quote"]
    assert quotes[0].attribution is None


def test_quotes_accept_objects_with_attribution(tmp_path):
    path = tmp_path / "quotes.json"
    path.write_text(
        json.dumps({"quotes": [{"text": "hi", "author": "Ada", "source": "Notes"}]}),
        encoding="utf-8",
    )
    quote = load_quotes(path)[0]
    assert quote.attribution == "Ada, Notes"


def test_quotes_skip_unusable_entries(tmp_path):
    path = tmp_path / "quotes.json"
    path.write_text(json.dumps(["ok", "", 42, {"author": "no text"}]), encoding="utf-8")
    assert [quote.text for quote in load_quotes(path)] == ["ok"]


def test_invalid_quote_json_is_an_error(tmp_path):
    path = tmp_path / "quotes.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(WordSourceError, match="not valid JSON"):
        load_quotes(path)


def test_quote_attribution_variants():
    assert Quote("t", author="A").attribution == "A"
    assert Quote("t", source="S").attribution == "S"
    assert Quote("t").attribution is None


def test_pick_words_is_deterministic_for_a_seed():
    words = load_words()
    first = pick_words(words, 20, random.Random(7))
    second = pick_words(words, 20, random.Random(7))
    assert first == second
    assert len(first) == 20


def test_pick_words_rejects_non_positive_counts():
    with pytest.raises(ValueError, match="must be positive"):
        pick_words(["a"], 0, random.Random(1))


def test_pick_words_samples_with_replacement_from_short_lists():
    assert pick_words(["only"], 5, random.Random(1)) == ["only"] * 5


def test_pick_quote_needs_a_non_empty_list():
    with pytest.raises(WordSourceError, match="quote list is empty"):
        pick_quote([], random.Random(1))


def test_words_for_duration_leaves_generous_headroom():
    # Even a 300 wpm typist cannot exhaust a 60s test.
    assert words_for_duration(60) > 240
    assert words_for_duration(0) > 0


def test_build_target_time_mode_generates_plenty_of_words():
    target = build_target(TestMode.TIME, rng=random.Random(3), duration=30.0)
    assert len(target.text.split()) == words_for_duration(30.0)
    assert target.source is None


def test_build_target_words_mode_respects_the_count():
    target = build_target(TestMode.WORDS, rng=random.Random(3), word_count=17)
    assert len(target.text.split()) == 17


def test_build_target_quote_mode_carries_attribution():
    target = build_target(TestMode.QUOTE, rng=random.Random(3))
    assert target.text
    assert target.source is None or isinstance(target.source, str)


def test_build_target_validates_limits():
    with pytest.raises(ValueError, match="positive duration"):
        build_target(TestMode.TIME, rng=random.Random(1), duration=0)
    with pytest.raises(ValueError, match="positive word count"):
        build_target(TestMode.WORDS, rng=random.Random(1), word_count=0)


def test_build_target_uses_custom_sources(tmp_path):
    words = tmp_path / "w.txt"
    words.write_text("zzz\n", encoding="utf-8")
    target = build_target(TestMode.WORDS, rng=random.Random(1), word_count=3, wordlist_path=words)
    assert target.text == "zzz zzz zzz"

    quotes = tmp_path / "q.json"
    quotes.write_text(json.dumps([{"text": "solo", "author": "Me"}]), encoding="utf-8")
    quote_target = build_target(TestMode.QUOTE, rng=random.Random(1), quotes_path=quotes)
    assert quote_target.text == "solo"
    assert quote_target.source == "Me"
