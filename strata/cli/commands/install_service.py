"""Install-service command: install systemd user service."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


name = "install-service"


def run(args: list[str]) -> None:
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    target = systemd_dir / "strata.service"

    # Locate the bundled service file
    dev = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "contrib"
        / "strata.service"
    )
    if dev.is_file():
        src = dev
    else:
        try:
            import importlib.resources as rsrc

            ref = rsrc.files("strata") / "contrib" / "strata.service"
            with rsrc.as_file(ref) as p:
                src = p.resolve()
        except Exception:
            print(
                "Error: could not locate strata.service bundle. "
                "Check your installation.",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        shutil.copy2(src, target)
    except OSError as e:
        print(f"Error: failed to install service: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\u2713 Installed systemd service to {target}")
    print()
    print("  Enable and start:")
    print("    systemctl --user daemon-reload")
    print("    systemctl --user enable --now strata")
    print()
    print("  Check status:")
    print("    systemctl --user status strata")
    print("    journalctl --user -u strata -f")
