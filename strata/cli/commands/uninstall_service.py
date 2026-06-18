"""Uninstall-service command: remove systemd user service."""

from __future__ import annotations

import sys
from pathlib import Path


name = "uninstall-service"


def run(args: list[str]) -> None:
    target = Path.home() / ".config" / "systemd" / "user" / "strata.service"
    if not target.exists():
        print(f"No systemd service installed at {target}")
        return
    try:
        target.unlink()
    except OSError as e:
        print(f"Error: failed to remove service: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"\u2713 Removed {target}")
    print("  Run: systemctl --user daemon-reload")
