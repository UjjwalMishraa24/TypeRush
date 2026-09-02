# typerush

A fast, distraction-free typing speed test that lives in your terminal.

Like monkeytype, but you never leave the keyboard. Gradient ASCII splash, live
WPM while you type, and a results card that stays in your scrollback.

```
 ████████╗██╗   ██╗██████╗ ███████╗██████╗ ██╗   ██╗███████╗██╗  ██╗
 ╚══██╔══╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗██║   ██║██╔════╝██║  ██║
    ██║    ╚████╔╝ ██████╔╝█████╗  ██████╔╝██║   ██║███████╗███████║
    ██║     ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗██║   ██║╚════██║██╔══██║
    ██║      ██║   ██║     ███████╗██║  ██║╚██████╔╝███████║██║  ██║
    ╚═╝      ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
 terminal typing speed test  ·  v0.1.0
```

---

## Features

- **Three modes** — timed (`--time 30`), fixed word count (`--words 50`), or a random quote (`--quote`)
- **Live stats** — WPM, raw WPM, accuracy and error count update as you type
- **Character-accurate highlighting** — correct, incorrect and untyped text are all styled differently, with a visible caret
- **Scrolling text window** — three lines at a time, following your cursor, so long tests never overflow the screen
- **Results card** — big gradient WPM number plus the full breakdown
- **History** — every completed run is appended to `~/.typerush/history.json`; view it with `--stats`
- **Config** — theme colours and defaults in `~/.typerush/config.json`
- **Custom text** — point `--wordlist` / `--quotes` at your own files
- **Fully offline** — no network calls, ever

## Install

Requires Python 3.11 or newer.

### As a global command (recommended)

```bash
pipx install .
typerush
```

### From source with uv

```bash
uv sync
uv run typerush
```

### From source with pip

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
typerush
```

`python -m typerush` works too, if you'd rather not rely on the console script.

## Usage

```bash
typerush                    # 30-second test (the default)
typerush --time 60          # 60-second test
typerush -t 15              # 15-second sprint
typerush --words 50         # type exactly 50 words
typerush --quote            # type a random quote
typerush --stats            # show past results and exit
typerush --stats --limit 25 # ...more of them
```

### Keys during a test

| Key | Action |
| --- | --- |
| any printable key | type |
| `backspace` | delete one character |
| `tab` or `ctrl+r` | restart with fresh text |
| `esc` | quit (a started test is reported as abandoned and not saved) |

The clock does not start until your first keystroke, so you can take as long as
you like getting comfortable.

### All options

| Flag | Description |
| --- | --- |
| `-t`, `--time SECONDS` | Timed mode |
| `-w`, `--words COUNT` | Word-count mode |
| `-q`, `--quote` | Quote mode |
| `--wordlist PATH` | Use your own word list (one word per line, `#` for comments) |
| `--quotes PATH` | Use your own quotes JSON |
| `--seed N` | Seed the generator for a reproducible test |
| `--stats` | Print the history table and exit |
| `--limit N` | Rows shown by `--stats` (default 10) |
| `--no-banner` | Skip the splash screen and start typing immediately |
| `--no-save` | Don't write this run to history |
| `--init-config` | Write a default `~/.typerush/config.json` and exit |
| `--version` | Print the version |
| `-h`, `--help` | Show help |

## How the score is calculated

Two different notions of "how much you typed" are tracked on purpose:

- **Net WPM** = `(correct characters currently on screen / 5) / minutes`.
  Fixing a typo with backspace really does improve this number.
- **Raw WPM** = `(all characters on screen / 5) / minutes` — errors included.
- **Accuracy** = `correct keystrokes / total keystrokes`, counted at the moment
  each key was pressed. A typo costs you accuracy even after you correct it,
  because accuracy is a measure of your fingers, not of your editing.
- **Errors** = keystrokes that were wrong when pressed.

`5` is the conventional characters-per-word used by every typing test, so scores
are comparable with monkeytype and friends.

Characters are compared to the target **strictly by index**: `typed[i]` is
correct only if it equals `target[i]`. Keystrokes past the end of the text are
ignored rather than appended, which keeps the on-screen line wrapping stable for
the whole run. If you insert an extra character mid-word, everything after it
shifts and reads as wrong until you backspace — the same model most terminal
typing tests use.

In timed mode the elapsed time is pinned to exactly the limit, so a 30-second
test always reports `30.0s` rather than `30.1s`.

## Configuration

Write a starter file with:

```bash
typerush --init-config     # creates ~/.typerush/config.json
```

```json
{
  "default_mode": "time",
  "default_time": 30,
  "default_words": 25,
  "show_banner": true,
  "save_history": true,
  "wordlist_path": null,
  "quotes_path": null,
  "theme": {
    "correct": "#e5e7eb",
    "incorrect": "#f87171",
    "pending": "#4b5563",
    "cursor": "#22d3ee",
    "accent": "#22d3ee",
    "mid": "#3b82f6",
    "secondary": "#a855f7",
    "good": "#4ade80",
    "muted": "#6b7280"
  }
}
```

The three banner stops are `accent → mid → secondary`. Unknown keys are ignored,
and a malformed file produces a warning rather than a crash. Set `TYPERUSH_HOME`
to move the whole directory somewhere else.

## Custom text

**Word list** — one word per line; blank lines and `#` comments are skipped,
duplicates are dropped so no word gets extra weight.

```
the
quick
brown
```

```bash
typerush --wordlist ~/words/klingon.txt --words 30
```

**Quotes** — either `{"quotes": [...]}` or a bare list. Each item may be a plain
string or an object:

```json
{
  "quotes": [
    { "text": "Talk is cheap. Show me the code.", "author": "Linus Torvalds" },
    "a bare string works too"
  ]
}
```

```bash
typerush --quotes ~/quotes/dune.json --quote
```

Both can be set permanently via `wordlist_path` / `quotes_path` in the config.

## Project layout

```
src/typerush/
  cli.py                  entrypoint, flag parsing, run loop
  banner.py               gradient ASCII art (pyfiglet + rich)
  game/                   no terminal imports — unit-testable
    engine.py             typing-test state machine
    stats.py              WPM / accuracy math
    wordlist.py           word + quote sources
  ui/                     terminal rendering only
    typing_screen.py      Textual app: splash + live typing view
    textview.py           word wrapping and character styling (pure)
    results_screen.py     results card and --stats table
  storage/
    config.py             ~/.typerush/config.json
    history.py            ~/.typerush/history.json
  data/
    words_common.txt      bundled word list
    quotes.json           bundled quotes
tests/
```

The split is deliberate: `game/` never imports `rich` or `textual`, so the rules
of the test can be verified without a terminal. `ui/textview.py` holds the
wrapping maths separately from the Textual app for the same reason.

## Development

```bash
uv sync                  # install deps
pytest                   # run the tests
ruff format .            # format
ruff check .             # lint
mypy                     # type-check (strict)
```

The engine takes its clock as a parameter (`time_fn`), so timing behaviour is
tested against a fake clock instead of `sleep`. The Textual app is exercised
headlessly through Textual's own `run_test()` pilot.

## License

MIT
