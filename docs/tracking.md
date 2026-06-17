# Cost Tracking

Strata keeps tabs on storage and operational costs across its three-tier system. This page explains the methodology, the `strata cost` command, and the data format behind it all.

## CostTracker

The `CostTracker` class in `strata/tracking.py` estimates how much  -  well, tokens  -  the Janitor is saving you. It reads the daemon log, extracts lifecycle metrics, and applies a simple token-estimation model. Nothing fancy, but it gets the job done.

### Metrics Tracked

| Metric | Description | Source |
|---|---|---|
| Daemon cycles | Number of completed maintenance cycles | Log lines matching `[Cycle N]` |
| Files migrated | Total files moved from active to cooled | Sum of `Migrated: N` values |
| Files evicted | Total files moved from cooled to archive | Sum of `Evicted: N` values |
| LRU decisions | Each eviction represents an LRU decision | Same as evicted count |
| Tokens saved | Estimated tokens not re-processed by LLM | Calculated from migrated/evicted counts |

### Token Estimation Methodology

The estimate compares against a hypothetical (and frankly wasteful) system that keeps every file in the active tier forever, requiring full re-processing on every cycle. Strata's smarter than that.

**Formula:**

```
tokens_saved = (migrated_files * 2000) + (evicted_files * 500)
```

| Variable | Value | Rationale |
|---|---|---|
| Active file size | ~2000 tokens | A typical markdown memory file, roughly 1500 words |
| Cooled file contribution | ~500 tokens | Archived files are accessed less; they contribute ~1/3 of the tokens of an active file |
| Estimation range | +-20% | Accounts for file size variation |

**Range output:** `lower = tokens * 80%`, `upper = tokens * 120%`. Think of it as a polite way of saying "give or take twenty percent."

### Methodology Text

- **Daemon cycles:** Counted from unique `[Cycle N]` entries in the daemon log. One cycle, one entry.
- **Files migrated:** Summed from the `Migrated:` values in daemon log lines.
- **Files evicted:** Summed from the `Evicted:` values in daemon log lines.
- **LRU decisions:** Every eviction is an LRU decision. Same number, just dressed up differently.
- **Tokens saved:** Compared against the hypothetical "keep everything forever" model. You're saving tokens by not reprocessing what you've already moved out of the way.

**Disclaimer:** These are ranges, not guarantees. Actual savings depend on file sizes and how often you access stuff. Your mileage may vary.

## The `strata cost` Command

```bash
strata cost
```

Running this prints a formatted savings summary. It looks something like this:

```
Strata Cost Savings (Estimated)
========================================
  Daemon cycles:     3
  Files migrated:    12
  Files evicted:     4
  LRU decisions:     4
  Tokens saved:      26,000 tokens
  Savings range:     20,800 - 31,200

  Methodology: Compared against hypothetical system...
  Disclaimer: These are approximate ranges...
```

Need machine-readable output? Use `--json` or `--agent`:

```bash
strata cost --json
```

Which gives you:

```json
{
  "status": "success",
  "command": "cost",
  "data": {
    "daemon_cycles": {"value": 3, "methodology": "...", "disclaimer": "..."},
    "files_migrated": {"value": 12, "methodology": "...", "disclaimer": "..."},
    "files_evicted": {"value": 4, "methodology": "...", "disclaimer": "..."},
    "lru_decisions": {"value": 4, "methodology": "...", "disclaimer": "..."},
    "tokens_saved_estimate": {"value": 26000, "methodology": "...", "disclaimer": "..."},
    "tokens_saved_range": {"value": "20,800 - 31,200", "methodology": "...", "disclaimer": "..."},
    "hook_calls": {
      "llm_calls_made": {"value": 0, "methodology": "...", "disclaimer": "..."},
      "tokens_consumed_estimate": {"value": 0, "methodology": "...", "disclaimer": "..."},
      "estimated_cost_usd": {"value": "$0.00", "methodology": "...", "disclaimer": "..."}
    }
  },
  "duration_ms": 12.3
}
```

If there's no daemon activity yet  -  say you just installed and haven't run `strata serve`  -  it gently tells you: "No daemon activity yet. Run 'strata serve' first."

## Cost Data Log

Every live (non-dry-run) daemon cycle writes a tracking line to `strata_cost.log`. Think of it as a paper trail for your savings.

**Format:**

```
CYCLE:<cycle_number>:<migrated_count>:<evicted_count>:<timestamp>
```

**Example:**

```
CYCLE:1:3:0:2026-06-08T02:00:00Z
CYCLE:2:0:1:2026-06-08T02:15:00Z
CYCLE:3:1:2:2026-06-08T02:30:00Z
```

| Field | Type | Description |
|---|---|---|
| CYCLE | literal | Identifies this as a cycle record. |
| cycle_number | int | Monotonically increasing cycle number. |
| migrated_count | int | Files migrated from active to cooled in this cycle. |
| evicted_count | int | Files evicted from cooled to archive in this cycle. |
| timestamp | ISO 8601 | Time of cycle completion (UTC). |

The log is append-only and never truncated. The `CostTracker` parses it to compute your aggregate metrics. Yes, it'll grow forever, but these lines are tiny  -  don't lose sleep over it.

## Storage Costs by Tier

| Stratum | Storage Medium | Relative Cost | Notes |
|---|---|---|---|
| Active | Markdown files on disk | Low | Plain text, no indexing overhead. |
| Cooled | Markdown files on disk | Low | Same as active, files just moved. |
| Archive | JSON blobs + SQLite FTS5 | Minimal | Compressed entries, tiny shadow index. ~200 bytes per entry for index. |

## Operational Costs

| Operation | Cost | Description |
|---|---|---|
| Migration | Trivial | One filesystem copy + delete per file. |
| Eviction | Trivial | One filesystem read, one JSON write, one SQLite insert. |
| Rehydration | Trivial | One SQLite select + one filesystem write. |
| Daemon idle | ~2 MB memory | Python process sleeping between cycles. |

## Search Costs by Backend

| Search Backend | Cost Character | Overhead |
|---|---|---|
| Filesystem grep | Free | No additional infrastructure. |
| Shadow Index (FTS5) | Minimal | Tiny SQLite database, no network calls. |
| QMD (BM25 + vector) | Moderate | Requires Node.js runtime, embedding computation on first run. |
| QMD + LLM reranker | Variable | Uses API credits or local compute per query. |

## Why No LLM Calls

Strata's Janitor doesn't use LLMs. It's all deterministic rules  -  file age, access count, that sort of thing. That decision comes with some nice perks:

- Maintenance costs are bounded and predictable. No mystery bills.
- No per-operation API fees. Every migration and eviction is free.
- Zero-effort setup: no API keys, no budgets, no ugly surprises.
- The `strata cost` command tracks only savings, not expenditures. Why? Because the Janitor itself costs absolutely nothing to run.

## Cross-Reference

- [Configuration](configuration.md) -- thresholds that affect cost
- [Architecture](architecture.md) -- lifecycle operations that incur cost
- [Search](search.md) -- cost differences between search backends
