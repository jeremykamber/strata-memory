"""JSON output helpers for the Strata CLI.

Manages the global JSON mode flag and provides structured JSON output
functions used by all CLI commands.
"""

from __future__ import annotations

import json
import sys
import time

_JSON_MODE = False
_START_TIME = 0.0


def set_mode(enable: bool = True) -> None:
    """Enable or disable JSON output mode."""
    global _JSON_MODE
    _JSON_MODE = enable


def is_json_mode() -> bool:
    """Return True if JSON output mode is active."""
    return _JSON_MODE


def set_start_time(t: float | None = None) -> None:
    """Record the monotonic start time for duration calculation."""
    global _START_TIME
    _START_TIME = t if t is not None else time.monotonic()


def json_print(command: str, data: dict) -> None:
    """Print a success JSON response with duration_ms."""
    elapsed = (time.monotonic() - _START_TIME) * 1000
    result = {
        "status": "success",
        "command": command,
        "data": data,
        "duration_ms": round(elapsed, 1),
    }
    print(json.dumps(result))


def json_error(command: str, message: str) -> None:
    """Print an error JSON response and exit."""
    elapsed = (time.monotonic() - _START_TIME) * 1000
    result = {
        "status": "error",
        "command": command,
        "message": message,
        "duration_ms": round(elapsed, 1),
    }
    print(json.dumps(result))
    sys.exit(1)
