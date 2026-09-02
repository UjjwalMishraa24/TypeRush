"""typerush — a terminal typing speed test.

The package is split so that game logic never imports terminal code:

* :mod:`typerush.game`    — pure state machine + WPM/accuracy math (unit-testable)
* :mod:`typerush.storage` — config and history files under ``~/.typerush``
* :mod:`typerush.ui`      — Textual/Rich rendering only
* :mod:`typerush.banner`  — gradient ASCII art title
* :mod:`typerush.cli`     — argument parsing and wiring
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
