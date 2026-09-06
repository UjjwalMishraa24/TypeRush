"""Command-line entry point.

Deliberately written without ``from __future__ import annotations``: Typer
inspects the real annotation objects to build the parser, and postponed
evaluation leaves it holding strings it cannot resolve.
"""

import random
import sys
from dataclasses import replace
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .banner import render_banner
from .game.engine import TestMode, TestResult, TypingEngine
from .game.wordlist import WordSourceError, build_target
from .storage.config import Config, ConfigError, load_config, save_config
from .storage.history import HistoryError, append_result, best_entry, history_path, load_history
from .theme import theme_names
from .ui.results_screen import render_history, render_results
from .ui.theme_picker import pick_theme
from .ui.typing_screen import Restart, run_test

HELP = """
A fast, distraction-free typing speed test for your terminal.

Run [bold]typerush[/bold] for a 30-second test, or pick a mode:
[bold]--time 60[/bold], [bold]--words 50[/bold], [bold]--quote[/bold].
While typing: [bold]tab[/bold] restarts, [bold]esc[/bold] quits.
Pick a colour scheme with [bold]--ui[/bold] (default, catppuccin,
tokyo-night, gruvbox).
"""

app = typer.Typer(
    add_completion=False,
    help=HELP,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()
errors = Console(stderr=True)


def _fail(message: str) -> None:
    errors.print(f"[bold red]error[/bold red] {message}")
    raise typer.Exit(code=1)


def _warn(message: str) -> None:
    errors.print(f"[yellow]warning[/yellow] {message}")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"typerush {__version__}")
        raise typer.Exit()


def _load_config_or_default() -> Config:
    try:
        return load_config()
    except ConfigError as exc:
        _warn(f"{exc}; using defaults")
        return Config()


def _resolve_mode(
    config: Config,
    seconds: int | None,
    word_count: int | None,
    quote: bool,
) -> TestMode:
    given = (
        ("--time", seconds is not None),
        ("--words", word_count is not None),
        ("--quote", quote),
    )
    chosen = [name for name, was_given in given if was_given]
    if len(chosen) > 1:
        _fail(f"pick one mode, not {' and '.join(chosen)}")
    if quote:
        return TestMode.QUOTE
    if word_count is not None:
        return TestMode.WORDS
    if seconds is not None:
        return TestMode.TIME
    try:
        return TestMode(config.default_mode)
    except ValueError:
        _warn(f"config default_mode {config.default_mode!r} is not a mode; using 'time'")
        return TestMode.TIME


def _show_history(config: Config, limit: int, banner: bool) -> None:
    if banner:
        console.print(render_banner(config.theme))
        console.print()
    console.print(render_history(load_history(), config.theme, limit=limit))
    console.print(f"[dim]history file: {history_path()}[/dim]")


def _record(result: TestResult, config: Config, save: bool) -> None:
    """Print the results card, saving the run first when appropriate."""
    history = load_history()
    previous_best = best_entry(history, mode=result.mode.value)
    is_best = result.completed and (previous_best is None or result.stats.wpm > previous_best.wpm)

    saved = False
    if result.completed and save:
        try:
            append_result(result)
            saved = True
        except HistoryError as exc:
            _warn(str(exc))

    console.print()
    console.print(render_results(result, config.theme, saved=saved, personal_best=is_best))


def _choose_theme_interactive(config: Config) -> Config | None:
    """Run the picker; return an updated config, or ``None`` if cancelled."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        _fail("theme picker needs an interactive terminal (try --theme NAME)")
    name = pick_theme(config.theme_name)
    if name is None or name == config.theme_name:
        return None
    return replace(config, theme_name=name)


@app.command(help=HELP)
def main(
    seconds: int | None = typer.Option(
        None, "--time", "-t", metavar="SECONDS", help="Timed test, e.g. --time 60."
    ),
    word_count: int | None = typer.Option(
        None, "--words", "-w", metavar="COUNT", help="Fixed-length test, e.g. --words 50."
    ),
    quote: bool = typer.Option(False, "--quote", "-q", help="Type a random quote."),
    wordlist: Path | None = typer.Option(
        None,
        "--wordlist",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Custom word list (one word per line) instead of the bundled one.",
    ),
    quotes: Path | None = typer.Option(
        None,
        "--quotes",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Custom quotes JSON instead of the bundled one.",
    ),
    seed: int | None = typer.Option(
        None, "--seed", help="Seed the text generator for a reproducible test."
    ),
    stats: bool = typer.Option(False, "--stats", help="Show past results and exit."),
    limit: int = typer.Option(10, "--limit", help="Rows to show with --stats.", min=1),
    no_banner: bool = typer.Option(False, "--no-banner", help="Skip the splash screen."),
    no_save: bool = typer.Option(False, "--no-save", help="Do not write this run to history."),
    ui: bool = typer.Option(
        False, "--ui", help="Pick a colour theme interactively, save it, and exit."
    ),
    theme: str | None = typer.Option(
        None,
        "--theme",
        metavar="NAME",
        help=f"Bundled theme to use for this run and save as default ({', '.join(theme_names())}).",
    ),
    init_config: bool = typer.Option(
        False, "--init-config", help="Write a default config file and exit."
    ),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    """Run a typing test."""
    config = _load_config_or_default()
    banner = config.show_banner and not no_banner

    if theme is not None:
        if theme not in theme_names():
            _fail(f"unknown theme {theme!r} (choose from {', '.join(theme_names())})")
        if theme != config.theme_name:
            config = replace(config, theme_name=theme)
            save_config(config)
            console.print(f"[green]saved[/green] theme [bold]{theme}[/bold]")

    if ui:
        updated = _choose_theme_interactive(config)
        if updated is None:
            raise typer.Exit()
        config = updated
        save_config(config)
        console.print(f"[green]saved[/green] theme [bold]{config.theme_name}[/bold]")
        raise typer.Exit()

    if init_config:
        written = save_config(config)
        console.print(f"[green]wrote[/green] {written}")
        raise typer.Exit()

    if stats:
        _show_history(config, limit, banner)
        raise typer.Exit()

    mode = _resolve_mode(config, seconds, word_count, quote)
    duration = float(seconds if seconds is not None else config.default_time)
    words_target = word_count if word_count is not None else config.default_words
    if mode is TestMode.TIME and duration <= 0:
        _fail("--time must be greater than 0")
    if mode is TestMode.WORDS and words_target <= 0:
        _fail("--words must be greater than 0")

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        _fail("typerush needs an interactive terminal (try --stats for past results)")

    rng = random.Random(seed)
    outcome: object = None
    show_splash = banner

    while True:
        try:
            target = build_target(
                mode,
                rng=rng,
                duration=duration,
                word_count=words_target,
                wordlist_path=wordlist or config.wordlist,
                quotes_path=quotes or config.quotes,
            )
        except WordSourceError as exc:
            _fail(str(exc))
            return

        engine = TypingEngine(
            target.text,
            mode=mode,
            duration=duration if mode is TestMode.TIME else None,
            word_limit=words_target if mode is TestMode.WORDS else None,
            source=target.source,
        )
        try:
            outcome = run_test(engine, theme=config.theme, show_banner=show_splash)
        except KeyboardInterrupt:  # pragma: no cover - depends on a real terminal
            outcome = None
        show_splash = False  # only greet once per session
        if not isinstance(outcome, Restart):
            break

    if isinstance(outcome, TestResult):
        _record(outcome, config, save=config.save_history and not no_save)
    else:
        console.print("[dim]no test recorded[/dim]")


def run() -> None:
    """Console-script entry point."""
    try:
        app()
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        errors.print("[dim]interrupted[/dim]")
        raise SystemExit(130) from None


if __name__ == "__main__":  # pragma: no cover
    run()
