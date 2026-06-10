---
name: strata-memory
description: Tiered memory system for AI agents. Use when the agent needs to store, retrieve, search, or manage memories across three tiers (active/cooled/archive).
---

# Strata — Agent Skill

Strata is a tiered markdown memory system. It stores memories as plain `.md` files and moves them between three strata based on age and access patterns.

## Quick Start

Read `active/index.md` first — it lists every file with its heading as description. Navigate by path. Search across all strata when you can't find something.

```bash
# Core workflow
strata read active/index.md           # Start here
strata add projects/idea.md "# Idea"  # Write a memory
strata search "what I was thinking"   # Search all tiers
strata status                         # System state
```

## Architecture

| Stratum | Directory | Access | Contents |
|---------|-----------|--------|----------|
| 1st (Active) | `active/` | Read+Write | Working context, current projects |
| 2nd (Cooled) | `cooled/` | Query only | Aged-out files, Janitor-managed |
| 3rd (Archive) | `archive/` + `shadow.db` | Searchable via query | Cold storage + keyword index |

**You ONLY write to the 1st Stratum.** The Janitor handles migration (1st→2nd) and eviction (2nd→3rd) automatically.

## Commands

### Read/Write
- `strata add <path> <content>` — Write a file (`strata add projects/koda/spec.md "# Spec..."`)
- `strata read <path>` — Read from any stratum (cascades active → cooled → archive). Reading cooled files tracks access and auto-promotes after 3 reads. Reading archived files auto-rehydrates to active.
- `strata list [path]` — List files (`strata list projects`)

### Search (all tiers)
- `strata search <query>` — Human-readable search across active/ + cooled/ + archive/
- `strata query <query>` — Same as search, JSON output for scripting

### Lifecycle
- `strata migrate` — Move stale active/ files to cooled/
- `strata promote` — Batch-promote hot cooled files to active/ (automatic on read, but this catches leftovers)
- `strata evict` — Move cold cooled/ files to archive/
- `strata maintenance` — Full cycle: promote → migrate → evict
- `strata rehydrate <id>` — Restore an archived file to active or cooled"

### Daemon
- `strata serve [--interval=N]` — Start automatic Janitor
- `strata stop` — Stop daemon
- `strata status` — Show state + daemon health

### Config
- `strata config` — Show thresholds, paths
- `strata index` — Regenerate `active/index.md`

## QMD (Optional Hybrid Search)

If `@tobilu/qmd` is installed:
```bash
strata qmd-setup    # Add active/ + cooled/ as QMD collections
strata qmd-embed    # Generate vector embeddings
```
When active, `strata search` uses BM25 + vector search. No LLM calls.

## How Lifecycle Works

- **Migration** (1st→2nd): Triggered by file age. Default: 14d for projects, 60d for entities, 7d for gtd. Configurable.
- **Eviction** (2nd→3rd): Triggered by LRU. Default: 90 days since last access. Files go to JSON in archive/ + keyword entry in shadow.db.
- **Re-hydration** (3rd→1st): When query finds archived content, file is restored to active/ for editing.
- **No LLM calls** for any lifecycle operation. Zero-effort maintenance.

## Directory Layout

```
strata_data/
├── active/index.md      ← READ THIS FIRST — master map of all files
├── active/projects/     ← Current initiatives + sprints
├── active/entities/     ← People, companies, tools
├── active/gtd/          ← Tasks
├── cooled/              ← Aged-out markdown files
├── archive/             ← Evicted JSON blobs
└── shadow.db            ← Keyword search index for archive
```
