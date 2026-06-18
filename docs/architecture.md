# Architecture

Strata stores your memories across three tiers  -  active, cooled, and archive. Think geological strata, but for notes instead of rocks. This page covers how the system works, how data moves between layers, and why each piece is the way it is.

## Three-Tier Structure

```
~/.strata/                    # Or ./strata_data/ for project-local
├── active/                   # 1st Stratum -- working memory
│   ├── index.md              # Auto-generated master map
│   └── ...                   # No preset folders -- AI organises organically
├── cooled/                   # 2nd Stratum -- aged-out files
├── archive/                  # 3rd Stratum -- cold JSON storage
├── shadow.db                 # Shadow Index (SQLite FTS5)
├── strata.log                # Daemon activity log
├── strata.pid                # Daemon PID file
└── strata_cost.log           # Cost tracking data
```

| Stratum | Directory | Access | Latency | Storage |
|---|---|---|---|---|
| 1st (Active) | `active/` | Read/write | ~1 ms | Markdown files |
| 2nd (Cooled) | `cooled/` | Read-only via search | ~5 ms | Markdown files |
| 3rd (Archive) | `archive/` | Read-only via search + rehydration | ~10 ms | JSON blobs + SQLite FTS5 |

### 1st Stratum  -  Active

The agent reads and writes here directly. Files are plain markdown on disk. No database, no vector index  -  just files. It's almost refreshingly simple.

An auto-generated `index.md` works as a master map. It lists every file in the active stratum with its first heading as a description. The workflow: read `index.md` first, then navigate to specific files by path.

**Agent rule:** Full read/write access. This is your workspace.

**Characteristics:**

- Fastest access (~1 ms per read)
- No indexing overhead  -  the `index.md` regenerates after every write
- Path-based navigation (no search needed for known files)
- Files older than their decay threshold are eligible for migration

### 2nd Stratum  -  Cooled

When a file hasn't been modified for longer than its decay threshold, the Janitor moves it from `active/` to `cooled/`. The file stays as a plain markdown file on disk. The only difference is the agent can't write to it directly anymore.

**Agent rule:** Read-only via search. The Janitor tracks access counts for LRU calculations and promotion decisions. If you need to edit something, it can be rehydrated back to active.

**Moving back up (Promotion):** The Janitor also moves files the opposite way. When a cooled file gets accessed 3 or more times (configurable via `promotion_threshold`), it gets promoted back to active/. The file has proven useful again  -  it's restored to the working tier where the agent can read and edit it directly.

**Characteristics:**

- Same storage medium as active (markdown files)
- Searchable via filesystem grep or QMD
- Access tracking via a JSON sidecar file (`stratum_2_access.json`)
- Files that exceed the LRU threshold are evicted to the archive

### 3rd Stratum  -  Archive

When a cooled file hasn't been accessed for longer than the LRU window, the Janitor evicts it to `archive/`. The full content gets saved as a JSON blob. A lightweight Shadow Index (SQLite FTS5) keeps it keyword-searchable.

**Agent rule:** Can't write here. Archived files can be rehydrated back to active/ or cooled/ using `strata rehydrate <id> --target=active|cooled`. The agent can choose whether to restore the file for editing (active) or for reference (cooled).

**Characteristics:**

- Coldest storage tier
- Keyword search via SQLite FTS5 shadow index
- Rehydration restores the file to `active/` for editing
- Minimal storage overhead per entry (keywords + 200-char preview + path)

## The Janitor

The Janitor is the only process that moves data between strata. It runs on a schedule with deterministic rules  -  no LLM calls, no guesswork. That keeps maintenance costs bounded and predictable.

```
┌─────────────┐    promote     ┌──────────────┐         ┌──────────────┐
│   active/   │ ◀──────2+──────   cooled/   │ ──evict──▶   archive/   │
│ (1st Strat) │ ──migrate──▶   │ (2nd Strat) │   LRU>    │ (3rd Strat)  │
│             │   age>    │    │ threshold │  + shadow.db │
└─────────────┘         └──────────────┘         └──────────────┘
       ▲                                                │
       └──────────────────────◀─────────────────────────┘
                       rehydrate
```

### Migration (1st -> 2nd)

`strata migrate` or the daemon's periodic cycle:

1. Scan `active/` for files matching `active_file_patterns`
2. For each file, calculate its age in days since last modification
3. Look up the decay threshold for the file's top-level directory (e.g., a file under `projects/` matches `"projects": 14`)
4. If age >= threshold, copy the file to `cooled/` and delete from `active/`
5. Log the migration

**Dry run preview:** `strata migrate --dry-run` shows what would happen without making changes. The daemon's first cycle is always a dry run.

### Eviction (2nd -> 3rd)

`strata evict` or the daemon's periodic cycle:

1. Scan `cooled/` for files
2. For each file, check its access data from `stratum_2_access.json`
3. If (now - last_accessed) > `lru_days` AND access_count <= `lru_min_access_count`:
   a. Save the file content as a JSON blob in `archive/`
   b. Create a Shadow Index entry (keywords, 200-char preview, path to JSON)
   c. Delete the file from `cooled/`
   d. Log the eviction

### Promotion (2nd -> 1st)

The Janitor moves files **up** the strata. When a cooled file gets read frequently enough, it's promoted back to active/.

**Trigger:** Access count >= `promotion_threshold` (default: 3).

**Automatic promotion:** `strata read` on a cooled file tracks the access count. When the threshold is reached, the file is promoted inline  -  the content is returned, and the file moves from `cooled/` to `active/` as part of the same operation. No separate command needed.

**Batch promotion:** `strata promote` and `strata maintenance` also promote eligible files for cases where the Janitor ran a batch cycle.

**Effect:** Copy from `cooled/` to `active/`, delete the cooled copy, remove the access tracking entry, regenerate the index.

**Intent:** If the agent keeps reading a cooled file, that file is clearly still relevant. Rather than letting it sink into archive, promotion brings it back to the surface where the agent can work with it directly.

### Rehydration (3rd -> 1st or 3rd -> 2nd)

When a search query matches an archived entry via the Shadow Index:

1. The search result includes the archive path and a hint to rehydrate
2. The agent can:
   - Run `strata rehydrate <shadow_id> --target=active|cooled` for explicit control
   - Run `strata read <original_path>` for automatic rehydration to active
3. Strata reads the archived JSON blob
4. The file is restored to the target tier (active/ for editing, cooled/ for reference)
5. The Shadow Index entry is removed

Rehydration happens automatically when you read an archived file by its original path. The file is restored to the 1st Stratum so the agent can work with it directly without an extra command.

## The Shadow Index

When a file is archived, the Janitor doesn't just delete it. It stores a lightweight entry in a SQLite FTS5 database  -  keywords, a 200-character preview, and the path to the full JSON blob.

This enables keyword search across millions of archived entries at minimal cost. A million ghosts cost practically nothing in storage.

**Schema:**

```
shadow_index table:
  id              TEXT PRIMARY KEY    -- UUID
  original_path   TEXT NOT NULL       -- path in cooled/
  keywords        TEXT DEFAULT '[]'   -- JSON array of tags
  archive_path    TEXT NOT NULL       -- path to JSON blob
  summary_preview TEXT DEFAULT ''     -- first 200 chars of content
  evicted_at      TEXT NOT NULL       -- ISO timestamp

shadow_fts virtual table (FTS5):
  keywords, summary_preview
```

The FTS5 virtual table stays in sync via INSERT and DELETE triggers on `shadow_index`. No manual maintenance needed.

## Daemon Mode

The background daemon automates the Janitor. It runs as a standalone Python process with:

- A configurable interval (default: 900 seconds / 15 minutes)
- First cycle is always a dry run (unless `--live` is passed)
- Logging to both `strata.log` and stderr
- PID file for process management
- Graceful shutdown on SIGINT/SIGTERM
- Cost data logging to `strata_cost.log`

The daemon is what makes Strata a "set it and forget it" memory system. Start it once; it handles everything.

## Data Integrity

- **No in-place modification.** Migration copies then deletes. Eviction reads, archives, then deletes. A crash between copy and delete may leave the file in both locations, but data is never lost.
- **Shadow Index is append-friendly.** Archived files are never modified. Rehydration reads the JSON but doesn't remove the shadow entry. The index only grows.
- **File patterns prevent surprises.** Only files matching `active_file_patterns` (`.md`, `.txt`, `.json`, `.yaml`, `.yml`) are considered for migration. Other files in the active directory are ignored.

## Concurrency Model

The daemon runs a single maintenance thread. Concurrent `strata migrate` / `strata evict` calls from the CLI against the same data directory can race with the daemon. This is safe because:

- Migration uses `shutil.copy2` + `unlink` (atomic on most filesystems)
- Eviction reads the JSON, writes to archive, then deletes from cooled
- The Shadow Index uses SQLite with WAL mode for safe concurrent reads

## Cross-Reference

- [Configuration](configuration.md)  -  thresholds that control Janitor behaviour
- [CLI Reference](cli-reference.md)  -  lifecycle commands (migrate, evict, maintenance)
- [Search](search.md)  -  how searches span all three strata
- [Tracking](tracking.md)  -  cost implications of each stratum
