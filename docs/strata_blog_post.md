LLM memory is fundamentally broken right now because it treats context as a flat plane.

You either shove everything into an ever-expanding context window (which degrades reasoning + costs a fortune), or you dump it into a vector database and pray semantic search retrieves the right thing.

> If you break it down to its essence, current memory systems fail because they ignore the temporal decay of information.

As a Resident Advisor (RA), when I'm managing an active incident in Stevens Court, I need the exact context of the resident, the specific issue, people involved, emails sent, etc.

Two months later, after it's all resolved, I just need a summary of the resolution.

Two **years** later, I only need to know that the incident happened + where to find the original file if it ever resurfaces.

Strata fixes this.

It is a tiered, distance-based (you'll see what I mean by that in a second) memory architecture that separates pertinent memories, "familiar" memories, and archived, long-term storage.

This document outlines exactly how the system is structured, how data migrates between layers, and how it solves the token-burning inefficiencies of current frameworks.

## The Core Philosophy

Especially with the advent of OpenClaw and [Andrej Karpathy's llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), memory has moved to markdown, and is very, very LLM heavy.

A "janitor" agent constantly organizes markdown files, re-summarizes context, relates ideas to one another, and checks to check if memories need to be updated or pruned. In the case of [mem0](https://mem0.ai/), the janitor is a custom-built LLM agent, running on every query, that cleans up and maintains a memory graph (mem0g).

This is a massive waste of input tokens.

Strata separates the "decision to move" from the "act of moving." It relies on human-cognition-inspired algorithmic triggers to flag data for migration, so we only invoke the LLM to actually compress and format the data once those triggers fire.

That results in the intelligence of an LLM without recurring polling costs.

---

## The First Stratum: The Active Shell (High-Resolution Markdown)

The first stratum is the agent's working memory. This is the "shell" (the essential, immediate context). It is structured entirely in Markdown files organized in a standard directory tree.

When my personal agent (Niklaus) is actively working on a feature for Kynd, it doesn't need to do a fuzzy semantic search to find the active code requirements. It needs an exact, structured file.

### Structure and Indexing

The Phase 1 directory is organized logically:
* `/projects` (Active initiatives + sprints)
* `/entities` (People, companies, software tools)
* `/gtd` (Immediate tasks synced from Todoist)
* `index.md` (The master map of the directory)

Every file contains raw, uncompressed text. If there is an email thread, the entire transcript is here. If there are API docs for a Go backend, the full text is here.

The indexing is explicit. The `index.md` file acts as the router. When the agent needs information, it first reads the index; it then decides which specific folder and file to read. It uses standard file-system traversal (OS-level reads) instead of vector similarity. This guarantees 100% precision for active tasks.

### The Inefficiency Solved

Current startups try to use Vector DBs for active projects. If you ask an agent "what did Joe say about the Koda database schema yesterday?", a vector search might return a conversation from three weeks ago because the words "database" and "Joe" are semantically similar. Phase 1 solves this by giving the agent a strict, readable file structure. It knows exactly where the current Koda specs are stored.

---

## The Transition: Phase 1 to Phase 2

Data cannot live in Phase 1 forever; the directory would become too large for the agent to navigate efficiently. We need to move data out when it cools down.

### The Algorithmic Trigger

We do not use an LLM to monitor file age. We use a simple Python cron job (the Janitor). The Janitor runs every night at 2:00 AM. It scans the metadata of every Markdown file in Phase 1.

If a file has a `last_modified` date older than 14 days, the trigger activates. (I hear you + understand where you're coming from if you think 14 days is too short; this threshold is configurable per directory, so the `/entities` folder might have a 60-day decay).

### The LLM Consolidation

Once the trigger fires, the system makes an LLM call. The LLM is handed the raw Markdown file and a strict system prompt:

> "You are the Strata Migration Engine. Take this raw project file and compress it into a high-density Memory Block. Extract the core outcomes, the final technical decisions, and all relevant entities. Discard conversational filler. Format the output as a JSON object containing a 200-word summary and an array of metadata tags."

The LLM processes the text. It turns a 3,000-word planning document for the iStartup Lab into a concise summary; it tags it with `[iStartup, launch_sprint]`.

This solves the "semantic loss" problem. If we just blindly moved the raw text to a vector DB, the search would be chaotic. By having the LLM synthesize it first, we create clean, dense chunks that are highly optimized for retrieval.

---

## The Second Stratum: The Medium-Term Orbit (agent-db)

Stratum 2 is the semantic and relational memory. Once an active project cools down, those condensed "Memory Blocks" move into **agent-db** (a Postgres-backed system built specifically for autonomous agent memory). Instead of a generic vector database, we get a full relational engine with vector search built in.

This matters because a memory isn't just text; it's a relationship between a person, a place, and a project. agent-db understands that.

### The Database Schema

agent-db stores each Memory Block as a row in Postgres with a `pgvector` embedding for semantic search. The schema links memories to the entities they reference:

* **`memories` table**: Each entry has a unique UUID, the compressed summary text, a vector embedding of that summary, and structured metadata (source file, entity tags, timestamps, access counters).
* **`autonomy_records` table**: Tracks the agent's decision lineage; what information was used, when, and why.
* **Relational links**: Memories are connected to people, projects, locations, and even mood states through junction tables. This means you can ask "find memories about the Koda funding round, linked to Joe, that happened near the iStartup Lab" and get exactly what you need.

### Hybrid Search Mechanics

When the agent can't find what it needs in Phase 1, it queries Phase 2. agent-db supports hybrid search: dense vector similarity for semantic matching, GIN-indexed full-text search for keyword precision, and relational filters for entity-level queries.

If I ask Niklaus to recall how we handled a specific React state issue last year, it searches the vector space for the semantic meaning of the prompt; it also filters the metadata for the `React` tag and looks for links to the `Koda` project.

Every time a memory is retrieved, the system increments `access_count` and updates `last_accessed`. This is crucial for the next transition.

---

## The Transition: Second to Third Stratum

Postgres with pgvector is fast, but it still consumes RAM and storage. Keeping memories from five years with zero retrievals in active Postgres is wasteful.

### The Eviction Logic

We use a Least Recently Used (LRU) algorithm. The Janitor script runs a weekly scan on the agent-db database. It looks for rows where `last_accessed` is older than 90 days and `access_count` is below a certain threshold.

If a memory hits this criteria, it is evicted from Postgres.

### Preserving the Thread

We do not just delete the memory. The Janitor takes the raw JSON object from the database and saves it to a flat file on cheap storage (like an S3 bucket or a local hard drive). It then deletes the row and its embedding from the active Postgres tables.

---

## The Final (Third) Stratum: The Cold Archive + Shadow Index

This is the most critical of the strata, and what sets this system apart from others (e.g mem0 or QMD). How do you find a memory if it's no longer in the active database? You use a Shadow Index.

### The Shadow Index Structure

When the Janitor evicts a memory to Phase 3, it leaves behind a "ghost" in a lightweight SQLite database (the Shadow Index). This database doesn't use vector embeddings. It's a simple table containing:
* `id`: The original UUID.
* `keywords`: The entity tags from the Phase 2 metadata.
* `archive_path`: The exact file path pointing to the JSON file in deep storage.

### Re-Hydration

If the agent searches Phase 1 (fails) and Phase 2 (fails), it runs a quick keyword query against the Shadow Index.

If it finds a match (perhaps searching for a specific Koda investor from a year ago), it grabs the `archive_path`. The agent then executes a tool call to read that specific JSON file from the cold archive.

Once the file is read, the system "re-hydrates" the memory. It pulls the summary back into agent-db, generates a new embedding, and resets the `access_count`. The memory is back in the active orbit because it proved useful again.

### Solving the Archive Problem

Current systems like Mem0 just keep growing their graph. They never offload data, which means their context retrieval gets slower and noisier over time. Other open-source tools just delete old context entirely.

The Shadow Index solves this. It costs practically zero compute to store a million keywords in SQLite; it allows the agent to maintain an infinite memory horizon without cluttering the active Postgres space.

---

## System Integration and Tool Calling

For Strata to work, the LLM agent (whether it is OpenClaw or a custom Python script) needs specific tool definitions.

It needs standard file operations (read, write, list) for Phase 1. It needs a `query_strata` tool that handles the cascading search logic (checking Phase 1 first, then Phase 2 in agent-db, then falling back to the Shadow Index).

The agent never needs to manage the transitions. The agent only reads and writes to Phase 1. The algorithmic Janitor handles the rest asynchronously. The agent simply trusts that the environment is curated.

---

## The Synthesis: Strata Meets agent-db

Here's the thing about both approaches on their own. Strata is great at lifecycle management; it knows when data should move and when it should die. But its summaries are too simple to capture the rich web of connections between people, projects, and places. agent-db solves that with relational linking, but without Strata's eviction logic, it would keep everything warm forever and burn through storage costs.

So the synthesis is this: Strata provides the lifecycle discipline (the Janitor, the LRU eviction, the Shadow Index), and agent-db powers Phase 2 as the relational memory engine (the Shadow Index handles cold eviction from there to Phase 3). Strata is the Janitor that agent-db is missing; agent-db is the Knowledge Graph that Strata's summaries are too simple to capture on their own.

Right now we're seeing an industry obsessed with throwing more compute at the memory problem; Strata proves that structured decay and asynchronous consolidation is the actual path forward for autonomous systems.
