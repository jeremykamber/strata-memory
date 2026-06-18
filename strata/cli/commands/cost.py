"""Show estimated cost savings from Janitor automation."""

from __future__ import annotations


from strata.cli._json import json_print, is_json_mode
from strata.cli._config import load_config
from strata.tracking import CostTracker

name = "cost"


def run(args: list[str]) -> None:
    """Show estimated cost savings from Janitor automation."""
    config = load_config()

    tracker = CostTracker(config)
    summary = tracker.get_summary()

    # Check for no daemon activity
    if "error" in summary:
        if is_json_mode():
            json_print("cost", {"error": summary["error"]})
            return
        print(summary["error"])
        return

    if is_json_mode():
        json_print("cost", summary)
        return

    # Formatted output
    print("Strata Cost Savings (Estimated)")
    print("=" * 40)
    print(f"  Daemon cycles:     {summary['daemon_cycles']['value']}")
    print(f"  Files migrated:    {summary['files_migrated']['value']}")
    print(f"  Files evicted:     {summary['files_evicted']['value']}")
    print(f"  LRU decisions:     {summary['lru_decisions']['value']}")
    print(f"  Tokens saved:      {summary['tokens_saved_estimate']['value']:,} tokens")
    print(f"  Savings range:     {summary['tokens_saved_range']['value']}")
    print()
    print(
        f"  Methodology: {summary.get('tokens_saved_estimate', {}).get('methodology', '')}"
    )
    print(
        f"  Disclaimer: {summary.get('tokens_saved_estimate', {}).get('disclaimer', '')}"
    )
