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

### Read/Write (1st Stratum only)

- `strata add <path> <content>` — Write a file (`strata add projects/koda/spec.md "# Spec..."`)
- `strata read <path>` — Read full content (`strata read projects/koda/spec.md`)
- `strata list [path]` — List files (`strata list projects`)

### Search (all tiers)

- `strata search <query>` — Human-readable search across active/ + cooled/ + archive/
- `strata query <query>` — Same as search, JSON output for scripting

### Lifecycle

- `strata migrate` — Move stale active/ files to cooled/
- `strata promote` — Move hot cooled/ files (accessed 3+ times) back to active/
- `strata evict` — Move cold cooled/ files to archive/
- `strata maintenance` — Full lifecycle: promote → migrate → evict
- `strata rehydrate <id> [--target=active|cooled]` — Restore archived file
- `strata forget <path>` — Archive a specific cooled file

### Daemon

- `strata serve [--interval=N]` — Start automatic Janitor
- `strata stop` — Stop daemon
- `strata status` — Show state + daemon health
- `strata install-service` — Install systemd service
- `strata history` — View daemon log

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
- **Promotion** (2nd→1st): When a cooled file is accessed 3+ times (configurable via `promotion_threshold`), the Janitor moves it back to active/. The file proved useful again — it gets a second chance at the surface.
- **Re-hydration** (3rd→1st or 3rd→2nd): Archived files can be restored to active/ (editable) or cooled/ (query-only) using `strata rehydrate <id> --target=active|cooled`.
- **No LLM calls** for any lifecycle operation. Zero-effort maintenance.

### Promotion & Re-hydration

```bash
# Check which cooled files have been accessed enough to promote
strata promote --dry-run

# Execute promotion
strata promote

# Restore an archived file to active (editable)
strata rehydrate <shadow_id> --target=active

# Restore to cooled (query-only, avoids re-eviction risk)
strata rehydrate <shadow_id> --target=cooled
```

## Directory Layout

```
strata_data/
├── active/index.md      ← READ THIS FIRST — master map of all files
├── active/...           ← No preset folders — AI organises organically
├── cooled/              ← Aged-out markdown files
├── archive/             ← Evicted JSON blobs
└── shadow.db            ← Keyword search index for archive
```
