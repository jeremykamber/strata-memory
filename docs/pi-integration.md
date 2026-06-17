# Pi Integration

Strata ships with a Pi extension that gives Pi coding agents built-in memory awareness. The extension injects Strata context into the agent's system prompt, captures full conversation transcripts after every prompt, and a background daemon component extracts standalone knowledge files from those transcripts.

## Overview

The Strata Pi extension is a TypeScript file at `skills/pi/strata.ts` that implements the [Pi Extension API](https://github.com/earendil-works/pi-coding-agent). It provides two hooks:

1. **`before_agent_start`**: Injects Strata architecture and commands into the agent's system prompt at session start. The agent learns about the three tiers and key CLI commands without being told.
2. **`agent_end`**: After each prompt completes, saves the full conversation transcript (user + assistant messages) as a plain markdown file. No heuristic filtering — the raw transcript is always preserved.

Conversation transcripts are saved to `pi/conversations/YYYY-MM-DD/` for later processing. A background distillation step (running inside the Strata daemon) periodically reads new transcripts, sends them as a batch to a configurable small LLM, and writes extracted fact files to `pi/facts/YYYY-MM-DD/`. The daemon uses the same `pi-config.json` LLM configuration that was previously used for per-turn classification.

## Installation

### Via CLI

```bash
strata pi-install
```

This copies `strata.ts` to `~/.pi/agent/extensions/strata.ts`. After installation, run `/reload` in Pi to activate the extension.

To overwrite an existing install without prompting:

```bash
strata pi-install --force
```

### Manual Installation

```bash
cp skills/pi/strata.ts ~/.pi/agent/extensions/strata.ts
```

Then run `/reload` in Pi.

### Prerequisites

- Pi CLI (`pi`) must be installed. Get it from [pi.ai](https://pi.ai).
- Strata CLI must be installed and on `$PATH`.

## Quick Setup: LLM Distillation

Once the extension is installed and Pi is capturing conversations, enable LLM-powered fact extraction in two steps.

### 1. Set your API key

```bash
# Using OpenRouter (free tier available):
export STRATA_OPENROUTER_API_KEY="sk-or-..."
strata config set llm.provider openrouter
strata config set llm.model openrouter/free
strata config set llm.enabled true

# Or using OpenAI:
# export STRATA_OPENAI_API_KEY="sk-..."
# strata config set llm.provider openai
# strata config set llm.model gpt-4o-mini
# strata config set llm.enabled true
```

Add the `export STRATA_OPENROUTER_API_KEY=...` line to your `~/.zshrc` or `~/.bashrc`
so it persists across terminal sessions.

### 2. Check it's working

```bash
strata distiller status
# → Distiller: ENABLED (openrouter / openrouter/free)
# → Pending: 0 conversation(s)
```

Now run Pi for a while. Each prompt is automatically captured as a transcript.
To manually trigger extraction of any pending conversations:

```bash
strata distiller run
# → Processed 3 conversation(s)
# → Wrote 1 fact file(s)
```

Or start the daemon for automatic extraction every 15 minutes:

```bash
strata serve
```

### Full CLI Reference

| Command | What it does |
|---------|--------------|
| `strata distiller status` | Show LLM config state and pending conversation count |
| `strata distiller run` | Manually trigger LLM fact extraction |
| `strata distiller run --dry-run` | Preview what would be processed |
| `strata config get llm` | Show full LLM configuration |
| `strata config get llm.<key>` | Show a specific LLM config value |
| `strata config set llm.<key> <value>` | Set an LLM config value |
| `strata status` | Show system status (includes distiller state) |

## Extension Behaviour

### Auto-Injected System Prompt

At session start, the extension appends a Strata memory section to the agent's system prompt:

```
## Strata Memory System

Your Strata memory store lives at `/Users/you/.strata`. It organises information
across three tiers of plain markdown files:

- **1st Stratum (active/)** -- working memory; read and write here freely
- **2nd Stratum (cooled/)** -- aged-out files; query only
- **3rd Stratum (archive/ + shadow.db)** -- cold storage with keyword search

### Key commands

| Command | Purpose |
|---------|---------|
| `strata add <path> <content>` | Save important information you learn |
| `strata read <path>` | Read the full content of a file |
| `strata search <query>` | Search across all three tiers |
| `strata list [path]` | List available files |

Use **`strata add`** whenever you learn something substantive.
Use **`strata search`** at the start of a session or when you need to recall past context.
```

### Full Conversation Capture

After each prompt completes, the extension saves the full conversation (all user and assistant messages) as a plain markdown file. Unlike the previous `turn_end` handler, there is **no heuristic filtering** — the raw transcript is always preserved.

The `agent_end` handler:

1. Extracts the full message array from `event.messages` (available in the [Pi Extension API](how_to_make_pi_extension.md#agent_start--agent_end))
2. Formats each message with its role (`user`, `assistant`) and text content
3. Generates a session identifier using the current timestamp and a short content hash for uniqueness
4. Writes the transcript to `pi/conversations/YYYY-MM-DD/YYYYMMDDThhmmss-{hash}.md`

**Session identity format:** `YYYYMMDDThhmmss-{hash}.md`

- Date-prefixed timestamp enables day-level search (`strata search 20260617`)
- Short hash ensures uniqueness across concurrent sessions

**Writing logic:** Uses `node:fs` to write directly to the Strata directory (no `strata add` CLI call), with `recursive: true` directory creation. Filesystem errors are silently caught — the extension never blocks Pi.

### Base Directory Detection

The extension auto-detects the Strata store directory, preferring project-local:

```typescript
// Resolution order:
// 1. ./strata_data/active/ exists -> use ./strata_data/
// 2. Fallback -> ~/.strata/
```

## LLM Configuration (for Daemon Distillation)

The `pi-config.json` LLM configuration, previously used for per-turn classification, now powers **background distillation** inside the Strata daemon. When `llm.enabled: true` and a valid API key is configured, the daemon reads new conversation transcripts, sends them to the configured LLM in batch, and writes extracted fact files.

The configuration file is **optional** — without it, the daemon skips distillation but the extension still captures raw transcripts.

### Config File Location

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
| `llm.enabled` | `false` | Enable background distillation. **Off by default** — transcripts are always captured but facts are extracted only when enabled. |
| `llm.provider` | `"openai"` | Provider to use. Options: `"openai"`, `"anthropic"`, `"openrouter"`. |
| `llm.model` | `"gpt-4o-mini"` | Model identifier. Defaults vary by provider (see below). Recommended: a small/cheap model (GPT-4o-mini or equivalent) since distillation runs every ~15 minutes. |
| `llm.apiKey` | `""` | API key. Can be a direct string or an env var reference like `"${STRATA_OPENAI_API_KEY}"`. When empty, falls back to well-known env vars per provider. |
| `llm.temperature` | `0.0` | LLM temperature (0.0 = deterministic extraction). |
| `llm.maxTokens` | `500` | Maximum tokens for the extraction response. |

### Default Models by Provider

| Provider | Default Model |
|----------|---------------|
| `openai` | `gpt-4o-mini` |
| `anthropic` | `claude-3-5-haiku-latest` |
| `openrouter` | `openai/gpt-4o-mini` |

### API Key Configuration

The daemon resolves the API key in the same order as the extension:

1. **Direct string** in `llm.apiKey` (e.g., `"sk-..."`)
2. **Env var reference** in `llm.apiKey` (e.g., `"${MY_CUSTOM_KEY}"`)
3. **Well-known env var** per provider (see table below)
4. Empty string — distillation is disabled

| Provider | Well-known Env Vars |
|----------|---------------------|
| `openai` | `STRATA_OPENAI_API_KEY`, `OPENAI_API_KEY` |
| `anthropic` | `STRATA_ANTHROPIC_API_KEY`, `ANTHROPIC_API_KEY` |
| `openrouter` | `STRATA_OPENROUTER_API_KEY`, `OPENROUTER_API_KEY` |

**Security recommendation:** Use env var references in the config file and set the actual key in your shell profile or .env file:

```bash
# ~/.zshrc or equivalent
export STRATA_OPENAI_API_KEY="sk-..."
```

Then in `pi-config.json`:

```json
{
  "llm": {
    "enabled": true,
    "apiKey": "${STRATA_OPENAI_API_KEY}"
  }
}
```

### Example Configurations

**OpenAI (recommended starter):**

```json
{
  "llm": {
    "enabled": true,
    "provider": "openai",
    "apiKey": "${STRATA_OPENAI_API_KEY}"
  }
}
```

**Anthropic Claude:**

```json
{
  "llm": {
    "enabled": true,
    "provider": "anthropic",
    "model": "claude-3-5-haiku-latest",
    "apiKey": "${STRATA_ANTHROPIC_API_KEY}"
  }
}
```

**OpenRouter (access multiple model families):**

```json
{
  "llm": {
    "enabled": true,
    "provider": "openrouter",
    "model": "openai/gpt-4o-mini",
    "apiKey": "${STRATA_OPENROUTER_API_KEY}"
  }
}
```

## Background Distillation

When `pi-config.json` has `llm.enabled: true` and a valid API key, the Strata daemon performs background distillation as the first step of each maintenance cycle. This runs every 15 minutes by default (`strata serve`).

### How it Works

1. **Scan**: The daemon reads the conversation files from `pi/conversations/` and checks a tracking sidecar (`pi/distill_state.json`) to identify which transcripts haven't been processed yet.
2. **Batch**: All new transcripts are joined together and sent to the configured LLM in a single API call.
3. **Extract**: The LLM receives a structured extraction prompt and returns standalone facts as bullet points with topic categories (`[projects]`, `[entities]`, `[gtd]`, `[reference]`, `[general]`).
4. **Store**: Extracted facts are written as a markdown file to `pi/facts/YYYY-MM-DD/` with a sequential batch number.

### Dry Run

The daemon's first cycle is always a dry run (unless `--live` is passed). During the dry run, distillation reports how many transcripts would be processed without calling the LLM or writing files.

### Cost

Distillation calls the LLM once per maintenance cycle (every ~15 minutes), in a single batch. At GPT-4o-mini pricing (~$0.15/1M input tokens), a typical cycle costs less than $0.01. No API call is made when there are no new undistilled transcripts.

### Graceful Degradation

- If `pi-config.json` is missing, distillation silently skips — conversation capture is unaffected.
- If the LLM API call fails (network error, rate limit, invalid key), the error is logged and conversations are retried on the next cycle.
- If the LLM returns "no significant facts to extract," conversations are still marked as processed — no fact file is written.

## Distill vs Agent Queries

Distillation and agent queries serve different purposes:

| Aspect | Distillation (daemon) | Agent query (runtime) |
|--------|----------------------|----------------------|
| **When** | Every ~15 min in background | On demand, during a session |
| **What** | Extracts standalone facts from raw conversations | Searches all three strata for context |
| **Cost** | Single small-LLM call per cycle | Zero external cost (filesystem + FTS5) |
| **Storage** | Creates new fact files in `pi/facts/` | Reads existing files across all strata |
| **Purpose** | Turn raw transcripts into reusable knowledge | Retrieve stored memories for current session |

The agent can still use `strata search` to find relevant context. Distillation enriches the fact corpus over time, making searches more productive across sessions.

## File Layout

```
~/.pi/agent/extensions/
  strata.ts            # The installed Strata extension

~/.strata/
  pi-config.json        # Optional LLM configuration (for daemon distillation)
  active/               # 1st Stratum — working memory
    pi/
      conversations/    # Raw conversation transcripts (written by extension)
        2026-06-17/
          20260617T143022-abcd1234.md
      facts/            # Distilled knowledge files (written by daemon)
        2026-06-17/
          001-distilled-knowledge-001.md
      memos/            # Legacy auto-stored memories (from previous versions)
      distill_state.json  # Tracking sidecar (written by daemon)

skills/pi/
  strata.ts            # Source file bundled with Strata (for reference)
```

The installed extension is a standalone TypeScript file with zero npm dependencies. Pi loads all files from `extensions/` at startup.

## Skill Install (Alternative for Non-Pi Agents)

For non-Pi agents (OpenCode, Claude Code, Cursor, Codex, Windsurf), Strata provides a skill install via the Vercel Skills protocol:

```bash
strata skill install         # Interactive -- choose scope + agents
strata skill install --global # Non-interactive, all agents
```

This installs a skill definition (SKILL.md) that teaches the agent Strata's architecture and commands. Unlike the Pi extension, the skill is static — it provides knowledge but does not run hooks.

## The Extension Code

The extension source (`skills/pi/strata.ts`) is deliberately zero-dependency and runs in Pi's TypeScript runtime. Key design decisions:

- **Always-on conversation capture.** The `agent_end` hook saves every conversation transcript with no heuristic filtering — raw data is never discarded.
- **Zero npm dependencies.** Uses Node.js builtins (`node:fs`, `node:crypto`, `node:path`, `node:os`) and globally available `fetch()` (Node 18+) for API calls. No `package.json` needed.
- **Background distillation.** Knowledge extraction is separated from capture and runs in the daemon, not during the Pi session. Keeps the extension fast and non-blocking.
- **Silent failures.** If the filesystem is unwritable, the extension silently skips. It never blocks Pi.
- **Secure key configuration.** API keys can reference env vars (`${VAR_NAME}`), keeping secrets out of the config file.
- **Off by default.** Distillation must be explicitly enabled in `pi-config.json` — but conversation capture always runs.

## Workflow Patterns

### Session Context Injection

The `before_agent_start` hook means the agent starts every session already knowing about Strata. No need to remind it at the start of each conversation.

```bash
# Agent will already know about these on first turn
strata search "previous context"
strata read index.md
```

### Cross-Session Knowledge Growth

Every conversation is captured as a transcript. Over time, the daemon extracts standalone facts from those transcripts into `pi/facts/`. The agent uses `strata search` to find relevant context — searches across transcripts (1st Stratum), facts, memos, cooled files, and archived content.

### Periodic Maintenance

Lifecycle maintenance (migration, eviction) runs independently via the daemon, with distillation as the first step:

```bash
strata serve           # Start background Janitor + distiller
```

The extension, distiller, and daemon are complementary. The extension captures raw data. The distiller extracts knowledge. The daemon manages the lifecycle across all strata.

## Migration from Previous Versions

Prior to this version, the extension used a `turn_end` handler with an optional LLM classifier and heuristic fallback. The key differences:

| Before | After |
|--------|-------|
| `turn_end` handler | `agent_end` handler |
| Heuristic filtering (length, headings, lists) | No filtering — all conversations captured |
| Optional per-turn LLM classification | Background distillation in daemon |
| Stored to `pi/memos/`, `pi/projects/`, etc. | Raw transcripts → `pi/conversations/`, facts → `pi/facts/` |
| `pi-config.json` `llm.enabled` powered per-turn classification | Same config now powers daemon distillation |

Existing `pi/memos/` files are untouched. New captures go to `pi/conversations/`.

## Cross-Reference

- [Installation](installation.md) — setting up Strata before Pi integration
- [CLI Reference](cli-reference.md) — `strata mcp`, `strata skill install`, `strata pi-install` commands
- [Architecture](architecture.md) — how strata transitions and distillation work
- [Search](search.md) — how the agent retrieves stored memories
- [Configuration](configuration.md) — complete configuration reference including Pi extension
