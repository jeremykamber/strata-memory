# Configuration

Strata is configured via the `StrataConfig` dataclass in `strata/config.py`. This page documents every configuration field, its default value, and how to change it at runtime.

## StrataConfig Fields

### Core Paths

| Field | Type | Default | Description |
|---|---|---|---|
| `base_dir` | `Path` | `./strata_data/` or `~/.strata/` | Root directory for all three strata. Auto-detected: project-local `./strata_data/` wins over global `~/.strata/`. Override with `$STRATA_HOME`. |
| `active_dir` | `str` | `"active"` | Directory name for the 1st Stratum (working memory). Relative to `base_dir`. |
| `cooled_dir` | `str` | `"cooled"` | Directory name for the 2nd Stratum (aged-out files). Relative to `base_dir`. |
| `stratum_3_archive` | `str` | `"archive"` | Directory name for the 3rd Stratum (cold JSON storage). Relative to `base_dir`. |
| `stratum_3_shadow_db` | `str` | `"stratum_3_shadow.db"` | Filename for the SQLite FTS5 shadow index. Relative to `base_dir`. |

### Decay Thresholds (Migration: 1st -> 2nd Stratum)

Controls how many days a file can sit untouched in the active stratum before the Janitor moves it to cooled.

| Field | Type | Default | Description |
|---|---|---|---|
| `decay_thresholds` | `dict[str, int]` | `{"projects": 14, "entities": 60, "gtd": 7, "pi/conversations": 7, "pi": 30, "*": 30}` | Days before a file is considered stale and eligible for migration from active to cooled. Keys can be multiple path components (e.g. `"pi/conversations"`) for deeper routing; matching uses the longest prefix. `"*"` is the fallback for unmatched paths. |

Default thresholds by directory:

| Directory | Threshold | Rationale |
|---|---|---|
| `projects/` | 14 days | Active initiatives. Two weeks without updates means they have cooled off. |
| `entities/` | 60 days | People, companies, tools. Context that stays relevant longer. |
| `gtd/` | 7 days | Tasks and quick notes. One week and they are stale. |
| `pi/conversations/` | 7 days | Raw conversation transcripts. Quick to accumulate, quick to cool. |
| `pi/` (facts, memos) | 30 days | Distilled facts and memos under `pi/`. One month without access. |
| Everything else | 30 days | Default. One month without access. |

### Promotion (2nd -> 1st Stratum)

Controls how frequently a cooled file must be accessed before it gets promoted back to active.

| Field | Type | Default | Description |
|---|---|---|---|
| `promotion_threshold` | `int` | `3` | Number of accesses to a cooled file before the Janitor promotes it back to active. Once a file crosses this threshold, it is moved from `cooled/` to `active/` and access tracking is reset. |

When a file in `cooled/` is read (via `strata read`), the access count increments. If it reaches `promotion_threshold`, the file is automatically promoted back to `active/` during the read operation. The batch `strata promote` and `strata maintenance` commands also check thresholds. This prevents frequently-referenced content from being buried by age-based decay.

### Rehydration (3rd -> 1st / 3rd -> 2nd)

Controls the default target tier when rehydrating archived files.

| Field | Type | Default | Description |
|---|---|---|---|
| `rehydration_target` | `str` | `"active"` | Default target stratum for rehydration. `"active"` restores to the 1st Stratum (editable). `"cooled"` restores to the 2nd Stratum (query-only). Can be overridden per-call with `--target=active|cooled`. |

### LRU Eviction (2nd -> 3rd Stratum)

Controls how long a file can sit untouched in the cooled stratum before the Janitor evicts it to the archive.

| Field | Type | Default | Description |
|---|---|---|---|
| `lru_days` | `int` | `90` | Days since last access after which a cooled file is eligible for eviction to archive. |
| `lru_min_access_count` | `int` | `1` | Maximum number of accesses a file may have to avoid eviction. Files accessed more often than this are retained. |
| `lru_decay_thresholds` | `dict[str, int]` | `{"*": 90}` | Per-directory LRU thresholds. Same pattern as `decay_thresholds`. Falls back to `lru_days` when no match. |

A file is evicted when: (now - last_accessed) > `lru_days` AND access_count <= `lru_min_access_count`.

### Search Backend

| Field | Type | Default | Description |
|---|---|---|---|
| `search_backend` | `str` | `"qmd"` | Search backend: `"qmd"` for BM25 + vector hybrid, `"fts5"` for SQLite FTS5 keyword only. |
| `qmd_enabled` | `bool` | `False` | Derived from `search_backend` (read-only property). True when `search_backend == "qmd"`. |
| `qmd_reranker` | `Optional[str]` | `None` | LLM reranker provider URL (e.g., `"openai://gpt-4o-mini"`, `"ollama://llama3"`). |
| `qmd_reranker_warning_shown` | `bool` | `False` | Internal flag to prevent repeated cost warnings. |
| `qmd_collection_prefix` | `str` | `"strata_"` | Prefix for QMD collection names (e.g., `"strata_active"`, `"strata_cooled"`). |

### File Patterns

| Field | Type | Default | Description |
|---|---|---|---|
| `active_file_patterns` | `list[str]` | `["*.md", "*.txt", "*.json", "*.yaml", "*.yml"]` | Glob patterns for files the Janitor considers when scanning the active stratum. Files not matching any pattern are ignored during migration. |

## Environment Variable Overrides

| Variable | Overrides | Description |
|---|---|---|
| `$STRATA_HOME` | `base_dir` | Forces the data directory to this path. The highest-priority override. Also used in `detect_base_dir()`. |

Resolution order for `base_dir`:

1. `$STRATA_HOME` environment variable (always wins)
2. `./strata_data/` in the current directory (project-local)
3. `~/.strata/` (global fallback)

## Persisted Configuration

Configuration is persisted to `strata.json` in the base directory after `strata init` or `strata config set`. This file stores runtime-overridable settings:

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

Fields not in this file use `StrataConfig` defaults. The persisted config merges with defaults at load time -- you only need to store values that differ from defaults.

## Runtime Configuration (CLI)

View and modify configuration at runtime:

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

The `strata config set` value parser understands:

- Integers: `14`, `0`, `-1`
- Floats: `3.14`, `0.5`
- Booleans: `true`, `false`, `yes`, `no`, `1`, `0`
- JSON arrays/objects: `'["*.md", "*.txt"]'`, `'{"projects": 21}'`
- Everything else: treated as a string

Changes persist immediately to `strata.json`.

## Pi Extension Configuration

The Pi extension (`skills/pi/strata.ts`) reads its own configuration from `<strataBaseDir>/pi-config.json`. This file is separate from `strata.json` because the Pi extension runs in TypeScript (not Python) and its config is consumed solely by the extension.

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
|-------|---------|-------------|
| `llm.enabled` | `false` | Enable LLM-powered memory classification. **Off by default.** When disabled, the extension uses the heuristic regex fallback. |
| `llm.provider` | `"openai"` | LLM provider: `"openai"`, `"anthropic"`, or `"openrouter"`. |
| `llm.model` | Provider default | Model identifier. Defaults: `gpt-4o-mini` (OpenAI), `claude-3-5-haiku-latest` (Anthropic), `openai/gpt-4o-mini` (OpenRouter). |
| `llm.apiKey` | `""` | API key or env var reference (`"${VAR_NAME}"`). When empty, falls back to well-known env vars per provider. |
| `llm.temperature` | `0.0` | LLM temperature (0.0 = deterministic classification). |
| `llm.maxTokens` | `500` | Maximum tokens for the classification response. |

### API Key Resolution

The extension resolves the API key in this order:

1. Direct string in `llm.apiKey`
2. Env var reference in `llm.apiKey` (e.g., `"${STRATA_OPENAI_API_KEY}"`)
3. Well-known env vars per provider: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`
4. Empty → LLM classification disabled, falls back to heuristic

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

This file is consumed only by the Pi extension (TypeScript), not by the Python CLI. Changes require a `/reload` in Pi to take effect.

## Cross-Reference

- [CLI Reference](cli-reference.md) -- commands to view and modify config at runtime
- [Architecture](architecture.md) -- how thresholds drive Janitor behaviour
- [Tracking](tracking.md) -- how configuration affects cost calculations
- [Search](search.md) -- search backend configuration details
- [Pi Integration](pi-integration.md) -- Pi extension configuration and LLM setup
