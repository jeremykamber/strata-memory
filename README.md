# Strata — Tiered Memory for AI Agents

**CLI-first, stdlib-first memory system for AI agents.** Install it, run `strata init`, and your agent has a three-tier memory system — no API key, no database, no vector search.

```bash
# Install from source (PyPI publishing coming soon)
pip install git+https://github.com/jeremykamber/strata-memory.git

# Initialize your global memory store
strata init

# Write a memory
strata add projects/koda/requirements.md "# Koda needs OAuth2 + payments"

# Search across all layers
strata search "koda oauth2"
```

**Or use it programmatically from Python:**

```python
from strata import Strata
strata = Strata()
strata.write_active("projects/koda/requirements.md", "# Koda needs OAuth2 + payments")
results = strata.query("koda oauth2")
strata.run_maintenance()
```

Think of it like geological strata — your most recent memories sit in the top layer where you can grab them instantly. As they age, they settle into deeper layers. But unlike real rock, they can be brought back to the surface when needed.

**For AI coding assistants:** install the Strata skill and your agent will know Strata's commands and architecture automatically. [Jump to Skill Install →](#skill-install)

Interested more of the conceptual, "head in the clouds" stuff? [Check out the blog post.](https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents)

## Why Strata?

Current memory systems treat all information the same. A conversation from five minutes ago and a decision from six months ago get identical treatment — same storage, same retrieval cost, same fidelity. That's wasteful.

**Strata fixes this with a simple idea:** memories age like geological strata. Fresh memories sit on top where you can reach them fast. Old memories settle into deeper layers. But unlike rocks, they can be brought back when dug up.

Three insights make this work:

1. **Information decays** — a memory from today deserves higher fidelity than one from two years ago
2. **Don't pay an LLM to check the time** — algorithmic triggers (file age, access count) decide *when* to move data; no AI needed for that
3. **Files are the fastest database** — for active work, reading a markdown file from a known path beats any vector search

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    STRATA ARCHITECTURE                   │
├─────────────┬──────────────┬────────────────────────────┤
│ 1st Stratum │ 2nd Stratum  │ 3rd Stratum               │
│ (active/)   │ (cooled/)    │ (archive/ + shadow.db)    │
├─────────────┼──────────────┼────────────────────────────┤
│ Agent reads │ Query-only   │ Cold storage              │
│ and writes  │ (Janitor     │ with keyword              │
│ here        │  manages)    │ shadow index              │
├─────────────┼──────────────┼────────────────────────────┤
│ ~1ms access │ ~5ms access  │ ~10ms via re-hydration    │
│ Filesystem  │ Filesystem   │ JSON blobs + SQLite FTS5  │
└──────┬──────┴──────┬───────┴────────────┬───────────────┘
       │             │                    │
       ▼             ▼                    ▼
  ┌─────────┐  ┌─────────┐         ┌──────────┐
  │ Janitor │─►│ Janitor │─►       │ Shadow   │
  │ migrate │  │ evict   │  ──►    │ Index    │
  │ 1st→2nd │  │ 2nd→3rd │         │ (search) │
  └─────────┘  └─────────┘         └──────────┘
```

**The Janitor** is the only thing that moves data between layers. It runs on a schedule (every 15 min by default) and uses simple rules — no LLM calls needed.

## Quick Start

Strata is a CLI first — agents use it via shell commands. The Python API is also available for programmatic use.

### Install

```bash
# Install from source (PyPI publishing coming soon)
pip install git+https://github.com/jeremykamber/strata-memory.git

# Or local development install:
# cd strata-memory && pip install -e .
```

Zero external pip dependencies. Works anywhere Python 3.9+ runs.

### CLI — use globally (recommended)

```bash
strata init            # Creates ~/.strata/ — your global memory store
strata add projects/idea.md "# My idea"
strata search "idea"
```

### CLI — per-project

```bash
cd my-project
strata init --local    # Creates ./strata_data/
strata add docs/spec.md "# Project spec"
strata search "spec"
```

### Python API

Use Strata programmatically from Python scripts and applications:

```python
from strata import Strata

# Auto-detects: uses ./strata_data/ if it exists, else ~/.strata/
strata = Strata()

# ── 1st Stratum: Working memory ──────────────────────────
# Write markdown files. They're real files on disk.
strata.write_active("projects/koda/spec.md", """# Koda Platform
Stack: React + Go + PostgreSQL
Features: OAuth2, Stripe, real-time dashboard
""")

strata.write_active("entities/joe.md", "# Joe: React/Go engineer on Koda team")

# Read it back — exact, no fuzzy search
schema = strata.read_active("projects/koda/spec.md")

# List what's available
files = strata.list_active("projects")

# ── Search across all layers ─────────────────────────────
results = strata.query("koda oauth2")
for r in results:
    print(f"[{r['tier']}] {r['source']}: {r['content'][:80]}")

# ── Lifecycle ────────────────────────────────────────────
# Preview what the Janitor would do
strata.migrate(dry_run=True)

# Execute migration (1st → 2nd Stratum)
strata.migrate()

# Execute eviction (2nd → 3rd Stratum)
strata.evict()

# Both at once
strata.run_maintenance()
```

## Skill Install — Make Any Agent Strata-Aware

Strata ships with an agent skill that teaches AI coding assistants how to use Strata's commands and architecture. Once installed, your agent knows about `strata init`, `strata add`, `strata search`, and the three-tier architecture — without being told.

```bash
# Interactive — follow the prompts to choose scope + agents
strata skill install

# Non-interactive — install globally to all agents at once
strata skill install --global
```

**Works with:** OpenCode, Claude Code, PI, Cursor, Codex, Windsurf, and any agent that supports the [Vercel Skills](https://github.com/vercel-labs/skills) protocol (55+ agent formats).

Requires Node.js. Delegates to `npx skills add` under the hood.

**Why this matters:** Without the skill, you'd have to tell your agent about Strata every session. With it, the agent already knows the commands, the architecture, and how to use each stratum. One install, zero repetition.

## Agent Plugins

Strata ships with native plugins for AI coding assistants, going beyond the CLI with automatic memory context injection and lifecycle management.

### PI Extension (Available Now)

The [Pi coding agent](https://pi.ai) extension at `skills/pi/strata.ts` provides:

- **Auto-injected system prompt** — the agent knows about Strata's tiers and commands on every session start
- **Auto-memory storage** — after each turn, the extension evaluates whether the response contains information worth persisting
- **Two-phase decision pipeline** — uses a configurable LLM classifier (OpenAI, Anthropic, or OpenRouter) when enabled, with a zero-dependency regex heuristic as fallback
- **Semantic path routing** — LLM-suggested titles and categories organize memories into `pi/<category>/<title>.md`

Install with `strata pi-install`, then `/reload` in Pi. The LLM classification is off by default -- enable it by creating `pi-config.json` in your Strata store. See the [Pi Integration](docs/pi-integration.md) documentation for details.

### OpenCode Plugin (Coming Soon)

Full Strata integration via OpenCode's plugin system with tool calling, automatic context injection, and lifecycle management.

### OpenClaw Plugin (Coming Soon)

OpenClaw harness integration with automatic context injection.

## CLI Reference

```bash
# Setup
strata init                # Create ~/.strata/ (global)
strata init --local        # Create ./strata_data/ (project)
strata init --global       # Force ~/.strata/

strata config              # Show settings
strata status              # Show system state

# Writing (1st Stratum only — working memory)
strata add <path> <content>
echo "note" | strata add <path>
strata add --text "quick note"

# Reading
strata read <path>         # Read a file
strata list [path]         # List files

# Searching (all three layers)
strata search <query>      # Human-readable
strata query <text>        # JSON (for scripts)

# Lifecycle
strata migrate             # Move stale files to cooled/
strata evict               # Move cold files to archive/
strata maintenance         # Both at once
strata forget <path>       # Archive a specific file

# Daemon (background Janitor)
strata serve               # Start (checks every 15 min)
strata serve --interval=300# Every 5 min
strata stop                # Stop daemon
strata restart             # Restart
strata history             # View daemon log

# Agent integration
strata mcp                 # MCP protocol server
strata --agent-help        # Agent usage guide
strata skill install       # Install Strata skill for AI coding assistants (interactive)
strata skill install --global  # Install globally to all agents (non-interactive)

# QMD (optional hybrid search)
strata qmd-setup           # Add collections
strata qmd-embed           # Generate embeddings
```

## How the Strata Work

### 1st Stratum — Active (surface layer)

Fastest layer. Plain markdown files in `active/`. The agent reads and writes here directly. There's no database, no vector index — just files on disk.

The `index.md` file is auto-generated and acts as the master map. When the agent needs context, it reads `index.md` first, then navigates to the right file by path.

```bash
strata add projects/koda/spec.md "# Koda spec"
cat strata_data/active/index.md
# → Lists every file with its heading as description
```

**Agent rule:** Full read/write access. This is your workspace.

### 2nd Stratum — Cooled (middle layer)

When a file hasn't been touched for a while (configurable: 14 days for projects, 60 for entities), the Janitor moves it from `active/` to `cooled/`. It's still a markdown file on disk. The only difference is the agent can't write to it directly.

```bash
strata migrate              # Janitor moves stale files
strata list-stratum-2       # See what's in cooled/
strata search "query"       # Searches cooled/ too (read-only)
```

**Agent rule:** Read-only via search. If you need to edit something, the Janitor can rehydrate it back to active.

### 3rd Stratum — Archive (deep layer)

When a cooled file hasn't been accessed in months (default: 90 days), the Janitor evicts it to `archive/`. The full content is saved as JSON. A lightweight Shadow Index (SQLite FTS5) keeps it searchable by keyword.

```bash
strata evict                # Janitor archives old files
strata search "old project" # Still finds it via shadow index
# → Shows "_needs_rehydration: true"
```

**Agent rule:** Can't write here either. Archived files can be rehydrated back to active when needed.

### The Shadow Index

This is what makes Strata different from mem0 or QMD. When a file is archived, the Janitor doesn't just delete it. It stores a "ghost" entry in a tiny SQLite database — just keywords, a 200-char preview, and a file path to the JSON. A million ghosts cost practically nothing.

When you search and don't find anything in active or cooled, Strata hits the Shadow Index. If it finds a match, it reads the archived JSON and puts the file back in active. The memory resurfaces because it proved useful again.

## Agent Integration

Strata exposes **both a CLI and a Python API.** The CLI is the most natural interface for AI agents that can run shell commands. The Python API is available for programmatic use in scripts and applications.

### CLI (recommended for agents)

```bash
strata add path/to/doc.md "# content"
strata search "query"
strata read path/to/doc.md
strata list active/
```

### Python API

```python
from strata import Strata
strata = Strata()
strata.write_active("path/to/doc.md", "# content")
strata.query("query")
strata.list_active()
```

### Via function-calling tools

Strata also exposes 5 function-calling tools in OpenAI format:

| Tool | What it does |
|------|-------------|
| `strata_read_active` | Read a file from active/ |
| `strata_write_active` | Write a file to active/ |
| `strata_list_active` | List files in active/ |
| `strata_query` | Search across all 3 strata |
| `strata_forget` | Archive a cooled file to archive/ |

```python
# Get tool schemas
tools = strata.tools.all_schemas()

# Execute a tool call
result = strata.tools.execute("strata_query", {"query": "koda"})
```

Works with OpenAI, Anthropic, OpenClaw, or any harness that speaks function calling. Native plugins for these platforms are [coming soon](#upcoming--agent-plugins).

## Configuration

```python
from strata.config import StrataConfig

config = StrataConfig(
    # How many days before a file is "stale" enough to migrate
    # Key is first directory name, "*" is the default
    decay_thresholds={
        "projects": 14,    # Active projects: 2 weeks
        "entities": 60,    # People/companies: 2 months
        "gtd": 7,          # Tasks: 1 week
        "*": 30,           # Everything else: 1 month
    },

    # Eviction from cooled → archive
    lru_days=90,            # Evict if not accessed in 90 days
    lru_min_access_count=1, # And accessed ≤ 1 time
)
```

## Daemon Mode

The daemon automates the Janitor. It runs in the background and handles migration + eviction on a schedule:

```bash
strata serve &

# Check on it
strata status
# → Daemon: RUNNING (pid=12345)
# → Cycles completed: 3

# See what it's been doing
strata history --lines=20
# → 2026-01-15 02:00:00 [Cycle 1] Migrated: 3, Evicted: 0
# → 2026-01-15 02:15:00 [Cycle 2] Migrated: 0, Evicted: 1

# Stop when you want
strata stop
```

## QMD Integration (Optional)

[QMD](https://github.com/tobi/qmd) by Tobias Lütke is a local hybrid search engine. If you have it installed, Strata can use it for BM25 + vector search — still no LLM calls:

```bash
npm install -g @tobilu/qmd
strata qmd-setup     # Add active/ + cooled/ as collections
strata qmd-embed     # Generate vector embeddings
strata search "..."  # Now uses BM25 + vector fusion
```

Without QMD, search falls back to built-in filesystem grep. Works either way.

## Project Structure

```
~/.strata/                    # Or ./strata_data/ for local
├── active/                   # 1st Stratum — working memory
│   ├── index.md              # Auto-generated master map
│   ├── projects/             # Current initiatives
│   ├── entities/             # People, companies, tools
│   └── gtd/                  # Tasks
├── cooled/                   # 2nd Stratum — aged-out files
├── archive/                  # 3rd Stratum — cold JSON storage
├── shadow.db                 # Shadow Index (SQLite FTS5)
├── strata.log                # Daemon activity log
└── strata.pid                # Daemon PID file
```

## Why Files?

Every memory in Strata is a plain markdown file on disk. Not a blob in a database. Not a node in a graph. A file.

This matters because:
- **The agent can grep it.** `grep -r "OAuth2" strata_data/`
- **The agent can edit it.** `vim strata_data/active/projects/koda/spec.md`
- **The agent can pipe it.** `cat strata_data/active/index.md | head -20`
- **The agent can version it.** `git add strata_data && git commit -m "update"`

No API calls needed. No SDK required. Just files.

---

**License:** MIT

**Author:** Jeremy Kamber

**Version:** 0.2.0

**Follow development:** [Substack](https://substack.com/@jeremykamber) | [Blog](https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents)
