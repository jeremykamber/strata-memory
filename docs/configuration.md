# Configuration

Configuration lives in the `StrataConfig` dataclass inside `strata/config.py`. This page walks through every field, its default value, and how to tweak it at runtime. Think of it as the settings menu you never knew you needed.

## StrataConfig Fields

### Core Paths

| Field | Type | Default | Description |
|---|---|---|---|
| `base_dir` | `Path` | `./strata_data/` or `~/.strata/` | Root directory for all three strata. Auto-detected: project-local `./strata_data/` wins over global `~/.strata/`. Override with `$STRATA_HOME`. |
| `active_dir` | `str` | `"active"` | Directory name for the 1st Stratum (working memory). Relative to `base_dir`. |
| `cooled_dir` | `str` | `"cooled"` | Directory name for the 2nd Stratum (aged-out files). Relative to `base_dir`. |
| `stratum_3_archive` | `str` | `"archive"` | Directory name for the 3rd Stratum (cold JSON storage). Relative to `base_dir`. |
| `stratum_3_shadow_db` | `str` | `"stratum_3_shadow.db"` | Filename for the SQLite FTS5 shadow index. Relative to `base_dir`. |

Directory names  -  they're exactly what you'd expect. You can change them if you really want to, but the defaults are fine for almost everyone. The shadow DB filename lives here too, because it's another path under the base directory.

### Decay Thresholds (Migration: 1st -> 2nd Stratum)

These control how long a file can sit untouched in the active stratum before the Janitor nudges it over to cooled. Think of it as the "hey, are you still using this?" timer.

| Field | Type | Default | Description |
|---|---|---|---|
| `decay_thresholds` | `dict[str, int]` | `{"projects": 14, "entities": 60, "gtd": 7, "pi/conversations": 7, "pi": 30, "*": 30}` | Days before a file is considered stale and eligible for migration from active to cooled. Keys can be multiple path components (e.g. `"pi/conversations"`) for deeper routing; matching uses the longest prefix. `"*"` is the fallback for unmatched paths. |

Default thresholds by directory:

| Path prefix | Threshold | Rationale |
|---|---|---|
| `projects` | 14 days | Active initiatives. Two weeks without updates means they have cooled off. |
| `entities` | 60 days | People, companies, tools. Context that stays relevant longer. |
| `gtd` | 7 days | Tasks and quick notes. One week and they are stale. |
| `pi/conversations/` | 7 days | Raw conversation transcripts. Quick to accumulate, quick to cool. |
| `pi/` (facts, memos) | 30 days | Distilled facts and memos under `pi/`. One month without access. |
| Everything else | 30 days | Default. One month without access. |

The matching uses the longest prefix key, so a file in `pi/conversations/something.md` matches the 7-day `pi/conversations` rule instead of the 30-day `pi` rule. That's the kind of detail that sounds obvious once you read it, but made someone debug for an hour. You're welcome.

### Promotion (2nd -> 1st Stratum)

Sometimes a cooled file turns out to be more relevant than you thought. These fields control how often it needs to be accessed before it gets promoted back to active.

| Field | Type | Default | Description |
|---|---|---|---|
| `promotion_threshold` | `int` | `3` | Number of accesses to a cooled file before the Janitor promotes it back to active. Once a file crosses this threshold, it is moved from `cooled/` to `active/` and access tracking is reset. |

Here's how it works: when you read a file in `cooled/` (via `strata read`), its access count ticks up. Hit the threshold, and it gets promoted right then and there  -  no waiting for the next maintenance cycle. The batch commands (`strata promote` and `strata maintenance`) check thresholds too. This keeps frequently-referenced files from getting buried just because they're old.

### Rehydration (3rd -> 1st / 3rd -> 2nd)

Archived files don't have to stay archived forever. This field tells the system where they should land when they come back.

| Field | Type | Default | Description |
|---|---|---|---|
| `rehydration_target` | `str` | `"active"` | Default target stratum for rehydration. `"active"` restores to the 1st Stratum (editable). `"cooled"` restores to the 2nd Stratum (query-only). Can be overridden per-call with `--target=active\|cooled`. |

You might want "cooled" as the default if you're the cautious type  -  bring it back but don't let anyone edit it until they've proved they need to. Or just blast everything back to active and live on the edge. Your call.

### LRU Eviction (2nd -> 3rd Stratum)

This is the "you haven't touched this in a while" trigger for the cooled stratum. Files that nobody reads eventually get shipped off to the archive.

| Field | Type | Default | Description |
|---|---|---|---|
| `lru_days` | `int` | `90` | Days since last access after which a cooled file is eligible for eviction to archive. |
| `lru_min_access_count` | `int` | `1` | Maximum number of accesses a file may have to avoid eviction. Files accessed more often than this are retained. |
| `lru_decay_thresholds` | `dict[str, int]` | `{"*": 90}` | Per-directory LRU thresholds. Same pattern as `decay_thresholds`. Falls back to `lru_days` when no match. |

A file gets evicted when both conditions are true: it's been more than `lru_days` since anyone last looked at it, and it's been accessed fewer times than `lru_min_access_count`. In other words, if nobody's opened it in 90 days and it's only been read once (probably by accident), off it goes.

### Search Backend

| Field | Type | Default | Description |
|---|---|---|---|
| `search_backend` | `str` | `"qmd"` | Search backend: `"qmd"` for BM25 + vector hybrid, `"fts5"` for SQLite FTS5 keyword only. |
| `qmd_enabled` | `bool` | `False` | Derived from `search_backend` (read-only property). True when `search_backend == "qmd"`. |
| `qmd_reranker` | `Optional[str]` | `None` | LLM reranker provider URL (e.g., `"openai://gpt-4o-mini"`, `"ollama://llama3"`). |
| `qmd_reranker_warning_shown` | `bool` | `False` | Internal flag to prevent repeated cost warnings. |
| `qmd_collection_prefix` | `str` | `"strata_"` | Prefix for QMD collection names (e.g., `"strata_active"`, `"strata_cooled"`). |

`qmd_enabled` is derived from `search_backend`  -  you don't set it directly. If you switch to `fts5`, it's `False`. Switch back to `qmd`, it's `True`. Simple. The `qmd_reranker_warning_shown` flag is an internal detail you'll probably never touch. Consider it the "I told you this API call costs money" checkbox that gets ticked once and stays ticked.

### File Patterns

| Field | Type | Default | Description |
|---|---|---|---|
| `active_file_patterns` | `list[str]` | `["*.md", "*.txt", "*.json", "*.yaml", "*.yml"]` | Glob patterns for files the Janitor considers when scanning the active stratum. Files not matching any pattern are ignored during migration. |

Got some weird file extension from that one experiment you ran in 2022? Add it here, or watch the Janitor pretend it doesn't exist.

## Environment Variable Overrides

| Variable | Overrides | Description |
|---|---|---|
| `$STRATA_HOME` | `base_dir` | Forces the data directory to this path. The highest-priority override. Also used in `detect_base_dir()`. |

Resolution order for `base_dir`:

1. `$STRATA_HOME` environment variable (always wins  -  it's the nuclear option)
2. `./strata_data/` in the current directory (project-local)
3. `~/.strata/` (global fallback)

Most folks never set `$STRATA_HOME`. The auto-detection works well enough. But if you have Opinions about where your data lives, this is your escape hatch.

## Persisted Configuration

After `strata init` or `strata config set`, configuration gets written to `strata.json` in the base directory. It looks like this:

```json
{
  "search_backend": "qmd",
  "qmd_reranker": null,
  "lru_days": 90,
  "lru_min_access_count": 1,
  "decay_thresholds": {
    "projects": 14,
    "entities": 60,
    "gtd": 7,
    "*": 30
  },
  "active_file_patterns": ["*.md", "*.txt", "*.json", "*.yaml", "*.yml"]
}
```

Fields you don't include here fall back to `StrataConfig` defaults. The persisted file gets merged with defaults at load time, so you only need to store the things you're changing. It's the "don't repeat yourself" principle, applied to config storage. You're welcome.

## Runtime Configuration (CLI)

You can view and change config from the command line without ever opening a JSON file. Here's how:

```bash
# Show all configuration
strata config

# Get a specific value (supports dotted paths for nested fields)
strata config get decay_thresholds.projects
# Output: 14

strata config get lru_days
# Output: 90

# Set a value (value is auto-parsed: int, float, bool, JSON, or string)
strata config set decay_thresholds.projects 21
strata config set lru_days 60
strata config set search_backend fts5

# JSON mode for scripting
strata config --json
```

The value parser in `strata config set` is smarter than you'd expect:

- Integers: `14`, `0`, `-1`
- Floats: `3.14`, `0.5`
- Booleans: `true`, `false`, `yes`, `no`, `1`, `0`
- JSON arrays/objects: `'["*.md", "*.txt"]'`, `'{"projects": 21}'`
- Everything else: treated as a string

Changes hit the disk immediately  -  no `--save` flag, no `Are you sure?` prompt. If you typo a value, that's on you. (Okay, that's a little harsh. It'll probably be fine.)

## Pi Extension Configuration

The Pi extension (`skills/pi/strata.ts`) uses its own config file: `<strataBaseDir>/pi-config.json`. It's separate from `strata.json` because the Pi extension is written in TypeScript, not Python, and its settings are meaningless to the CLI anyway.

### File Location

| Strata Store | Config Path |
|---|---|
| Global (`~/.strata/`) | `~/.strata/pi-config.json` |
| Project-local (`./strata_data/`) | `./strata_data/pi-config.json` |

### Schema

```json
{
  "llm": {
    "enabled": false,
    "provider": "openai",
    "model": "gpt-4o-mini",
    "apiKey": "",
    "temperature": 0.0,
    "maxTokens": 500
  }
}
```

### Fields

| Field | Default | Description |
|---|---|---|
| `llm.enabled` | `false` | Enable LLM-powered memory classification. **Off by default.** When disabled, the extension uses the heuristic regex fallback. |
| `llm.provider` | `"openai"` | LLM provider: `"openai"`, `"anthropic"`, or `"openrouter"`. |
| `llm.model` | Provider default | Model identifier. Defaults: `gpt-4o-mini` (OpenAI), `claude-3-5-haiku-latest` (Anthropic), `openai/gpt-4o-mini` (OpenRouter). |
| `llm.apiKey` | `""` | API key or env var reference (`"${VAR_NAME}"`). When empty, falls back to well-known env vars per provider. |
| `llm.temperature` | `0.0` | LLM temperature (0.0 = deterministic classification). |
| `llm.maxTokens` | `500` | Maximum tokens for the classification response. |

LLM classification is off by default. There's a reason for that  -  it costs money, it's slower, and the heuristic regex fallback actually works pretty well for most people. Turn it on if you want better classification. Leave it off if you like free.

### API Key Resolution

The extension hunts for an API key in this order:

1. Direct string in `llm.apiKey`
2. Env var reference in `llm.apiKey` (e.g., `"${STRATA_OPENAI_API_KEY}"`)
3. Well-known env vars per provider: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`
4. Empty → LLM classification disabled, falls back to heuristic

Step 4 is the "we give up" case. If you don't set a key anywhere, the extension quietly shrugs and uses the heuristic instead. No errors, no drama.

### Example

```json
{
  "llm": {
    "enabled": true,
    "provider": "openai",
    "apiKey": "${STRATA_OPENAI_API_KEY}"
  }
}
```

This file is only consumed by the Pi extension (the TypeScript one), not the Python CLI. If you change it, you'll need a `/reload` in Pi before the new settings kick in.

## Cross-Reference

- [CLI Reference](cli-reference.md) -- commands to view and modify config at runtime
- [Architecture](architecture.md) -- how thresholds drive Janitor behaviour
- [Tracking](tracking.md) -- how configuration affects cost calculations
- [Search](search.md) -- search backend configuration details
- [Pi Integration](pi-integration.md) -- Pi extension configuration and LLM setup
