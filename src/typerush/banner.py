"""ASCII-art title rendering.

pyfiglet produces the block letters; each character is then coloured by its
horizontal position so the whole word sweeps through the theme's gradient stops
(cyan to blue to magenta by default). Everything degrades gracefully: a missing
font falls back to a built-in one, and a missing pyfiglet falls back to plain
styled text, so the CLI never crashes over decoration.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Group, RenderableType
from rich.text import Text

from . import __version__
from .storage.config import Theme

DEFAULT_TITLE = "typerush"
TAGLINE = "terminal typing speed test"
#: Tried in order; the first font pyfiglet actually has wins.
FONT_CHAIN = ("ansi_shadow", "big", "standard", "slant")

RGB = tuple[int, int, int]


def _hex_to_rgb(color: str) -> RGB:
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6:
        return (255, 255, 255)
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return (255, 255, 255)


def _rgb_to_hex(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def sample_gradient(stops: Sequence[str], position: float) -> str:
    """Colour at ``position`` (0.0-1.0) along a multi-stop gradient."""
    if not stops:
        return "#ffffff"
    if len(stops) == 1:
        return stops[0]
    clamped = min(max(position, 0.0), 1.0)
    segments = len(stops) - 1
    scaled = clamped * segments
    index = min(int(scaled), segments - 1)
    local = scaled - index
    start, end = _hex_to_rgb(stops[index]), _hex_to_rgb(stops[index + 1])
    blended = tuple(round(a + (b - a) * local) for a, b in zip(start, end, strict=True))
    return _rgb_to_hex(blended)  # type: ignore[arg-type]


def figlet_lines(text: str, font_chain: Sequence[str] = FONT_CHAIN) -> list[str]:
    """Render ``text`` as ASCII art, or return it plainly if pyfiglet is absent."""
    try:
        import pyfiglet
    except ImportError:  # pragma: no cover - pyfiglet is a declared dependency
        return [text]

    for font in font_chain:
        try:
            rendered = pyfiglet.Figlet(font=font).renderText(text)
        except Exception:  # any font problem just means "try the next one"
            continue
        lines = [line.rstrip() for line in rendered.rstrip("\n").splitlines()]
        if any(line.strip() for line in lines):
            return lines
    return [text]  # pragma: no cover - only if every font failed


def gradient_block(lines: Sequence[str], stops: Sequence[str]) -> Text:
    """Colour a block of text left-to-right across ``stops``."""
    width = max((len(line) for line in lines), default=1)
    divisor = max(width - 1, 1)
    block = Text()
    for row, line in enumerate(lines):
        for column, char in enumerate(line):
            if char == " ":
                block.append(" ")
            else:
                block.append(char, style=sample_gradient(stops, column / divisor))
        if row < len(lines) - 1:
            block.append("\n")
    return block


def render_banner(
    theme: Theme | None = None,
    *,
    title: str = DEFAULT_TITLE,
    tagline: str = TAGLINE,
    hint: str | None = None,
    version: str = __version__,
) -> RenderableType:
    """The full splash: gradient ASCII title, tagline with version, optional hint."""
    palette = theme or Theme()
    art = gradient_block(figlet_lines(title), palette.gradient)

    subtitle = Text()
    subtitle.append(tagline, style=palette.muted)
    subtitle.append("  ·  ", style=palette.pending)
    subtitle.append(f"v{version}", style=palette.secondary)

    parts: list[RenderableType] = [art, subtitle]
    if hint:
        parts.append(Text(hint, style=palette.muted))
    return Group(*parts)


def render_big_number(value: int | str, theme: Theme | None = None) -> Text:
    """A large gradient number, used for the WPM on the results card."""
    palette = theme or Theme()
    return gradient_block(figlet_lines(str(value)), palette.gradient)
