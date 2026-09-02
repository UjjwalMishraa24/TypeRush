"""The live typing screen: a full-screen Textual app.

Flow: optional gradient splash → typing view → app exits, handing the finished
:class:`~typerush.game.engine.TestResult` back to the CLI, which prints the
results card into normal scrollback.

Keys
----
printable / space  type
backspace          delete one character
tab, ctrl+r        restart with fresh text
escape, ctrl+c     quit (a started test is reported as abandoned)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import Static

from ..banner import render_banner
from ..game.engine import TestResult, TypingEngine
from ..storage.config import Theme
from .textview import (
    line_for_cursor,
    render_footer,
    render_target,
    render_topbar,
    visible_slice,
    wrap_indices,
)

#: How often live stats and the clock refresh, in seconds.
TICK_INTERVAL = 0.1
#: Lines of text kept on screen at once.
VISIBLE_LINES = 3
#: Width used before the widget has been laid out.
FALLBACK_WIDTH = 60
MIN_WIDTH = 20

SPLASH_HINT = "press any key to start  ·  esc to quit"


@dataclass(frozen=True, slots=True)
class Restart:
    """Sentinel returned when the user asks for a fresh test."""


RESTART = Restart()


class TypingScreen(App[object]):
    """Renders one attempt and returns a :class:`TestResult`, ``RESTART`` or ``None``."""

    CSS = """
    Screen {
        align: center middle;
    }
    #splash {
        width: auto;
        height: auto;
    }
    #test {
        width: 100%;
        height: auto;
    }
    #topbar, #footer {
        width: 100%;
        height: 1;
        padding: 0 2;
    }
    #words {
        width: 100%;
        padding: 1 2;
    }
    """

    ENABLE_COMMAND_PALETTE = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "quit_test", "quit", priority=True, show=False),
        Binding("ctrl+r", "restart_test", "restart", priority=True, show=False),
        Binding("tab", "restart_test", "restart", priority=True, show=False),
    ]

    def __init__(
        self,
        engine: TypingEngine,
        *,
        theme: Theme | None = None,
        show_banner: bool = True,
        visible_lines: int = VISIBLE_LINES,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.palette = theme or Theme()
        self.show_banner = show_banner
        self.visible_lines = max(1, visible_lines)
        self._on_splash = show_banner
        self._lines: list[list[int]] = []
        self._wrapped_width = 0
        #: Widgets only exist after on_mount; guards redraws triggered earlier.
        self._widgets_ready = False

    # ---------------------------------------------------------------- compose

    def compose(self) -> ComposeResult:
        yield Static(
            render_banner(self.palette, hint=SPLASH_HINT),
            id="splash",
        )
        with Vertical(id="test"):
            yield Static(id="topbar")
            yield Static(id="words")
            yield Static(id="footer")

    def on_mount(self) -> None:
        words = self.query_one("#words", Static)
        words.styles.height = self.visible_lines + 2  # + vertical padding
        self.query_one("#test", Vertical).display = not self._on_splash
        self.query_one("#splash", Static).display = self._on_splash
        self.set_interval(TICK_INTERVAL, self._on_tick)
        self._widgets_ready = True
        self._redraw()

    # ------------------------------------------------------------------ input

    def on_key(self, event: events.Key) -> None:
        if self._on_splash:
            event.stop()
            self._leave_splash()
            return

        if event.key == "backspace":
            event.stop()
            if self.engine.backspace():
                self._redraw()
            return

        char = event.character
        if char and (char == " " or char.isprintable()) and len(char) == 1:
            event.stop()
            self.engine.type_char(char)
            self._redraw()
            self._exit_if_finished()

    def on_resize(self, event: events.Resize) -> None:
        self._redraw()

    def action_quit_test(self) -> None:
        """Escape: leave, reporting a started test as abandoned."""
        if self.engine.started and not self.engine.finished:
            self.engine.abandon()
        self.exit(self.engine.result() if self.engine.started else None)

    def action_restart_test(self) -> None:
        self.exit(RESTART)

    # ----------------------------------------------------------------- render

    def _leave_splash(self) -> None:
        self._on_splash = False
        self.query_one("#splash", Static).display = False
        self.query_one("#test", Vertical).display = True
        self._redraw()

    def _on_tick(self) -> None:
        if self._on_splash:
            return
        self.engine.tick()
        self._redraw()
        self._exit_if_finished()

    def _exit_if_finished(self) -> None:
        if self.engine.finished:
            self.exit(self.engine.result())

    def _words_width(self) -> int:
        words = self.query_one("#words", Static)
        width = words.content_size.width or words.size.width or FALLBACK_WIDTH
        return max(width, MIN_WIDTH)

    def _redraw(self) -> None:
        if self._on_splash or not self._widgets_ready:
            return
        width = self._words_width()
        if width != self._wrapped_width or not self._lines:
            self._lines = wrap_indices(self.engine.target, width)
            self._wrapped_width = width

        cursor = self.engine.cursor
        cursor_line = line_for_cursor(self._lines, cursor)
        window = visible_slice(len(self._lines), cursor_line, self.visible_lines)

        self.query_one("#words", Static).update(
            render_target(
                self.engine.target,
                self.engine.char_states(),
                cursor,
                self._lines,
                window,
                self.palette,
                show_cursor=not self.engine.finished,
            )
        )
        self.query_one("#topbar", Static).update(render_topbar(self.engine, self.palette))
        self.query_one("#footer", Static).update(render_footer(self.engine, self.palette))


def run_test(
    engine: TypingEngine,
    *,
    theme: Theme | None = None,
    show_banner: bool = True,
    visible_lines: int = VISIBLE_LINES,
) -> TestResult | Restart | None:
    """Run the typing screen and return the outcome."""
    app = TypingScreen(
        engine,
        theme=theme,
        show_banner=show_banner,
        visible_lines=visible_lines,
    )
    outcome = app.run()
    if isinstance(outcome, (TestResult, Restart)):
        return outcome
    return None
