from __future__ import annotations

import json

from typer.testing import CliRunner

from typerush import __version__
from typerush.cli import app
from typerush.game.engine import TestMode, TypingEngine
from typerush.storage.config import config_path
from typerush.storage.history import append_result

runner = CliRunner()


def finished_result(text: str = "hello world"):
    engine = TypingEngine(text, mode=TestMode.QUOTE, source="Tester")
    for char in text:
        engine.type_char(char)
    return engine.result()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_the_modes():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for flag in ("--time", "--words", "--quote", "--stats"):
        assert flag in result.output


def test_stats_on_an_empty_history_explains_itself():
    result = runner.invoke(app, ["--stats"])
    assert result.exit_code == 0
    assert "no runs recorded yet" in result.output


def test_stats_lists_previous_runs():
    append_result(finished_result())
    result = runner.invoke(app, ["--stats", "--no-banner"])
    assert result.exit_code == 0
    assert "quote" in result.output
    assert "best" in result.output


def test_init_config_writes_the_file():
    result = runner.invoke(app, ["--init-config"])
    assert result.exit_code == 0
    assert config_path().exists()
    payload = json.loads(config_path().read_text(encoding="utf-8"))
    assert payload["default_time"] == 30


def test_conflicting_modes_are_rejected():
    result = runner.invoke(app, ["--time", "30", "--words", "50"])
    assert result.exit_code == 1
    assert "pick one mode" in result.output


def test_non_positive_time_is_rejected():
    result = runner.invoke(app, ["--time", "0"])
    assert result.exit_code == 1
    assert "--time must be greater than 0" in result.output


def test_non_positive_words_is_rejected():
    result = runner.invoke(app, ["--words", "0"])
    assert result.exit_code == 1
    assert "--words must be greater than 0" in result.output


def test_missing_wordlist_is_rejected_by_the_parser():
    result = runner.invoke(app, ["--wordlist", "/nope/does-not-exist.txt"])
    assert result.exit_code != 0


def test_running_without_a_terminal_fails_helpfully():
    # CliRunner is not a tty, which is exactly the case we want to cover.
    result = runner.invoke(app, ["--time", "5"])
    assert result.exit_code == 1
    assert "interactive terminal" in result.output


def test_malformed_config_warns_but_still_runs():
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("{broken", encoding="utf-8")
    result = runner.invoke(app, ["--stats"])
    assert result.exit_code == 0
    assert "warning" in result.output
    assert "using defaults" in result.output


def test_config_default_mode_is_validated():
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps({"default_mode": "banana"}), encoding="utf-8")
    result = runner.invoke(app, ["--no-banner"])
    assert "is not a mode" in result.output


def test_theme_flag_saves_the_named_preset():
    result = runner.invoke(app, ["--theme", "gruvbox", "--stats", "--no-banner"])
    assert result.exit_code == 0
    payload = json.loads(config_path().read_text(encoding="utf-8"))
    assert payload["theme_name"] == "gruvbox"


def test_theme_flag_with_the_current_theme_does_not_rewrite_the_file():
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps({"theme_name": "gruvbox"}), encoding="utf-8")
    result = runner.invoke(app, ["--theme", "gruvbox", "--stats", "--no-banner"])
    assert result.exit_code == 0
    assert "saved" not in result.output


def test_unknown_theme_flag_is_rejected():
    result = runner.invoke(app, ["--theme", "nonsense"])
    assert result.exit_code == 1
    assert "unknown theme" in result.output
    assert "gruvbox" in result.output


def test_ui_flag_without_a_terminal_fails_helpfully():
    # CliRunner is not a tty, which is exactly the case we want to cover.
    result = runner.invoke(app, ["--ui"])
    assert result.exit_code == 1
    assert "interactive terminal" in result.output
    assert "--theme" in result.output
