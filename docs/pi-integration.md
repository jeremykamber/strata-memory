# Pi Integration

Strata ships with a Pi extension that gives Pi coding agents built-in memory awareness. The extension injects Strata context into the agent's system prompt and automatically stores substantive content between sessions.

## Overview

The Strata Pi extension is a TypeScript file at `skills/pi/strata.ts` that implements the [Pi Extension API](https://github.com/earendil-works/pi-coding-agent). It provides two hooks:

1. **`before_agent_start`**: Injects Strata architecture and commands into the agent's system prompt at session start. The agent learns about the three tiers and key CLI commands without being told.
2. **`turn_end`**: After each assistant response, checks whether the content is worth storing (contains headings, code blocks, structured lists, or saving keywords). If so, persists it to Strata via `strata add`.

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

### Auto-Storage

After each turn, the extension checks the assistant's response against a content heuristic:

| Heuristic | Threshold |
|---|---|
| Minimum length | >= 50 characters |
| Markdown headings | One or more `# Heading` |
| Code blocks | One or more fenced ``` blocks |
| Bulleted lists | Two or more `-` lines |
| Numbered lists | Two or more `1.` lines |
| Saving keywords | "remember this", "key takeaway", "save this", etc. |

When content qualifies, it is saved to `pi/memos/` in the active stratum:

```bash
strata add pi/memos/architecture-decision.md "# Architecture Decision\n..."
```

The store path is derived from the first `H1` heading when available, falling back to a date-based name (`pi/memos/memo-2026-06-08.md`).

### Base Directory Detection

The extension auto-detects the Strata store directory, preferring project-local:

```typescript
// Resolution order:
// 1. ./strata_data/active/ exists -> use ./strata_data/
// 2. Fallback -> ~/.strata/
```

## File Layout

```
~/.pi/agent/extensions/
  strata.ts            # The installed Strata extension

skills/pi/
  strata.ts            # Source file bundled with Strata (for reference)
```

The installed extension is a standalone TypeScript file. Pi loads all files from `extensions/` at startup.

## Skill Install (Alternative for Non-Pi Agents)

For non-Pi agents (OpenCode, Claude Code, Cursor, Codex, Windsurf), Strata provides a skill install via the Vercel Skills protocol:

```bash
strata skill install         # Interactive -- choose scope + agents
strata skill install --global # Non-interactive, all agents
```

This installs a skill definition (SKILL.md) that teaches the agent Strata's architecture and commands. Unlike the Pi extension, the skill is static -- it provides knowledge but does not run hooks.

## The Extension Code

The extension source (`skills/pi/strata.ts`) is deliberately small (~180 lines) and zero-dependency. Key design decisions:

- **Silent failures.** If `strata` CLI is not available, the extension silently skips storage. It never blocks Pi.
- **No LLM calls.** Content quality heuristics use regex patterns only.
- **Date fallback.** Without a clear heading, content is saved to a dated memo file.
- **Project-local first.** Prefers `./strata_data/` over `~/.strata/` when the active directory exists in the current working directory.

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
