"""Show distillation state and manually run LLM distillation."""

from __future__ import annotations

import sys

from strata.cli._json import json_print, is_json_mode
from strata.cli._config import load_config
from strata.distiller import Distiller

name = "distiller"


def run(args: list[str]) -> None:
    """Handle the ``distiller`` command: show distillation state or trigger a run.

    Subcommands:
        ``strata distiller status``    Show pending count and config state.
        ``strata distiller run``       Manually run LLM distillation.
    """
    config = load_config()

    d = Distiller(config)
    cfg = d._load_config()

    # Subcommand dispatch
    sub = args[0] if args else ""

    if sub == "status":
        if is_json_mode():
            json_print(
                "distiller",
                {
                    "available": d.check_available(),
                    "llm_configured": cfg is not None,
                    "enabled": cfg["enabled"] if cfg else False,
                    "provider": cfg["provider"] if cfg else None,
                    "model": cfg["model"] if cfg else None,
                    "pending": d.get_pending_count(),
                },
            )
            return

        print("Distiller Status")
        print("=" * 40)
        if cfg is None:
            print("  LLM:         NOT CONFIGURED")
            print("  Configure:   strata config set llm.apiKey <key>")
        elif not d.check_available():
            print("  LLM:         CONFIGURED (unavailable \u2014 check API key)")
            print(f"  Provider:    {cfg.get('provider', '?')}")
        else:
            print(f"  LLM:         {'ENABLED' if cfg.get('enabled') else 'DISABLED'}")
            print(f"  Provider:    {cfg.get('provider', '?')}")
            print(f"  Model:       {cfg.get('model', '?')}")
        print(f"  Pending:     {d.get_pending_count()} conversation(s)")
        print()
        print("  Tip: run 'strata distiller run' to manually trigger")
        return

    if sub == "run":
        dry = "--dry-run" in args or "-n" in args
        if dry:
            result = d.process(dry_run=True)
        else:
            result = d.process()

        if is_json_mode():
            json_print("distiller", result)
            return

        status = result["status"]
        if status == "dry_run":
            print(f"Would process {result.get('would_process', 0)} conversation(s)")
            print("Pass --live to execute." if "--dry-run" not in args else "")
        elif status == "ok":
            print(f"Processed {result['processed']} conversation(s)")
            print(f"Wrote {result['facts_written']} fact file(s)")
        elif status == "no_facts_extracted":
            print(
                f"Processed {result['processed']} conversation(s) \u2014 no facts extracted"
            )
        elif status == "skipped":
            reason = result.get("reason", "unknown")
            print(f"Skipped: {reason}")
            if reason == "llm_not_configured":
                print("Run 'strata config set llm.apiKey <key>' to configure.")
        elif status == "error":
            print(f"Error: {result.get('reason', 'unknown')}")
        else:
            print(f"Result: {result}")
        return

    # No subcommand / unknown
    print("Usage: strata distiller status|run", file=sys.stderr)
    sys.exit(1)
