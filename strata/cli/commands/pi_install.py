"""``pi-install`` command: install the Strata Pi extension.

Installs the Strata Pi extension file to ``~/.pi/agent/extensions/strata.ts``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


name = "pi-install"


def _find_pi_skill_dir() -> Path | None:
    """Locate the bundled Strata Pi extension file.

    Resolution order:
    1. Relative to this file (development install / editable mode)
    2. Via importlib.resources (installed package)
    """
    # Development / editable mode: relative to project root
    dev = Path(__file__).resolve().parent.parent.parent / "skills" / "pi" / "strata.ts"
    if dev.is_file():
        return dev

    # Installed package: use importlib.resources
    try:
        import importlib.resources as rsrc

        ref = rsrc.files("strata") / "skills" / "pi" / "strata.ts"
        with rsrc.as_file(ref) as path:
            if path.is_file():
                return path.resolve()
    except Exception:
        pass

    return None


def run(args: list[str]) -> None:
    """Install the Strata Pi extension to ~/.pi/agent/extensions/strata.ts."""
    if not shutil.which("pi"):
        print("Error: 'pi' not found. Install Pi from https://pi.ai", file=sys.stderr)
        sys.exit(1)

    pi_ext_dir = Path.home() / ".pi" / "agent" / "extensions"
    pi_config = Path.home() / ".pi"

    if not pi_config.is_dir():
        print(
            "Warning: Pi config not found at ~/.pi/. Have you run Pi yet?",
            file=sys.stderr,
        )

    src = _find_pi_skill_dir()
    if src is None:
        print(
            "Error: Strata Pi extension not found. Reinstall strata-memory.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        pi_ext_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create {pi_ext_dir}: {e}", file=sys.stderr)
        sys.exit(1)

    dst = pi_ext_dir / "strata.ts"

    if dst.exists():
        force = "--force" in args
        if not force:
            try:
                choice = input("Overwrite existing strata.ts? [y/N]: ").strip()
            except EOFError:
                choice = "n"
            if choice.lower() != "y":
                print("Aborted.")
                return

    shutil.copy2(src, dst)
    print(f"\u2713 Strata Pi extension installed to {dst}")
    print("  Run /reload in Pi to activate.")
