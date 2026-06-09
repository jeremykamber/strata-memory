# CLI Reference

The `strata` CLI is the primary interface for agents and users. This page documents every command, its arguments, options, and expected behaviour.

## Global Flags

These flags can be used with any command:

| Flag | Description |
|---|---|
| `--json` | Output results as JSON (for scripting). Applies to all commands. |
| `--agent` | Alias for `--json`. Same behaviour. |

When `--json` or `--agent` is active, all output is a single JSON object with `status`, `command`, `data`, and `duration_ms` fields. Error output follows the same format with `status: "error"` and exits with code 1.

## Commands

### SETUP

#### `strata init`

Create a new Strata data directory.

**Purpose:** Initialise the directory structure for all three strata. Creates `active/`, `cooled/`, and `archive/` directories, sets up default subdirectories (`projects/`, `entities/`, `gtd/`), generates the initial `index.md`, and prompts for search backend selection.

**Usage:**
```bash
strata init                    # Creates ./strata_data/ (project-local, default)
strata init --local            # Explicit project-local (same as default)
strata init --global           # Creates ~/.strata/ (global)
strata init --non-interactive  # Skip QMD onboarding prompts
```

**Notes:**
- Interactive by default -- prompts to choose search backend (QMD hybrid, QMD + reranker, or FTS5 keyword)
- If QMD is selected, attempted auto-install via `npx` with 30s timeout
- Configuration is persisted to `.strata_config.json`

#### `strata config`

View or modify configuration.

**Purpose:** Show the current configuration or modify individual settings at runtime.

**Usage:**
```bash
strata config                          # Show all configuration
strata config get <key>                # Get a specific value
strata config set <key> <value>        # Set a specific value
```

**Examples:**
```bash
strata config get decay_thresholds.projects
# Output: 14

strata config set decay_thresholds.projects 21
strata config set lru_days 60
strata config set search_backend fts5
```

**Notes:**
- Keys support dotted paths for nested fields (e.g., `decay_thresholds.projects`)
- Values are auto-parsed: integers, floats, booleans, JSON, or plain strings
- Changes persist to `.strata_config.json` immediately
- JSON mode: `strata config --json`

#### `strata status`

Show system state.

**Purpose:** Display the current state of the Strata system -- file counts per stratum, daemon status, and base directory location.

**Usage:**
```bash
strata status
```

**Output includes:**
- Base directory path
- 1st Stratum stale file count (files pending migration)
- 2nd Stratum block count
- 3rd Stratum shadow entry count
- Daemon status (running/stopped, PID, cycle count)
- Recent daemon log lines (if running)

### READING / WRITING

#### `strata add <path> <content>`

Write content to the 1st Stratum.

**Purpose:** Create or overwrite a file in the active stratum. Multi-line content is supported. The `index.md` is regenerated after each write.

**Usage:**
```bash
strata add projects/koda/requirements.md "# Koda Platform\nOAuth2 + payments"
echo "# Quick note" | strata add gtd/note.md
strata add --text "Remember to deploy the API"     # Auto-routed to gtd/
strata add --file /path/to/local/file.md projects/notes.md  # Read from file
```

**Priority:** Inline text argument > `--file` content > stdin. If only one positional argument is given and stdin is a pipe, content is read from stdin.

**Notes:**
- Creates parent directories automatically
- Path traversal is blocked (paths must resolve within `active/`)
- Regenerates `index.md` after writing
- Exit code 1 on file read failure or missing content

#### `strata read <path>`

Read a file from the 1st Stratum.

**Purpose:** Print the full content of a file in the active stratum.

**Usage:**
```bash
strata read projects/koda/spec.md
strata read index.md
```

**Notes:**
- Exit code 1 if file is not found or path is a directory
- Direct stratum 1 access only (use `strata search` for other strata)

#### `strata list [path]`

List files and directories in the 1st Stratum.

**Purpose:** Discover available context. Shows files and directories with type and size.

**Usage:**
```bash
strata list                 # List active root
strata list projects        # List projects subdirectory
```

**Output format:** `[dir] projects/` or `[file] projects/koda/notes.md (1234b)`

#### `strata list-stratum-2`

List 2nd Stratum (cooled) files.

**Purpose:** See what files have been migrated to the cooled stratum. Shows path, size, and last modification date.

**Usage:**
```bash
strata list-stratum-2
```

#### `strata index`

Regenerate the 1st Stratum `index.md`.

**Purpose:** Rebuild the master map of all active files. Normally regenerated automatically after every `strata add`, but this command provides manual regeneration.

**Usage:**
```bash
strata index
```

**Output:** Prints the first 300 characters of the regenerated index.

### SEARCHING

#### `strata search <query>`

Search across all memory tiers.

**Purpose:** Human-readable search across active/, cooled/, and archive/ strata.

**Usage:**
```bash
strata search "koda oauth2"
strata search "postgresql pgvector"
```

**Output format:**
```
  [1] [ACTIVE] · score=1.50 · projects/koda/requirements.md
       # Koda Platform...OAuth2 + payments...

  [2] [ARCHIVE] · score=0.25 · archive:stratum_3_abc123.json
       # Koda Database Schema...PostgreSQL...
       [in archive -- query strata forget <id> to rehydrate]
```

**Notes:**
- Results are ranked by relevance score
- Tier tags: `ACTIVE` (stratum_1), `MEDIUM` (stratum_2), `ARCHIVE` (stratum_3)
- Middle dot (`·`) separator between fields
- Archived results show a rehydration hint
- Exit code 1 if no query text provided

#### `strata query <text>`

Search across all memory tiers (JSON output).

**Purpose:** Same search as `strata search` but outputs raw JSON for scripting.

**Usage:**
```bash
strata query "koda oauth2"
```

**Output:** JSON array of result objects with `content`, `tier`, `source`, `score`, and `metadata` fields.

### LIFECYCLE

#### `strata migrate`

Move stale files from active to cooled.

**Purpose:** Scan the 1st Stratum for files older than their decay threshold and move them to the 2nd Stratum. Files remain as markdown.

**Usage:**
```bash
strata migrate              # Execute migration
strata migrate --dry-run    # Preview without making changes
```

**Notes:**
- Shows a spinner animation during execution (suppressed in piped output or JSON mode)
- Dry run output lists files that would be migrated
- Exit code 1 on errors

#### `strata evict`

Move cold files from cooled to archive.

**Purpose:** Scan the 2nd Stratum for files exceeding LRU thresholds and evict them to the 3rd Stratum. Creates JSON blob + shadow index entry.

**Usage:**
```bash
strata evict              # Execute eviction
strata evict --dry-run    # Preview without making changes
```

**Notes:**
- Shows a spinner animation
- Dry run output lists memories that would be evicted
- Exit code 1 on errors

#### `strata maintenance`

Run full lifecycle cycle.

**Purpose:** Execute migrate and evict in sequence. One command for complete maintenance.

**Usage:**
```bash
strata maintenance              # Execute both
strata maintenance --dry-run    # Preview both
```

**Output:** JSON with `migrated` and `evicted` arrays, plus totals.

#### `strata forget <path>`

Archive a specific cooled file immediately.

**Purpose:** Explicitly archive a file from the 2nd Stratum to the 3rd Stratum. Like an "archive now" button for a specific file.

**Usage:**
```bash
strata forget projects/old-idea.md
```

**Notes:**
- File path must exist in `cooled/`
- Uses the first path segment as tags
- Exit code 1 if file not found in 2nd Stratum

#### `strata cost`

Show estimated cost savings from Janitor automation.

**Purpose:** Display metrics on daemon activity and estimated token savings from automated lifecycle management.

**Usage:**
```bash
strata cost
```

**Output:**
```
Strata Cost Savings (Estimated)
========================================
  Daemon cycles:     3
  Files migrated:    12
  Files evicted:     4
  LRU decisions:     4
  Tokens saved:      26,000 tokens
  Savings range:     20,800 - 31,200

  Methodology: Compared against hypothetical system...
  Disclaimer: These are approximate ranges...
```

See [Tracking](tracking.md) for detailed methodology.

### DAEMON

#### `strata serve`

Start background Janitor daemon.

**Purpose:** Start a background process that runs `strata maintenance` on a schedule. The daemon handles lifecycle automatically -- no manual intervention needed.

**Usage:**
```bash
strata serve                        # Default: 900s interval, first cycle dry run
strata serve --interval=300         # Every 5 minutes
strata serve --live                 # Skip initial dry run, go straight to live
```

**Options:**
| Option | Default | Description |
|---|---|---|
| `--interval=SECONDS` | `900` | Seconds between maintenance cycles. |
| `--live` | (dry run first) | Skip initial dry run, execute live immediately. |

**Notes:**
- Checks for existing daemon PID before starting (prevents duplicates)
- Logs to `strata.log` and stderr
- PID file at `strata.pid`
- Blocking -- runs until interrupted (Ctrl+C)

#### `strata daemon`

Alias for `strata serve`.

#### `strata stop`

Stop running daemon.

**Purpose:** Send SIGTERM to the running daemon process and wait for graceful shutdown.

**Usage:**
```bash
strata stop
```

**Notes:**
- Reads PID from `strata.pid`
- Waits up to 5 seconds for graceful shutdown
- Cleans up PID file on success
- Safe to call when daemon is not running (prints message, no error)

#### `strata restart`

Restart daemon.

**Purpose:** Stop the running daemon and start a new one with the same arguments.

**Usage:**
```bash
strata restart
strata restart --interval=600
```

#### `strata history`

Show Janitor daemon log.

**Purpose:** View the daemon activity log. Useful for checking what the Janitor has been doing.

**Usage:**
```bash
strata history              # Show last 20 lines
strata history --lines=50   # Show last 50 lines
```

**Notes:**
- Reads from `strata.log` in the base directory
- Exit code 0 even if no log exists (prints a message)

### AGENT INTEGRATION

#### `strata mcp`

Start MCP protocol server.

**Purpose:** Start the Model Context Protocol (MCP) server over stdio. This lets MCP-compatible agents (Claude Desktop, etc.) interact with Strata directly.

**Usage:**
```bash
strata mcp
```

**Notes:**
- Runs over stdio (for MCP transport)
- Blocking -- runs until stdin closes or interrupted
- See [MCP specification](https://modelcontextprotocol.io) for protocol details

#### `strata skill install`

Install Strata skill for AI coding assistants.

**Purpose:** Install the Strata agent skill, which teaches AI coding assistants about Strata's commands and architecture. Supports OpenCode, Claude Code, PI, Cursor, Codex, Windsurf, and 55+ agent formats via the [Vercel Skills](https://github.com/vercel-labs/skills) protocol.

**Usage:**
```bash
strata skill install                 # Interactive -- choose scope + agents
strata skill install --global        # Non-interactive global install
```

**Notes:**
- Requires Node.js (`npx`)
- Interactive mode launches `npx skills add` with prompts
- Global mode passes `--all --global --yes` flags for unattended install
- The skill is bundled at `strata/skills/strata/SKILL.md`

#### `strata pi-install`

Install Strata Pi extension.

**Purpose:** Install the Strata extension for the Pi coding agent. Copies `strata.ts` to `~/.pi/agent/extensions/`.

**Usage:**
```bash
strata pi-install          # Interactive (prompts before overwrite)
strata pi-install --force  # Overwrite existing extension without prompt
```

**Notes:**
- Requires Pi CLI (`pi`) to be installed
- Installs to `~/.pi/agent/extensions/strata.ts`
- After install, run `/reload` in Pi to activate
- See [Pi Integration](pi-integration.md) for extension details

#### `strata --agent-help`

Print agent usage guide.

**Purpose:** Display the inline agent help text that describes Strata architecture and commands from an AI agent's perspective.

**Usage:**
```bash
strata --agent-help
```

**Output:** Markdown-formatted guide covering architecture, commands, best practices -- designed to be injected into an agent's context.

### QMD (Optional Hybrid Search)

#### `strata qmd-setup`

Configure QMD collections for all Strata directories.

**Purpose:** Add `active/` and `cooled/` directories as QMD collections for hybrid search.

**Usage:**
```bash
strata qmd-setup
```

**Notes:**
- Collection names: `strata_active`, `strata_cooled`
- Requires `@tobilu/qmd` to be installed
- Exit code 0 even if QMD is not installed (prints a message)

#### `strata qmd-embed`

Generate vector embeddings.

**Purpose:** Generate vector embeddings for all QMD collections. This enables vector semantic search.

**Usage:**
```bash
strata qmd-embed
```

**Notes:**
- May take a while on first run (especially for large collections)
- Requires QMD to be installed
- Exit code 0 even if QMD is not installed (prints a message)

#### `strata qmd-status`

Show QMD index status.

**Purpose:** Display the current status of QMD collections and indexes.

**Usage:**
```bash
strata qmd-status
```

**Notes:**
- Shows collection health, embedding status, index size
- Requires QMD to be installed

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `1` | General error (invalid args, missing data directory, file not found, daemon not running, etc.). |

In JSON mode (`--json` / `--agent`), errors produce a JSON object with `status: "error"` and exit code 1.

## Cross-Reference

- [Installation](installation.md) -- setting up the CLI
- [Configuration](configuration.md) -- fields that influence command behaviour
- [Architecture](architecture.md) -- lifecycle commands and the Janitor
- [Search](search.md) -- search and query commands
- [Tracking](tracking.md) -- cost command methodology
- [Pi Integration](pi-integration.md) -- pi-install and skill install
