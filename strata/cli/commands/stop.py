"""Stop command: stop a running daemon."""

from __future__ import annotations

from strata.cli._config import load_config
from strata.daemon import stop_daemon

name = "stop"


def run(args: list[str]) -> None:
    config = load_config()
    result = stop_daemon(config)
    print(result["message"])
