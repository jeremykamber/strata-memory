# The Strata Manifesto

## Why Memory Needs Layers

Strata is a CLI-first memory system. Agents interact with it through shell commands (`strata add`, `strata search`, `strata read`) — no SDK required, no API calls, just the filesystem. The Python API is a secondary interface for programmatic use.

In geology, strata are layers of rock that build up over time. The top layer is today's sediment — fresh, accessible, still settling. Dig deeper and you find older layers — compressed, quieter, but still there if you need to drill down.

Human memory works the same way. What you had for breakfast is near the surface. What you learned in high school is deeper. But both are retrievable — they just sit at different depths.

LLM memory is the opposite. It's flat.

You either shove everything into one ever-expanding context window (which degrades reasoning and burns tokens), or you dump it all into a vector database and hope the embedding model figures it out. Both approaches treat a memory from five minutes ago the same as a memory from five years ago. Same retrieval cost. Same storage tier. Same fidelity.

This is like storing a fossil and a fresh leaf in the same box. It works, but it's wasteful.

## The Core Insight

The key idea behind Strata is simple: **separate the decision to move data from the act of compressing it.**

Current systems (mem0, OpenClaw) use LLMs to constantly monitor and reorganize memory. Every query triggers a check. Every operation runs a janitor loop. You're paying an AI to check if something is old — a job a two-line Python function handles for free.

Strata flips this. Algorithmic triggers decide *when* to move data:

- **File modification time** tells you it's stale. No AI needed.
- **Last access date** tells you it's cold. No AI needed.
- **Access count** tells you it's irrelevant. No AI needed.

Only once a trigger fires do we invoke anything smarter — and in the current architecture, even that step is just moving a file. No LLM, no compression, no token cost.

**That's the difference between a system that calls you every hour to ask "is it time yet?" and one that only taps your shoulder when it's actually time.**

## The Three Strata

### 1st Stratum — The Active Layer

Like the topsoil on a forest floor. Fresh, alive, full of activity. This is where the agent works.

Every memory here is a plain markdown file in a known directory. The agent reads `active/index.md` to get the map, then navigates to the right file by path. No vector search, no embedding, no approximate retrieval. The agent knows where things are because it put them there.

**Latency:** ~1ms. **Storage:** Filesystem. **Cost:** Zero.

The `index.md` is auto-generated and lists every file with its first heading as the description. When the agent asks "what's in my workspace?", it reads the index — not a vector database.

### 2nd Stratum — The Cooled Layer

Like sediment that's settled but hasn't hardened into rock. The files are still there, still readable, but you don't interact with them daily.

The Janitor moves files here from the 1st Stratum based on age (default: 14 days for projects, 60 for entities). The agent can still search and read them via `strata search`, but it can't write to them directly. If it needs to edit something, the file gets rehydrated back to the 1st Stratum first.

**Latency:** ~5ms. **Storage:** Filesystem. **Managed by:** Janitor.

### 3rd Stratum — The Archive

This is the bedrock. Memories that haven't been touched in months get compressed into JSON and stored flat. A lightweight Shadow Index (SQLite with FTS5) keeps them searchable by keyword.

When the Janitor evicts a file here, it leaves behind a "ghost" in the Shadow Index — just keywords, a 200-character preview, and a file path. No vectors, no embeddings. A million ghosts cost less than a megabyte.

If a search finds a ghost, the file gets rehydrated back to the 1st Stratum. The memory resurfaces because it proved useful again.

**Latency:** ~10ms (with rehydration). **Storage:** Flat JSON + SQLite FTS5.

**This is what sets Strata apart.** mem0 never forgets — it grows forever. Most open-source tools just delete. Strata archives with a retrievable shadow. It's the difference between throwing something away and putting it in a labeled box in the basement.

## Why Files, Not Databases

Every memory in Strata is a plain file on disk. Not a row in a table. Not a node in a graph. A `.md` file.

This is deliberate. Files are the most agent-native format there is:

- An agent can read a file with `cat` or `strata read`
- An agent can write a file with `echo >` or `strata add`
- An agent can search files with `grep` or `strata search`
- An agent can list files with `ls` or `strata list`
- An agent can version files with `git`
- An agent can pipe files anywhere

No SDK. No API. No database drivers. Just the filesystem, which every operating system has had since 1971.

## The Shadow Index

This is the mechanism that makes infinite memory practical without infinite storage cost.

When a file is archived, the Shadow Index records:
- The original file path
- Entity tags (inferred from the directory structure)
- The archive file location
- A 200-character preview

That's it. The Shadow Index is a SQLite database with FTS5 full-text search — same tech that powers SQLite's built-in search. It doesn't store embeddings, vectors, or graph relationships. It stores keywords and a pointer to where the full content lives.

If the agent searches and finds nothing in active or cooled, it hits the Shadow Index. A match means the file gets rehydrated — pulled from the archive back into active, where the agent can read and edit it again.

**The Shadow Index is the difference between "deleted forever" and "put away for now."**

## What Strata Doesn't Do

- **No LLM calls.** The Janitor moves files based on timestamps, not AI decisions.
- **No vector database.** Search is filesystem grep or optional QMD (BM25 + vector).
- **No graph database.** Relationships are implicit through directory structure.
- **No distributed consensus.** Single filesystem, single agent.
- **No API keys.** Minimal configuration out of the box.

## The Agent Contract

The contract between Strata and any AI agent is minimal:

1. **Read and write markdown files** in the 1st Stratum. That's the only direct interaction.
2. **Search across all strata** via `strata search` or `strata_query`. The cascade handles the rest.
3. **Never manage transitions.** The Janitor runs in the background. The agent trusts the environment is curated.

This works with any LLM, any agent framework, any programming language that can call a CLI or read a file.

## Comparison

| System | Trigger | Storage | LLM calls | Retrieval |
|--------|---------|---------|-----------|-----------|
| **mem0** | Every query | Graph DB | Per query + maintenance | Semantic + graph |
| **OpenClaw** | Every operation | Markdown + LLM | Per operation + janitor | LLM re-summarized |
| **LangChain** | On get/put | Vector DB | Per embedding | Vector similarity |
| **QMD** | On index | SQLite (FTS5 + vec) | Per query (optional) | BM25 + vector + rerank |
| **Strata** | File age / LRU | Filesystem + SQLite | **None** | Filesystem + FTS5 |

## The Philosophy

Most memory systems are built by engineers who think about storage. Strata is built by thinking about *forgetting.*

Information decays. That's not a bug — it's the feature that makes memory useful. The right question isn't "how do I store everything with maximum fidelity?" It's "how do I store each piece of information at the fidelity it deserves, for as long as it proves useful?"

Like geological strata, Strata layers memories by age. The top layer is for today's work. The middle layer is for last month's projects. The bottom layer is for everything else — compressed, indexed, but never truly gone.

And unlike real rock, these layers are permeable. A memory from the bottom can resurface when the agent needs it. The Shadow Index is the fault line that connects deep time to the present.
