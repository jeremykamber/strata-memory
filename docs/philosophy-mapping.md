# Strata Blog Post  -  Philosophy Alignment

**Author:** Jeremy Kamber / Strata Contributors
**Date:** 2026-06-08
**Source blog:** <https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents>

---

## Purpose

The [Strata blog post](https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents) sketches a vision. This codebase is what actually shipped. They're not twins  -  more like siblings who went through different phases in high school. Some ideas made the jump to code exactly as written. Others got bent, trimmed, or quietly dropped when reality pushed back. This document maps every major blog concept onto what's really in the repo, explains where and why things diverged, and flags which features are still on the wishlist.

The mapping breaks into two zones:

- **Green zone:** Core philosophy where the code matches the blog closely. These are non-negotiable  -  if you change them, you're changing what Strata is.
- **Gray zone:** Deliberate deviations. Each one has a rationale. Future work could close these gaps, but only if the original constraints no longer apply.

---

## Alignment Table

| Blog Claim | Implementation Reality | Status |
|---|---|---|
| Three strata: active (markdown) -> agent-db (Postgres + pgvector) -> archive (JSON + SQLite) | Three strata: active/ (markdown), cooled/ (markdown, same format), archive/ (JSON + SQLite FTS5). No Postgres. No pgvector. | GRAY |
| Stratum 2 is agent-db: relational memory engine with entity linking and pgvector embeddings | Stratum 2 is cooled/: plain markdown files on disk in a separate directory. Access tracking via JSON sidecar. No entity graph. No vector embeddings. | GRAY |
| Migration includes an LLM call to compress files into dense summaries | Migration is a file move with no LLM involvement. Content stays as-is. No compression or summarization. | GRAY |
| Eviction from Postgres after LRU threshold | Eviction from cooled/ filesystem after LRU threshold. Same logic, different storage medium. | GREEN |
| Shadow Index: lightweight SQLite with keywords + archive_path | Shadow Index: SQLite FTS5 with full-text search, keywords column, 200-char preview. FTS5 is actually more capable than the blog described. | GREEN |
| Re-hydration: archived file back to agent-db with new embedding | Re-hydration: archived file back to active/ as markdown. No embedding regeneration needed (no vector DB). | GRAY |
| Cascading search: Phase 1 -> Phase 2 -> Shadow Index | Cascading search: S1 -> S2 -> S3. QMD hybrid search when available, filesystem grep fallback. Same cascade structure. | GREEN |
| Janitor is algorithmic (no LLM to check file age) | Janitor uses file mtime + access count. **Zero LLM calls for lifecycle decisions.** An optional background Distiller runs inside the same daemon for knowledge extraction — but that's a separate concern with its own config and cost, not part of the Janitor. | GREEN |
| LLM-only compression after algorithmic trigger | No LLM compression anywhere. Files stay as markdown throughout their lifecycle. | GRAY |
| Files in active/, relational DB in cooled/ | Files in both active/ and cooled/. Only archive/ uses structured storage (JSON). | GRAY |
| CLI tool definitions for agents | Full CLI with grouped help, JSON mode, spinners, config get/set, cost tracking, skill install, MCP server. | GREEN+ |
| Zero-dependency (stdlib only) | Zero-dependency indeed. No Postgres, no vector DB. LLM calls only via optional Distiller (uses stdlib `urllib.request`, no new pip deps). Optional extras for QMD/OpenAI/Anthropic. | GREEN |

---

## What We Changed and Why

### 1. Stratum 2 is the filesystem, not Postgres

**Blog vision:** Stratum 2 runs agent-db, a Postgres-backed relational memory engine with pgvector. It ties memories to entities  -  people, projects, places  -  through junction tables.

**Implementation:** Stratum 2 is cooled/, a directory of markdown files. Same format as active/. Same filesystem. The only difference is access policy: agents can't write here directly.

**Why the change:**

- Postgres is a dependency. Strata is zero-dependency by design. Adding Postgres would turn "pip install and go" into "install and configure a whole database first."
- pgvector needs Postgres 16+ and a setup step. That conflicts with the CLI-first "just run it" model.
- The blog's agent-db integration is aspirational. It describes a product that doesn't exist yet. Building it would be a separate project.
- Filesystem storage for cooled/ still does the job: slower access path, but still searchable. The files sit on disk and cost nothing to maintain.

**Tradeoff:** You lose entity-level relational queries and vector search in Stratum 2. The QMD bridge partly makes up for it with optional BM25 + vector search across active/ and cooled/. But it's not the same thing.

### 2. No LLM compression during migration

**Blog vision:** When the Janitor fires, an LLM compresses each file into a dense summary. That summary lives in agent-db. The original file goes to archive.

**Implementation:** The Janitor copies the file from active/ to cooled/ as-is. No LLM call. No compression. No summarization.

**Why the change:**

- LLM calls cost money and add latency. The Janitor fires every 15 minutes. Compressing every stale file would rack up a real bill over time.
- Compression throws away information. If the agent needs the original context later, a summary won't cut it. Keeping the full markdown preserves fidelity.
- The blog's compression step assumes agent-db exists to store and query those summaries. It doesn't. Compressing to nowhere is pointless.
- Filesystem storage is cheap. Keeping full-content files in cooled/ costs basically nothing.

**Tradeoff:** Cooled/ files take up more disk space than compressed summaries would. For a single-user agent system, that's a rounding error. If you're running at massive scale someday, compression might earn another look.

### 3. Simple access tracking instead of database-backed LRU

**Blog vision:** Postgres tracks `access_count` and `last_accessed` per row. Clean LRU queries all day.

**Implementation:** A JSON sidecar file (`stratum_2_access.json`) stores access data per file path. The Janitor reads it, computes ages, and picks eviction candidates.

**Why the change:**

- No Postgres means no built-in row-level access tracking. The JSON sidecar is a pragmatic stand-in.
- The JSON file stays under 10 KB even for thousands of entries. It loads in milliseconds. You won't notice the serialization overhead.
- The LRU logic is the same as what the blog describes: age + access count thresholds. Only the storage format changed.

**Tradeoff:** The JSON sidecar has no concurrency protection. Two processes hitting cooled/ at the same time could lose updates. At current scale  -  single-user, daemon-driven  -  that's fine. If you need multi-process access later, you'll want something more rigorous.

### 4. Re-hydration goes to active/, not agent-db

**Blog vision:** Re-hydrated memories go back into agent-db (Postgres) with a fresh embedding.

**Implementation:** Re-hydrated files land back in active/ as plain markdown. No embedding. No database.

**Why the change:** It's consistent with the "everything on the filesystem" decision. Re-hydration restores the file to its original working directory where the agent can read and write it directly. There's no database to repopulate.

---

## Implemented vs Aspirational

The blog describes a system that mixes Strata (lifecycle management) with agent-db (rich relational memory). The current codebase implements the Strata half fully. The agent-db half is still on the vision board.

### Fully implemented (Strata core)

| Feature | Status | Module |
|---|---|---|
| Three-tier filesystem storage | Fully implemented | storage.py |
| Algorithmic Janitor (migrate + evict) | Fully implemented | janitor.py |
| Decay thresholds per directory | Fully implemented | config.py |
| LRU eviction with access tracking | Fully implemented | janitor.py, storage.py |
| Shadow Index (SQLite FTS5) | Fully implemented | storage.py |
| Cascading search (S1 -> S2 -> S3) | Fully implemented | query.py |
| CLI with grouped help, JSON mode | Fully implemented | cli/ (_cli_main.py + commands/) |
| Daemon mode with configurable interval | Fully implemented | daemon.py |

### Implemented beyond the blog

| Feature | Module |
|---|---|
| Cost tracking estimation | tracking.py |
| Skill install for AI coding assistants | cli/commands/skill.py |
| PI extension installation | cli/commands/pi_install.py |
| Background distillation (conversation → fact files) | distiller.py, cli/commands/distiller.py |
| MCP protocol server | mcp_server.py |
| Config persistence with get/set | cli/commands/config_cmd.py |
| QMD auto-install and onboarding | cli/commands/qmd.py, storage.py |
| JSON mode for script consumption | cli/_json.py |
| Spinner UX for lifecycle commands | cli/_spinner.py |
| OpenCode function-calling tools | tools.py |

### Aspirational (described in blog, not implemented)

| Feature | Blog reference | Blockers |
|---|---|---|
| agent-db Postgres integration | "agent-db powers Phase 2" | Needs a separate product. Out of scope for Strata on its own. |
| LLM compression on migration | "The LLM processes the text" | Cost, latency, and information loss. Filesystem is good enough. |
| Entity-relationship memory graph | "relational links through junction tables" | Requires Postgres + schema design. Filesystem can't do relations natively. |
| Autonomy records for decision lineage | "autonomy_records table" | Needs structured storage and a query API. Not urgent for single-agent setups. |
| pgvector embeddings for Stratum 2 | "pgvector embedding for semantic search" | Partially covered by the QMD bridge, but baked-in embeddings don't exist. |

---

## Key Principles to Preserve

These principles hold across both the blog and the codebase. Don't touch 'em.

### Files are the truth

Every memory in Strata is a plain file on disk. Not a blob in a database. Not a node in a graph. This is non-negotiable. It means the agent can grep, edit, pipe, and version memories without any Strata-specific tooling.

### The Janitor is algorithmic

Lifecycle decisions use file age and access count, not LLM calls. No AI checks the clock. This is the core insight that separates Strata from the competition — and yes, that's worth repeating.

The daemon *also* runs an optional Distiller that uses an LLM for knowledge extraction from transcripts, but that's a separate concern. The Distiller doesn't make lifecycle decisions. It doesn't affect what gets migrated, evicted, or promoted. They share a process but not a purpose.

### Three distinct access tiers

Active (full R/W), cooled (query only), archive (re-hydration or bust). The tiers form a clear cost hierarchy: fastest access on top, cheapest storage on bottom. This structure must not collapse into a flat system.

### CLI-first, always

The command line is the primary interface. The Python API exists for scripting but mirrors the CLI. Every feature must work from a terminal before it can be called from Python — and honestly, the terminal version should be the nicer experience.

### Distillation is optional and separate

Knowledge extraction is a value-add layer, not part of the core lifecycle. The Distiller:

- Runs in batch (once per 15 minutes), not inline on every query.
- Uses a separate cheap model (GPT-4o-mini default), not the agent's primary model.
- Preserves raw transcripts after processing. Nothing is consumed or replaced.
- Is disabled by default. No API key configured = no distillation, no cost, no LLM integration.

This principle protects the core architecture from scope creep. The Janitor stays algorithmic. The Distiller stays optional. Neither compromises the other.

---

## Conclusion

The Strata blog post and the Strata codebase share the same DNA. The three-tier architecture, the algorithmic Janitor, the Shadow Index, the cascading search — all of it made the trip to code intact. The big differences all trace back to one decision: replace Postgres (blog) with filesystem (code). That choice ripples through every gray-zone item in the alignment table.

The filesystem-first approach is the right call for Strata as a standalone project. It keeps the install zero-dependency, the setup instant, and the maintenance near zero. The optional Distiller adds background knowledge extraction without compromising the algorithmic Janitor — they're separate concerns that happen to share a daemon process. If agent-db or something like it shows up later, Strata's architecture is clean enough to plug it into Stratum 2 without rewriting anything. For now, files work. And files are enough.
