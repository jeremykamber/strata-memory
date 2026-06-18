# Strata

**Tiered memory for AI agents, minus the hype.** One install, one `strata init`, and bam  -  you've got a three-layer memory system. No API keys, no vector databases, no background LLM janitors quietly torching tokens on every query.

```bash
pip install git+[https://github.com/jeremykamber/strata-memory.git](https://github.com/jeremykamber/strata-memory.git)

strata init
strata add projects/kynd/requirements.md "# Kynd needs OAuth2 + payments"
strata search "oauth2 payments"

```

I named it after rock layers (creative, I know). Each stratum represents a different depth of memory. Active items sit at the surface where your agent can grab them fast; old items settle into deeper layers over time. And here's the thing  -  information decays on purpose. That's not a bug, it's the whole point. A system that remembers everything is functionally identical to a system that remembers nothing. The signal drowns in the noise. Perfect recall? It's an anchor.

---

## The Problem

Most memory systems treat every piece of data like it matters equally. A passing thought from five minutes ago gets the same VIP treatment as a core architectural decision from six months ago. Same storage, same retrieval, same fidelity. That's a problem  -  in two big ways.

First, vector search degrades as your document count rises. Eventually every document starts looking semantically similar to every other document. You end up digging through your own haystack for a needle that should've been sitting right there on your desk.

Second, developers try to fix this by running an LLM-powered background process on every query. Every single read, write, or search triggers an API call to clean and prioritize memories. Your API credits disappear faster than pizza at a hackathon. And the LLM has to judge incoming data against potentially hundreds of existing memories  -  which gets harder and more expensive the more you use the system.

Human memory works through compression and neglect. We actively remember what we use, and we forget what we ignore. Our brains push old conversations to the background (eventually letting them fade out completely). Autonomous systems need this exact mechanic to function long-term. Structured decay beats throwing more compute at the problem.

## What Makes Strata Different

Two specific choices define the architecture.

**Active memory stays physically separated from long-term storage.** The agent only ever interacts with a small subset of memories at any given moment. It never gets bogged down by old context it stopped touching weeks ago.

**The migration trigger is algorithmic.** File age and access recency dictate what shifts between tiers. There's no LLM getting paid by the token to guess if a file is old. That job belongs to simple system timestamps  -  which are free, fast, and don't hallucinate.

This creates an environment where information naturally settles into deeper, cheaper storage. You avoid spending tokens to decide what matters.

## How It Works

```text
┌──────────────────┬─────────────────┬────────────────────────────┐
│  1st Stratum     │  2nd Stratum    │  3rd Stratum               │
│  (active/)       │  (cooled/)      │  (archive/ + shadow.db)    │
├──────────────────┼─────────────────┼────────────────────────────┤
│  Read/write      │  Query-only     │  Cold JSON storage         │
│  Plain .md files │  Aged-out .md   │  with FTS5 keyword index   │
│  on disk         │  files on disk  │                            │
├──────────────────┼─────────────────┼────────────────────────────┤
│  ~1ms access     │  ~5ms access    │  ~10ms via re-hydration    │
│  No database     │  No database    │                            │
└────────┬─────────┴────────┬────────┴──────────┬─────────────────┘
         │                  │                   │
         ▼                  ▼                   ▼
    ┌──────────┐      ┌──────────┐       ┌──────────┐
    │ Janitor  │ ──── │ Janitor  │ ────  │ Shadow   │
    │ migrate  │      │ evict    │       │ Index    │
    │ 1st→2nd  │      │ 2nd→3rd  │       │ (search) │
    └──────────┘      └──────────┘       └──────────┘

```

The Janitor moves data between the layers. It runs on a schedule or whenever you call it. It relies entirely on simple rules  -  no LLM calls, no text compression, no token spend. Just timestamps and elbow grease.

### 1st Stratum  -  Active (the surface layer)

This is your agent's working memory. Plain markdown files in a standard directory tree. No database, no vector index, no fuss.

The agent reads `active/index.md` first. This auto-generated map lists every file and uses the first heading as a description. The agent checks the map, picks a path, and reads the target file directly. You bypass vector search and embedding noise completely  -  things are exactly where you put them.

Write structured markdown with clear headings. The index grabs the first `# heading` and uses it as the file's description.

**Agent rule:** Full read/write access. This is the main workspace.

**Transition trigger:** The Janitor checks the modification time. If a file sits untouched past its decay threshold (default is 14 days for projects, 60 for entities, and 7 for tasks), it's eligible for migration.

**Moving back up (Promotion):** The Janitor also moves in reverse. When a cooled file gets accessed 3 or more times (the `promotion_threshold`), it gets promoted back to active/. The file proved useful again  -  so it resurfaces to the working tier where the agent can edit it directly. This keeps frequently-referenced context from getting buried by age-based decay.

### 2nd Stratum  -  Cooled (the middle layer)

The Janitor copies aged-out files from `active/` to `cooled/`. They stay as standard markdown files on your disk. The agent can search and read them  -  direct writes are blocked.

**Agent rule:** Read-only access through `strata search`. Queries return the results directly. Editing a file means rehydrating it back to the active tier first.

**Transition trigger:** A cooled file faces eviction when it meets two conditions. It must sit untouched for `lru_days` (default is 90). The access count also needs to be at or below `lru_min_access_count` (default is 1). A JSON sidecar file logs every read and search hit to track this access.

### 3rd Stratum  -  Archive (the deep layer)

Untouched cooled files eventually drop into `archive/`. The Janitor saves the full content as JSON in flat storage. A minimal entry goes into the Shadow Index (a SQLite FTS5 database) with just keywords, a 200-character preview, and the file path. Still no vectors, no embeddings.

A million archived entries cost less than a megabyte of disk space. Yes, really.

If a future search matches an archived entry, the file gets rehydrated. The Janitor reads the JSON, writes it back to the active tier, and deletes the shadow entry. The memory resurfaces simply because it proved useful again.

There's a massive difference between throwing something in the trash and packing it in a labeled box in your basement. Strata does the latter.

### The Janitor (lifecycle manager)

The Janitor runs entirely on algorithms. It checks the clock instead of analyzing text.

* **Migration (1st → 2nd):** Copies the file from `active/` to `cooled/`, deletes the original, and starts access tracking. File age triggers this step.
* **Promotion (2nd → 1st):** When a cooled file gets read 3+ times (configurable via `promotion_threshold`), it's automatically promoted back to `active/`. The file proved useful again  -  it resurfaces to the working tier.
* **Eviction (2nd → 3rd):** Reads the file content, saves it as JSON to `archive/`, creates the FTS5 entry in `shadow.db`, and deletes the cooled copy. LRU logic triggers this step.
* **Rehydration (3rd → 1st or 3rd → 2nd):** Reads the archived JSON, writes the content back to `active/` or `cooled/` at the original path, and removes the shadow entry. Triggered automatically when you `strata read` an archived file, or manually via `strata rehydrate <id> --target=active|cooled`.

Zero LLM calls. Zero token spend. The Janitor just looks at the clock.

## Quick Start

### Install

```bash
pip install git+[https://github.com/jeremykamber/strata-memory.git](https://github.com/jeremykamber/strata-memory.git)

```

Zero pip dependencies. Works on Python 3.9 and newer.

### Initialize

```bash
# Project-local (creates ./strata_data/)
strata init

# Global (creates ~/.strata/)
strata init --global

```

### Write Memories

```bash
strata add projects/kynd/requirements.md "# Kynd Platform
Stack: React + Go + PostgreSQL
Features: OAuth2, Stripe, real-time dashboard
"

# Pipe content in
echo "Joe: React/Go engineer on the Kynd team" | strata add entities/joe.md

# Quick note (auto-routed to quick-note-<ts>.md at root)
strata add --text "Review PR by end of day"

# Read it back
strata read projects/kynd/requirements.md

# List what's available
strata list projects

```

### Search Across All Three Strata

```bash
strata search "oauth2 payments"
# → [1] [ACTIVE] · score=1.50 · projects/kynd/requirements.md
#       Kynd Platform Stack: React + Go + PostgreSQL Features: OAuth2...
# → [2] [ARCHIVE] · score=0.50 · archive:strata_3/abc123.json
#       [in archive  -  archived file can be rehydrated]

# JSON output
strata query "oauth2"

```

### Let the Janitor Work

```bash
# Preview first
strata migrate --dry-run
strata promote --dry-run
strata evict --dry-run

# Execute
strata maintenance           # Full cycle: promote → migrate → evict

# Or background daemon (every 15 min by default)
strata serve &

```

### Agent Memory (Pi Extension)

Strata ships with a zero-dependency Pi extension that auto-captures every conversation and optionally extracts knowledge via a small LLM.

```bash
# 1. Install the extension
strata pi-install
# Then run /reload in Pi

# 2. Enable LLM fact extraction (secure key prompt)
strata config set llm.apiKey        # Prompts securely  -  won't echo
strata config set llm.provider openrouter
strata config set llm.model openrouter/free
strata config set llm.enabled true

# 3. Background daemon handles lifecyle + distillation
strata serve
```

Every Pi prompt gets automatically saved as a transcript. The daemon periodically sends new transcripts to the LLM and writes extracted facts to `pi/facts/`  -  searchable with `strata search`.

```bash
# Check distillation state
strata distiller status

# Manually trigger extraction
strata distiller run
```

See [`docs/pi-integration.md`](docs/pi-integration.md) for the full breakdown.

## Python API

```python
from strata import Strata

# Auto-detects: ./strata_data/ if it exists, else ~/.strata/
strata = Strata()

# Write to active tier
strata.write_active("projects/kynd/spec.md", "# Kynd Platform\n...")

# Read from active tier
content = strata.read_active("projects/kynd/spec.md")

# Search across all three tiers
results = strata.query("oauth2 payments")

# Lifecycle
strata.migrate(dry_run=True)  # Preview
strata.migrate()              # Execute
strata.evict()                # Archive old memories
strata.run_maintenance()      # Both at once

# Context manager
with Strata() as s:
    s.write_active("note.md", "# Hello")

```

### Function-Calling Tools

Strata exposes six OpenAI-compatible function-calling tools:

| Tool | Purpose |
| --- | --- |
| `strata_read_active` | Read a file from active memory (falls back to cooled/archive) |
| `strata_write_active` | Write a file to active memory |
| `strata_list_active` | List files in active memory |
| `strata_query` | Search across all three tiers |
| `strata_forget` | Archive a cooled file to cold storage |
| `strata_rehydrate` | Restore an archived file to active or cooled |

```python
# Get tool schemas for any LLM harness
tools = strata.tools.all_schemas()

# Execute a tool call
result = strata.tools.execute("strata_query", {"query": "kynd"})

```

This plays nice with OpenAI, Anthropic, OpenClaw, or any harness that supports function calling.

### MCP Server

Strata also ships with an MCP (Model Context Protocol) server for agents speaking JSON-RPC 2.0 over stdio:

```bash
strata mcp

```

It supports Claude Code and any standard MCP client.

## CLI Reference

```text
SETUP
  strata init                    Initialize directory structure
  strata config [get/set]        Show or modify configuration
  strata status                  Show system state

READING / WRITING (1st Stratum only)
  strata add <path> [content]    Write content (or pipe, or --text)
  strata read <path>             Read from any stratum (auto-promotes cooled)
  strata list [path]             List files and directories
  strata list-stratum-2          List 2nd Stratum (cooled) files
  strata index                   Regenerate index.md

SEARCHING (all three strata)
  strata search <query>          Human-readable results
  strata query <text>            JSON output

LIFECYCLE
  strata migrate [--dry-run]     Move stale files active/ → cooled/
  strata promote [--dry-run]     Move hot cooled files back to active/
  strata evict [--dry-run]       Move cold files cooled/ → archive/
  strata maintenance [--dry-run] Full cycle: promote → migrate → evict
  strata rehydrate <id>          Restore archived file to active or cooled
  strata forget <path>           Archive a specific cooled file
  strata cost                    Show estimated Janitor savings

DAEMON
  strata serve [--interval=N]    Start background Janitor daemon
  strata stop                    Stop daemon
  strata restart                 Restart daemon
  strata install-service         Install systemd service (auto-start on boot)
  strata uninstall-service       Remove systemd service
  strata history [--lines=N]     Show daemon activity log

AGENT INTEGRATION
  strata mcp                     MCP protocol server (stdio)
  strata skill install           Install Strata skill for AI agents
  strata pi-install [--force]    Install Strata Pi extension
  strata --agent-help            Agent usage guide

QMD (optional hybrid search)
  strata qmd-setup               Configure QMD collections (needs Node.js)
  strata qmd-embed               Generate vector embeddings
  strata qmd-status              Show QMD index status

```

## Configuration

```python
from strata.config import StrataConfig

config = StrataConfig(
    decay_thresholds={
        "projects": 14,    # Active projects: 2 weeks
        "entities": 60,    # People and companies: 2 months
        "gtd": 7,          # Tasks: 1 week
        "*": 30,           # Everything else: 1 month
    },
    lru_days=90,             # Evict if not accessed in 90 days
    lru_min_access_count=1,  # And accessed 1 time or fewer
)

```

The config persists to `strata.json` in the base directory. You can tweak it at runtime:

```bash
strata config set decay_thresholds.gtd 14
strata config get lru_days
# → 90

```

### Environment Variables

| Variable | Overrides | Description |
|---|---|---|
| `$STRATA_HOME` | `base_dir` | Forces the data directory to this path. Highest priority override. |

When `$STRATA_HOME` is set, `strata init` and all other commands use it as the root:

```bash
export STRATA_HOME=/custom/path
strata init            # Initializes at /custom/path
strata add note.md "# Hello"  # Writes to /custom/path/active/note.md
```

Resolution order for `base_dir`: `$STRATA_HOME` > `./strata_data/` (project-local) > `~/.strata/` (global fallback).

## Daemon Mode

The daemon automates the Janitor operations. It runs silently in the background and loops through migration and eviction. The first cycle defaults to a dry run unless you pass `--live`.

Without the daemon, your memories stay in the active stratum forever. The Janitor never runs. You lose the whole benefit of automatic tiered decay. If you want Strata to actually cycle memories between tiers, the daemon needs to be running.

### Run as a background process

```bash
strata serve &

# Check status
strata status
# → Daemon: RUNNING (pid=12345)
# → Cycles completed: 3

# View the log
strata history
# → 2026-06-09 02:00:00 [Cycle 1] Migrated: 3, Evicted: 0

# Stop when needed
strata stop
```

This runs until you stop it or reboot. Solid for development and short-lived sessions.

### Run as a systemd service (recommended for production)

Persists across reboots, auto-restarts on failure, logs to journald:

```bash
# Install the service (copies unit file to ~/.config/systemd/user/)
strata install-service

# Enable and start now
systemctl --user daemon-reload
systemctl --user enable --now strata

# Check status
systemctl --user status strata

# Tail logs
journalctl --user -u strata -f

# Stop
systemctl --user stop strata

# Uninstall
systemctl --user disable --now strata
strata uninstall-service
systemctl --user daemon-reload
```

The service runs with security hardening (`NoNewPrivileges=true`, `ProtectHome=read-only`, `ProtectSystem=strict`). It logs to journald instead of `strata.log`.

### Daemon vs manual lifecycle

You don't actually need the daemon at all. You can run lifecycle stuff explicitly:

```bash
strata maintenance          # Run both migration and eviction now
strata maintenance --dry-run  # Preview what would happen
```

But the daemon is the only way to get fully automatic tiered memory. Without it, stale files pile up in the active stratum indefinitely.

## Agent Integration

You've got four ways to connect Strata to an AI agent:

### 1. CLI (recommended)

```bash
strata add path/to/doc.md "# content"
strata search "query"
strata read path/to/doc.md
strata list

```

### 2. Python API

```python
from strata import Strata
strata = Strata()
strata.write_active("path/doc.md", "# content")

```

### 3. Function-calling tools

```python
tools = strata.tools.all_schemas()

```

### 4. MCP protocol

```bash
strata mcp

```

### Skill Install

Strata includes a skill specifically for AI coding assistants. Once it's installed, your agent automatically understands the commands and the architecture.

```bash
# Interactive
strata skill install

# Non-interactive, global
strata skill install --global

```

This works across 55+ agent formats (including OpenCode, Claude Code, Pi, Cursor, Codex, and Windsurf). You'll need Node.js for the `npx skills add` command.

### Pi Extension

You can also install the Strata extension for the Pi coding agent:

```bash
strata pi-install

```

## Search Backends

Strata provides three search modes. You pick one during init or swap it later.

### 1. FTS5 Keyword Search (default)

The system gracefully handles missing dependencies. If you skip installing QMD, search drops back to filesystem grep across `active/` and `cooled/`, plus SQLite FTS5 queries against the Shadow Index for archived files. Zero external dependencies. Works wherever Python runs.

### 2. QMD Hybrid Search (optional, recommended)

[QMD](https://github.com/tobi/qmd) by Tobias Lütke brings BM25 full-text and vector search. Still no LLM calls anywhere in sight. Vectors generate locally on your machine:

```bash
npm install -g @tobilu/qmd
strata qmd-setup
strata qmd-embed
strata search "..."  # Now uses hybrid search

```

### 3. QMD with LLM Rerankers (optional)

You can plug a reranker provider (OpenAI, Ollama, etc.) into QMD for better relevance scoring. This is the only search path that actually touches an LLM. Entirely optional  -  you won't miss it unless you're chasing those last few relevance points.

## Why Files

Every single memory in Strata exists as a plain file on your disk. No database rows, no graph nodes. Just standard `.md` files.

Files are the most agent-native format available right now.

* You can `cat`, `vim`, or `grep` them.
* Piping them into standard unix tools works flawlessly.
* Git handles version control like a champ.

No SDKs. No APIs. No database drivers. You just use the filesystem  -  which every operating system has supported since 1971, give or take.

## Project Structure

```text
~/.strata/                    # Or ./strata_data/ for local projects
├── active/                   # 1st Stratum  -  working memory
│   ├── index.md              # Auto-generated master map
│   └── ...                   # No preset folders — AI organises organically
├── cooled/                   # 2nd Stratum — aged-out files
├── archive/                  # 3rd Stratum — cold JSON storage
├── shadow.db                 # Shadow Index (SQLite FTS5)
├── strata.log                # Daemon activity log
├── strata.pid                # Daemon PID file
└── strata.json               # Persisted configuration

```

## Comparison

| System | Storage Layer | Data Migration | Lifecycle AI Calls | Search Mechanism |
| --- | --- | --- | --- | --- |
| **mem0** | Graph DB | Manual only | Per query + maintenance | Semantic + graph traversal |
| **LangMem** | LangGraph BaseStore (Vectors) | Manual only | High (extracts/updates prompts) | Vector similarity |
| **Karpathy's LLM Wiki** | Plain Markdown | No tiers (active graph) | High (compiles/links notes) | Semantic + keyword |
| **OpenClaw** | Markdown files + SQLite | No active decay | Low (turn summarization) | QMD hybrid / built-in |
| **OpenBrain** | Supabase (Postgres) | No active decay | Low (RAG extraction) | pgvector semantic + keyword |
| **Strata** | Filesystem + SQLite | **Yes (bidirectional  -  Algorithmic Janitor)** | **Zero** | FTS5 + optional QMD |

## What Strata Doesn't Do

* **No LLM calls during lifecycle management.** The Janitor watches timestamps instead of evaluating semantics. You pay nothing in token costs.
* **Vector databases are strictly optional.** Search defaults to grep and FTS5. Add vectors later with QMD if you really want them.
* **Graph databases are excluded.** Relationship context lives in the directory structure. That's it.
* **No external API keys needed.** Everything runs locally.
* **Distributed consensus isn't part of the design.** You get a single filesystem for a single agent. It's a memory space, not a production database.

The underlying philosophy is brutally simple. Information naturally decays over time. Don't fight it  -  build around it. Forgetting is what makes memory useful. The real question is how to store each piece of information at the fidelity it deserves, for exactly as long as it's relevant.

---

**Version:** 0.2.0 (in beta)

**License:** MIT

**Author:** Jeremy Kamber

**Links:** [GitHub](https://github.com/jeremykamber/strata-memory) · [Substack](https://substack.com/@jeremykamber) · [Blog](https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents)
