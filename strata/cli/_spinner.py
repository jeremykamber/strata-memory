"""\r-based rotating spinner for the Strata CLI.

No-op when output is piped or JSON mode is active. Used by command
modules to show progress during long-running operations.
"""

from __future__ import annotations

import contextlib
import sys
import threading
import time

from strata.cli._json import is_json_mode


@contextlib.contextmanager
def spinner(msg: str = "Processing"):
    """\r-based rotating spinner. No-op when piped or in JSON mode."""
    if not sys.stdout.isatty() or is_json_mode():
        yield
        return
    stop_event = threading.Event()
    start = time.monotonic()
    chars = r"-\|/"

    def _spin():
        idx = 0
        while not stop_event.is_set():
            sys.stdout.write(f"\r{msg} {chars[idx]}")
            sys.stdout.flush()
            idx = (idx + 1) % len(chars)
            stop_event.wait(0.1)

    t = threading.Thread(target=_spin, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop_event.set()
        t.join(0.2)
        elapsed = time.monotonic() - start
        sys.stdout.write(f"\r{msg} ({elapsed:.0f}s)\n")
        sys.stdout.flush()
