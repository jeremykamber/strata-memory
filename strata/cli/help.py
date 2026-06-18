from __future__ import annotations


def print_usage():
    """Panel-grouped help organized by category."""

    def _fmt_cmd(cmd: str) -> str:
        return f"strata {cmd}" if not cmd.startswith("--") else cmd

    groups = [
        (
            "SETUP",
            [
                (_fmt_cmd("init"), "Initialize directory structure"),
                (_fmt_cmd("config [get/set]"), "Show or modify configuration"),
                (_fmt_cmd("status"), "Show system state"),
            ],
        ),
        (
            "READING/WRITING",
            [
                (
                    _fmt_cmd("add <path> [content]"),
                    "Write content to 1st Stratum (or stdin)",
                ),
                (_fmt_cmd("read <path>"), "Read a 1st Stratum file"),
                (_fmt_cmd("list [path]"), "List 1st Stratum files and directories"),
                (_fmt_cmd("list-stratum-2"), "List 2nd Stratum (cooled) files"),
                (_fmt_cmd("index"), "Regenerate index.md"),
            ],
        ),
        (
            "SEARCHING",
            [
                (_fmt_cmd("search <query>"), "Search across all memory tiers"),
                (
                    _fmt_cmd("query <text>"),
                    "Search across all memory tiers (JSON output)",
                ),
            ],
        ),
        (
            "LIFECYCLE",
            [
                (_fmt_cmd("migrate"), "Run 1st -> 2nd Stratum migration"),
                (_fmt_cmd("promote"), "Move hot cooled files back to active"),
                (_fmt_cmd("evict"), "Run 2nd -> 3rd Stratum eviction"),
                (_fmt_cmd("maintenance"), "Run full lifecycle cycle"),
                (_fmt_cmd("forget <path>"), "Archive a cooled file to 3rd Stratum"),
                (
                    _fmt_cmd("rehydrate <id> [--target=active|cooled]"),
                    "Restore archived file to active or cooled",
                ),
                (_fmt_cmd("cost"), "Show estimated cost savings from Janitor"),
            ],
        ),
        (
            "DAEMON",
            [
                (_fmt_cmd("serve [--interval=N]"), "Start background Janitor daemon"),
                (_fmt_cmd("stop"), "Stop running daemon"),
                (_fmt_cmd("restart"), "Restart daemon"),
                (_fmt_cmd("install-service"), "Install systemd service"),
                (_fmt_cmd("uninstall-service"), "Uninstall systemd service"),
                (_fmt_cmd("history [--lines=N]"), "Show Janitor daemon log"),
                (
                    _fmt_cmd("distiller status"),
                    "Show distillation state and pending conversations",
                ),
                (_fmt_cmd("distiller run"), "Manually trigger LLM distillation"),
            ],
        ),
        (
            "AGENT INTEGRATION",
            [
                (_fmt_cmd("mcp"), "Start MCP protocol server (stdio)"),
                (
                    _fmt_cmd("skill install"),
                    "Install Strata skill for AI coding assistants",
                ),
                (_fmt_cmd("pi-install [--force]"), "Install Strata Pi extension"),
                (_fmt_cmd("--agent-help"), "Show agent usage guide"),
            ],
        ),
        (
            "QMD",
            [
                (_fmt_cmd("qmd-setup"), "Configure QMD collections (requires Node.js)"),
                (_fmt_cmd("qmd-embed"), "Generate QMD vector embeddings"),
                (_fmt_cmd("qmd-status"), "Show QMD index status"),
            ],
        ),
    ]
    print("Strata \u2014 Tiered Memory System")
    print()
    for title, cmds in groups:
        print(f"  {title}")
        for cmd, desc in cmds:
            print(f"    {cmd:<30} {desc}")
        print()


def agent_help() -> str:
    """Return the full agent help text."""
    return """# Strata \u2014 Agent Help

Strata is a tiered memory system for AI agents. It stores memories as plain
markdown files and moves them between three strata based on age and access.

## Architecture

  strata_data/
  \u251c\u2500\u2500 active/     \u2190 1st Stratum: Agent reads/writes here (working memory)
  \u251c\u2500\u2500 cooled/     \u2190 2nd Stratum: Aged-out files, searchable (Janitor manages)
  \u2514\u2500\u2500 archive/    \u2190 3rd Stratum: Cold storage + shadow index (keyword-retrievable)

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
      No LLM calls \u2014 files stay as markdown.

  strata evict
      Move cold files from cooled/ to archive/ (configurable LRU threshold).
      Creates shadow index entry for retrieval.

  strata maintenance
      Run migrate + evict in one command.

### System

  strata status     Show system state (files per tier, daemon status)
  strata config     Show configuration (thresholds, paths)
  strata index      Regenerate the 1st Stratum index.md
  strata skill install
                    Install Strata skill for AI coding assistants.
                    Interactive by default (choose scope + agents).
                    Use --global for non-interactive global install.
                    Requires Node.js for 'npx skills add'.

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

1. READ index.md FIRST \u2014 it's the map of all active files.
2. Write markdown files with structured headings (# Title, ## Section).
3. Use the index.md auto-generated descriptions to find the right file.
4. Search across all strata when you can't find something in active/.
5. Trust the Janitor \u2014 it handles migrations automatically.
6. Files in cooled/ are read-only for the agent (query only).
   If you need to edit a cooled file, request rehydration.

## How It Works

- Migration is triggered by file age (default: 14 days for projects, 60 for entities).
- Eviction is triggered by LRU (default: 90 days since last access).
- The Shadow Index (shadow.db) tracks archived files by keyword for retrieval.
- Re-hydration restores archived files back to the 1st Stratum.
"""
