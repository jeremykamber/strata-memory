"""``skill`` command: install the Strata skill for AI coding assistants.

Supports the ``install`` subcommand (interactive by default, ``--global``
for non-interactive global install).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


name = "skill"


def _find_skill_dir() -> Path | None:
    """Locate the bundled strata skill directory for AI agents.

    Resolution order:
    1. Relative to this file (development install / editable mode)
    2. Via importlib.resources (installed package)
    """
    # Development / editable mode: relative to this script
    dev = Path(__file__).resolve().parent.parent.parent / "skills" / "strata"
    if dev.is_dir():
        return dev

    # Installed package: use importlib.resources
    try:
        import importlib.resources as rsrc

        ref = rsrc.files("strata") / "skills" / "strata"
        with rsrc.as_file(ref) as path:
            if path.is_dir():
                return path.resolve()
    except Exception:
        pass

    return None


def _cmd_skill_install(rest: list[str]) -> None:
    """Install the Strata skill for AI coding assistants.

    Supports ``--global`` flag for non-interactive global install.
    Delegates to ``npx skills add`` (requires Node.js).

    Args:
        rest: Remaining arguments after ``skill install``.
    """
    skill_dir = _find_skill_dir()
    if skill_dir is None:
        print(
            "Error: Strata skill not found. Reinstall strata-memory.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not shutil.which("npx"):
        print(
            "Error: 'npx' not found. Install Node.js from https://nodejs.org/",
            file=sys.stderr,
        )
        print("Then run: strata skill install", file=sys.stderr)
        sys.exit(1)

    global_mode = "--global" in rest

    cmd = ["npx", "-y", "skills@latest", "add", str(skill_dir)]
    if global_mode:
        cmd.extend(["--all", "-g", "-y"])
        print("Installing Strata skill globally for all AI agents...")
        print(f"  Skill:    {skill_dir}")
    else:
        print("Launching interactive skill installer...")
        print(f"  Skill:    {skill_dir}")
        print("  Follow the prompts to choose scope (global/project) and agents.")
        print()

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(
            f"Error: Skill installation failed (exit code {result.returncode})",
            file=sys.stderr,
        )
        sys.exit(1)

    print()
    print("\u2713 Strata skill installed! It's now available to your AI assistants.")
    print("  Agents should auto-detect it. Try: strata --agent-help")


def run(args: list[str]) -> None:
    """Handle the ``skill`` command and its subcommands.

    Args:
        args: Remaining arguments after ``skill``.
    """
    if not args:
        print("Usage: strata skill install")
        print("")
        print("  Installs the Strata agent skill for AI coding assistants")
        print("  (OpenCode, Claude Code, PI, Cursor, Codex, etc.).")
        print("")
        print("  By default it runs the Vercel Labs skills CLI interactively \u2014")
        print("  you'll be prompted to choose scope (global/project) and agents.")
        print("")
        print("Flags:")
        print("  --global   Skip interactive prompts, install globally to all agents")
        print("")
        print("Requires Node.js (npx). Uses 'npx skills add' from vercel-labs/skills.")
        return

    subcommand = args[0]
    if subcommand == "install":
        _cmd_skill_install(args[1:])
    else:
        print(f"Unknown skill subcommand: {subcommand}")
        print("Usage: strata skill install")
        sys.exit(1)
