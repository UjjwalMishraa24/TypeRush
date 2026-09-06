from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime

import pytest

from typerush.game.engine import TestMode, TypingEngine
from typerush.storage.config import (
    Config,
    ConfigError,
    config_from_mapping,
    config_path,
    load_config,
    save_config,
    typerush_home,
)
from typerush.storage.history import (
    HistoryEntry,
    append_result,
    average_wpm,
    best_entry,
    entry_from_result,
    history_path,
    load_history,
    recent_entries,
    save_history,
)
from typerush.theme import Theme


def finished_result(wpm_text: str = "hello world", *, mode: TestMode = TestMode.QUOTE):
    engine = TypingEngine(wpm_text, mode=mode, source="Tester")
    for char in wpm_text:
        engine.type_char(char)
    return engine.result()


# --------------------------------------------------------------------- config


def test_home_follows_the_environment_variable(isolated_home):
    assert typerush_home() == isolated_home
    assert config_path() == isolated_home / "config.json"
    assert history_path() == isolated_home / "history.json"


def test_missing_config_returns_defaults():
    assert load_config() == Config()


def test_save_then_load_round_trips():
    original = Config(
        default_time=45,
        show_banner=False,
        theme_name="gruvbox",
        theme_overrides={"accent": "#ff0000"},
    )
    path = save_config(original)
    assert path.exists()
    assert load_config() == original


def test_save_creates_the_directory(isolated_home):
    assert not isolated_home.exists()
    save_config(Config())
    assert isolated_home.is_dir()


def test_empty_config_file_returns_defaults():
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("   \n", encoding="utf-8")
    assert load_config() == Config()


def test_malformed_config_raises_so_the_cli_can_warn():
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("{oops", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_config()


def test_unknown_keys_are_ignored():
    config = config_from_mapping({"default_time": 15, "future_option": "???"})
    assert config.default_time == 15
    assert config == Config(default_time=15)


def test_wrongly_typed_values_are_ignored():
    config = config_from_mapping(
        {
            "default_time": "sixty",  # not an int
            "default_words": -5,  # not positive
            "show_banner": "yes",  # not a bool
            "default_mode": "  ",  # blank
        }
    )
    assert config == Config()


def test_booleans_are_not_accepted_as_integers():
    assert config_from_mapping({"default_time": True}).default_time == Config().default_time


def test_partial_theme_overrides_keep_other_colours():
    config = config_from_mapping({"theme": {"accent": "#123456", "bogus": 1}})
    assert config.theme.accent == "#123456"
    assert config.theme.correct == Theme().correct


def test_theme_gradient_uses_three_stops():
    theme = Theme(accent="#111111", mid="#222222", secondary="#333333")
    assert theme.gradient == ("#111111", "#222222", "#333333")


def test_path_properties_expand_the_user(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    config = Config(wordlist_path="~/w.txt", quotes_path="~/q.json")
    assert config.wordlist == tmp_path / "w.txt"
    assert config.quotes == tmp_path / "q.json"


def test_unset_paths_are_none():
    assert Config().wordlist is None
    assert Config().quotes is None


def test_saved_config_is_valid_json():
    save_config(Config())
    payload = json.loads(config_path().read_text(encoding="utf-8"))
    assert payload["default_mode"] == "time"
    assert payload["theme_name"] == "default"
    # Overrides are stored under the legacy "theme" key, empty when none are set.
    assert payload["theme"] == {}


def test_config_resolves_the_named_preset():
    config = Config(theme_name="catppuccin")
    assert config.theme.accent == "#94e2d5"


def test_config_theme_overrides_apply_on_top_of_the_preset():
    config = Config(theme_name="catppuccin", theme_overrides={"accent": "#ff0000"})
    assert config.theme.accent == "#ff0000"
    assert config.theme.correct == "#cdd6f4"


def test_config_unknown_theme_name_falls_back_to_default():
    config = Config(theme_name="nonsense")
    assert config.theme == Theme()


def test_config_reads_a_legacy_theme_block():
    config = config_from_mapping({"theme": {"accent": "#123456"}})
    assert config.theme_name == "default"
    assert config.theme.accent == "#123456"


# -------------------------------------------------------------------- history


def test_missing_history_is_empty():
    assert load_history() == []


def test_append_then_load_round_trips():
    entry = append_result(finished_result())
    stored = load_history()
    assert stored == [entry]
    assert stored[0].completed is True
    assert stored[0].source == "Tester"


def test_append_preserves_order():
    append_result(finished_result("first pass"))
    append_result(finished_result("second pass"))
    assert [entry.correct_chars for entry in load_history()] == [10, 11]


def test_entry_from_result_uses_the_given_timestamp():
    when = datetime(2026, 8, 24, 9, 30, 0)
    entry = entry_from_result(finished_result(), when)
    assert entry.timestamp.startswith("2026-08-24T09:30")
    assert entry.when == when


def test_entry_rounds_floats_for_a_tidy_file():
    entry = entry_from_result(finished_result())
    assert entry.wpm == round(entry.wpm, 2)
    assert entry.elapsed == round(entry.elapsed, 2)


def test_corrupt_history_is_ignored_rather_than_fatal():
    history_path().parent.mkdir(parents=True, exist_ok=True)
    history_path().write_text("{not json", encoding="utf-8")
    assert load_history() == []


def _as_dict(entry: HistoryEntry) -> dict[str, object]:
    return {field: getattr(entry, field) for field in HistoryEntry.__dataclass_fields__}


def test_bare_list_history_is_accepted():
    entry = entry_from_result(finished_result())
    history_path().parent.mkdir(parents=True, exist_ok=True)
    history_path().write_text(json.dumps([_as_dict(entry)]), encoding="utf-8")
    assert load_history() == [entry]


def test_rows_missing_required_keys_are_skipped():
    good = _as_dict(entry_from_result(finished_result()))
    history_path().parent.mkdir(parents=True, exist_ok=True)
    history_path().write_text(
        json.dumps({"version": 1, "entries": [good, {"mode": "time"}, "nonsense", 5]}),
        encoding="utf-8",
    )
    assert len(load_history()) == 1


def test_unknown_columns_in_history_are_dropped():
    row = _as_dict(entry_from_result(finished_result()))
    row["future_field"] = "ignored"
    history_path().parent.mkdir(parents=True, exist_ok=True)
    history_path().write_text(json.dumps({"entries": [row]}), encoding="utf-8")
    assert len(load_history()) == 1


def test_save_history_trims_to_the_cap(monkeypatch):
    monkeypatch.setattr("typerush.storage.history.MAX_ENTRIES", 3)
    entries = [entry_from_result(finished_result()) for _ in range(5)]
    save_history(entries)
    assert len(load_history()) == 3


def sample(wpm: float, *, mode: str = "time", completed: bool = True) -> HistoryEntry:
    return HistoryEntry(
        timestamp="2026-08-24T10:00:00",
        mode=mode,
        label=mode,
        wpm=wpm,
        raw_wpm=wpm + 5,
        accuracy=97.0,
        errors=2,
        elapsed=30.0,
        correct_chars=100,
        incorrect_chars=3,
        completed=completed,
    )


def test_best_entry_picks_the_highest_wpm():
    entries = [sample(50), sample(90), sample(70)]
    best = best_entry(entries)
    assert best is not None
    assert best.wpm == 90


def test_best_entry_ignores_abandoned_runs():
    entries = [sample(50), sample(200, completed=False)]
    best = best_entry(entries)
    assert best is not None
    assert best.wpm == 50


def test_best_entry_can_filter_by_mode():
    entries = [sample(50, mode="time"), sample(90, mode="words")]
    timed = best_entry(entries, mode="time")
    assert timed is not None
    assert timed.wpm == 50
    assert best_entry(entries, mode="quote") is None


def test_best_entry_of_nothing_is_none():
    assert best_entry([]) is None


def test_average_wpm_covers_completed_runs_only():
    assert average_wpm([sample(50), sample(70), sample(500, completed=False)]) == 60.0
    assert average_wpm([]) == 0.0


def test_recent_entries_are_newest_first():
    entries = [sample(10), sample(20), sample(30)]
    assert [entry.wpm for entry in recent_entries(entries, 2)] == [30, 20]
    assert recent_entries(entries, 0) == []


def test_entry_with_a_bad_timestamp_returns_none():
    assert sample(50).when is not None
    broken = replace(sample(50), timestamp="not-a-date")
    assert broken.when is None
