---
title: feat: Pi knowledge capture and background distillation
type: feat
status: active
date: 2026-06-17
origin: docs/brainstorms/pi-knowledge-capture-and-distill.md
---

# Pi Knowledge Capture & Background Distillation

## Summary

Replace the Pi extension's heuristic per-turn classification with always-on full-conversation capture at `agent_end`, then add a background distill step inside the Strata daemon that calls a configurable small LLM to extract standalone fact files from raw transcripts. The extension saves plain markdown transcripts to `pi/conversations/`; the daemon's maintenance cycle reads undistilled transcripts, sends them in one batch to the configured LLM, and writes extracted facts to `pi/facts/`. Facts are append-only — no merge/dedup at write time. The agent reconciles multiple facts on the same topic at query time using file timestamps.

---

## Problem Frame

The current Pi extension classifies content at each `turn_end` by heuristic or optional LLM call — and stores only what passes the gate, discarding the raw conversation. This misses important information and loses the transcript material entirely. The new design always preserves the raw conversation and extracts knowledge from it in the background, at cents per cycle, using a cheap model that runs inside the daemon. (See origin document for the full pain narrative.)

---

## Requirements

- R1. Full conversation transcript saved at each `agent_end` event — no heuristic filtering
- R2. Transcripts saved as markdown files in `pi/conversations/YYYY-MM-DD/YYYYMMDDThhmmss-{hash}.md` (date-prefixed timestamp for ordering, short hash for uniqueness across concurrent sessions)
- R3. Distillation runs inside the daemon's maintenance cycle — no separate CLI or scheduler
- R4. Distill skips already-processed conversations via a tracking sidecar
- R5. Distill uses `pi-config.json`'s existing `llm` block for the configured small LLM
- R6. Distill sends all new transcripts in one batch, writes one fact file per cycle to `pi/facts/YYYY-MM-DD/NNN-title.md`
- R7. Distill does not call the LLM when there are no new undistilled conversations
- R8. Fact files are append-only — no cross-file references, no merge/dedup metadata
- R9. Raw conversations cool faster than fact files (default: 7d conversations, 30d facts)
- R10. The existing `before_agent_start` system-prompt injection is preserved unchanged
- R11. Old `turn_end` heuristic/LLM classification handler is removed

**Origin actors:** A1 (Human user), A2 (Pi extension), A3 (Strata daemon), A4 (Distill LLM), A5 (Agent)
**Origin flows:** F1 (Capture), F2 (Distill), F3 (Query / Reconcile)
**Origin acceptance examples:** AE1–AE5

---

## Scope Boundaries

- **No standalone distill CLI.** Distillation runs automatically during `strata serve`. No new CLI commands.
- **No supersedes or merge/dedup system.** Facts are append-only. Agent reconciles at read time.
- **No Janitor lifecycle changes.** Existing promote/migrate/evict mechanics unchanged. Conversations and facts flow through the same lifecycle with different decay thresholds.
- **No vector search or embedding pipeline.** Reconciliation is file-system native (timestamps, `strata search`).
- **No MCP protocol changes.** Knowledge capture and distill live entirely in the extension and daemon.
- **No new Python dependencies.** LLM API calls use stdlib `urllib.request`. No `httpx`, `requests`, or `openai` package added.
- **No new npm dependencies.** Extension changes stay zero-dep, using Node.js built-ins and global `fetch()`.

### Deferred to Follow-Up Work

- **Distill cost tracking via `strata_cost.log`** — the existing cost-log format can be extended with a DISTILL line type, but this is a tracking enhancement, not a core feature. Can be added in a separate PR.

---

## Context & Research

### Relevant Code and Patterns

- **`skills/pi/strata.ts`** — The existing Pi extension. Has `before_agent_start` and `turn_end` hooks, `pi-config.json` loading, and three provider LLM call implementations (OpenAI, Anthropic, OpenRouter). New `agent_end` handler follows the same hook pattern.
- **`strata/storage.py` — `QmdWrapper` class** — Pattern for a gracefully-degrading optional backend. Has lazy `check_available()`, all external calls wrapped in try/except, no hard dependency. The new `Distiller` class follows this pattern exactly.
- **`strata/storage.py` — `Stratum2Storage._access_sidecar_path()`** — Pattern for JSON sidecar tracking. Read-modify-write on a flat JSON file. The distill tracker uses the same pattern for `pi/distill_state.json`.
- **`strata/daemon.py` — `StrataDaemon._run_cycle()`** — The daemon's cycle wrapper. Calls `self._strata.run_maintenance()` and logs results. Distill integrates as an additional step in `run_maintenance()`.
- **`strata/__init__.py` — `Strata.run_maintenance()`** — Chains promote → janitor (promote/migrate/evict). Distill runs before promote so non-distilled conversations in active/ are processed before they could be migrated.
- **`strata/config.py` — `StrataConfig.get_decay_days()`** — Uses first path component as decay key. Needs multi-component support for `pi/conversations/` vs `pi/` (facts/memos).
- **`docs/pi-integration.md`** — Documents the full extension architecture, hook lifecycle, and config schema. Must be updated to reflect `agent_end` capture and removed `turn_end`.

### External References

- Pi Extension API docs: `docs/how_to_make_pi_extension.md` — documents `agent_end` receives `event.messages` (full conversation transcript), while `turn_end` only sees individual assistant messages.

---

## Key Technical Decisions

- **`agent_end` over `turn_end` for capture.** `agent_end` receives `event.messages` — the full conversation including user and assistant turns. `turn_end` only sees the single assistant message. This is the primary reason the current extension misses context.
- **Distill runs before promote (first step of maintenance).** Prevents a race where a new conversation in active/ is migrated to cooled/ between maintenance cycles before distill processes it. Distill reads from active/; running first guarantees transcripts are still there.
- **`urllib.request` for LLM API calls.** Strata is stdlib-only by design. No new pip dependencies. `urllib.request` with `urllib.parse` + `json` is sufficient for HTTP POST calls to OpenAI, Anthropic, and OpenRouter.
- **JSON sidecar for distill tracking.** Same pattern as `stratum_2_access.json`. Flat JSON at `pi/distill_state.json` mapping conversation paths to distillation metadata. Simple, proven, no DB needed.
- **One batch file per cycle.** All new transcripts are sent to the LLM in one call. This maximizes context efficiency and minimizes API call cost. If the LLM returns zero facts, no fact file is written but conversations are still marked as distilled (the LLM judged nothing worth extracting).
- **Conversation filename: `YYYYMMDD-{datetime}-{short-hash}.md`.** Date-prefixed for day-level search (`strata search 20260617`), date+time for ordering across concurrent sessions, short hash for uniqueness.
- **Decay thresholds via multi-component path matching.** `get_decay_days()` is extended to check progressively longer path prefixes, so `"pi/conversations": 7` and `"pi": 30` can coexist.

---

## Open Questions

### Resolved During Planning

- **Session identity format:** `YYYYMMDD-{datetime}-{short-hash}.md`. Date-prefixed for search, time + hash for uniqueness.
- **Distill model config:** Reuse existing `llm` block in `pi-config.json`. No separate `distill_llm` field since the per-turn classification call is eliminated.
- **Distill tracking mechanism:** JSON sidecar at `pi/distill_state.json`, matching the `stratum_2_access.json` pattern.
- **Distill in maintenance ordering:** Before promote, so conversations are processed before they could be migrated.

### Deferred to Implementation

- **LLM prompt template for distillation.** The prompt design (system prompt, formatting instructions, output schema) affects extraction quality and should be empirically iterated during implementation. Initial version: instruct the LLM to extract facts as bullet points with topic categories, one fact file per batch.
- **Max transcript tokens per batch.** If 50 transcripts exceed the LLM's context window, implement a truncation strategy (send N most recent, rotate remaining to next cycle). Default: try all in one batch.
- **Hash source for session identity.** Options: short hash of the full message content, UUID fragment, timestamp-only (low-concurrency environments). Will choose during implementation based on testing.
- **Dry-run semantics for distill.** The existing lifecycle pattern (report "would N" without side effects) applies to scanning conversations. The LLM call is inherently non-dry-runnable. Implementation should: report undistilled count, skip LLM call, log what would have been extracted.

---

## Output Structure

```
skills/pi/
  strata.ts                          # Modified — agent_end capture added, turn_end removed

strata/
  __init__.py                        # Modified — Distiller import, run_maintenance extended
  config.py                          # Modified — get_decay_days extended for multi-component paths
  distiller.py                       # NEW — Distiller class, LLM API calls, tracking

strata_data/
  active/pi/
    conversations/                   # NEW — raw transcripts (created by extension)
      2026-06-17/
        20260617T143022-abcd1234.md
    facts/                           # NEW — distilled fact files (created by daemon)
      2026-06-17/
        001-extracted-knowledge.md
    memos/                           # Existing — heuristic captures (unchanged)
    distill_state.json               # NEW — tracking sidecar (created by daemon)

tests/
  test_distiller.py                  # NEW — unit tests for Distiller module
  test_daemon.py                     # Modified — tests for distill integration
  test_janitor.py                    # May be modified — if decay threshold tests affected
```

---

## Implementation Units

### U1. Add `agent_end` capture to Pi extension

**Goal:** Replace the `turn_end` heuristic/LLM classification with always-on full-conversation capture at `agent_end`. Raw transcripts are saved to `pi/conversations/` as plain markdown files.

**Requirements:** R1, R2, R10, R11

**Dependencies:** None — standalone extension change

**Files:**

- Modify: `skills/pi/strata.ts`
- Test: manual verification via Pi (no automated test harness for TypeScript extension)

**Approach:**

1. Remove the `turn_end` handler entirely (both LLM classification and heuristic fallback). This includes removing `isWorthStoring()`, `classifyWithLLM()`, `callOpenAI()`, `callAnthropic()`, `callOpenRouter()`, `buildClassificationPrompt()`, and `persistToStrata()`. The `deriveStorePath()` function may also be removed or kept for other uses.
2. Keep `before_agent_start` handler unchanged.
3. Add a new `pi.on("agent_end", ...)` handler that:
   - Extracts the full conversation from `event.messages` (available as an array of message objects)
   - Formats it as a markdown document with a header section (date, session metadata) and the full message sequence
   - Generates the session identity: `YYYYMMDDThhmmss-{short-hash}` where the hash is derived from the message content (use a simple hash function via Node.js native `crypto` module)
   - Saves to `pi/conversations/YYYY-MM-DD/YYYYMMDDThhmmss-{hash}.md` by constructing a `strata add` call, OR by writing directly using `node:fs`
4. Decision: write directly via `node:fs` (faster, fewer dependencies on `strata add` CLI) or via `pi.exec("strata", ["add", ...])` (consistent with existing pattern). Prefer direct `node:fs` write since the path is known — no need for the CLI routing logic.

**Patterns to follow:**

- `before_agent_start` handler for hook registration pattern
- `extractTextFromMessage()` — existing function for extracting text from message objects (currently only extracts from a single assistant message; will need adaptation for full conversation)
- `getStrataBaseDir()` — existing path resolution for the base directory

**Test scenarios:**

- **Happy path:** Given an `agent_end` event with 3 conversation messages, the handler creates a file at `pi/conversations/YYYY-MM-DD/YYYYMMDDThhmmss-{hash}.md` containing the formatted transcript
- **Edge case — event with empty messages:** Handler skips without error when `event.messages` is empty or absent
- **Edge case — existing conversations directory:** Handler creates a new file inside an already-existing date directory alongside existing transcripts
- **Error path — filesystem write failure:** Handler silently fails (catch and log, never block Pi)

**Verification:**

- After a Pi session, a transcript file exists at the expected path under `pi/conversations/`
- The file contains the user's messages and the assistant's responses in chronological order
- The `before_agent_start` prompt injection still fires correctly
- Removing the old `turn_end` handler does not cause Pi startup errors

---

### U2. Create `strata/distiller.py` module

**Goal:** New Python module that reads new conversation transcripts, calls the configured small LLM via stdlib HTTP, and writes extracted fact files.

**Requirements:** R4, R5, R6, R7, R8

**Dependencies:** U1 must define the conversation file format and location

**Files:**

- Create: `strata/distiller.py`
- Test: `tests/test_distiller.py`

**Approach:**

1. Create `Distiller` class following the `QmdWrapper` pattern:
   - Constructor accepts `StrataConfig` and optionally a custom `pi_config_path`
   - Lazy-init: reads `pi-config.json` on first use, not at construction
   - All external calls wrapped in try/except returning status dicts
   - Graceful degradation: missing config, missing API key, network errors all return empty results

2. Configuration loading (`_load_config()`):
   - Read `<base_dir>/pi-config.json` (same file the extension reads)
   - Parse `llm` block — `enabled`, `provider`, `model`, `apiKey`
   - Resolve API key: direct string → env var reference (`${VAR}`) → well-known env vars per provider → empty
   - If `enabled` is `false` or no API key resolves, distill is disabled

3. Conversation scanning (`_find_new_conversations()`):
   - Walk `active/pi/conversations/` recursively for `*.md` files
   - Load distill state from `active/pi/distill_state.json`
   - Return only files not yet in the state dict
   - State shape: `{"conversations": {"rel_path": {"distilled_at": "timestamp", "cycle": N}}, "last_checked": "timestamp"}`

4. LLM API calls (`_call_llm(transcripts)`):
   - Implement three provider functions using `urllib.request`:
     - `_call_openai(messages, config)` — POST to `https://api.openai.com/v1/chat/completions`
     - `_call_anthropic(messages, config)` — POST to `https://api.anthropic.com/v1/messages`
     - `_call_openrouter(messages, config)` — POST to `https://openrouter.ai/api/v1/chat/completions`
   - Build extraction prompt: instruct the LLM to extract facts as bullet points, each with a topic category and a one-sentence description
   - Send all new transcripts joined by separators as a single system + user message pair
   - Parse the response for extracted fact content

5. Fact file writing (`_write_fact(content)`):
   - Compute date-based path: `pi/facts/YYYY-MM-DD/`
   - Determine the next sequential number: scan existing files in the date directory, max+1
   - Derive title from first significant line of this batch's output (or use a generic batch title)
   - Write content as markdown file

6. Distill state management (`_mark_distilled(conversation_paths)`):
   - Read `distill_state.json`, add entries for processed files
   - Write back (read-modify-write, same as `stratum_2_access.json`)

7. Public API:
   - `process(dry_run=False) -> dict` — main entry point. Scans conversations, calls LLM if new ones exist and config allows, writes facts, updates state. Dry-run returns count without calling LLM.
   - `check_available() -> bool` — whether `pi-config.json` has a valid LLM config
   - `get_pending_count() -> int` — number of undistilled conversations (no LLM call)

**Patterns to follow:**

- `QmdWrapper` in `strata/storage.py` — lazy `_available` flag, try/except wrappers, status dict returns
- `Stratum2Storage._access_sidecar_path()` — JSON sidecar read-modify-write pattern
- `Stratum1Storage._resolve()` — path traversal safety
- `Pi extension callOpenAI()` / `callAnthropic()` in `skills/pi/strata.ts` — the TypeScript implementations already define the exact API request/response shapes; the Python versions mirror them

**Test scenarios:**

- **Happy path — no new conversations:** `get_pending_count()` returns 0, `process()` returns `{"status": "skipped", "reason": "no_new_conversations", "processed": 0}`
- **Happy path — new conversations with LLM:** Given 2 undistilled transcripts and valid `pi-config.json`, `process()` calls the LLM (mock the HTTP call), writes a fact file to `pi/facts/YYYY-MM-DD/001-*.md`, and updates `distill_state.json` for both source files
- **Edge case — LLM returns no facts:** LLM responds with "no significant facts to extract". `process()` still marks conversations as distilled, writes no fact file, returns `{"status": "no_facts_extracted"}`
- **Edge case — `pi-config.json` missing:** `check_available()` returns `False`, `process()` returns `{"status": "skipped", "reason": "no_config"}`
- **Edge case — API call fails (network error):** `process()` returns `{"status": "error", "reason": "api_error"}`, conversations are NOT marked as distilled, retriable next cycle
- **Edge case — invalid JSON response from LLM:** Parsing fails, treated as API error, conversations not marked
- **Edge case — dry run:** `process(dry_run=True)` returns `{"status": "dry_run", "would_process": 2}`, no LLM call, no state changes
- **Edge case — distill_state.json corrupted:** Malformed JSON causes a read error; `_find_new_conversations()` returns all conversations (reprocesses from scratch)
- **Integration — provider selection:** `_call_llm` routes to correct provider function based on `pi-config.json` provider field (OpenAI, Anthropic, OpenRouter)
- **Integration — env var resolution:** API key from `${STRATA_OPENAI_API_KEY}` resolves correctly

**Verification:**

- `pytest tests/test_distiller.py` passes all scenarios
- Manual E2E: create a fake `pi-config.json`, write a transcript file, call `distiller.process()` from Python REPL, verify fact file is created with expected content
- Manual failure: delete `pi-config.json`, verify `process()` returns gracefully without crash

---

### U3. Integrate distill into Strata class and daemon

**Goal:** Wire the `Distiller` into the `Strata` class and daemon maintenance cycle so distill runs automatically.

**Requirements:** R3, R9

**Dependencies:** U2 (Distiller must exist)

**Files:**

- Modify: `strata/__init__.py`
- Modify: `strata/config.py`
- Modify: `tests/test_daemon.py`
- Modify: `tests/test_janitor.py` (potentially, if decay thresholds changed)

**Approach:**

1. In `strata/__init__.py`:
   - Add `from strata.distiller import Distiller`
   - In `Strata.__init__()`, add `self.distiller = Distiller(self.config)`
   - Modify `run_maintenance()` to add distill as the first step, before janitor:

     ```python
     def run_maintenance(self, dry_run: bool = False) -> dict:
         distilled = self.distiller.process(dry_run=dry_run)
         promoted = self.promote(dry_run=dry_run)
         migrated = self.migrate(dry_run=dry_run)
         evicted = self.evict(dry_run=dry_run)
         return {
             "distilled": distilled,
             "promoted": promoted,
             "migrated": migrated,
             "evicted": evicted,
             "total_distilled": ...,
             ...
         }
     ```

2. In `strata/config.py`:
   - Modify `get_decay_days()` to support multi-component path matching:

     ```python
     def get_decay_days(self, path: str) -> int:
         rel = path.strip("/")
         parts = rel.split("/")
         # Check progressively longer prefixes: "pi" → "pi/conversations"
         for i in range(len(parts), 0, -1):
             key = "/".join(parts[:i])
             if key in self.decay_thresholds:
                 return self.decay_thresholds[key]
         return self.decay_thresholds.get("*", 30)
     ```

   - Add default decay thresholds:

     ```python
     decay_thresholds: dict = field(
         default_factory=lambda: {
             "projects": 14,
             "entities": 60,
             "gtd": 7,
             "pi/conversations": 7,  # NEW — raw transcripts cool faster
             "pi": 30,               # NEW — facts and memos under pi/
             "*": 30,
         }
     )
     ```

3. In daemon (`strata/daemon.py`):
   - No changes needed — `_run_cycle()` already calls `self._strata.run_maintenance()`, which now includes distill.
   - The daemon already logs cycle results. Distill results will appear in the returned dict automatically.
   - Consider adding a log line for distill if it processed files (e.g., `[Cycle N] Distilled: X files`).

4. The daemon's existing `dry_run_first` flag will cause the first cycle to skip the LLM call (since `process(dry_run=True)` skips it). This is correct behavior — first-cycle dry run previews what distill would process.

**Patterns to follow:**

- Existing `run_maintenance()` return dict shape — distill follows the same `{"status", "counts"}` pattern
- Existing daemon cycle logging — `_run_cycle` already logs migrated/evicted counts; distill count added alongside
- `StrataConfig` field default factory — existing `field(default_factory=...)` pattern for mutable defaults

**Test scenarios:**

- **Integration — distill in maintenance cycle:** Given a `Strata` instance with an undistilled conversation in `pi/conversations/`, calling `run_maintenance()` executes distill before promote/migrate/evict. The conversation is marked distilled in `distill_state.json`.
- **Integration — dry run maintenance:** `run_maintenance(dry_run=True)` calls `distiller.process(dry_run=True)`, no LLM call is made, no state changes.
- **Regression — maintenance still works without config:** If `pi-config.json` is missing, `run_maintenance()` still runs promote/migrate/evict normally, and distill returns a no-op result.
- **Config — decay threshold matching:** Path `pi/conversations/2026-06-17/file.md` matches `"pi/conversations": 7` (longest prefix match). Path `pi/facts/2026-06-17/file.md` matches `"pi": 30`. Path `projects/notes.md` matches `"projects": 14` (unchanged behavior).
- **Regression — existing decay threshold paths still work:** `projects/foo.md` maps to `"projects": 14`, `entities/bar.md` maps to `"entities": 60`, `unknown/x.md` maps to `"*": 30`.

**Verification:**

- `pytest tests/test_daemon.py` passes (existing tests + new distill integration tests)
- `pytest tests/test_janitor.py` passes (existing tests unaffected)
- Manual: start daemon with `strata serve`, create a test conversation file, verify next cycle processes it

---

### U4. Update documentation

**Goal:** Document all changes — new extension behavior, distilled fact storage, config fields, and CLI behavior — so docs stay in sync with the implementation.

**Requirements:** Project rule: "After every change, update the relevant docs."

**Dependencies:** U1, U2, U3 must be complete (docs describe the final state)

**Files:**

- Modify: `docs/pi-integration.md`
- Modify: `docs/configuration.md`
- Modify: `docs/cli-reference.md`
- Modify: `strata/cli.py` (the module docstring / usage text)
- Potentially: `docs/architecture.md` (distill as new daemon phase)
- Potentially: `README.md` (if feature warrants a mention)

**Approach:**

1. **`docs/pi-integration.md`** — Major update:
   - Replace the "Auto-Storage Decision Pipeline" section with a description of always-on capture at `agent_end`
   - Remove the LLM classification section (the `turn_end` LLM call is eliminated)
   - Add a "Background Distillation" section describing the daemon-based extraction
   - Update the "Storage Path Derivation" section to describe `pi/conversations/` and `pi/facts/`
   - Update the "File Layout" section to show `conversations/` and `facts/` directories
   - Add a new "Session Identity" section explaining `YYYYMMDD-{datetime}-{hash}.md` format

2. **`docs/configuration.md`** — Update decay threshold documentation:
   - Document new `pi/conversations` and `pi` decay threshold keys
   - Update the `StrataConfig` reference

3. **`docs/cli-reference.md`** — Minor update if distill-related config commands exist (`strata config` key listing)

4. **`strata/cli.py`** — Update module docstring if the distill feature adds commands (it shouldn't per scope — no standalone CLI command)

**Patterns to follow:**

- Existing doc structure in `docs/pi-integration.md` (markdown sections, code blocks, tables)
- The doc update pattern from previous changes (surgical, only what changed)

**Test scenarios:** (N/A — documentation only, no behavioral change)

**Verification:**

- Read each updated doc from end to end — no stale references to `turn_end` or LLM classification
- CLI reference matches actual CLI behavior
- Configuration reference matches actual `StrataConfig` fields

---

## System-Wide Impact

- **Interaction graph:** The Pi extension's `turn_end` handler is removed — any code or config relying on per-turn storage will stop. Users who explicitly enabled `llm.enabled` in `pi-config.json` will no longer get per-turn LLM classification; instead, the same LLM config now powers background distillation. This is intentional — the brainstorm resolved to eliminate the per-turn classification path entirely.
- **Error propagation:** Distill failures (network error, bad API key, malformed config) never crash the daemon or extension. Both layers catch and log errors silently. The extension is unbounded by Pi's event loop (async, fire-and-forget). The daemon wraps distill in try/except same as the rest of the cycle.
- **State lifecycle risks:**
  - **Partial-write to distill_state.json:** The read-modify-write on `distill_state.json` is not atomic. If the daemon is killed between reading and writing, conversations may be re-processed in the next cycle. This is acceptable — re-processing is idempotent (the LLM may produce slightly different fact files, but new files coexist alongside old ones).
  - **Orphaned distill_state.json:** If conversations are manually deleted from active/, their entries in `distill_state.json` become stale. The state file may slowly accumulate stale entries over time. This is acceptable — the state file is small (< 1KB even after months) and stale entries are harmless (they just mean "no need to process these non-existent files").
- **Unchanged invariants:** The `strata read` cascade, `strata search` query engine, MCP server, `before_agent_start` system prompt injection, and all Janitor lifecycle mechanics are unchanged. Conversations and facts flow through the existing lifecycle as plain files.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| LLM API call fails during distill | Wrapped in try/except — conversations not marked distilled, retried next cycle. Daemon logs error and continues. |
| `pi-config.json` missing or invalid | `Distiller.check_available()` returns False — distill silently skips. No crash. |
| 50+ new transcripts exceed LLM context window | Implementation will implement truncation: send N most recent, rotate remainder to next cycle. Default batch limit configurable (deferred to implementation). |
| User relies on `turn_end` LLM classification | Removed — but the `pi-config.json` `llm.enabled` flag is repurposed for distill. Users who set it to `true` will now get background distillation instead. Document this clearly. |
| Conversation files get migrated before distill | Distill runs first in maintenance cycle (before promote → migrate). Additionally, 7-day decay means conversations stay in active for a week — distill runs every 15 minutes. Extremely unlikely to miss. |
| Distill tokens per cycle exceed cost target | Single-batch LLM call at GPT-4o-mini prices: ~10K input tokens * $0.15/1M = ~$0.0015 per cycle. Even with 50 transcripts, well under $0.01 target. |

---

## Documentation / Operational Notes

- **Breaking change for existing users:** The `turn_end` LLM classification feature is removed. Users who had `llm.enabled: true` for per-turn classification will now have that config powering background distillation instead. The `pi-config.json` schema is unchanged, but the semantics of the `enabled` field shift. Update migration notes in the docs.
- **Migration path:** No data migration needed. Existing memos in `pi/memos/` are untouched. The new `pi/conversations/` and `pi/facts/` directories are created on first use.
- **Distill logs:** The daemon already logs every cycle. Distill results (processed count, errors) will appear in the daemon log at `strata.log`.

---

## Sources & References

- **Origin document:** [docs/brainstorms/pi-knowledge-capture-and-distill.md](../brainstorms/pi-knowledge-capture-and-distill.md)
- **Current Pi extension code:** `skills/pi/strata.ts`
- **Pi Extension API docs:** `docs/how_to_make_pi_extension.md` (for `agent_end` event spec)
- **Current daemon implementation:** `strata/daemon.py`
- **Current Strata class:** `strata/__init__.py`
