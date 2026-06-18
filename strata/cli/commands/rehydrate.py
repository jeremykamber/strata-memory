"""Handle the ``rehydrate`` command: restore an archived file to active or cooled."""

from __future__ import annotations

import sys

from strata import Strata
from strata.cli._config import load_config

name = "rehydrate"


def run(args: list[str]) -> None:
    """Restore an archived file to active or cooled stratum.

    Usage:
        strata rehydrate <shadow_id> [--target=active|cooled]

    The shadow ID comes from search results (``archive:id`` field).
    By default restores to active/; use ``--target=cooled`` to restore
    to the cooled stratum instead.
    """
    if not args:
        print("Usage: strata rehydrate <shadow_id> [--target=active|cooled]")
        return

    target_tier = "active"
    shadow_id = None
    for arg in args:
        if arg.startswith("--target="):
            target_tier = arg.split("=", 1)[1]
            if target_tier not in ("active", "cooled"):
                print(
                    f"Invalid target: {target_tier} (use --target=active or --target=cooled)",
                    file=sys.stderr,
                )
                sys.exit(1)
        elif not arg.startswith("--"):
            shadow_id = arg

    if not shadow_id:
        print(
            "Usage: strata rehydrate <shadow_id> [--target=active|cooled]",
            file=sys.stderr,
        )
        sys.exit(1)

    config = load_config()
    with Strata(config) as s:
        # Find shadow entry by id
        try:
            conn = s.s3._connect_shadow()
            row = conn.execute(
                "SELECT * FROM shadow_index WHERE id = ? OR original_path = ?",
                (shadow_id, shadow_id),
            ).fetchone()
        except Exception:
            row = None

        if not row:
            print(f"Shadow entry not found: {shadow_id}", file=sys.stderr)
            sys.exit(1)

        entry = dict(row)
        result = s.rehydrate(entry, target_tier=target_tier)
        if result is None:
            print(f"Could not read archive file for: {shadow_id}", file=sys.stderr)
            sys.exit(1)

        tier_name = {
            "active": "1st Stratum (active)",
            "cooled": "2nd Stratum (cooled)",
        }.get(target_tier, target_tier)
        print(f"Restored to {tier_name}: {result.get('original_path', '?')}")
