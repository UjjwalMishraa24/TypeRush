from __future__ import annotations

import io

from rich.console import Console

from typerush.game.engine import WpmSample
from typerush.theme import Theme
from typerush.ui.graph import (
    nice_ceiling,
    render_wpm_chart,
    sample_net_wpm,
    sample_raw_wpm,
    tick_step,
)

#: Four snapshots, 5s apart: a steady 60 net wpm with raw consistently above it.
SAMPLES = [
    WpmSample(elapsed=5.0, correct_chars=25, typed_chars=50),
    WpmSample(elapsed=10.0, correct_chars=50, typed_chars=110),
    WpmSample(elapsed=15.0, correct_chars=75, typed_chars=165),
    WpmSample(elapsed=20.0, correct_chars=100, typed_chars=220),
]


def per_second(chars: list[int]) -> list[WpmSample]:
    """Samples at 1s..N s; correct and typed counts identical (a perfect run)."""
    return [
        WpmSample(elapsed=float(second), correct_chars=count, typed_chars=count)
        for second, count in enumerate(chars, start=1)
    ]


def plain(chart) -> str:
    return str(chart.plain) if chart is not None else ""


def plot_area(chart) -> str:
    """Plain text minus the legend line, so marker counts see only the curves."""
    return "\n".join(plain(chart).splitlines()[:-1])


def test_sample_wpm_uses_the_five_char_word_convention():
    # 25 correct characters in 5 seconds = 25/5 words in 1/12 minute = 60 wpm.
    sample = WpmSample(elapsed=5.0, correct_chars=25, typed_chars=30)
    assert sample_net_wpm(sample) == 60.0
    assert sample_raw_wpm(sample) == 72.0


def test_nice_ceiling_rounds_up_to_tidy_numbers():
    assert nice_ceiling(0) == 10
    assert nice_ceiling(9) == 10
    assert nice_ceiling(11) == 20
    assert nice_ceiling(51) == 100
    assert nice_ceiling(120) == 200


def test_tick_step_keeps_the_axis_readable():
    assert tick_step(3) == 1
    assert tick_step(12) == 2
    assert tick_step(30) == 5
    assert tick_step(120) == 30


def test_too_few_samples_renders_nothing():
    assert render_wpm_chart([]) is None
    assert render_wpm_chart(per_second([5])) is None


def test_chart_draws_axes_labels_and_both_curves():
    chart = render_wpm_chart(SAMPLES)
    assert chart is not None
    text = plain(chart)
    # Y axis: raw peaks at 132, so the ceiling is 200 with a mid-tick at 100.
    assert "200 ┤" in text
    assert " 0 ┤" in text
    # X axis: 20-second test, ticks every 5s.
    for tick in ("0s", "5s", "10s", "15s", "20s"):
        assert tick in text
    assert "┼" in text
    # Legend reports the final net and raw values.
    assert "net 60 wpm" in text
    assert "raw 132 wpm" in text
    # Both curves are drawn in the plot area (not just in the legend).
    assert "█" in plot_area(chart)
    assert "▒" in plot_area(chart)


def test_one_marker_per_sample_per_curve():
    chart = render_wpm_chart(SAMPLES)
    assert chart is not None
    plot = plot_area(chart)
    assert plot.count("█") == 4
    assert plot.count("▒") == 4


def test_coincident_net_and_raw_show_only_the_net_marker():
    chart = render_wpm_chart(per_second([10, 20, 30]))
    assert chart is not None
    plot = plot_area(chart)
    # Net draws last, so where the curves overlap the net marker wins.
    assert plot.count("█") == 3
    assert "▒" not in plot


def test_backspaced_corrections_show_up_as_a_dip():
    # Correct chars drop between seconds 2 and 3 (a typo being fixed).
    net = [sample_net_wpm(sample) for sample in per_second([20, 40, 25, 30])]
    assert net[2] < net[1]  # the dip is real in the data…
    # …and the chart kept every sample's mark.
    chart = render_wpm_chart(per_second([20, 40, 25, 30]))
    assert chart is not None
    assert plot_area(chart).count("█") == 4


def test_chart_is_themeable():
    chart = render_wpm_chart(SAMPLES, Theme(accent="#ff0000", muted="#00ff00"))
    assert chart is not None
    buffer = io.StringIO()
    console = Console(file=buffer, width=80, force_terminal=True, color_system="truecolor")
    console.print(chart)
    rendered = buffer.getvalue()
    # The net curve is drawn in the accent colour, raw in muted.
    assert "\x1b[38;2;255;0;0m" in rendered
    assert "\x1b[38;2;0;255;0m" in rendered
