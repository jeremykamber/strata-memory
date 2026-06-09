# Pi Integration

Strata ships with a Pi extension that gives Pi coding agents built-in memory awareness. The extension injects Strata context into the agent's system prompt and automatically stores substantive content between sessions.

## Overview

The Strata Pi extension is a TypeScript file at `skills/pi/strata.ts` that implements the [Pi Extension API](https://github.com/earendil-works/pi-coding-agent). It provides two hooks:

1. **`before_agent_start`**: Injects Strata architecture and commands into the agent's system prompt at session start. The agent learns about the three tiers and key CLI commands without being told.
2. **`turn_end`**: After each assistant response, decides whether the content is worth persisting to Strata. The decision uses a two-phase pipeline:
   - **Phase 1 (LLM classifier)**: Calls a configurable LLM provider (OpenAI, Anthropic, or OpenRouter) with a structured prompt that returns JSON: `{ should_store, reason, title, category }`. **Off by default** — requires opt-in configuration.
   - **Phase 2 (heuristic fallback)**: Uses regex pattern matching (headings, code blocks, lists, saving keywords). This is the default when the LLM is disabled, unreachable, or returns invalid results.

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

### Auto-Storage Decision Pipeline

After each turn, the extension evaluates the assistant's response using a two-phase pipeline:

```
                  ┌─────────────────────┐
                  │  turn_end fires      │
                  │  extract text        │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │  text >= 50 chars?   │──No──→ skip
                  └──────────┬──────────┘
                             │ Yes
                             ▼
                  ┌─────────────────────┐
                  │  LLM enabled?        │
                  │  (config.llm.enabled)│
                  └──────────┬──────────┘
                         │        │
                      Yes│        │No
                         ▼        ▼
              ┌──────────────┐   ┌─────────────────────┐
              │ Call LLM     │   │ Heuristic fallback  │
              │ classifier   │   │ (isWorthStoring)    │
              └──────┬───────┘   └──────────┬──────────┘
                     │                      │
              ┌──────▼──────┐         ┌──────▼──────┐
              │ Result      │   No    │ Worth       │   No
              │ valid?      │─────→   │ storing?    │─────→ skip
              └──────┬──────┘         └──────┬──────┘
                     │ Yes                   │ Yes
                     ▼                       ▼
              ┌──────────────────────────────────┐
              │  Persist to Strata (strata add)  │
              └──────────────────────────────────┘
```

#### Phase 1: LLM Classifier (configurable, off by default)

When `pi-config.json` has `llm.enabled: true`, the extension calls the configured provider with a structured prompt. The LLM analyzes the text and returns a JSON object:

```json
{
  "should_store": true,
  "reason": "Contains architectural decision about database choice",
  "title": "Database Migration to PostgreSQL",
  "category": "projects"
}
```

Fields:

| Field | Type | Description |
|-------|------|-------------|
| `should_store` | boolean | Whether the content should be persisted |
| `reason` | string | Brief explanation of the decision |
| `title` | string | Suggested memory title (when storing) |
| `category` | string | Suggested category: `projects`, `entities`, `gtd`, `reference`, or `general` |

The LLM-suggested `title` and `category` are used for semantic path routing — content is saved to `pi/<category>/<slugified-title>.md` instead of the default `pi/memos/` directory.

#### Phase 2: Heuristic Fallback (default)

When the LLM is disabled or unreachable, the extension falls back to the original regex heuristic:

| Heuristic | Threshold |
|---|---|
| Minimum length | >= 50 characters |
| Markdown headings | One or more `# Heading` |
| Code blocks | One or more fenced ``` blocks |
| Bulleted lists | Two or more `-` lines |
| Numbered lists | Two or more `1.` lines |
| Saving keywords | "remember this", "key takeaway", "save this", etc. |

### Storage Path Derivation

When the LLM supplies a `title` and `category`, the path is derived semantically:

```
pi/<category>/<slugified-title>.md
```

Without LLM data, the path is derived from the first `H1` heading when available, falling back to a date-based name (`pi/memos/memo-2026-06-08.md`).

### Base Directory Detection

The extension auto-detects the Strata store directory, preferring project-local:

```typescript
// Resolution order:
// 1. ./strata_data/active/ exists -> use ./strata_data/
// 2. Fallback -> ~/.strata/
```

## LLM Configuration

The extension reads its configuration from `<strataBaseDir>/pi-config.json`. The configuration file is **optional** — when missing, defaults are used (LLM classification disabled, heuristic only).

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
| `llm.enabled` | `false` | Enable LLM-powered memory classification. **Off by default** — the heuristic is the default path. |
| `llm.provider` | `"openai"` | Provider to use. Options: `"openai"`, `"anthropic"`, `"openrouter"`. |
| `llm.model` | `"gpt-4o-mini"` | Model identifier. Defaults vary by provider (see below). |
| `llm.apiKey` | `""` | API key. Can be a direct string or an env var reference like `"${STRATA_OPENAI_API_KEY}"`. When empty, falls back to well-known env vars per provider. |
| `llm.temperature` | `0.0` | LLM temperature (0.0 = deterministic classification). |
| `llm.maxTokens` | `500` | Maximum tokens for the classification response. |

### Default Models by Provider

| Provider | Default Model |
|----------|---------------|
| `openai` | `gpt-4o-mini` |
| `anthropic` | `claude-3-5-haiku-latest` |
| `openrouter` | `openai/gpt-4o-mini` |

### API Key Configuration

The extension resolves the API key in this order:

1. **Direct string** in `llm.apiKey` (e.g., `"sk-..."`)
2. **Env var reference** in `llm.apiKey` (e.g., `"${MY_CUSTOM_KEY}"`)
3. **Well-known env var** per provider (see table below)
4. Empty string — classification returns null, falls back to heuristic

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

## File Layout

```
~/.pi/agent/extensions/
  strata.ts            # The installed Strata extension

~/.strata/
  pi-config.json        # Optional LLM configuration (create to enable)
  active/               # 1st Stratum — working memory
    pi/memos/           # Auto-stored memories (heuristic routing)
    pi/projects/        # Auto-stored memories (LLM category: projects)
    pi/entities/        # Auto-stored memories (LLM category: entities)
    pi/gtd/             # Auto-stored memories (LLM category: gtd)
    pi/reference/       # Auto-stored memories (LLM category: reference)
    pi/general/         # Auto-stored memories (LLM category: general)

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

This installs a skill definition (SKILL.md) that teaches the agent Strata's architecture and commands. Unlike the Pi extension, the skill is static -- it provides knowledge but does not run hooks.

## The Extension Code

The extension source (`skills/pi/strata.ts`) is deliberately zero-dependency and runs in Pi's TypeScript runtime. Key design decisions:

- **Two-phase decision pipeline.** LLM classification first (when enabled), heuristic fallback always available. The system degrades gracefully without network or API keys.
- **Zero npm dependencies.** Uses Node.js builtins (`node:fs`, `node:path`, `node:os`) and globally available `fetch()` (Node 18+) for API calls. No `package.json` needed.
- **Semantic storage paths.** LLM-suggested titles and categories route content to `pi/<category>/<title>.md`, enabling organized retrieval.
- **Silent failures.** If the Strata CLI or LLM API is unavailable, the extension silently skips storage. It never blocks Pi.
- **Secure key configuration.** API keys can reference env vars (`${VAR_NAME}`), keeping secrets out of the config file.
- **Off by default.** LLM classification must be explicitly enabled in `pi-config.json`. The heuristic provides a zero-config experience.

## Workflow Patterns

### Session Context Injection

The `before_agent_start` hook means the agent starts every session already knowing about Strata. No need to remind it at the start of each conversation.

```bash
# Agent will already know about these on first turn
strata search "previous context"
strata read index.md
```

### Cross-Session Memory

The `turn_end` hook means significant content from one session is automatically available in the next. The agent can run `strata search` to recall decisions, architecture notes, or user preferences from earlier sessions.

With the LLM classifier enabled, the agent saves **only genuinely valuable memories** with meaningful titles and categories, making retrieval faster and more relevant.

### Periodic Maintenance

While the extension handles storage, lifecycle maintenance (migration, eviction) runs independently via the daemon:

```bash
strata serve           # Start background Janitor
```

The extension and daemon are complementary. The extension writes to active; the daemon manages the lifecycle. They share the same data directory.

## Cross-Reference

- [Installation](installation.md) -- setting up Strata before Pi integration
- [CLI Reference](cli-reference.md) -- `strata mcp`, `strata skill install`, `strata pi-install` commands
- [Architecture](architecture.md) -- how strata transitions work behind the scenes
- [Search](search.md) -- how the agent retrieves stored memories
- [Configuration](configuration.md) -- complete configuration reference including Pi extension
