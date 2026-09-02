"""End-of-test results card and the ``--stats`` history table.

Both are plain Rich renderables printed to the normal terminal after the Textual
app has exited, so results stay in scrollback instead of vanishing with the
alternate screen.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..banner import render_big_number
from ..game.engine import TestResult
from ..storage.config import Theme
from ..storage.history import HistoryEntry, average_wpm, best_entry


def _metric(label: str, value: str, theme: Theme, *, colour: str | None = None) -> Text:
    text = Text()
    text.append(f"{label} ", style=theme.muted)
    text.append(value, style=f"bold {colour or theme.correct}")
    return text


def _metric_grid(rows: Sequence[Sequence[Text]]) -> Table:
    grid = Table.grid(padding=(0, 4))
    columns = max((len(row) for row in rows), default=0)
    for _ in range(columns):
        grid.add_column(justify="left")
    for row in rows:
        grid.add_row(*row)
    return grid


def render_results(
    result: TestResult,
    theme: Theme | None = None,
    *,
    saved: bool = False,
    personal_best: bool = False,
) -> RenderableType:
    """The banner-style summary card for a finished (or abandoned) attempt."""
    palette = theme or Theme()
    stats = result.stats

    rows = [
        [
            _metric("wpm", str(stats.wpm_display), palette, colour=palette.accent),
            _metric("raw", str(stats.raw_wpm_display), palette),
            _metric("accuracy", f"{stats.accuracy_display:.1f}%", palette, colour=palette.good),
        ],
        [
            _metric(
                "errors",
                str(stats.errors),
                palette,
                colour=palette.incorrect if stats.errors else palette.good,
            ),
            _metric("time", f"{stats.elapsed:.1f}s", palette),
            _metric("chars", f"{stats.correct_chars}/{stats.typed_chars}", palette),
        ],
    ]

    body: list[RenderableType] = [render_big_number(stats.wpm_display, palette), _metric_grid(rows)]

    if result.source:
        attribution = Text()
        attribution.append("— ", style=palette.pending)
        attribution.append(result.source, style=f"italic {palette.secondary}")
        body.append(attribution)

    notes: list[Text] = []
    if personal_best:
        notes.append(Text("★ personal best", style=f"bold {palette.good}"))
    if not result.completed:
        notes.append(Text("abandoned — not saved to history", style=palette.incorrect))
    elif not saved:
        notes.append(Text("not saved to history", style=palette.muted))
    if notes:
        joined = Text("   ").join(notes)
        body.append(joined)

    title = Text()
    title.append("result", style=f"bold {palette.accent}")
    title.append(f"  ·  {result.label}", style=palette.muted)

    return Panel(
        Group(*body),
        title=title,
        title_align="left",
        border_style=palette.secondary,
        padding=(1, 3),
    )


def _format_when(entry: HistoryEntry) -> str:
    parsed: datetime | None = entry.when
    return parsed.strftime("%Y-%m-%d %H:%M") if parsed else entry.timestamp


def render_history(
    entries: Sequence[HistoryEntry],
    theme: Theme | None = None,
    *,
    limit: int = 10,
) -> RenderableType:
    """A table of recent runs plus best/average summary."""
    palette = theme or Theme()
    if not entries:
        return Panel(
            Text(
                "no runs recorded yet — run `typerush` to set your first score",
                style=palette.muted,
            ),
            title=Text("history", style=f"bold {palette.accent}"),
            title_align="left",
            border_style=palette.secondary,
            padding=(1, 3),
        )

    table = Table(
        box=None,
        expand=False,
        pad_edge=False,
        header_style=palette.muted,
        padding=(0, 2),
    )
    table.add_column("when", style=palette.muted, no_wrap=True)
    table.add_column("mode", style=palette.secondary, no_wrap=True)
    table.add_column("wpm", justify="right", style=f"bold {palette.accent}")
    table.add_column("raw", justify="right", style=palette.correct)
    table.add_column("acc", justify="right", style=palette.good)
    table.add_column("err", justify="right", style=palette.correct)

    ordered = list(entries)[-limit:][::-1] if limit > 0 else []
    for entry in ordered:
        table.add_row(
            _format_when(entry),
            entry.label,
            f"{round(entry.wpm)}",
            f"{round(entry.raw_wpm)}",
            f"{entry.accuracy:.1f}%",
            str(entry.errors),
        )

    all_entries = list(entries)
    best = best_entry(all_entries)
    summary = Text()
    summary.append("runs ", style=palette.muted)
    summary.append(str(len(all_entries)), style=f"bold {palette.correct}")
    summary.append("    best ", style=palette.muted)
    summary.append(
        f"{round(best.wpm)} wpm" if best else "—",
        style=f"bold {palette.accent}",
    )
    summary.append("    average ", style=palette.muted)
    summary.append(f"{average_wpm(all_entries):.1f} wpm", style=f"bold {palette.good}")

    return Panel(
        Group(table, Text(""), summary),
        title=Text("history", style=f"bold {palette.accent}"),
        title_align="left",
        border_style=palette.secondary,
        padding=(1, 3),
    )
