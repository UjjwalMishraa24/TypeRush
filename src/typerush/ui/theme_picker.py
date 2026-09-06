"""The ``--ui`` theme picker: a full-screen Textual app.

Shows every bundled theme in a box; moving the selection re-renders the ASCII
banner live in the highlighted palette so you can judge gradients before
committing. Enter returns the chosen name (the CLI persists it); escape
returns ``None`` and leaves the config untouched.
"""

from __future__ import annotations

from typing import ClassVar

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Static

from ..banner import render_banner
from ..theme import THEMES, theme_names

HINT = "↑/↓ or j/k to move  ·  enter to select  ·  esc to cancel"
PREVIEW_HINT = "press enter to save this theme"


class ThemePicker(App[str | None]):
    """Renders the theme list; returns the chosen name, or ``None`` on escape."""

    CSS = """
    Screen {
        align: center middle;
    }
    #picker {
        width: auto;
        height: auto;
    }
    """

    ENABLE_COMMAND_PALETTE = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "cancel", priority=True, show=False),
        Binding("enter", "choose", "select", priority=True, show=False),
        Binding("up,k", "move(-1)", "up", show=False),
        Binding("down,j", "move(1)", "down", show=False),
    ]

    def __init__(
        self,
        current: str = "default",
        *,
        show_banner: bool = True,
    ) -> None:
        super().__init__()
        self.names = theme_names()
        #: Index of the highlighted row.
        self.index = self._row_of(current)
        self.show_banner = show_banner

    def _row_of(self, name: str) -> int:
        try:
            return self.names.index(name)
        except ValueError:
            return 0

    # ---------------------------------------------------------------- compose

    def compose(self) -> ComposeResult:
        yield Static(id="picker")

    def on_mount(self) -> None:
        self._redraw()

    # ------------------------------------------------------------------ input

    def on_key(self, event: events.Key) -> None:
        event.stop()

    # ----------------------------------------------------------------- render

    def _redraw(self) -> None:
        self.query_one("#picker", Static).update(self._render())

    def _render(self) -> Group:
        name = self.names[self.index]
        theme = THEMES[name]

        list_rows = Table.grid(padding=(0, 2))
        list_rows.add_column(justify="right")
        list_rows.add_column()
        for row, candidate in enumerate(self.names):
            palette = THEMES[candidate]
            marker = "●" if row == self.index else " "
            bullet = Text(marker, style=palette.accent if row == self.index else palette.muted)
            label = Text(candidate, style=palette.correct if row == self.index else palette.muted)
            if row == self.index:
                label.stylize(f"bold {palette.accent}")
            list_rows.add_row(bullet, label)

        box = Panel(
            list_rows,
            title="theme",
            title_align="left",
            border_style=theme.accent,
        )

        parts = []
        if self.show_banner:
            parts.append(render_banner(theme, hint=PREVIEW_HINT))
        parts.append(box)
        parts.append(Text(HINT, style=theme.muted))
        return Group(*parts)

    # ---------------------------------------------------------------- actions

    def action_move(self, step: int) -> None:
        self.index = (self.index + step) % len(self.names)
        self._redraw()

    def action_choose(self) -> None:
        self.exit(self.names[self.index])

    def action_cancel(self) -> None:
        self.exit(None)


def pick_theme(current: str = "default") -> str | None:
    """Run the picker; returns the chosen theme name, or ``None`` if cancelled."""
    return ThemePicker(current).run()
