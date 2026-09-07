"""ASCII chart of speed over time for the results card.

Pure Rich rendering: the engine's per-second :class:`~typerush.game.engine.WpmSample`
snapshots go in, a themed chart comes out. There is no terminal state here, so
every function is unit-testable without a Textual app.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text

from ..game.engine import WpmSample
from ..game.stats import calculate_raw_wpm, calculate_wpm
from ..theme import Theme

#: Rows of plot area and columns of curve, before axis labels.
PLOT_HEIGHT = 7
PLOT_WIDTH = 44
#: Curve markers: net speed is solid and on top, raw speed is speckled below.
NET_CHAR = "█"
RAW_CHAR = "▒"
#: X-axis tick candidates; the first that keeps the axis readable wins.
TICK_STEPS = (1, 2, 5, 10, 15, 30, 60, 120)


def sample_net_wpm(sample: WpmSample) -> float:
    """Net WPM at the moment the sample was taken."""
    return calculate_wpm(sample.correct_chars, sample.elapsed)


def sample_raw_wpm(sample: WpmSample) -> float:
    """Raw WPM (errors included) at the moment the sample was taken."""
    return calculate_raw_wpm(sample.typed_chars, sample.elapsed)


def nice_ceiling(value: float) -> int:
    """Smallest tidy number (10, 20, 50, 100, …) at or above ``value``."""
    value = max(value, 10.0)
    # Annotated because mypy types ``int ** int`` as Any (negative exponents
    # return a float), which would leak Any through the returns below.
    magnitude: int = 10 ** (len(str(int(value))) - 1)
    for factor in (1, 2, 5, 10):
        ceiling = factor * magnitude
        if value <= ceiling:
            return ceiling
    return 10 * magnitude  # pragma: no cover - the loop always returns first


def tick_step(duration: float) -> int:
    """X-axis tick interval that keeps the axis to a handful of labels."""
    for step in TICK_STEPS:
        if duration / step <= 6:
            return step
    return TICK_STEPS[-1]  # pragma: no cover - very long tests only


def render_wpm_chart(
    samples: Sequence[WpmSample],
    theme: Theme | None = None,
    *,
    width: int = PLOT_WIDTH,
    height: int = PLOT_HEIGHT,
) -> Text | None:
    """Two-line chart (net + raw WPM over seconds), or ``None`` when too little data.

    ``None`` (rather than a placeholder) lets the results card simply skip the
    chart for tests that ended before the first full second.
    """
    palette = theme or Theme()
    if len(samples) < 2:
        return None

    net = [sample_net_wpm(sample) for sample in samples]
    raw = [sample_raw_wpm(sample) for sample in samples]
    y_max = float(nice_ceiling(max(*net, *raw)))
    duration = samples[-1].elapsed
    span = duration if duration > 0 else 1.0

    def column(time: float) -> int:
        return round(time / span * (width - 1))

    def row(value: float) -> int:
        ratio = min(max(value / y_max, 0.0), 1.0)
        return round((1.0 - ratio) * (height - 1))

    # Raw goes down first so the net curve wins any cell they share.
    marks: dict[tuple[int, int], tuple[str, str]] = {}
    for series, char, colour in ((raw, RAW_CHAR, palette.muted), (net, NET_CHAR, palette.accent)):
        for sample, value in zip(samples, series, strict=True):
            marks[(row(value), column(sample.elapsed))] = (char, colour)

    chart = Text()
    for y in range(height):
        if y == 0:
            label = f"{y_max:.0f}"
        elif y == height // 2:
            label = f"{y_max / 2:.0f}"
        elif y == height - 1:
            label = "0"
        else:
            label = ""
        chart.append(f"{label:>3} ", style=palette.muted)
        chart.append("┤" if label else "│", style=palette.pending)
        for x in range(width):
            char, colour = marks.get((y, x), (" ", palette.pending))
            chart.append(char, style=colour)
        chart.append("\n")

    chart.append("    ", style=palette.muted)
    chart.append("┼", style=palette.pending)
    chart.append("─" * width, style=palette.pending)
    chart.append("\n")

    axis_labels = [" "] * (width + 4)
    for tick in range(0, int(duration) + 1, tick_step(duration)):
        label = f"{tick}s"
        position = column(tick)
        for offset, char in enumerate(label):
            if position + offset < len(axis_labels):
                axis_labels[position + offset] = char
    chart.append("     ", style=palette.muted)
    chart.append("".join(axis_labels), style=palette.muted)
    chart.append("\n")

    chart.append(f"{NET_CHAR} net ", style=palette.accent)
    chart.append(f"{net[-1]:.0f} wpm", style=f"bold {palette.accent}")
    chart.append(f"    {RAW_CHAR} raw ", style=palette.muted)
    chart.append(f"{raw[-1]:.0f} wpm", style=f"bold {palette.muted}")
    return chart
