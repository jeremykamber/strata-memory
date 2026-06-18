"""Search command for the Strata CLI.

Searches across all three memory tiers: active (1st Stratum), cooled
(2nd Stratum), and archive (3rd Stratum + shadow index).

``strata search <text>``  — human-readable output
``strata query <text>``   — JSON output (handled via --json flag at dispatch)
"""

from __future__ import annotations


from strata import Strata
from strata.cli._json import json_print, json_error, is_json_mode
from strata.cli._config import load_config

name = "search"
aliases = ["query"]


def _print_search_results(results: list[dict]) -> None:
    """Print search results in human-readable format.

    Each result is tagged with its stratum tier (ACTIVE, MEDIUM, ARCHIVE).
    Archived results that need rehydration are flagged with a note.

    Args:
        results: List of search result dicts from ``query_engine.search()``.
    """
    if not results:
        print("No results found.")
        return
    for i, r in enumerate(results, 1):
        tier_tag = {
            "stratum_1": "ACTIVE",
            "stratum_2": "MEDIUM",
            "stratum_3": "ARCHIVE",
        }.get(r["tier"], r["tier"])
        source = r.get("source", "?")
        content = r.get("content", "")
        score = r.get("score", 0)
        meta = r.get("metadata", {})

        sep = "\u00b7"
        print(f"\n  [{i}] [{tier_tag}] {sep} score={score:.2f} {sep} {source}")

        if content:
            preview = content[:120].replace("\n", " ").strip()
            print(f"       {preview}...")

        if r["tier"] == "stratum_3" and meta.get("_needs_rehydration"):
            print("       [in archive \u2014 use strata rehydrate <id> to restore]")


def run(args: list[str]) -> None:
    """Handle the ``search`` and ``query`` commands.

    ``search`` produces human-readable output by default (JSON if the
    ``--json`` global flag was set).  The ``query`` alias is handled at
    the dispatch layer by enabling JSON mode before calling ``run``.

    Args:
        args: Remaining arguments after the command name (the search text).
    """
    query_text = " ".join(args) if args else ""
    if not query_text:
        if is_json_mode():
            json_error("search", "No search text provided")
        print("Usage: strata search <search text>")
        return

    config = load_config()
    with Strata(config) as s:
        results = s.query(query_text, top_k=10)
        if is_json_mode():
            json_print("search", results)
            return
        _print_search_results(results)
