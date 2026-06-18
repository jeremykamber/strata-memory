"""Handle the ``forget`` command: archive a cooled file to 3rd Stratum."""

from __future__ import annotations

import sys

from strata import Strata
from strata.cli._config import load_config

name = "forget"


def run(args: list[str]) -> None:
    """Archive a file from 2nd Stratum to 3rd Stratum."""
    if not args:
        print("Usage: strata forget <path>")
        return
    path = args[0]
    config = load_config()
    with Strata(config) as s:
        source = s.s2._root / path
        if not source.exists():
            print(f"File not found in 2nd Stratum: {path}")
            sys.exit(1)
        tags = [path.split("/")[0]] if "/" in path else []
        archive_path = s.s3.archive_file(source, path, tags=tags)
        source.unlink()
        print(f"Archived to: {archive_path}")
