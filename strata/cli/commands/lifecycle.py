"""Lifecycle commands for the Strata CLI.

Handles migration (active -> cooled), promotion (cooled -> active),
eviction (cooled -> archive), and full maintenance cycles.

The dispatch layer (main / registry) MUST prepend the operation name
as the first element of ``args`` so that ``run`` can determine which
lifecycle operation to perform.  See aliases in the registry for
``migrate``, ``promote``, ``evict``, and ``maintenance``.

Example dispatch::
    lifecycle.run(["migrate", "--dry-run"])
    lifecycle.run(["promote"])
    lifecycle.run(["evict"])
    lifecycle.run(["maintenance"])
"""

from __future__ import annotations

import json
import sys

from strata import Strata
from strata.cli._json import json_print, json_error, is_json_mode
from strata.cli._config import load_config
from strata.cli._spinner import spinner

name = "lifecycle"
aliases: list[str] = []


def run(args: list[str]) -> None:
    """Handle lifecycle commands: ``migrate``, ``promote``, ``evict``, ``maintenance``.

    Expects ``args[0]`` to be the operation name (set by the dispatch
    layer).  The remaining args after the operation are treated as flags
    (e.g. ``--dry-run``).

    Args:
        args: A list where ``args[0]`` is the operation (``"migrate"``,
            ``"promote"``, ``"evict"``, or ``"maintenance"``), and
            ``args[1:]`` are option flags.
    """
    if not args:
        if is_json_mode():
            json_error("lifecycle", "No operation specified")
        print(
            "Usage: strata migrate|promote|evict|maintenance [--dry-run]",
            file=sys.stderr,
        )
        return

    command = args[0]
    rest = args[1:]
    dry_run = "--dry-run" in rest

    config = load_config()
    with Strata(config) as s:
        s.s1.ensure_dirs()
        s.s3.ensure_dirs()

        if command == "migrate":
            with spinner("Migrating"):
                results = s.migrate(dry_run=dry_run)
            if is_json_mode():
                json_print(
                    "migrate",
                    {"files": results, "count": len(results), "dry_run": dry_run},
                )
                return
            print(json.dumps(results, indent=2))
            print(f"\nMigrated: {len(results)} files")

        elif command == "promote":
            with spinner("Promoting"):
                results = s.promote(dry_run=dry_run)
            if is_json_mode():
                json_print(
                    "promote",
                    {"files": results, "count": len(results), "dry_run": dry_run},
                )
                return
            print(json.dumps(results, indent=2))
            print(f"\nPromoted: {len(results)} files")

        elif command == "evict":
            with spinner("Evicting"):
                results = s.evict(dry_run=dry_run)
            if is_json_mode():
                json_print(
                    "evict",
                    {
                        "memories": results,
                        "count": len(results),
                        "dry_run": dry_run,
                    },
                )
                return
            print(json.dumps(results, indent=2))
            print(f"\nEvicted: {len(results)} memories")

        elif command == "maintenance":
            with spinner("Running maintenance"):
                result = s.run_maintenance(dry_run=dry_run)
            if is_json_mode():
                json_print("maintenance", result)
                return
            print(json.dumps(result, indent=2))
            print(
                f"\nPromoted: {result.get('total_promoted') or len(result.get('promoted', []))}"
            )
            print(
                f"Migrated: {result.get('total_migrated') or len(result.get('migrated', []))}"
            )
            print(
                f"Evicted:  {result.get('total_evicted') or len(result.get('evicted', []))}"
            )

        else:
            if is_json_mode():
                json_error("lifecycle", f"Unknown lifecycle operation: {command}")
            print(
                f"Unknown lifecycle operation: {command}",
                file=sys.stderr,
            )
