"""Pytest bootstrap: make `src.*` importable regardless of invocation cwd."""

import pathlib
import sys

# bot/ directory (parent of tests/) — imports are rooted at `src.`
BOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))
