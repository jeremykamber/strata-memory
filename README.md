# Strata — Tiered Memory for AI Agents

**Zero-dependency memory system for AI agents.** Structured decay, asynchronous consolidation, portable to any LLM and any agent harness.

```python
from strata import Strata
from strata.config import StrataConfig

config = StrataConfig(base_dir="./my_memory")
strata = Strata(config)

# Active working memory (1st Stratum)
strata.write_active("projects/kynd/requirements.md", "# Kynd Requirements\n...")

# Search across all tiers
results = strata.query("kynd requirements")

# Run lifecycle maintenance
strata.run_maintenance()
```

## Why Strata?

Current memory systems fail because they treat context as a flat plane. Vector databases burn tokens on every query, and monolithic context windows degrade reasoning at scale.

**Strata fixes this with three insights:**

1. **Information decays over time** — a memory from today needs higher fidelity than one from two years ago
2. **Separate the decision from the act** — algorithmic triggers (file age, access frequency) decide *when* to move data; LLMs only run *to compress it*
3. **File systems beat fuzzy databases for what's important** — for active work, a markdown file in a known directory beats a vector search every time

## Strata

| Stratum | Name | Backend | Latency | Retention |
|------|------|---------|---------|-----------|
| 1st Stratum | Active Shell | Filesystem (Markdown) | ~1ms | Configurable decay (default 14-60 days) |
| 2nd Stratum | Medium-Term Orbit | SQLite + FTS5 | ~5ms | LRU eviction (default 90 days stale) |
| 3rd Stratum | Cold Archive | Flat JSON + Shadow Index | ~10ms | Infinite (keyword-retrievable) |

## Quick Start

### Installation

```bash
# Core (zero dependencies)
pip install strata-memory

# With LLM compression support
pip install strata-memory[openai]   # OpenAI
pip install strata-memory[anthropic] # Anthropic
pip install strata-memory[all]      # Both
```

### Initialize

```bash
strata init
```

Creates `./strata_data/active/{projects, entities, gtd}/`.

### Basic Usage

```python
from strata import Strata
from strata.config import StrataConfig

config = StrataConfig(base_dir="./my_strata")
strata = Strata(config)

# ── 1st Stratum: Active Working Memory ────────────────────────

# Write context the agent needs now
strata.write_active("projects/koda/schema.md", """
# Koda Database Schema
- users: id, email, name, created_at
- projects: id, name, owner_id, status
- subscriptions: id, user_id, plan, expires_at
""")

strata.write_active("entities/joe.md", "# Joe Smith\nRole: Software Engineer\nSkills: React, Go, PostgreSQL")

# Read it back exactly
schema = strata.read_active("projects/koda/schema.md")

# List available context
files = strata.list_active("projects/koda")

# ── Query Across All Tiers ────────────────────────────────

# Searches 1st Stratum → 2nd Stratum → 3rd Stratum in cascade
results = strata.query("koda database schema")
for r in results:
    print(f"[{r['tier']}] {r['source']}: {r['content'][:80]}")

# With entity tag filters
results = strata.query("joe", filters={"tags": ["engineer"]})

# ── Store and Retrieve Memory Blocks ──────────────────────

from strata.models import MemoryBlock

block = MemoryBlock(
    summary="Koda v2 uses PostgreSQL with pgvector for semantic search across all customer data",
    entity_tags=["koda", "postgresql", "architecture"],
    metadata={"decision": "pgvector chosen over elasticsearch"},
)
memory_id = strata.store_memory(block)

retrieved = strata.get_memory(memory_id)

# ── Lifecycle Maintenance ─────────────────────────────────

# Migrate stale 1st Stratum files to 2nd Stratum (with LLM compression)
report = strata.migrate(dry_run=True)       # Preview first
report = strata.migrate(dry_run=False)      # Execute

# Evict cold 2nd Stratum memories to 3rd Stratum archive
report = strata.evict()

# Full cycle in one call
report = strata.run_maintenance()

# ── Cleanup ───────────────────────────────────────────────

strata.close()

# Or use the context manager:
with Strata(config) as s:
    s.write_active("projects/test.md", "# Test")
```

### With LLM Compression

```python
from strata import Strata
from strata.janitor import Janitor
from strata.providers import openai_compress

strata = Strata()
strata.janitor.llm_compress = openai_compress(api_key="sk-...", model="gpt-4o-mini")

# Now migration will compress files via LLM instead of raw truncation
strata.migrate()
```

## Agent Integration (OpenAI-Compatible Tools)

Strata exposes 5 function-calling tools that work with any LLM harness:

```python
# Get all tool schemas (OpenAI format)
tools = strata.tools.all_schemas()
```

| Tool | Description |
|------|-------------|
| `strata_read_active` | Read a file from active memory by path |
| `strata_write_active` | Write a file to active memory (creates dirs) |
| `strata_list_active` | List files/directories in active memory |
| `strata_query` | Cascade search across all 3 tiers |
| `strata_forget` | Explicitly archive a 2nd Stratum memory to 3rd Stratum |

### Integration with OpenAI

```python
from openai import OpenAI
client = OpenAI()

system = "You have access to a Strata memory system. Use the tools below."

messages = [
    {"role": "system", "content": system},
    {"role": "user", "content": "What do we know about Koda's schema?"},
]

# Get tool schemas and call OpenAI
tools = strata.tools.all_schemas()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
)

# Execute any tool calls the model makes
for choice in response.choices:
    if choice.finish_reason == "tool_calls":
        for tc in choice.message.tool_calls:
            result = strata.tools.execute(
                tc.function.name,
                json.loads(tc.function.arguments),
            )
```

### Integration with Anthropic

```python
from anthropic import Anthropic
client = Anthropic()

# Convert schemas to Anthropic tool format
tools = [
    {"name": s["function"]["name"], "description": s["function"]["description"],
     "input_schema": s["function"]["parameters"]}
    for s in strata.tools.all_schemas()
]
```

## Configuration

```python
from strata.config import StrataConfig

config = StrataConfig(
    base_dir=Path("./strata_data"),

    # How many days before a file is "stale" enough to migrate
    # Key is first directory segment, "*" is default
    decay_thresholds={
        "projects": 14,    # Active projects decay after 2 weeks
        "entities": 60,    # Entity profiles last 2 months
        "gtd": 7,          # Tasks decay after 1 week
        "*": 30,           # Default for everything else
    },

    # 2nd Stratum → 3rd Stratum LRU eviction
    lru_days=90,             # Evict if last accessed >90 days ago
    lru_min_access_count=1,  # And accessed ≤1 time

    # LLM compression (optional)
    llm_provider="openai",
    llm_model="gpt-4o-mini",

    # Embedding (optional)
    embedding_model="text-embedding-3-small",
)
```

## CLI Reference (Standalone Tool)

Strata runs as a standalone CLI tool — like `mem0` but with structured decay.

```bash
# Initialization
strata init                    # Create directory structure

# Active Memory (1st Stratum)
strata add <path> <content>    # Write a file
echo "content" | strata add <path>   # Pipe content
strata add --text "quick note" # Auto-routed to gtd/
strata read <path>             # Read a file
strata list [path]             # List directory
strata list-stratum-2             # List 2nd Stratum memories

# Search
strata search <query>          # Human-readable search across all tiers
strata query <text>            # JSON search output (for scripting)

# Lifecycle Management
strata migrate                 # Migrate stale 1st Stratum → 2nd Stratum
strata migrate --dry-run       # Preview without changes
strata evict                   # Evict cold 2nd Stratum → 3rd Stratum
strata evict --dry-run         # Preview evictions
strata maintenance             # Full lifecycle cycle

# Daemon (Automatic Lifecycle)
strata serve                   # Start background Janitor daemon
strata serve --interval=300    # Check every 5 minutes
strata serve --live            # Skip initial dry-run
strata daemon                  # Alias for serve
strata stop                    # Stop running daemon
strata restart                 # Restart daemon

# System
strata status                  # Show state + daemon status
strata config                  # Show current configuration
strata history                 # Show Janitor daemon log
strata forget <memory-id>      # Archive a specific memory

# MCP Protocol (for AI agent integration)
strata mcp                     # Start MCP server over stdio
```

### Daemon Mode (Set and Forget)

The daemon is what makes Strata a "set and forget" memory system. It runs in the background and automatically handles memory lifecycle:

```bash
# Start the daemon (checks every 15 minutes by default)
strata serve &

# First cycle is always a dry-run for safety
# After dry-run confirms actions, subsequent cycles run live

# Check status while daemon is running
strata status
# → Daemon: RUNNING (pid=12345)
# → Cycles completed: 3
# → 1st Stratum: 2 stale files pending
# → 2nd Stratum: 15 memory blocks
# → 3rd Stratum: 42 shadow entries

# View the daemon log
strata history --lines=50
# → 2026-01-15 02:00:00 [INFO] [Cycle 1] Starting maintenance (DRY RUN)
# → 2026-01-15 02:00:00 [INFO] [Cycle 1] Migrated: 3, Evicted: 0
# → 2026-01-15 02:15:00 [INFO] [Cycle 2] Starting maintenance (LIVE)
# → 2026-01-15 02:15:00 [INFO] [Cycle 2] Migrated: 3, Evicted: 0
```

The daemon:
- Runs Janitor maintenance on a configurable interval (default: 900s/15min)
- Logs all activity to `{base_dir}/strata.log`
- Creates a PID file at `{base_dir}/strata.pid`
- Responds to SIGINT/SIGTERM for graceful shutdown
- Starts with a dry-run cycle (configurable via `--live`)
- Handles both migration (1st Stratum → 2) and eviction (2nd Stratum → 3) automatically

### MCP Server

For AI agent integration, start the MCP protocol server:

```bash
# Start MCP server over stdio (compatible with any MCP client)
strata mcp
```

This exposes all 5 Strata tools via the Model Context Protocol. Any MCP-compatible agent (Claude Code, OpenClaw, custom agents) can connect and use Strata as a memory backend:

```json
// Client sends:
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
// Server responds:
{"jsonrpc":"2.0","id":1,"result":{"tools":[
  {"name":"strata_read_active","description":"Read...","inputSchema":{...}},
  {"name":"strata_write_active","description":"Write...","inputSchema":{...}},
  {"name":"strata_list_active","description":"List...","inputSchema":{...}},
  {"name":"strata_query","description":"Search...","inputSchema":{...}},
  {"name":"strata_forget","description":"Archive...","inputSchema":{...}}
]}}
```

Supports stdio transport (line-delimited JSON-RPC 2.0). Zero dependencies.

## Re-hydration

When a query finds a result in 3rd Stratum (the cold archive), it returns `{_needs_rehydration: true}`. The agent can then rehydrate it back to 2nd Stratum:

```python
for r in results:
    if r["tier"] == "stratum_3" and r["metadata"].get("_needs_rehydration"):
        block = strata.janitor.rehydrate(r["metadata"])
        if block:
            print(f"Rehydrated: {block.summary[:80]}")
```

## Project Structure

```
strata_data/
├── active/                    # 1st Stratum: Active Shell
│   ├── projects/              # Current initiatives + sprints
│   ├── entities/              # People, companies, tools
│   └── gtd/                   # Immediate tasks
├── stratum_2.db                  # 2nd Stratum: SQLite + FTS5
├── archive/                   # 3rd Stratum: Cold JSON files
└── shadow.db                  # 3rd Stratum: Shadow Index (SQLite)
```

## How Migration Works (No LLM Required)

Without an LLM provider, migration truncates the raw file content (first 2000 chars) and infers tags from the file path:

```
projects/koda-api/schema.md → tags: ["projects", "Koda-Api Schema"]
raw_content[:2000]           → summary
```

With an LLM provider, the full content is sent for compression:
```
"Compress this into a Memory Block: extract outcomes, decisions, entities..."
```

## How Eviction Works

The Janitor queries 2nd Stratum for memories where `last_accessed` is older than `lru_days` AND `access_count` is ≤ `lru_min_access_count`. It writes the full memory block to a JSON file in `archive/`, creates a keyword-searchable entry in the Shadow Index (`shadow.db`), then deletes from 2nd Stratum.

## The Shadow Index

The Shadow Index is a lightweight SQLite database with FTS5 full-text search. It stores only:
- Original memory UUID
- Entity tags (keywords)
- Archive file path
- 200-character summary preview

This keeps the cold archive searchable at near-zero storage cost.

---

**License:** MIT
**Author:** Jeremy Kamber
**Version:** 0.1.0
