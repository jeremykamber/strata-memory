# Strata

**Tiered memory for AI agents.** You can get a three-layer memory system up and running with one install and a quick `strata init`. You don't need API keys, heavy vector databases, or large LLM calls managing complex memory graphs (and in doing so, burning several holes in your wallet).

```bash
pip install git+https://github.com/jeremykamber/strata-memory.git

strata init
strata add projects/kynd/requirements.md "# Kynd needs OAuth2 + payments"
strata search "oauth2 payments"

```

I named it after rock layers because... well, geologists are great at naming things. 

Each stratum handles a different depth of memory. Active items sit right at the surface so your agent can grab them instantly, while older notes settle into deeper layers over time.

Information decays on purpose here. That isn't a shortcoming, it's the core feature. When a system remembers everything, it basically remembers nothing because your actual signal gets completely drowned out by noise. Perfect recall is just an expensive anchor.

---

## The Problem

Most memory systems treat every piece of data like it's a VIP. A random thought from five minutes ago gets the exact same storage, retrieval, and fidelity as a massive architectural decision from six months ago. This approach breaks down in two major ways.

First, vector search gets worse as your document count goes up. Eventually, everything starts looking semantically similar to everything else. You end up hunting through your own haystack for a needle that really should have been sitting right on your desk.

Second, developers try to fix this by throwing an LLM-powered background process at every query. Every read, write, or search ends up triggering an API call to clean up and prioritize your data. The more data (memories) you have, the more the LLM has to reason about each time.

Human brains survive through compression and neglect. We actively remember what we use, and we let the rest fade. Autonomous systems need that exact same mechanic if they're going to function long-term. Structured decay is just better than throwing more compute at the problem.

## What Makes Strata Different

Two main architectural choices keep things fast and cheap:

* **Physical Separation:** Active memory stays completely separate from long-term storage. The agent only interacts with a small subset of memories at any given moment, so it never gets bogged down by old context from last month.
* **Algorithmic Migration:** File age and access recency dictate when data shifts between tiers. You don't need an LLM getting paid by the token to guess if a file is old. Simple system timestamps handle that job for free without hallucinating.

Your information naturally settles into deeper, cheaper storage, and you stop spending money just to decide what matters.

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
    ┌──────────┐       ┌──────────┐        ┌──────────┐
    │ Janitor  │ ────  │ Janitor  │ ────   │ Shadow   │
    │ migrate  │       │ evict    │        │ Index    │
    │ 1st→2nd  │       │ 2nd→3rd  │        │ (search) │
    └──────────┘       └──────────┘        └──────────┘

```

A simple script called the Janitor manages the layers. It runs on a schedule or whenever you call it manually. It relies entirely on clear rules instead of LLM calls or text compression, moving files around using timestamps and basic logic.

### 1st Stratum - Active

This is your agent's working memory, stored as plain markdown files in a standard directory tree.

The agent reads `active/index.md` first. This auto-generated map lists every file and pulls its description from the first heading. Because the agent checks the map and reads the target file directly, you completely bypass vector search and embedding noise.

When writing data, use structured markdown with clear headings. The index will grab your first `# heading` to use as the file description.

* **Agent Rule:** Full read and write access.
* **Transition Trigger:** The Janitor checks the modification time. If a file sits untouched past its threshold (default is 14 days for projects, 60 for entities, and 7 for tasks), it moves down.
* **Promotion:** When a cooled file gets accessed 3 or more times, the Janitor automatically promotes it back to `active/`. This ensures frequently-referenced context doesn't get buried just because it's old.

### 2nd Stratum - Cooled

When files age out of the active tier, the Janitor copies them over to `cooled/`. They stay on your disk as standard markdown files.

* **Agent Rule:** Read-only access through `strata search`. If the agent needs to edit a file, the system rehydrates it back to the active tier first.
* **Transition Trigger:** A cooled file faces eviction when it hasn't been touched for `lru_days` (default is 90) and its access count is at or below `lru_min_access_count` (default is 1). A tiny JSON sidecar file tracks these access stats.

### 3rd Stratum - Archive

Untouched files in the cooled tier eventually drop into `archive/`. The Janitor saves the full content as JSON in flat storage and creates a minimal entry in a SQLite FTS5 database (the Shadow Index) with keywords, a 200-character preview, and the file path.

A million archived entries cost less than a megabyte of disk space, which is great news if you hate buying hard drives. If a future search hits an archived entry, the Janitor reads the JSON, writes it back to the active tier, and clears the shadow entry.

Packing things away in a labeled box in your basement is very different from throwing them in the trash. Strata does the former.

---

## Quick Start

### Install

```bash
pip install git+https://github.com/jeremykamber/strata-memory.git

```

This package has zero pip dependencies and runs fine on Python 3.9 or newer.

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

# Quick note (auto-routes to quick-note-<ts>.md)
strata add --text "Review PR by end of day"

# Read it back
strata read projects/kynd/requirements.md

```

### Search Across Tiers

```bash
strata search "oauth2 payments"
# → [1] [ACTIVE] · score=1.50 · projects/kynd/requirements.md
#       Kynd Platform Stack: React + Go + PostgreSQL Features: OAuth2...

```

### Run Maintenance

```bash
# Preview changes first
strata migrate --dry-run

# Run the full cycle (promote → migrate → evict)
strata maintenance

```

---

## Agent Memory (Pi Extension)

Strata includes a zero-dependency Pi extension that logs your conversations and pulls out core facts using a lightweight LLM.

```bash
strata pi-install
# Then run /reload in Pi

strata config set llm.apiKey       # Prompts securely
strata config set llm.provider openrouter
strata config set llm.model openrouter/free
strata config set llm.enabled true

# Start the daemon to handle distillation
strata serve

```

Your prompts are automatically saved as transcripts. The background daemon sends these transcripts to your configured LLM and writes the extracted facts directly to `pi/facts/`, making them searchable later.

---

## Python API

```python
from strata import Strata

# Auto-detects local or global setup
strata = Strata()

# Write and read directly
strata.write_active("projects/kynd/spec.md", "# Kynd Platform\n...")
content = strata.read_active("projects/kynd/spec.md")

# Query everything
results = strata.query("oauth2 payments")

# Manual maintenance
strata.run_maintenance()

```

### Function-Calling Tools

Strata provides six OpenAI-compatible tools out of the box, including `strata_read_active`, `strata_write_active`, and `strata_query`. You can grab the schemas easily:

```python
tools = strata.tools.all_schemas()

```

### MCP Server

If your agent speaks JSON-RPC 2.0 over stdio (like Claude Code), you can spin up the built-in Model Context Protocol server:

```bash
strata mcp

```

---

## Configuration

Settings are stored in `strata.json` inside your base directory. You can adjust your decay windows or LRU thresholds directly from the CLI:

```bash
strata config set decay_thresholds.gtd 14
strata config get lru_days
# → 90

```

### Environment Variables

You can override the data directory by setting `$STRATA_HOME`. When configured, all initialization and file writes default to that specific path.

---

## Daemon Mode

The background daemon automates the Janitor's workflow. If you don't run the daemon, your files will stay in the active tier forever (making the whole tiered concept somewhat pointless).

```bash
# Start the daemon
strata serve &

# Check on it
strata status
# → Daemon: RUNNING (pid=12345)

```

For production environments, you can install it as a standard user systemd service:

```bash
strata install-service
systemctl --user enable --now strata

```

---

## Why Files?

Every memory in Strata lives as a plain text file on your disk rather than a database row or a graph node. Markdown files are the most native format available for AI agents right now. You can `cat`, `vim`, or `grep` them whenever you want, and version control works perfectly out of the box with Git. Operating systems have supported files since around 1971, so the bugs are mostly worked out by now.

---

## Project Structure

```text
~/.strata/                    # Or ./strata_data/ for local projects
├── active/                   # 1st Stratum — working memory
│   ├── index.md              # Auto-generated master map
│   └── ...                   # Organised organically by your agent
├── cooled/                   # 2nd Stratum — aged-out files
├── archive/                  # 3rd Stratum — cold JSON storage
├── shadow.db                 # Shadow Index (SQLite FTS5)
└── strata.json               # Persisted configuration

```

---

## Comparison

| System | Storage Layer | Data Migration | Lifecycle AI Calls | Search Mechanism |
| --- | --- | --- | --- | --- |
| **mem0** | Graph DB | Manual only | Per query + maintenance | Semantic + graph |
| **LangMem** | Vectors | Manual only | High | Vector similarity |
| **Strata** | Filesystem + SQLite | **Algorithmic Janitor** | **Zero** | FTS5 + optional QMD |

---

## What Strata Doesn't Do

* **No LLM calls for maintenance:** The Janitor tracks timestamps instead of analyzing semantics. You pay nothing in token costs to organize files.
* **Vector databases are optional:** Search defaults to grep and FTS5. You can bring your own vectors later with QMD if you actually want them.
* **No graph databases:** Relationship context lives inside your directory structure instead of a heavy graph layer.
* **No external API keys required:** Everything runs locally on your machine.

Forgetting things is what actually makes memory useful. Strata just focuses on storing each piece of information at the right depth for exactly as long as it matters.

---

**Version:** 0.2.0 (beta)

**License:** MIT

**Author:** Jeremy Kamber
