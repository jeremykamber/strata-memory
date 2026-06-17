# Search

So you want to find something. Strata's got a few ways to help, depending on how elaborate you want to get. Out of the box  -  no extras, no fuss  -  it uses plain old filesystem grep for active and cooled files, plus SQLite FTS5 for the archive shadow index. Bring along the optional QMD package, and suddenly you've got BM25 full-text search and vector embeddings doing a hybrid dance. Fancy.

## Search Flow

When you run `strata search <query>` or `strata query <query>`, the `QueryEngine` follows a cascade  -  a funnel that starts with the fanciest tool available and works its way down:

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

If you've got QMD installed, Strata starts by running a hybrid search across both active and cooled collections. Here's the breakdown:

1. **BM25 Full-Text Search** (`strata search` via `qmd search`): Good old keyword matching, weighted by term frequency. If your query words appear in the file, this finds them.

2. **Vector Semantic Search** (`strata vsearch` via `qmd vsearch`): Embedding-based similarity. This is where it gets clever  -  it finds stuff that's conceptually related, not just keyword-matched.

3. **Reciprocal Rank Fusion (RRF)**: Combines both result sets using `RRF` scoring (`score += 1 / (k + position)` where `k=60`). The result: a ranked, deduplicated list that's better than either method alone.

4. **Optional LLM Reranking**: Configured a reranker provider (say `openai://gpt-4o-mini`)? QMD can re-rank results using an actual LLM. This costs API credits, so save it for when you really need that extra polish.

The neat thing about QMD hybrid search is that it gives you semantic understanding without needing an LLM at all. The BM25 + vector fusion catches both exact keyword matches and conceptually similar content. Best of both worlds.

### Phase 1: Filesystem Search (Fallback)

No QMD? No problem. Strata falls back to a straightforward directory-walking grep:

1. Walk `active/` and `cooled/` recursively
2. Split the query into lowercase terms
3. Score each file: 1.0 per term matched in the path, 0.5 per term in the content
4. Return the top scorers from each stratum

It's zero-dependency and runs anywhere Python does. Semantic matching? Not so much  -  your results are only as good as your keyword game.

### Phase 2: Shadow Index (Always Runs)

Whatever happened in phase 1, the engine always checks the 3rd Stratum Shadow Index. It's a safety net for archived content:

1. Connect to the SQLite FTS5 database (`stratum_3_shadow.db`)
2. Run the FTS5 `MATCH` query against `keywords` and `summary_preview` columns
3. Score results by FTS5 rank (descending)
4. If you passed tags, it filters by `keywords LIKE '%"tagname"%'`

Archived files aren't gone  -  they're just in a different room. The shadow index makes sure you can still find them.

### Phase 3: Fusion and Ranking

Results from all three phases get thrown into one pot, sorted by score (descending), and the top `top_k` (default: 10) come back to you:

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

Here's a closer look at each option.

### Filesystem Grep (Fallback)

The built-in fallback. It walks directories and matches terms. No frills.

- **Dependencies:** Zero (stdlib only)
- **Latency:** Proportional to file count (walks everything)
- **Quality:** Keyword only, no semantic matching
- **Best for:** Small to moderate stores  -  under 1000 files, you're fine

### Shadow Index (SQLite FTS5)

Always used for the archive stratum. A lightweight keyword index that punches above its weight.

- **Dependencies:** Zero (stdlib `sqlite3`)
- **Latency:** ~5ms per query, scale doesn't matter
- **Quality:** Keyword-based FTS5 with ranking
- **Storage:** ~200 bytes per entry (keywords + 200-char preview + path)

### QMD (BM25 + Vector Fusion)

The optional hybrid engine. Runs locally, no LLM required for the base search.

- **Dependencies:** Node.js + `@tobilu/qmd`
- **Latency:** ~100-500ms per query (embeddings take a moment)
- **Quality:** Semantic matching via embeddings + BM25 keyword fusion
- **Storage:** Vector index size depends on collection size

#### Setup

```bash
npm install -g @tobilu/qmd
strata qmd-setup    # Add active/ + cooled/ as QMD collections
strata qmd-embed    # Generate vector embeddings
```

Collections are named `strata_active` and `strata_cooled`. The prefix is configurable via `qmd_collection_prefix`, if you're the type who likes custom labels.

#### Reranker Providers

QMD supports optional LLM rerankers for when you really need top-tier results:

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

1. **Be specific.** "koda oauth2 stripe" beats "project info" every time. Precision is power.
2. **Start with `strata list` or `strata read index.md`** when you know where things live. Search is for discovery, not navigation.
3. **Check the tier labels.** Archived results score lower and might need rehydration before you can do much with them.
4. **Install QMD once you've got more than a handful of files.** The filesystem fallback gets sluggish as your store grows; QMD stays snappy.
5. **Use `strata query` for scripting.** The JSON output is stable, parseable, and won't surprise you.

## Cross-Reference

- [CLI Reference](cli-reference.md) -- `strata search` and `strata query` commands
- [Architecture](architecture.md) -- how the shadow index fits into the tiered system
- [Installation](installation.md) -- QMD setup instructions
- [Tracking](tracking.md) -- cost comparison of search backends
- [Configuration](configuration.md) -- search_backend and qmd_reranker settings
