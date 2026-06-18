"""Handle the ``read`` command: print a file's contents.

Reads from any stratum (active -> cooled -> archive). When reading
from the 2nd Stratum, access is tracked and the file may be
automatically promoted back to active. When reading from the 3rd
Stratum, the file is automatically rehydrated to active.
"""

from __future__ import annotations

import sys

from strata import Strata
from strata.cli._config import load_config

name = "read"


def run(args: list[str]) -> None:
    """Print the contents of a memory file.

    Args:
        args: Remaining arguments (expects ``<path>``).
    """
    if not args:
        print("Usage: strata read <path>")
        return
    config = load_config()
    with Strata(config) as s:
        try:
            result = s.read(args[0])
            source = result.get("source", "active")
            if result.get("promoted"):
                count = result.get("access_count", 0)
                print(f"\u2b06 Promoted from cooled (accessed {count} times)\n")
            elif result.get("rehydrated"):
                print("\u2b06 Restored from archive to 1st Stratum (active)\n")
            elif source == "cooled":
                count = result.get("access_count", 0)
                print(
                    f"\u2192 Read from cooled (access {count}/{s.config.promotion_threshold})\n"
                )
            print(result["content"])
        except FileNotFoundError:
            print(f"File not found: {args[0]}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
