LLM memory is fundamentally broken right now because it treats context as a flat plane.

You either cram everything into an ever-expanding context window (which tanks reasoning *and* costs a fortune), or you dump it into a vector database and pray semantic search pulls up the right thing.

> If you break it down to its essence, current memory systems fail because they ignore the temporal decay of information.

Think about it like this. When I'm an RA managing an active incident in Stevens Court, I need the full picture  -  the resident, the issue, the people involved, the emails sent. Everything.

Two months later, after it's all wrapped up? I just need a summary of the resolution.

Two **years** later, I only need to know the incident happened and where to find the original file if it ever comes back up.

Strata gets this.

It's a tiered, distance-based (you'll see what I mean in a second) memory architecture that separates three kinds of memories: what's relevant right now, what's familiar, and what's archived for the long haul.

This doc breaks down exactly how the system is structured, how data moves between layers, and how it solves the token-wasting nonsense of current frameworks.

## The Core Philosophy

With OpenClaw and [Andrej Karpathy's llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) making the rounds, memory has shifted to markdown  -  and it's getting very, very LLM-happy.

A "janitor" agent constantly organizes files, re-summarizes context, relates ideas to each other, and checks whether memories need updating or pruning. [mem0](https://mem0.ai/), for instance, runs a custom-built LLM agent on every single query just to clean up and maintain a memory graph.

That's an enormous waste of input tokens.

Strata separates the "decision to move" from the "act of moving." It uses algorithmic triggers  -  inspired by how human memory works  -  to flag data for migration. The LLM only gets called to actually compress and format the data *after* those triggers fire.

You get the intelligence of an LLM without the recurring polling costs. Nice, right?

---

## The First Stratum: The Active Shell (High-Resolution Markdown)

The first stratum is the agent's working memory. It's the "shell"  -  the immediate, essential context. Everything lives in Markdown files organized in a standard directory tree.

When my personal agent (Niklaus) is actively working on a feature for Kynd, it doesn't need to run a fuzzy semantic search to find the active code requirements. It just needs the right file.

### Structure and Indexing

The Phase 1 directory is organized logically:

* `/projects`  -  Active initiatives and sprints
* `/entities`  -  People, companies, software tools
* `/gtd`  -  Immediate tasks synced from Todoist
* `index.md`  -  The master map of the directory

Every file has raw, uncompressed text. If there's an email thread, the whole thing is here. If there are API docs for a Go backend, you get the full text  -  no summaries, no shortcuts.

Indexing is explicit. The `index.md` file acts as a router. When the agent needs info, it reads the index, then picks which folder and file to open. That's standard filesystem traversal  -  OS-level reads  -  not vector similarity. You get 100% precision for active tasks. No guesswork.

### The Problem It Solves

Current startups throw vector databases at active projects. Ask an agent "what did Joe say about the Koda database schema yesterday?" and a vector search might hand you a conversation from three weeks ago because "database" and "Joe" happened to show up in the same sentence. Phase 1 sidesteps this entirely: the agent knows exactly where the current Koda specs live because there's a file for that.

---

## The Transition: Phase 1 to Phase 2

Data can't live in Phase 1 forever. The directory would balloon until the agent can't navigate it efficiently. You need to move stuff out when it cools down.

### The Algorithmic Trigger

We don't use an LLM to watch the clock. We use a simple Python cron job  -  the Janitor. It runs every night at 2:00 AM and scans the metadata of every Markdown file in Phase 1.

If a file's `last_modified` date is older than 14 days, the trigger fires. (Yeah, 14 days sounds short. Don't worry  -  you can configure this per directory. The `/entities` folder might get a 60-day decay instead.)

### The LLM Consolidation

Once the trigger fires, the LLM gets to work. It receives the raw Markdown file and a strict system prompt:

> "You are the Strata Migration Engine. Take this raw project file and compress it into a high-density Memory Block. Extract the core outcomes, the final technical decisions, and all relevant entities. Discard conversational filler. Format the output as a JSON object containing a 200-word summary and an array of metadata tags."

The LLM takes a 3,000-word planning document for the iStartup Lab and turns it into a tight summary, tagged with `[iStartup, launch_sprint]`.

This solves the "semantic loss" problem. Blindly shoving raw text into a vector DB creates chaos. LLM synthesis gives you clean, dense chunks that are actually optimized for retrieval later.

---

## The Second Stratum: The Medium-Term Orbit (agent-db)

Stratum 2 is where semantic and relational memory lives. Once an active project goes cold, those condensed "Memory Blocks" move into **agent-db**  -  a Postgres-backed system built for autonomous agent memory. It's not a generic vector database. It's a relational engine with vector search built in.

Here's why that matters: a memory isn't just text. It's a relationship between a person, a place, and a project. agent-db understands that.

### The Database Schema

agent-db stores each Memory Block as a Postgres row with a `pgvector` embedding for semantic search. The schema wires memories to the entities they reference:

* **`memories` table**: Each entry has a unique UUID, compressed summary text, a vector embedding of that summary, and structured metadata  -  source file, entity tags, timestamps, access counters.
* **`autonomy_records` table**: Tracks the agent's decision lineage  -  what information was used, when, and why.
* **Relational links**: Memories connect to people, projects, locations, and even mood states through junction tables. You can ask "find memories about the Koda funding round, linked to Joe, that happened near the iStartup Lab" and get exactly what you're after.

### Hybrid Search Mechanics

When the agent can't find what it needs in Phase 1, it queries Phase 2. agent-db supports hybrid search: dense vector similarity for semantic matching, GIN-indexed full-text search for keyword precision, and relational filters for entity-level queries.

So when I ask Niklaus to recall how we handled a tricky React state issue last year, it searches the vector space for semantic meaning, filters on the `React` tag, and looks for links to the `Koda` project.

Every time a memory gets retrieved, the system bumps `access_count` and updates `last_accessed`. This is pretty important for the next step.

---

## The Transition: Second to Third Stratum

Postgres with pgvector is fast. But it still consumes RAM and storage, and keeping memories from five years ago that nobody's ever touched is wasteful.

### The Eviction Logic

We use a Least Recently Used (LRU) algorithm. The Janitor runs a weekly scan on agent-db, looking for rows where `last_accessed` is older than 90 days and `access_count` sits below a threshold.

Hit those criteria? Evicted from Postgres.

### Preserving the Thread

We don't just delete the memory. The Janitor grabs the raw JSON object, saves it to a flat file on cheap storage (S3 bucket, local hard drive, whatever), then deletes the row and its embedding from the active Postgres tables.

---

## The Final (Third) Stratum: The Cold Archive + Shadow Index

This is the most critical layer  -  and the one that sets this system apart from mem0, QMD, and everything else in the space. How do you find a memory if it's no longer in the active database? You use a Shadow Index.

### The Shadow Index Structure

When the Janitor evicts a memory to Phase 3, it leaves a ghost behind in a lightweight SQLite database (the Shadow Index). No vector embeddings here. Just a simple table with:

* `id`: The original UUID.
* `keywords`: Entity tags from the Phase 2 metadata.
* `archive_path`: The exact file path to the JSON file in deep storage.

### Re-Hydration

The agent searches Phase 1 (fails). Searches Phase 2 (fails). It then runs a quick keyword query against the Shadow Index.

If it finds a match  -  say, a specific Koda investor from a year ago  -  it grabs the `archive_path` and reads that JSON file from cold storage.

Once read, the system "re-hydrates" the memory: pulls the summary back into agent-db, generates a new embedding, and resets `access_count`. The memory is back in the active orbit because it proved useful again.

### Solving the Archive Problem

Current systems like Mem0 just keep growing their graph. They never offload data, so retrieval gets slower and noisier over time. Other open-source tools just delete old context and call it a day.

The Shadow Index dodges both traps. It costs basically nothing to store a million keywords in SQLite. And it gives the agent an infinite memory horizon without cluttering up the active Postgres space.

---

## System Integration and Tool Calling

For Strata to work, the LLM agent  -  whether it's OpenClaw or a custom Python script  -  needs specific tool definitions.

It needs standard file operations (read, write, list) for Phase 1. And it needs a `query_strata` tool that handles the cascading search: check Phase 1, fall through to Phase 2 in agent-db, then fall back to the Shadow Index.

The agent never manages the transitions. It only reads and writes Phase 1. The algorithmic Janitor handles the rest asynchronously. The agent just trusts its environment is curated.

---

## The Synthesis: Strata Meets agent-db

Here's the thing about each approach on its own. Strata is great at lifecycle management  -  it knows when data should move and when it should retire. But its summaries are too simple to capture the rich web of connections between people, projects, and places. agent-db solves that with relational linking, but without Strata's eviction logic, it'd keep everything warm forever and burn through storage costs.

So the synthesis is this: Strata provides the lifecycle discipline  -  the Janitor, the LRU eviction, the Shadow Index  -  and agent-db powers Phase 2 as the relational memory engine. The Shadow Index handles cold eviction from there to Phase 3. Strata is the Janitor that agent-db is missing. agent-db is the knowledge graph that Strata's summaries are too simple to capture on their own.

Right now the industry is obsessed with throwing more compute at the memory problem. Strata proves that structured decay and asynchronous consolidation is the real path forward for autonomous systems. No praying required.
