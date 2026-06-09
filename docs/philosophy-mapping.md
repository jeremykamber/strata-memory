# Strata Blog Post — Philosophy Alignment

**Author:** Jeremy Kamber / Strata Contributors
**Date:** 2026-06-08
**Source blog:** https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents

---

## Purpose

The [Strata blog post](https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents) lays out a vision. This codebase is the implementation. They are not identical. Some ideas survived translation to code exactly. Others shifted because reality pushed back. This document maps each major concept from the blog onto what actually shipped, explains the divergences, and flags aspirational features still ahead.

The mapping uses two zones:

- **Green zone:** Core philosophy where the code matches the blog closely. These are non-negotiable, and any future changes should preserve them.
- **Gray zone:** Deliberate deviations from the blog. Each has a rationale. Future work could narrow these gaps, but only if the rationale no longer holds.

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
| Janitor is algorithmic (no LLM to check file age) | Janitor uses file mtime + access count. No LLM calls at all, including migration. | GREEN |
| LLM-only compression after algorithmic trigger | No LLM compression anywhere. Files stay as markdown throughout their lifecycle. | GRAY |
| Files in active/, relational DB in cooled/ | Files in both active/ and cooled/. Only archive/ uses structured storage (JSON). | GRAY |
| CLI tool definitions for agents | Full CLI with grouped help, JSON mode, spinners, config get/set, cost tracking, skill install, MCP server. | GREEN+ |
| Zero-dependency (stdlib only) | Zero-dependency indeed. No Postgres, no vector DB. Optional extras for QMD/OpenAI/Anthropic. | GREEN |

---

## What We Changed and Why

### 1. Stratum 2 is filesystem, not Postgres

**Blog vision:** Stratum 2 runs agent-db, a Postgres-backed relational memory engine with pgvector. It links memories to entities (people, projects, places) through junction tables.

**Implementation:** Stratum 2 is cooled/, a directory of markdown files. Same format as active/. Same filesystem. The only difference is access policy (agent can't write here directly).

**Why the change:**

- Postgres is a dependency. Strata is zero-dependency by design. Adding Postgres would break the install and setup experience.
- pgvector requires Postgres 16+ and a database setup step. That conflicts with the CLI-first "install and go" model.
- The blog's agent-db integration is aspirational. It describes a product that doesn't exist yet. Building it would require a separate project.
- Filesystem storage for cooled/ still satisfies the core requirement: data has a slower access path but remains searchable. The files stay on disk and cost nothing to maintain.

**Tradeoff:** We lose entity-level relational queries and vector search in Stratum 2. The QMD bridge partially compensates with optional BM25 + vector search across active/ and cooled/.

### 2. No LLM compression during migration

**Blog vision:** When the Janitor triggers, an LLM call compresses each file into a high-density summary. The summary lives in agent-db. The original file is archived.

**Implementation:** The Janitor copies the file from active/ to cooled/ as-is. No LLM call. No compression. No summarization.

**Why the change:**

- LLM calls cost money and add latency. The Janitor runs every 15 minutes. Compressing every stale file would accumulate significant API costs.
- Compression loses information. If the agent needs the original context, a summary is insufficient. By keeping the full markdown content, we preserve fidelity.
- The blog's compression step assumes a downstream system (agent-db) that can store and query the summaries. That system doesn't exist yet. Compressing to nowhere adds no value.
- Filesystem storage is cheap. Keeping full-content files in cooled/ costs almost nothing.

**Tradeoff:** Cooled/ files consume more disk space than compressed summaries. For a single-user agent system, this is negligible. For multi-tenant or high-scale, compression could matter later.

### 3. Simple access tracking instead of database-backed LRU

**Blog vision:** Postgres tracks access_count and last_accessed per row, enabling precise LRU eviction queries.

**Implementation:** A JSON sidecar file (stratum_2_access.json) stores access data per file path. The Janitor reads it, computes ages, and evicts candidates.

**Why the change:**

- No Postgres means no built-in row-level access tracking. The JSON sidecar is a pragmatic substitute.
- The JSON file is < 10 KB for thousands of entries. It loads in milliseconds. Serialization overhead is invisible at Strata's scale.
- The LRU logic is identical to what the blog describes: age + access count thresholds. Only the storage format differs.

**Tradeoff:** JSON sidecar has no concurrency protection. Two processes accessing cooled/ simultaneously could lose updates. At the current scale (single-user, daemon-driven), this is acceptable.

### 4. Re-hydration returns to active/, not agent-db

**Blog vision:** Re-hydrated memories go back into agent-db (Postgres) with a fresh embedding.

**Implementation:** Re-hydrated files go back into active/ as plain markdown. No embedding. No database.

**Why the change:** Consistent with the decision to keep everything on the filesystem. Re-hydration restores the file to its original stratum (active/) where the agent can read and write it directly. There's no database to repopulate.

---

## Implemented vs Aspirational

The blog describes a system that blends Strata (lifecycle management) with agent-db (rich relational memory). The current codebase implements the Strata half fully. The agent-db half remains aspirational.

### Fully implemented (Strata core)

| Feature | Status | Module |
|---|---|---|
| Three-tier filesystem storage | Fully implemented | storage.py |
| Algorithmic Janitor (migrate + evict) | Fully implemented | janitor.py |
| Decay thresholds per directory | Fully implemented | config.py |
| LRU eviction with access tracking | Fully implemented | janitor.py, storage.py |
| Shadow Index (SQLite FTS5) | Fully implemented | storage.py |
| Cascading search (S1 -> S2 -> S3) | Fully implemented | query.py |
| CLI with grouped help, JSON mode | Fully implemented | cli.py |
| Daemon mode with configurable interval | Fully implemented | daemon.py |

### Implemented beyond the blog

| Feature | Module |
|---|---|
| Cost tracking estimation | tracking.py |
| Skill install for AI coding assistants | cli.py |
| PI extension installation | cli.py |
| MCP protocol server | mcp_server.py |
| Config persistence with get/set | cli.py |
| QMD auto-install and onboarding | cli.py, storage.py |
| JSON mode for script consumption | cli.py |
| Spinner UX for lifecycle commands | cli.py |
| OpenCode function-calling tools | tools.py |

### Aspirational (described in blog, not implemented)

| Feature | Blog reference | Blockers |
|---|---|---|
| agent-db Postgres integration | "agent-db powers Phase 2" | Requires a separate product. Out of scope for the Strata project. |
| LLM compression on migration | "The LLM processes the text" | Cost, latency, and information loss. Filesystem is sufficient. |
| Entity-relationship memory graph | "relational links through junction tables" | Requires Postgres + schema design. Filesystem can't represent relations natively. |
| Autonomy records for decision lineage | "autonomy_records table" | Requires structured storage and a query API. Not urgent for single-agent use. |
| pgvector embeddings for Stratum 2 | "pgvector embedding for semantic search" | Partially covered by QMD bridge, but baked-in embeddings don't exist. |

---

## Key Principles to Preserve

These principles hold across both the blog and the implementation. They should not change.

### Files are the truth

Every memory in Strata is a plain file on disk. Not a blob in a database. Not a node in a graph. This is non-negotiable. It means the agent can grep, edit, pipe, and version memories without any Strata-specific tooling.

### The Janitor is algorithmic

Lifecycle decisions use file age and access count, not LLM calls. No AI checks the clock. This is the core insight that separates Strata from competing systems.

### Three distinct access tiers

Active (full R/W), cooled (query only), archive (re-hydration required). The tiers form a clear cost hierarchy: fastest access on top, cheapest storage on bottom. This structure must not collapse into a flat system.

### CLI-first, always

The command line is the primary interface. Python API exists for scripting but mirrors the CLI. Every feature must be accessible from the terminal before it can be accessed from Python.

---

## Conclusion

The Strata blog post and the Strata codebase share the same DNA. The three-tier architecture, the algorithmic Janitor, the Shadow Index, the cascading search all made the transition intact. The major differences come down to one decision: replace Postgres (blog) with filesystem (code). That decision cascades through every gray-zone item in the alignment table.

The filesystem-first approach is the right call for Strata as a standalone project. It keeps the install zero-dependency, the setup instant, and the maintenance near zero. If agent-db or a similar system materializes later, Strata's architecture is clean enough to plug it into Stratum 2 without rewriting anything. For now, files work, and files are enough.
