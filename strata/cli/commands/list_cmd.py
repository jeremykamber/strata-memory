"""Handle the ``list`` and ``list-stratum-2`` commands.

``list`` shows 1st Stratum files and directories.
``list-stratum-2`` shows cooled (2nd Stratum) files.
"""

from __future__ import annotations


from strata import Strata
from strata.cli._config import load_config

name = "list"


def run(args: list[str]) -> None:
    """Show 1st Stratum files and directories.

    Args:
        args: Remaining arguments (optional ``<path>`` to list).
    """
    path = args[0] if args else ""
    config = load_config()
    with Strata(config) as s:
        entries = s.list_active(path)
        if not entries:
            print(f"Empty or not found: {path or '/'}")
            return
        for e in entries:
            t = "dir" if e["type"] == "directory" else "file"
            print(f"  [{t}] {e['path']} ({e['size']}b)")


def list_stratum_2() -> None:
    """Show 2nd Stratum (cooled) files.

    This function is exposed for registration under the name
    ``list-stratum-2``. It is a separate entry point from the primary
    ``list`` command.
    """
    config = load_config()
    with Strata(config) as s:
        files = s.s2.list_all()
        if not files:
            print("No 2nd Stratum files.")
            return
        for f in files:
            print(f"  {f['path']} ({f['size']}b, modified {f['modified'][:10]})")
