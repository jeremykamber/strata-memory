# Strata Memory System — Agent Guide

This document is for AI agents working on the Strata codebase. It describes the architecture, conventions, and rules for contributing.

## Project Overview

Strata is a CLI-first, zero-dependency tiered memory system for AI agents. It stores memories as plain markdown files in three tiers, each with different access and retention policies. The project lives at `github.com/jeremykamber/strata-memory`.

- **Language:** Python 3.9+
- **Core dependencies:** zero (stdlib only)
- **Optional:** openai, anthropic (for API integrations), QMD/Node.js (for hybrid search)
- **CLI entry point:** `strata.cli:main`
- **Package name:** `strata-memory`

## Architecture: Three Strata

Strata stores data in a base directory (auto-detected: `./strata_data/` for project-local, `~/.strata/` for global, `$STRATA_HOME` overrides all).

```
<base>/
  active/           1st Stratum — working memory (agent reads/writes)
  cooled/           2nd Stratum — aged-out files (agent queries only)
  archive/          3rd Stratum — cold JSON storage + shadow index
  shadow.db         SQLite FTS5 shadow index
  strata.log        Daemon activity log
  strata.pid        Daemon PID file
```

### 1st Stratum (`active/`)

Full read/write access. Plain markdown files on disk, no database. An auto-generated `index.md` maps all files with their first heading as description. Agent workflow: read `index.md` first, navigate to files by path.

### 2nd Stratum (`cooled/`)

Read-only for agents. Files moved here by the Janitor when they exceed their decay threshold (defaults: projects=14d, entities=60d, gtd=7d, *=30d). Still plain markdown on disk. Accessible via `strata search`.

### 3rd Stratum (`archive/`)

Cold storage. Evicted from cooled/ after LRU threshold (default: 90 days since last access, access count <= 1). Full content saved as JSON. A Shadow Index (SQLite FTS5) keeps archived files keyword-searchable. Archived files can be rehydrated back to active/.

### The Janitor

The Janitor is the lifecycle manager. It moves data between strata using algorithmic triggers (file age, access count). No LLM calls. Runs on demand or via daemon (`strata serve`, default 15-min interval). First cycle is always a dry run.

### The Shadow Index

A SQLite FTS5 database (`shadow.db`) that stores keywords, a 200-char preview, and file paths for archived memories. Enables search across all three strata without needing to scan the archive directory.

## CLI Reference

```
Setup:
  strata init                Create ./strata_data/ (project-local)
  strata init --global       Create ~/.strata/ (global)
  strata init --local        Explicit local (default)

Writing (1st Stratum only):
  strata add <path> <content>           Write content to a file
  echo "note" | strata add <path>       Pipe content
  strata add --text "quick note"        Quick write (auto-routed to gtd/)

Reading:
  strata read <path>                    Read a file from active/
  strata list [path]                    List files/directories in active/
  strata list-stratum-2                 List files in cooled/

Searching (all three layers):
  strata search <query>                 Human-readable results
  strata query <text>                   JSON output (for scripting)

Lifecycle:
  strata migrate                        Move stale files active/ -> cooled/
  strata evict                          Move cold files cooled/ -> archive/
  strata maintenance                    Both at once
  strata forget <path>                  Archive a specific cooled file to 3rd Stratum
  strata index                          Regenerate index.md

Daemon:
  strata serve [--interval=N]           Start Janitor daemon (default 900s)
  strata serve --live                   Skip initial dry run
  strata stop                           Stop daemon
  strata restart                        Restart daemon
  strata history [--lines=N]            Show daemon log
  strata status                         Show system state

QMD (optional hybrid search):
  strata qmd-setup                      Configure QMD collections (needs Node.js)
  strata qmd-embed                      Generate vector embeddings
  strata qmd-status                     Show index status

Agent Integration:
  strata mcp                            Start MCP protocol server (stdio)
  strata skill install                  Install Strata skill for AI coding assistants
  strata skill install --global         Non-interactive global install
  strata --agent-help                   Show agent usage guide
```

## Configuration

`StrataConfig` dataclass in `strata/config.py`:

```python
@dataclass
class StrataConfig:
    base_dir: Path                        # Data root (auto-detected)
    active_dir: str = "active"            # 1st Stratum dir name
    cooled_dir: str = "cooled"            # 2nd Stratum dir name
    stratum_3_archive: str = "archive"    # 3rd Stratum dir name
    stratum_3_shadow_db: str = "stratum_3_shadow.db"

    decay_thresholds: dict = {            # Days before migration
        "projects": 14,                   # Active projects: 2 weeks
        "entities": 60,                   # People/companies: 2 months
        "gtd": 7,                         # Tasks: 1 week
        "*": 30,                          # Default: 1 month
    }

    lru_days: int = 90                    # Days before eviction (cooled -> archive)
    lru_min_access_count: int = 1         # Min accesses to avoid eviction
    active_file_patterns: list = ["*.md", "*.txt", "*.json", "*.yaml", "*.yml"]
    qmd_enabled: bool = False
    qmd_collection_prefix: str = "strata_"
```

Config is overridable via `$STRATA_HOME` env var (forces base directory).

## Python API

```python
from strata import Strata

strata = Strata()                     # Auto-detects base directory
strata.write_active("path/doc.md", "# Content")
strata.read_active("path/doc.md")
strata.list_active("path")
strata.query("search text")           # Searches all 3 strata
strata.migrate(dry_run=True)          # Preview migration
strata.migrate()                      # Execute migration
strata.evict()                        # Execute eviction
strata.run_maintenance()              # migrate + evict
strata.generate_index()               # Regenerate index.md
```

The `Strata` class is a context manager:

```python
with Strata() as s:
    s.write_active("note.md", "# Hello")
```

## Project Structure

```
strata/
  __init__.py        Top-level Strata class, version
  cli.py             CLI entry point and agent-help text
  config.py          StrataConfig dataclass, detect_base_dir
  daemon.py          Background Janitor daemon
  janitor.py         Migration and eviction logic
  mcp_server.py      MCP protocol server
  models.py          Data models
  query.py           QueryEngine (search across all strata)
  storage.py         Stratum1Storage, Stratum2Storage, Stratum3Storage, QmdWrapper
  tools.py           OpenAI-compatible function-calling tools
  skills/            Agent skill definitions for AI coding assistants

docs/
  strata_blog_post.md               Published blog post about Strata
  how_to_make_pi_extension.md       Guide for creating PI-compatible extensions

landing_page/       Astro project for the Strata marketing site
tests/              Pytest test suite
skills/             ConWey-compatible agent skills
```

## Docs Structure

Agent-facing documentation lives in:

- **README.md** — Full project documentation, CLI reference, install guide, Python API
- **AGENTS.md** (this file) — Concise guide for AI agents working ON this project
- **docs/** — Extended documentation (blog posts, integration guides)
- **strata/cli.py** docstring — Inline CLI reference (also printed by `strata` with no args)

## Contribution Rules

1. **After every change, update the relevant docs.** If you change a command, update the CLI reference. If you change a config field, update the config section. Outdated docs are bugs.

2. **No new pip dependencies.** Strata is stdlib-first by design. Optional dependencies are strictly scoped to `[openai]`, `[anthropic]`, and `[all]` extras.

3. **No Jest or TypeScript test infra.** Tests are Python pytest only.

4. **No doc generation pipeline.** All documentation is hand-written markdown. Keep it that way.

5. **Conventional commits.** Every logical change gets a commit. Format: `type(scope): description`. Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.

6. **Match the codebase style.** Two spaces for indentation. No type annotations in `__init__` signatures beyond `Optional`/`List` from typing. Dataclasses for config objects.

7. **Files are the truth.** Strata stores data as plain markdown files. No databases for active storage. Keep changes aligned with this principle.

8. **The Janitor is algorithmic.** No LLM calls in lifecycle management. Migration and eviction decisions are based on file age, access count, and configurable thresholds.

## Key Principles

- **CLI-first.** The command line is the primary interface. The Python API exists for programmatic use but mirrors the CLI.
- **No mock data in tests.** E2E tests execute against the real storage layer (filesystem, SQLite).
- **Fail loud.** Surface errors, don't silently swallow them. Print to stderr and exit non-zero on failure.
- **Keep the agent-help text in sync.** `strata --agent-help` prints inline documentation from `cli.py`. If you change behavior, update that text too.
