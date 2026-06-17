---
date: 2026-06-17
topic: pi-knowledge-capture-and-distill
---

# Pi Knowledge Capture & Background Distillation

## Summary

Replace the Pi extension's heuristic per-turn knowledge capture with always-on transcript archiving at `agent_end`, then add a background distill step inside the Strata daemon that uses a small configurable LLM to extract standalone fact files from raw transcripts. Facts are append-only — no merge/dedup at write time. The agent reconciles multiple facts on the same topic at query time using file timestamps.

---

## Problem Frame

The current Pi extension classifies conversation content at each `turn_end` using heuristics — a cheap rule-based check that either stores the output to a wiki path or discards it. The optional LLM config fires per-turn for a classification-only call that labels turns as "store" or "skip." Both paths share a problem: the raw conversation is lost after classification. What wasn't explicitly stored is gone.

This misses important information in three ways: (1) content that doesn't match heuristic patterns is silently dropped, (2) the per-turn LLM classification call is wasted when the heuristic fires first, and (3) knowledge extraction happens inline during the agent's active session, competing with the agent's primary task for context budget and latency.

The project already has the right infrastructure to fix this — a running daemon with a configurable maintenance cycle, zero-dependency file storage, and a config schema that could specify a small distillation model. What's missing is the data path: always-on capture that preserves raw material, and a background process that turns that material into structured knowledge without interfering with the agent's live work.

---

## Actors

- A1. **Human user**: Produces conversations through normal use of Pi
- A2. **Pi extension**: Captures raw conversation transcripts at `agent_end` and saves them to Strata
- A3. **Strata daemon**: Orchestrates the maintenance cycle including the distill step
- A4. **Distill LLM**: The configured small model (e.g., GPT-4o-mini, Claude Haiku) that extracts facts from transcripts
- A5. **Agent**: Reads Pi's knowledge base (fact files) when responding to user queries

---

## Key Flows

- F1. **Capture**
  - **Trigger:** `agent_end` event fires
  - **Actors:** A2
  - **Steps:** Extension reads current conversation transcript from agent context → constructs unique session identity → writes full transcript as a markdown file to `pi/conversations/YYYY-MM-DD/`
  - **Outcome:** Raw conversation is durably stored in Strata's first stratum
  - **Covered by:** R1, R2, R3

- F2. **Distill**
  - **Trigger:** Daemon maintenance cycle runs (default every 15 min)
  - **Actors:** A3, A4
  - **Steps:** Distill checks for new undistilled conversations in `pi/conversations/` → if none found, skips → reads all new transcript files → sends them to the configured small LLM with an extraction prompt → writes returned facts as standalone markdown files in `pi/facts/YYYY-MM-DD/` → marks conversations as distilled
  - **Outcome:** Raw conversations are processed into standalone fact files; raw transcripts enter their cooling lifecycle
  - **Covered by:** R4, R5, R6, R7, R8

- F3. **Query / Reconcile**
  - **Trigger:** Agent needs to retrieve stored knowledge about a topic
  - **Actors:** A5
  - **Steps:** Agent searches or lists `pi/facts/` for relevant files → finds zero, one, or multiple fact files covering the topic → reads the most recent file(s) → reconciles any differences by file timestamp and content relevance
  - **Outcome:** Agent produces a synthesized view of the knowledge it has on the topic, aware of which facts are older or potentially superseded
  - **Covered by:** R9, R10, R11

---

## Requirements

**Capture**

- R1. The Pi extension must save the full conversation transcript at each `agent_end` event. No heuristic filtering. No classification gate.

- R2. Captured transcripts must be saved as plain markdown files in a dedicated conversations directory under Strata's first stratum: `pi/conversations/YYYY-MM-DD/`.

- R3. Each transcript file must carry a unique session identity. Identity format: `{timestamp}-{session-hash}.md`. The timestamp is when the session ended; the session hash provides uniqueness across concurrent sessions.

**Distill**

- R4. Distillation must run as part of the daemon's existing maintenance cycle, alongside promote → migrate → evict. No separate CLI command. No new scheduling infra.

- R5. Distill must skip conversation files that have already been processed. A lightweight tracking mechanism (flag file, sidecar, or filename marker) must persist this state between cycles.

- R6. Distill must use the configured small LLM — repurposing `pi-config.json`'s existing `llm` schema for model selection (`provider`, `model`, `api_key`).

- R7. Distill must produce standalone fact files — one file per distill batch. Each fact file is written to `pi/facts/YYYY-MM-DD/` with a sequential numeric prefix and a descriptive title. Fact files are append-only: they reference no other files, carry no supersedes metadata, and contain no cross-file merge/dedup logic.

- R8. Distill must not invoke the LLM when there are no new undistilled conversations. Metadata check only — zero new transcripts means zero cost.

**Fact Storage**

- R9. Fact files live in `pi/facts/YYYY-MM-DD/` under Strata's first stratum, organized by the date of distillation.

- R10. Multiple fact files on the same topic must be able to coexist without conflict. No uniqueness constraint on topic, title, or content.

**Agent Reconciliation**

- R11. The agent must reconcile multiple fact files on the same topic at query time. The reconciliation mechanism is file-system native: file timestamp indicates recency; number of files on a topic indicates activity level. No database queries, no merge API.

- R12. The agent must be able to navigate the facts directory via existing Strata primitives: `strata search` (keyword), `strata list pi/facts/` (listing), and `strata read pi/facts/2026-06-17/001-*.md` (direct read).

**Lifecycle**

- R13. Raw conversation transcripts must have a shorter decay threshold than fact files. Default suggestion: 7 days for transcripts, matching the GTD threshold; 30 days for facts, matching the default. Both must be configurable in `StrataConfig`.

**Configuration**

- R14. The `pi-config.json` schema must support specifying a distill model independently from the extension's LLM configuration — or if unified, must clearly document that the same model config is used for both capture-time classification (when enabled) and background distillation.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3.** Given an `agent_end` event with a conversation transcript of ~2000 tokens in the agent's context, when the extension fires, a markdown file named `20260617T143022-abcd1234.md` is written to `pi/conversations/2026-06-17/` containing the full transcript text.

- AE2. **Covers R4, R8.** Given a daemon maintenance cycle where all conversation files under `pi/conversations/` already carry distill markers, when distill runs, no HTTP call is made to any LLM provider and no new files appear under `pi/facts/`.

- AE3. **Covers R5, R6, R7.** Given a daemon maintenance cycle with 3 new undistilled conversation files in `pi/conversations/2026-06-17/`, when distill runs, it reads all 3 transcripts, sends them as one batch to the configured LLM, writes exactly one new file to `pi/facts/2026-06-17/` with extracted facts, and marks all 3 source conversations as distilled.

- AE4. **Covers R10, R11.** Given two fact files — `pi/facts/2026-06-17/001-database-postgresql.md` and `pi/facts/2026-06-20/002-database-sqlite.md` — when the agent searches `pi/facts/` for "database", both files are returned by `strata search`. The agent reads both and uses the file mod time to determine that the SQLite fact (June 20) is more recent than the Postgres fact (June 17).

- AE5. **Covers R13.** Given a raw conversation file created 8 days ago in `pi/conversations/` (threshold: 7 days), when the Janitor's migrate cycle runs, the conversation file is moved from active to cooled. A fact file created 8 days ago in `pi/facts/` (threshold: 30 days) is not moved.

---

## Success Criteria

- A user can have multiple Pi sessions and never use a heuristic store command, yet all substantive facts from those sessions appear in `pi/facts/` within one maintenance cycle.
- An agent searching for a previously discussed topic finds one or more relevant fact files and can determine recency by file timestamp alone.
- The distill step costs < $0.01 per maintenance cycle in LLM API usage for a typical session's worth of transcripts.

---

## Scope Boundaries

- **No standalone distill CLI command.** Distillation runs automatically during `strata serve`. The user does not invoke it.
- **No supersedes or merge/dedup system.** Facts are append-only. The agent deals with multiplicity at read time.
- **No Janitor lifecycle changes.** The existing cool/evict/archive mechanics remain unchanged. Transcripts and facts flow through the same lifecycle with different decay thresholds.
- **No vector search or embedding pipeline.** Reconciliation is file-system native — timestamps, file names, and `strata search` (FTS5).
- **No changes to `strata read` cascade behavior.** Reading a fact or conversation file works exactly like reading any other Strata file — cascading through active → cooled → archive.
- **No MCP protocol changes.** Knowledge capture and distillation live entirely in the extension and daemon. The MCP server continues serving its existing interface.

---

## Key Decisions

- **Append-only facts over single-authoritative-wiki.** A cheap LLM writing a single merged wiki would save the agent read-time effort but would also need to be good at merge/dedup without losing information. Append-only defers the hard problem to the expensive model that's better at it and accepts that the agent may read 2-3 files instead of 1. This follows the pattern of "optimize for write-time simplicity, pay cost at read time."

- **Distill inside daemon maintenance over standalone scheduler.** Strata already has a cyclic daemon with configurable interval. Adding distill as a maintenance step costs zero scheduling infra and inherits the daemon's existing lifecycle (PID tracking, log, graceful shutdown). The tradeoff is that distill doesn't run when the daemon isn't running.

- **Raw transcripts cool faster than facts.** Transcripts are bulkier and lose value quickly — once distilled, the raw conversation is rarely needed. Facts accumulate knowledge value over time and should persist longer. Different decay thresholds express this naturally.

- **Small LLM for distill, not the user's agent model.** Background distillation shouldn't compete with the agent's primary model budget (cost, rate limits, API keys). A separate cheaper model config gives the user independent control over distill cost vs. quality.

---

## Dependencies / Assumptions

- The Pi extension has access to the full conversation transcript at `agent_end`. (Requires verification during planning.)
- The daemon runs `strata serve` with a configured interval. Distill is inactive when the daemon is not running.
- The `pi-config.json` file exists at the Strata base directory with LLM provider configuration.
- The Strata base directory is writable and has sufficient disk space for accumulated conversation transcripts (typical: < 1 MB per session; 7 days of transcripts < 50 MB).

---

## Outstanding Questions

### Resolve Before Planning

- [RESOLVED][Affects R3] Session identity: `YYYYMMDD-{session-hash}.md`. Date-prefixed for day-level search, per-session hash for uniqueness. Filenames format is `YYYYMMDD-<hash>.md`.

- [RESOLVED][Affects R6] Since the new design eliminates the per-turn classification call entirely, there is only one LLM call path (background distill). Reuse the existing `llm` block in `pi-config.json` for the distill model. No separate `distill_llm` field needed.

### Deferred to Planning

- [Affects R5][Technical] What form should the distill tracking take? Options: a JSON sidecar in `pi/`, a marker appended to the filename (e.g., `file.md.done`), a line in a tracking file, or an FTS5 entry. Will resolve during implementation when the filesystem access pattern is clearer.

- [Affects R6][Technical] Batch size and prompt template for distill. Should the small LLM receive all new transcripts in one call or one per file? The choice affects token window size (and therefore model selection) and extraction quality. Will resolve during implementation with empirical testing.

- [Affects R13][Needs research] What specific decay thresholds to use for transcripts vs facts. Defaults of 7d / 30d are starting points; real-world validation needed during testing.
