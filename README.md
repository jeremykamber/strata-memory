# Strata

**Tiered memory for AI agents.** One install, one `strata init`, and you have a three-layer memory system. It bypasses API keys, vector databases, and background LLM janitors that burn tokens on every query.

```bash
pip install git+[https://github.com/jeremykamber/strata-memory.git](https://github.com/jeremykamber/strata-memory.git)

strata init
strata add projects/kynd/requirements.md "# Kynd needs OAuth2 + payments"
strata search "oauth2 payments"

```

I named it after rock layers. Each stratum represents a different depth of memory. Active items sit at the surface where your agent grabs them fast; old items settle into deeper layers over time. Information decays on purpose. That is a deliberate design choice. A system that remembers every single detail is functionally identical to a system that remembers nothing at all. The signal gets drowned out by the noise. Perfect recall is an anchor.

---

## The Problem

Most memory systems treat every piece of data identically. A passing thought from five minutes ago and a core architectural decision from six months ago get the exact same storage, retrieval, and fidelity. That wastes resources in two major ways.

First, vector search degrades as the document count rises. Eventually every document becomes semantically similar to every other document. You end up digging through your own haystack to find a needle that should have been on your desk.

Second, developers try to solve this by running an LLM-powered background process on every query. Every single read, write, or search triggers an API call to clean and prioritize those memories. Your API credits disappear quickly. The LLM then has to judge incoming data against potentially hundreds of existing memories; this gets harder and more expensive the more you use the system.

Human memory works through compression and neglect. We actively remember what we use, and we forget what we ignore. Our brains push old conversations to the background (eventually letting them fade out completely). Autonomous systems need this exact mechanic to function long-term. Structured decay beats throwing more compute at the problem.

## What Makes Strata Different

Two specific choices define the architecture.

**Active memory remains physically separated from long-term storage.** The agent only interacts with a small subset of memories at any given moment. It never gets bogged down by old context it stopped touching weeks ago.

**The migration trigger is algorithmic.** File age and access recency dictate what shifts between the tiers. There is no LLM getting paid to guess if a file is old. That job belongs to simple system timestamps.

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

The Janitor moves data between the layers. It runs on a schedule or whenever you call it. It relies entirely on simple rules; there are no LLM calls, no text compression, and no token spend.

### 1st Stratum — Active (the surface layer)

This functions as the agent's working memory. You get plain markdown files inside a standard directory tree. You won't find a database or a vector index here.

The agent reads `active/index.md` first. This auto-generated map lists every file and uses the first heading as the description. The agent looks at the map, picks a path, and reads the target file directly. You bypass vector search and embedding noise completely; things are exactly where you put them.

Write structured markdown with clear headings. The index grabs the first `# heading` to use as the file's description.

**Agent rule:** Full read/write access. This acts as the main workspace.

**Transition trigger:** The Janitor checks the modification time. If a file sits untouched past its decay threshold (the default is 14 days for projects, 60 for entities, and 7 for tasks), it becomes eligible for migration.

### 2nd Stratum — Cooled (the middle layer)

The Janitor copies aged-out files from `active/` to `cooled/`. It stays a standard markdown file on your disk. The agent can search and read it; direct writes are blocked.

**Agent rule:** Read-only access through `strata search`. Queries return the results directly. Editing the file requires rehydration back to the active tier.

**Transition trigger:** A cooled file faces eviction when it meets two specific conditions. It must sit untouched for `lru_days` (default is 90). The access count must also be at or below `lru_min_access_count` (default is 1). A JSON sidecar file logs every read and search hit to track this access.

### 3rd Stratum — Archive (the deep layer)

Untouched cooled files eventually drop into `archive/`. The Janitor saves the full content as JSON in flat storage. A minimal entry goes into the Shadow Index (a SQLite FTS5 database) with just the keywords, a 200-character preview, and the file path. You still avoid vectors and embeddings here.

A million archived entries cost less than a megabyte of disk space.

If a future search matches an archived entry, the file rehydrates. The Janitor reads the JSON, writes it back into the active tier, and deletes the shadow entry. The memory resurfaces simply because it proved useful again.

There is a massive difference between throwing an item in the trash and packing it in a labeled box in your basement.

### The Janitor (lifecycle manager)

The Janitor runs entirely on algorithms. It checks the time instead of analyzing text.

* **Migration (1st → 2nd):** Copies the file from `active/` to `cooled/`, deletes the original, and starts the access tracking. File age triggers this step.
* **Eviction (2nd → 3rd):** Reads the file content, saves it as JSON to `archive/`, creates the FTS5 entry in `shadow.db`, and deletes the cooled copy. The LRU logic triggers this step.
* **Rehydration (3rd → 1st):** Reads the archived JSON, writes the content back to `active/` at the original path, and removes the shadow entry. A successful search match in the archive triggers this step.

You avoid all LLM calls and token spend. The Janitor just looks at the clock.

## Quick Start

### Install

```bash
pip install git+[https://github.com/jeremykamber/strata-memory.git](https://github.com/jeremykamber/strata-memory.git)

```

This requires zero pip dependencies. It works on Python 3.9 and newer.

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

# Quick note (auto-routed to gtd/)
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
#       [in archive — archived file can be rehydrated]

# JSON output
strata query "oauth2"

```

### Let the Janitor Work

```bash
# Preview first
strata migrate --dry-run
strata evict --dry-run

# Execute
strata maintenance

# Or background daemon (every 15 min by default)
strata serve &

```

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

Strata exposes five OpenAI-compatible function-calling tools:

| Tool | Purpose |
| --- | --- |
| `strata_read_active` | Read a file from active memory |
| `strata_write_active` | Write a file to active memory |
| `strata_list_active` | List files in active memory |
| `strata_query` | Search across all three tiers |
| `strata_forget` | Archive a cooled file to cold storage |

```python
# Get tool schemas for any LLM harness
tools = strata.tools.all_schemas()

# Execute a tool call
result = strata.tools.execute("strata_query", {"query": "kynd"})

```

This works with OpenAI, Anthropic, OpenClaw, or any harness supporting function calling.

### MCP Server

Strata ships with an MCP (Model Context Protocol) server for agents speaking JSON-RPC 2.0 over stdio:

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
  strata read <path>             Read a 1st Stratum file
  strata list [path]             List files and directories
  strata list-stratum-2          List 2nd Stratum (cooled) files
  strata index                   Regenerate index.md

SEARCHING (all three strata)
  strata search <query>          Human-readable results
  strata query <text>            JSON output

LIFECYCLE
  strata migrate [--dry-run]     Move stale files active/ → cooled/
  strata evict [--dry-run]       Move cold files cooled/ → archive/
  strata maintenance [--dry-run] Both at once
  strata forget <path>           Archive a specific cooled file
  strata cost                    Show estimated Janitor savings

DAEMON
  strata serve [--interval=N]    Start background Janitor daemon
  strata stop                    Stop daemon
  strata restart                 Restart daemon
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

The config persists to `strata.json` in the base directory. You can alter it at runtime:

```bash
strata config set decay_thresholds.gtd 14
strata config get lru_days
# → 90

```

## Daemon Mode

The daemon automates the Janitor operations. It runs silently in the background and loops through the migration and eviction processes. The first cycle defaults to a dry run unless you supply the `--live` flag:

```bash
strata serve &

# Check status
strata status
# → Daemon: RUNNING (pid=12345)
# → Cycles completed: 3

# View the log
strata history
# → 2026-06-09 02:00:00 [Cycle 1] Migrated: 3, Evicted: 0

strata stop

```

## Agent Integration

You have four ways to connect Strata to an AI agent:

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

Strata includes a skill specifically for AI coding assistants. Once installed, your agent automatically understands the commands and the architecture.

```bash
# Interactive
strata skill install

# Non-interactive, global
strata skill install --global

```

This works across 55+ agent formats (including OpenCode, Claude Code, Pi, Cursor, Codex, and Windsurf). You will need Node.js for the `npx skills add` command.

### Pi Extension

You can also install the Strata extension for the Pi coding agent:

```bash
strata pi-install

```

## Search Backends

Strata provides three search modes. You choose one during initialization or swap it later.

### 1. FTS5 Keyword Search (default)

The system gracefully handles missing dependencies. If you skip installing QMD, the search drops back to filesystem grep across `active/` and `cooled/`; it also runs SQLite FTS5 queries against the Shadow Index to find archived files. You need zero external dependencies. It works wherever Python runs.

### 2. QMD Hybrid Search (optional, recommended)

[QMD](https://github.com/tobi/qmd) by Tobias Lütke introduces BM25 full-text and vector search. You still avoid LLM calls completely. The vectors generate locally on your machine:

```bash
npm install -g @tobilu/qmd
strata qmd-setup
strata qmd-embed
strata search "..."  # Now uses hybrid search

```

### 3. QMD with LLM Rerankers (optional)

You can plug a reranker provider (OpenAI, Ollama, etc.) into QMD for better relevance scoring. This represents the only search path that actually touches an LLM. It remains entirely optional.

## Why Files

Every single memory in Strata exists as a plain file on your disk. It avoids database rows; it avoids graph nodes. Everything is just a standard `.md` file.

Files provide the most agent-native format available today.

* You can run `cat`, `vim`, or `grep` against them.
* Piping them into standard unix tools works flawlessly.
* Git handles the version control perfectly.

You bypass SDKs, APIs, and database drivers. You just use the filesystem (which every operating system has supported since 1971).

## Project Structure

```text
~/.strata/                    # Or ./strata_data/ for local projects
├── active/                   # 1st Stratum — working memory
│   ├── index.md              # Auto-generated master map
│   ├── projects/
│   ├── entities/
│   └── gtd/
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
| **Strata** | Filesystem + SQLite | **Yes (Algorithmic Janitor)** | **Zero** | FTS5 + optional QMD |

## What Strata Doesn't Do

* **No LLM calls during lifecycle management.** The Janitor watches timestamps instead of evaluating semantics. You pay nothing in token costs.
* **Vector databases are strictly optional.** The search defaults to standard grep and FTS5. You can add vectors later using QMD.
* **Graph databases are excluded.** Relationship context lives strictly in the directory structure.
* **External API keys aren't needed.** You rely entirely on local resources.
* **Distributed consensus isn't part of the design.** You get a single filesystem for a single agent. It functions as a memory space rather than a production database.

The underlying philosophy is extremely simple. Information naturally decays over time. You shouldn't fight that reality; you should build around it. The mechanism of forgetting actually makes memory useful. The real question is how to store each piece of information at the fidelity it deserves, for precisely the duration it remains relevant.

---

**Version:** 0.1.0 (in beta)

**License:** MIT

**Author:** Jeremy Kamber

**Links:** [GitHub](https://github.com/jeremykamber/strata-memory) · [Substack](https://substack.com/@jeremykamber) · [Blog](https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents)
