"""Command-line interface for Strata memory system.

Usage:
    strata init                    Initialize directory structure
    strata add <path> [content]    Write content to 1st Stratum (or stdin)
    strata search <query>          Search across all memory tiers
    strata query <text>            Search across all memory tiers (JSON output)
    strata read <path>             Read a 1st Stratum file
    strata list [path]             List 1st Stratum files and directories
    strata list-stratum-2             List 2nd Stratum (cooled) files
    strata forget <path>           Archive a cooled file to 3rd Stratum
    strata migrate                 Run 1st -> 2nd Stratum migration
    strata evict                   Run 2nd -> 3rd Stratum eviction
    strata maintenance             Run full lifecycle cycle
    strata serve [--interval=N]    Start background Janitor daemon
    strata daemon                  Alias for "serve"
    strata stop                    Stop running daemon
    strata restart                 Restart daemon
    strata status                  Show system status
    strata config                  Show current configuration
    strata history [--lines=N]     Show Janitor daemon log
    strata mcp                     Start MCP protocol server (stdio)
    strata qmd-setup               Configure QMD collections (requires Node.js)
    strata qmd-embed               Generate QMD vector embeddings
    strata qmd-status              Show QMD index status
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from strata import Strata
from strata.config import StrataConfig, detect_base_dir
from strata.daemon import StrataDaemon, get_daemon_status
from strata.mcp_server import MCPServer


def _config(**kwargs) -> StrataConfig:
    if "base_dir" not in kwargs:
        kwargs["base_dir"] = detect_base_dir()
    return StrataConfig(**kwargs)


def main(argv: Optional[list[str]] = None):
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        _print_usage()
        return

    if args[0] in ("--agent-help", "agent-help"):
        print(_agent_help())
        return

    command = args[0]

    if command == "init":
        _cmd_init(args[1:])

    elif command == "add":
        _cmd_add(args[1:])

    elif command in ("search", "query"):
        _cmd_query(command, args[1:])

    elif command == "read":
        _cmd_read(args[1:])

    elif command == "list":
        _cmd_list(args[1:])

    elif command == "list-stratum-2":
        _cmd_list_stratum_2()

    elif command == "forget":
        _cmd_forget(args[1:])

    elif command in ("migrate", "evict", "maintenance"):
        _cmd_lifecycle(command, args[1:])

    elif command in ("serve", "daemon"):
        _cmd_serve(args[1:])

    elif command == "stop":
        _cmd_stop()

    elif command == "restart":
        _cmd_stop()
        _cmd_serve(args[1:])

    elif command == "status":
        _cmd_status()

    elif command == "config":
        _cmd_config(args[1:])

    elif command == "history":
        _cmd_history(args[1:])

    elif command == "qmd-setup":
        _cmd_qmd_setup()

    elif command == "qmd-embed":
        _cmd_qmd_embed()

    elif command == "qmd-status":
        _cmd_qmd_status()

    elif command == "index":
        _cmd_index()

    elif command == "mcp":
        _cmd_mcp()

    else:
        print(f"Unknown command: {command}")
        _print_usage()
        sys.exit(1)


def _print_usage():
    print(globals()["__doc__"])


def _with_strata(fn, config: Optional[StrataConfig] = None):
    """Open Strata, call fn, close."""
    c = config or _config()
    with Strata(c) as s:
        fn(s)


def _cmd_init(rest: list[str] | None = None):
    explicit = rest or []
    if "--global" in explicit or "-g" in explicit:
        base_dir = Path.home() / ".strata"
    elif "--local" in explicit or "-l" in explicit:
        base_dir = Path("./strata_data")
    else:
        base_dir = Path("./strata_data")
    config = StrataConfig(base_dir=base_dir)
    with Strata(config) as s:
        s.s1.ensure_dirs()
        s.s2.ensure_dirs()
        s.s3.ensure_dirs()
    kind = "global" if base_dir == Path.home() / ".strata" else "local"
    print(f"Initialized {kind} Strata at {config.base_dir.resolve()}")


def _cmd_add(rest: list[str]):
    """Add content to 1st Stratum active memory.

    Usage:
        strata add projects/kynd/notes.md "Some content here"
        echo "content" | strata add projects/kynd/notes.md
        strata add --text "Quick memory note"    # auto-routed to gtd/quick-notes.md
    """
    config = _config()
    with Strata(config) as s:
        if not rest:
            # Read from stdin
            content = sys.stdin.read().strip()
            if not content:
                print("No content provided. Pipe content or pass path + content.")
                print("  echo 'my note' | strata add projects/notes.md")
                return
            # If only one arg, it's the path; if none, use default
            path = "gtd/quick-note.md"
            s.write_active(path, content)
            print(f"Written to: {s.s1._root / path}")
            return

        if rest[0] == "--text" and len(rest) >= 2:
            path = f"gtd/quick-note-{int(time.time())}.md"
            content = " ".join(rest[1:])
            s.write_active(path, content)
            print(f"Written to: {s.s1._root / path}")
            return

        if len(rest) >= 2:
            path = rest[0]
            content = " ".join(rest[1:])
        else:
            path = rest[0]
            content = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
            if not content:
                print("Provide content as second argument or pipe it:")
                print(f"  strata add {path} 'your content'")
                print(f"  echo 'your content' | strata add {path}")
                return

        s.write_active(path, content)
        print(f"Written to: {s.s1._root / path}")


def _cmd_query(command: str, rest: list[str]):
    query_text = " ".join(rest) if rest else ""
    if not query_text:
        print(f"Usage: strata {command} <search text>")
        return
    config = _config()
    with Strata(config) as s:
        results = s.query(query_text, top_k=10)
        if command == "search":
            _print_search_results(results)
        else:
            print(json.dumps(results, indent=2))


def _print_search_results(results: list[dict]):
    if not results:
        print("No results found.")
        return
    for i, r in enumerate(results, 1):
        tier_tag = {"stratum_1": "ACTIVE", "stratum_2": "MEDIUM", "stratum_3": "ARCHIVE"}.get(r["tier"], r["tier"])
        source = r.get("source", "?")
        content = r.get("content", "")
        score = r.get("score", 0)
        meta = r.get("metadata", {})

        print(f"\n  [{i}] [{tier_tag}] (score={score:.2f})")
        print(f"       Source: {source}")

        if content:
            preview = content[:120].replace("\n", " ").strip()
            print(f"       {preview}...")

        if r["tier"] == "stratum_3" and meta.get("_needs_rehydration"):
            print(f"       [in archive — query strata forget <id> to rehydrate]")


def _cmd_read(rest: list[str]):
    if not rest:
        print("Usage: strata read <path>")
        return
    config = _config()
    with Strata(config) as s:
        try:
            content = s.read_active(rest[0])
            print(content)
        except FileNotFoundError:
            print(f"File not found: {rest[0]}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


def _cmd_list(rest: list[str]):
    path = rest[0] if rest else ""
    config = _config()
    with Strata(config) as s:
        entries = s.list_active(path)
        if not entries:
            print(f"Empty or not found: {path or '/'}")
            return
        for e in entries:
            t = "dir" if e["type"] == "directory" else "file"
            print(f"  [{t}] {e['path']} ({e['size']}b)")


def _cmd_list_stratum_2():
    config = _config()
    with Strata(config) as s:
        files = s.s2.list_all()
        if not files:
            print("No 2nd Stratum files.")
            return
        for f in files:
            print(f"  {f['path']} ({f['size']}b, modified {f['modified'][:10]})")


def _cmd_forget(rest: list[str]):
    """Archive a file from 2nd Stratum to 3rd Stratum."""
    if not rest:
        print("Usage: strata forget <path>")
        return
    path = rest[0]
    config = _config()
    with Strata(config) as s:
        source = s.s2._root / path
        if not source.exists():
            print(f"File not found in 2nd Stratum: {path}")
            sys.exit(1)
        tags = [path.split("/")[0]] if "/" in path else []
        archive_path = s.s3.archive_file(source, path, tags=tags)
        source.unlink()
        print(f"Archived to: {archive_path}")


def _cmd_lifecycle(command: str, rest: list[str]):
    dry_run = "--dry-run" in rest
    config = _config()
    with Strata(config) as s:
        s.s1.ensure_dirs()
        s.s3.ensure_dirs()
        if command == "migrate":
            results = s.migrate(dry_run=dry_run)
            print(json.dumps(results, indent=2))
            print(f"\nMigrated: {len(results)} files")
        elif command == "evict":
            results = s.evict(dry_run=dry_run)
            print(json.dumps(results, indent=2))
            print(f"\nEvicted: {len(results)} memories")
        elif command == "maintenance":
            result = s.run_maintenance(dry_run=dry_run)
            print(json.dumps(result, indent=2))
            print(f"\nMigrated: {result.get('total_migrated') or len(result.get('migrated', []))}")
            print(f"Evicted:  {result.get('total_evicted') or len(result.get('evicted', []))}")


def _cmd_serve(rest: list[str]):
    interval = 900
    dry_run_first = True
    for arg in rest:
        if arg.startswith("--interval="):
            interval = int(arg.split("=")[1])
        elif arg == "--live":
            dry_run_first = False
        elif arg == "--help":
            print("Usage: strata serve [--interval=SECONDS] [--live]")
            print("  --interval=N   Seconds between maintenance cycles (default: 900)")
            print("  --live         Skip initial dry-run, go straight to live operations")
            return

    config = _config()
    status = get_daemon_status(config)
    if status["running"]:
        print(f"Daemon is already running (pid={status['pid']}). Use 'strata stop' first or 'strata restart'.")
        return

    daemon = StrataDaemon(
        config=config,
        interval_seconds=interval,
        dry_run_first=dry_run_first,
    )
    print(f"Starting Strata daemon (interval={interval}s, dry_run_first={dry_run_first})")
    print(f"  Log:  {daemon._log_path.resolve()}")
    print(f"  PID:  {daemon._pid_path.resolve()}")
    print("Press Ctrl+C to stop.")
    daemon.start()


def _cmd_stop():
    from strata.daemon import stop_daemon
    config = _config()
    result = stop_daemon(config)
    print(result["message"])


def _cmd_status():
    config = _config()
    status = get_daemon_status(config)
    with Strata(config) as s:
        p1_count = len(s.s1.scan_stale_files())
        p2_count = s.s2.count()
        p3_count = s.s3.get_shadow_count()
        active_root = config.active_path().resolve()

    print(f"Strata Memory System — Status")
    print(f"  Base directory: {config.base_dir.resolve()}")
    print(f"  Active root:    {active_root}")
    print(f"")
    print(f"  1st Stratum (Active):  {p1_count} stale file(s) pending")
    print(f"  2nd Stratum (Medium):  {p2_count} memory block(s)")
    print(f"  3rd Stratum (Archive): {p3_count} shadow entr(ies)")
    print(f"")
    print(f"  Daemon: {'RUNNING (pid=' + str(status['pid']) + ')' if status['running'] else 'STOPPED'}")

    if status["running"]:
        print(f"  Cycles completed: {status['cycle_count']}")
        if status["log_lines"]:
            print(f"  Recent log:")
            for line in status["log_lines"][-5:]:
                print(f"    {line}")


def _cmd_config(rest: list[str]):
    config = _config()
    print(f"strata Configuration")
    print(f"{'=' * 40}")
    print(f"  base_dir:           {config.base_dir.resolve()}")
    print(f"  active_dir:         {config.active_dir}")
    print(f"  cooled_dir:         {config.cooled_dir}")
    print(f"  qmd_enabled:        {config.qmd_enabled}")
    print(f"  stratum_3_archive:     {config.stratum_3_archive}")
    print(f"  stratum_3_shadow_db:   {config.stratum_3_shadow_db}")
    print(f"")
    print(f"  Decay thresholds:")
    for pattern, days in sorted(config.decay_thresholds.items()):
        print(f"    /{pattern}:  {days} days")
    print(f"")
    print(f"  LRU eviction:       {config.lru_days} days, ≤{config.lru_min_access_count} access(es)")
    print(f"  QMD enabled:        {config.qmd_enabled}")
    print(f"  File patterns:      {', '.join(config.active_file_patterns)}")


def _cmd_history(rest: list[str]):
    lines = 20
    for arg in rest:
        if arg.startswith("--lines="):
            lines = int(arg.split("=")[1])

    config = _config()
    log_path = config.base_dir / "strata.log"
    if not log_path.exists():
        print("No daemon log found. Start the daemon with 'strata serve'.")
        return

    content = log_path.read_text(encoding="utf-8").strip()
    log_lines = content.split("\n")
    tail = log_lines[-lines:]
    print(f"Janitor Log ({len(tail)} of {len(log_lines)} lines):")
    print(f"{'=' * 60}")
    for line in tail:
        print(f"  {line}")


def _cmd_index():
    """Regenerate the 1st Stratum index.md."""
    config = _config()
    with Strata(config) as s:
        s.generate_index()
    idx = config.active_path() / "index.md"
    if idx.exists():
        print(f"Index regenerated: {idx.resolve()}")
        print(idx.read_text()[:300])
    else:
        print("No active files to index.")


def _cmd_mcp():
    """Start MCP protocol server over stdio."""
    server = MCPServer()
    try:
        server.run_stdio()
    finally:
        server.close()


def _cmd_qmd_setup():
    """Configure QMD collections for all Strata directories."""
    config = _config()
    from strata.storage import QmdWrapper
    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed. Install it with: npm install -g @tobilu/qmd")
        return
    results = qmd.setup_collections()
    for r in results:
        print(f"  [{r['status']}] {r['name']}: {r.get('path', '')}")
    print("\nRun 'strata qmd-embed' to generate vector embeddings.")


def _cmd_qmd_embed():
    """Generate QMD vector embeddings."""
    config = _config()
    from strata.storage import QmdWrapper
    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed. Install it with: npm install -g @tobilu/qmd")
        return
    print("Generating embeddings (may take a while on first run)...")
    result = qmd.embed(force=False)
    print(result.get("output", "Done."))


def _cmd_qmd_status():
    """Show QMD index status."""
    config = _config()
    from strata.storage import QmdWrapper
    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed.")
        return
    result = qmd.get_status()
    print(result.get("output", "Unknown status."))


def _agent_help() -> str:
    return """# Strata — Agent Help

Strata is a tiered memory system for AI agents. It stores memories as plain
markdown files and moves them between three strata based on age and access.

## Architecture

  strata_data/
  ├── active/     ← 1st Stratum: Agent reads/writes here (working memory)
  ├── cooled/     ← 2nd Stratum: Aged-out files, searchable (Janitor manages)
  └── archive/    ← 3rd Stratum: Cold storage + shadow index (keyword-retrievable)

- The agent ONLY reads and writes to the 1st Stratum (active/).
- The Janitor (background process) moves files from active/ to cooled/,
  and from cooled/ to archive/, based on configurable thresholds.
- The agent queries across ALL three strata via `strata search`.

## Principle

Start by reading `active/index.md`. It lists every file in the 1st Stratum
with its first heading as a description. Navigate to specific files by path.

For anything you can't find in the 1st Stratum, use `strata search`.
The cascade search checks all three strata automatically.

## Commands

### Reading & Writing (1st Stratum only)

  strata add <path> <content>
      Write a file. Creates parent dirs. Updates index.md.
      Example: strata add projects/koda/spec.md "# Koda Platform..."

  strata read <path>
      Read a file's full content.
      Example: strata read projects/koda/spec.md

  strata list [path]
      List files/directories in the 1st Stratum.
      Example: strata list projects

### Searching (ALL three strata)

  strata search <query>
      Human-readable search across active/ + cooled/ + archive/.
      Example: strata search "koda oauth2"

  strata query <query>
      Same as search but outputs JSON (for scripting).
      Example: strata query "postgresql pgvector"

### Lifecycle

  strata migrate
      Move stale files from active/ to cooled/ (configurable age threshold).
      No LLM calls — files stay as markdown.

  strata evict
      Move cold files from cooled/ to archive/ (configurable LRU threshold).
      Creates shadow index entry for retrieval.

  strata maintenance
      Run migrate + evict in one command.

### System

  strata status     Show system state (files per tier, daemon status)
  strata config     Show configuration (thresholds, paths)
  strata index      Regenerate the 1st Stratum index.md

### Daemon (Automatic Lifecycle)

  strata serve [--interval=N]
      Start the Janitor daemon. Runs migrate + evict every N seconds.
      Default interval: 900 (15 min). First cycle is a dry run.
      strata stop    Stop the daemon.
      strata restart Restart the daemon.
      strata history Show the daemon activity log.

### QMD Integration (optional hybrid search)

  Requires: npm install -g @tobilu/qmd

  strata qmd-setup  Add active/ + cooled/ as QMD collections
  strata qmd-embed  Generate vector embeddings
  strata qmd-status Check QMD index health

  When QMD is active, `strata search` uses BM25 + vector search (no LLM).

## Best Practices

1. READ index.md FIRST — it's the map of all active files.
2. Write markdown files with structured headings (# Title, ## Section).
3. Use the index.md auto-generated descriptions to find the right file.
4. Search across all strata when you can't find something in active/.
5. Trust the Janitor — it handles migrations automatically.
6. Files in cooled/ are read-only for the agent (query only).
   If you need to edit a cooled file, request rehydration.

## How It Works

- Migration is triggered by file age (default: 14 days for projects, 60 for entities).
- Eviction is triggered by LRU (default: 90 days since last access).
- The Shadow Index (shadow.db) tracks archived files by keyword for retrieval.
- Re-hydration restores archived files back to the 1st Stratum.
"""


if __name__ == "__main__":
    main()
