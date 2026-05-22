# The Strata Manifesto

## The Flat-Context Fallacy

LLM memory is fundamentally broken because it treats context as a flat plane.

You either shove everything into an ever-expanding context window (which degrades reasoning and costs a fortune), or you dump it into a vector database and pray semantic search retrieves the right thing. Both approaches ignore the single most important property of information: **it decays over time.**

A conversation you had five minutes ago about the bug you're actively fixing deserves different treatment than a design decision from six months ago that you haven't referenced since. Current systems treat both with the same fidelity, the same storage cost, and the same retrieval latency.

This is wasteful. It degrades agent performance as the corpus grows. And it's completely unnecessary.

## The Fundamental Insight

The key innovation in Strata is separating the **decision to move** from the **act of moving**.

Industry approaches like mem0 and OpenClaw use LLM janitors that continuously monitor, re-summarize, and reorganize memory on every operation. This is a massive waste of input tokens. You're paying an LLM to check if something changed when a two-line Python function could tell you the same thing.

**Algorithmic triggers decide *when* to move data. LLMs only run *to compress it*.**

- A file's modification timestamp tells you it's old. No LLM needed.
- A database row's `last_accessed` column tells you it's cold. No LLM needed.
- An access counter below a threshold tells you it's irrelevant. No LLM needed.

The LLM is only invoked at the moment of migration — to compress, summarize, and extract entities from the raw data. That's one LLM call per stale file, not one LLM call per query. The difference in token cost is an order of magnitude.

## The Three Tiers

Information exists on a continuum from "currently essential" to "might be useful someday." Strata carves this continuum into three discrete tiers, each optimized for a specific access pattern:

### 1st Stratum: The Active Shell

**Storage:** Filesystem markdown files. **Cost:** Zero dependencies, OS-native reads. **Latency:** ~1ms.

The active shell is the agent's working memory. It's structured exactly like a well-organized project directory because that's what it is. When the agent is working on a feature, it doesn't need to do a fuzzy semantic search to find the active specification. It reads `projects/kynd/requirements.md`. Directly. Exactly. Every time.

The index is explicit. The `index.md` file acts as the router — the agent reads it first, then decides which specific file to open. No vector similarity, no approximate retrieval, no chance of getting the wrong file because "database" and "base" happened to have similar embeddings.

1st Stratum is the fastest and most reliable form of memory because it sidesteps the entire retrieval problem. The agent knows where things are because it put them there.

**The inefficiency solved:** Vector databases for active projects are a category error. If you ask "what did Joe say about the Koda database schema yesterday?" and a vector search returns a conversation from three weeks ago because the words "database" and "Joe" are semantically similar, your architecture is wrong. 1st Stratum solves this with a strict, readable file structure. The agent knows exactly where the current Koda specs are stored.

### 2nd Stratum: The Medium-Term Orbit

**Storage:** SQLite with FTS5. **Cost:** Built into Python. **Latency:** ~5ms.

2nd Stratum is the semantic and relational memory. Once a project cools down, the Janitor compresses those files into Memory Blocks — condensed summaries optimized for retrieval. An LLM (optional, pluggable) transforms 3,000 words of planning document into a 200-word summary with extracted entity tags.

This solves the semantic loss problem. If we moved raw text to a database, search would be chaotic. By synthesizing it first, we create clean, dense chunks optimized for retrieval.

2nd Stratum uses SQLite's built-in FTS5 (Full-Text Search, version 5) for searching. Not a dedicated vector database. Here's why:

**FTS5 gives you keyword-aware search with ranking, snippets, and highlight functionality — all without a single external dependency.** For 90% of memory retrieval tasks, a human-readable tag like `[koda, funding]` is more useful than a vector embedding. When you need semantic similarity, you can plug in an embedding provider. But it's optional. The system works without it.

The relational structure links memories to entities through JSON metadata, enabling queries like "find memories about the Koda funding round, linked to Joe, that happened near the iStartup Lab" — all through simple SQL with JSON extraction operators.

### 3rd Stratum: The Cold Archive + Shadow Index

**Storage:** Flat JSON files + SQLite Shadow Index. **Cost:** Near-zero. **Latency:** ~10ms.

Data cannot live in 2nd Stratum forever. SQLite with FTS5 is fast, but it still consumes storage and memory. Keeping memories from five years ago with zero retrievals in active storage is wasteful.

But we don't just delete them. That's what every other system does — either grow forever (mem0) or prune without recovery (most open-source tools). Both approaches lose information permanently.

**The Shadow Index solves this.** When the Janitor evicts a memory to 3rd Stratum, it leaves behind a "ghost" entry in a lightweight SQLite database. No vector embeddings, no full text — just keywords, a 200-character preview, and a file path to the archived JSON. A million shadow entries cost practically nothing to store.

If the agent searches 1st Stratum (no results) and 2nd Stratum (no results), it runs a quick keyword query against the Shadow Index. If it finds a match, it reads the JSON file from the archive and re-hydrates the memory — pulls it back into 2nd Stratum, regenerates the embedding, resets the access counter. The memory is back in the active orbit because it proved useful again.

## Why Zero Dependencies

The core of Strata has exactly zero external dependencies. Not one pip package.

- 1st Stratum uses `pathlib` (stdlib).
- 2nd Stratum uses `sqlite3` (stdlib) with FTS5 (built into SQLite since 3.9.0).
- 3rd Stratum uses `sqlite3` and `json` (stdlib).

The only optional dependencies are the LLM providers (`openai`, `anthropic`), and they're loaded lazily. If they're not installed, Strata degrades gracefully: migration truncates content instead of compressing it.

This is a deliberate choice. Memory is the most fundamental subsystem of an AI agent. It should not depend on a fragile web of packages that break with every `pip update`. It should work in a Docker container, a serverless function, a Jupyter notebook, or embedded in a C extension — anywhere Python runs.

## Structured Decay vs. Every-Query Polling

Here is the core difference between Strata and every other memory system:

| System | Trigger | Cost |
|--------|---------|------|
| mem0 | Every query | LLM call per query |
| OpenClaw | Every operation | LLM call per operation |
| LangChain | On get/put | Embedding per retrieval |
| **Strata** | **File age / access frequency** | **Algorithmic check (nearly free)** |

Strata only invokes the LLM when data actually needs to move — when a file exceeds its decay threshold, or when a memory qualifies for LRU eviction. The Janitor's algorithmic checks (compare timestamps, check access counters) cost microseconds. The LLM compression costs tokens only when it actually compresses.

This is the difference between a notification system that calls you every hour to ask "is it time yet?" and one that only calls you when it's actually time.

## The Agent Contract

Strata defines a minimal, portable contract between the agent and its memory system:

1. **The agent reads and writes 1st Stratum** — it creates files, reads them, lists directories. This is the only direct interaction.
2. **The agent queries via `strata_query`** — a single tool that cascades through all three tiers and returns merged results.
3. **The agent never manages transitions** — the Janitor handles migration and eviction asynchronously.
4. **The agent never thinks about storage** — it writes to 1st Stratum, queries across all tiers, and trusts the environment is curated.

This contract works with any LLM and any agent harness. The tool schemas are defined in OpenAI function-calling format, which has become the de facto standard. Any system that consumes function-calling JSON can integrate Strata in minutes.

## The Synthesis: Strata Meets agent-db

Strata provides the lifecycle discipline — the Janitor, the LRU eviction, the Shadow Index. For 2nd Stratum, it uses SQLite with FTS5, which is sufficient for most use cases out of the box.

But if you need a full relational engine with vector search and detailed autonomy records, you can swap 2nd Stratum for agent-db (or any Postgres/pgvector-backed store). The interface is clean: `store()`, `get()`, `search_fts()`, `search_by_tags()`, `get_lru_candidates()`. Any backend that implements these methods can replace SQLite.

The synthesis is this: Strata provides the lifecycle management that agent-db is missing, and agent-db provides the relational graph that Strata's summaries are too simple to capture on their own. They're complementary.

## What Strata Is Not

- **Not a vector database.** 2nd Stratum uses FTS5, not vector search. Embeddings are optional and pluggable.
- **Not a graph database.** Entities are stored as JSON tags, not nodes and edges. If you need a full knowledge graph, connect agent-db.
- **Not a replacement for the model's context window.** 1st Stratum is for context the agent needs right now. 2nd Stratum is for recall. They serve different purposes.
- **Not a distributed system.** Strata is designed for a single agent working from a single filesystem. Distributed consensus is a separate problem.

## The Road Ahead

The industry is obsessed with throwing more compute at the memory problem. Bigger context windows. More expensive embedding models. Continuous re-summarization loops.

Strata proves that **structured decay and asynchronous consolidation is the actual path forward for autonomous systems.** The right architecture isn't the one that stores everything with maximal fidelity. It's the one that stores each piece of information with the fidelity it deserves, at the storage tier it earns, for as long as it proves useful.

This is how human memory works. This is how agent memory should work.

---

*"The best part is no part. The best process is no process. The best memory is the one you don't need to search."* — Strata First Principle
