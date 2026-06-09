# Search

Strata supports multiple search backends. Without any extras, it uses built-in filesystem grep for active and cooled strata, plus SQLite FTS5 for the archive shadow index. With the optional QMD package, it can use BM25 full-text search combined with vector embeddings for hybrid retrieval.

## Search Flow

When you run `strata search <query>` or `strata query <query>`, the `QueryEngine` follows a cascade:

```
                     ┌──────────────────┐
                     │   strata search  │
                     │   "oauth2 koda"  │
                     └────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   QMD available?  │
                    │  (npm @tobilu/qmd)│
                    └─────┬──────┬──────┘
                     YES  │      │  NO
               ┌──────────┘      └──────────┐
               ▼                              ▼
     ┌──────────────────┐          ┌──────────────────┐
     │  QMD hybrid      │          │  Filesystem grep  │
     │  search          │          │  stratum_1 + 2    │
     │  (BM25 + vector) │          │  (simple term     │
     │  All collections │          │   matching)       │
     └────────┬─────────┘          └────────┬─────────┘
              │                             │
              └──────────┬──────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │  Shadow Index    │
              │  FTS5 search     │
              │  (always runs)   │
              │  stratum_3       │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  Rank & dedupe   │
              │  Return top_k    │
              │  results         │
              └──────────────────┘
```

### Phase 1: QMD Hybrid Search (When Available)

If QMD is installed, Strata runs a hybrid search across both active and cooled strata collections:

1. **BM25 Full-Text Search** (`strata search` via `qmd search`): Keyword matching with term frequency weighting.
2. **Vector Semantic Search** (`strata vsearch` via `qmd vsearch`): Embedding-based similarity search.
3. **Reciprocal Rank Fusion (RRF)**: Combines both result sets using `RRF` scoring (`score += 1 / (k + position)` where `k=60`). This gives a ranked, deduplicated list.
4. **Optional LLM Reranking**: If a reranker provider is configured (e.g., `openai://gpt-4o-mini`), QMD can re-rank results using an LLM. This uses API credits.

QMD hybrid search provides semantic understanding without an LLM. The BM25 + vector fusion catches both exact keyword matches and conceptually similar content.

### Phase 1: Filesystem Search (Fallback)

When QMD is not available, Strata falls back to a simple filesystem grep-like search:

1. Walk `active/` and `cooled/` recursively
2. For each file, split the query into lowercase terms
3. Score each file by term matches in path (1.0 per term) and content (0.5 per term)
4. Return top results per stratum

The fallback is zero-dependency and works everywhere, but does not provide semantic matching. Search quality depends on keyword overlap.

### Phase 2: Shadow Index (Always Runs)

After gathering results from active and cooled strata (via either QMD or filesystem search), the engine always searches the 3rd Stratum Shadow Index:

1. Connect to the SQLite FTS5 database (`stratum_3_shadow.db`)
2. Run the FTS5 `MATCH` query against `keywords` and `summary_preview` columns
3. Score results by FTS5 rank (descending)
4. If provided, also search by tags via `keywords LIKE '%"tagname"%'`

### Phase 3: Fusion and Ranking

Results from all three phases are merged, sorted by score (descending), and the top `top_k` (default: 10) are returned:

```json
[
  {
    "content": "# Koda Platform\nStack: React + Go...",
    "tier": "stratum_1",
    "source": "projects/koda/spec.md",
    "score": 1.5,
    "metadata": {"path": "projects/koda/spec.md", "size": 1234}
  },
  {
    "content": "# Koda Database Schema...",
    "tier": "stratum_3",
    "source": "archive:stratum_3_abc123.json",
    "score": 0.25,
    "metadata": {
      "id": "uuid-123",
      "archive_path": "/path/to/archive/abc123.json",
      "_needs_rehydration": true
    }
  }
]
```

## Search Backends

### Filesystem Grep (Fallback)

The built-in fallback. Searches active and cooled strata by walking directories and matching terms.

- **Dependencies:** Zero (stdlib only)
- **Latency:** Proportional to number of files (walks all files)
- **Quality:** Keyword-based, no semantic matching
- **Best for:** Small to moderate stores (< 1000 files)

### Shadow Index (SQLite FTS5)

Always used for the archive stratum. Lightweight keyword index.

- **Dependencies:** Zero (stdlib `sqlite3`)
- **Latency:** ~5ms per query regardless of index size
- **Quality:** Keyword-based FTS5 matching with ranking
- **Storage:** ~200 bytes per entry (keywords + 200-char preview + path)

### QMD (BM25 + Vector Fusion)

Optional hybrid search engine. Runs locally, no LLM required for base hybrid search.

- **Dependencies:** Node.js + `@tobilu/qmd`
- **Latency:** ~100-500ms per query (embedding computation)
- **Quality:** Semantic matching via embeddings + BM25 keyword fusion
- **Storage:** Vector index size depends on collection size

#### Setup

```bash
npm install -g @tobilu/qmd
strata qmd-setup    # Add active/ + cooled/ as QMD collections
strata qmd-embed    # Generate vector embeddings
```

Collections are named `strata_active` and `strata_cooled`. The prefix is configurable via `qmd_collection_prefix`.

#### Reranker Providers

QMD supports optional LLM rerankers for improved result quality:

| Provider | Example URL | Cost |
|---|---|---|
| OpenAI | `openai://gpt-4o-mini` | API credits |
| Anthropic | `anthropic://claude-3-haiku` | API credits |
| Ollama | `ollama://llama3` | Local compute |
| Local GGUF | `local://path/to/model.gguf` | Local compute |

Configure via:
```bash
strata config set qmd_reranker "openai://gpt-4o-mini"
```

## Performance Characteristics

| Search Backend | 100 files | 10,000 files | 1M archived |
|---|---|---|---|
| Filesystem grep | ~5ms | ~500ms | N/A |
| Shadow Index FTS5 | ~5ms | ~5ms | ~50ms |
| QMD hybrid | ~100ms | ~500ms | N/A (active/cooled only) |

## Agent Usage

### CLI (recommended for agents)

```bash
# Human-readable output
strata search "koda oauth2"

# JSON output for scripting
strata query "koda oauth2"
```

### Python API

```python
from strata import Strata

strata = Strata()

# Search across all tiers
results = strata.query("koda oauth2")
for r in results:
    print(f"[{r['tier']}] {r['source']}: {r['content'][:80]}")

# With filters
results = strata.query(
    "koda",
    filters={"tags": ["project"]},
    top_k=10,
)
```

### Function Calling Tools

```python
# Get tool schemas for agent registration
tools = strata.tools.all_schemas()

# The strata_query tool expects:
# - query: string (required)
# - tags: string[] (optional)
# - top_k: integer (optional, default 5)
result = strata.tools.execute("strata_query", {"query": "koda"})
```

## Best Practices

1. **Use specific queries.** "koda oauth2 stripe" beats "project info" for precision.
2. **Start with `strata list` or `strata read index.md`** for known paths. Search is for discovery.
3. **Check tier labels.** Archived results have lower scores and may need rehydration.
4. **Install QMD for larger stores.** The filesystem fallback degrades with file count; QMD stays fast.
5. **Use `strata query` for scripting.** The JSON output is stable and parseable.

## Cross-Reference

- [CLI Reference](cli-reference.md) -- `strata search` and `strata query` commands
- [Architecture](architecture.md) -- how the shadow index fits into the tiered system
- [Installation](installation.md) -- QMD setup instructions
- [Tracking](tracking.md) -- cost comparison of search backends
- [Configuration](configuration.md) -- search_backend and qmd_reranker settings
