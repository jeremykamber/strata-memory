"""Command-line interface for Strata memory system.

Usage:
    strata init                    Initialize directory structure
    strata add <path> [content]    Write content to 1st Stratum (or stdin)
    strata search <query>          Search across all memory tiers
    strata query <text>            Search across all memory tiers (JSON output)
    strata read <path>             Read a 1st Stratum file
    strata list [path]             List 1st Stratum files and directories
    strata list-stratum-2             List 2nd Stratum (cooled) files
    strata forget <path>           Archive a cooled file to 3rd Stratum
    strata migrate                 Run 1st -> 2nd Stratum migration
    strata evict                   Run 2nd -> 3rd Stratum eviction
    strata maintenance             Run full lifecycle cycle
    strata serve [--interval=N]    Start background Janitor daemon
    strata daemon                  Alias for "serve"
    strata stop                    Stop running daemon
    strata restart                 Restart daemon
    strata status                  Show system status
    strata config                  Show current configuration
    strata history [--lines=N]     Show Janitor daemon log
    strata cost                    Show estimated cost savings from Janitor
    strata mcp                     Start MCP protocol server (stdio)
    strata qmd-setup               Configure QMD collections (requires Node.js)
    strata qmd-embed               Generate QMD vector embeddings
    strata qmd-status              Show QMD index status
    strata distiller status       Show distillation status and pending conversations
    strata distiller run           Manually trigger LLM distillation
    strata skill install           Install Strata skill for AI coding assistants (interactive)
    strata skill install --global  Install globally to all agents (non-interactive)
    strata pi-install [--force]   Install Strata Pi extension (~/.pi/agent/extensions/)
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from strata import Strata
from strata.config import StrataConfig, detect_base_dir
from strata.daemon import StrataDaemon, get_daemon_status
from strata.mcp_server import MCPServer

# ── Global state for JSON mode ──────────────────────────────────────────────────
_JSON_MODE = False  # Set to True via --json / --agent flag
_START_TIME = 0.0  # monotonic start of main() for duration_ms


def _config(**kwargs) -> StrataConfig:
    if "base_dir" not in kwargs:
        kwargs["base_dir"] = detect_base_dir()
    config = StrataConfig(**kwargs)
    # Load persisted config to override defaults
    config_path = config.base_dir / "strata.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    return config


def main(argv: list[str] | None = None):
    """Entry point for the Strata CLI.

    Parses command-line arguments, detects global flags (``--json``,
    ``--agent``), dispatches to the appropriate ``_cmd_*`` handler.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).
    """
    global _JSON_MODE, _START_TIME
    _START_TIME = time.monotonic()

    args = argv if argv is not None else sys.argv[1:]
    if not args:
        _print_usage()
        return

    # Parse global flags before command dispatch
    filtered: list[str] = []
    for a in args:
        if a in ("--json", "--agent"):
            _JSON_MODE = True
        else:
            filtered.append(a)
    args = filtered

    if not args:
        _print_usage()
        return

    if args[0] in ("--agent-help", "agent-help"):
        if _JSON_MODE:
            _json_print("agent-help", {"help": _agent_help()})
            return
        print(_agent_help())
        return

    command = args[0]

    if command == "init":
        _cmd_init(args[1:])

    elif command == "add":
        _cmd_add(args[1:])

    elif command in ("search", "query"):
        _cmd_query(command, args[1:])

    elif command == "read":
        _cmd_read(args[1:])

    elif command == "list":
        _cmd_list(args[1:])

    elif command == "list-stratum-2":
        _cmd_list_stratum_2()

    elif command == "forget":
        _cmd_forget(args[1:])

    elif command in ("migrate", "evict", "maintenance"):
        _cmd_lifecycle(command, args[1:])

    elif command in ("serve", "daemon"):
        _cmd_serve(args[1:])

    elif command == "stop":
        _cmd_stop()

    elif command == "restart":
        _cmd_stop()
        _cmd_serve(args[1:])

    elif command == "status":
        _cmd_status()

    elif command == "config":
        _cmd_config(args[1:])

    elif command == "history":
        _cmd_history(args[1:])

    elif command == "qmd-setup":
        _cmd_qmd_setup()

    elif command == "qmd-embed":
        _cmd_qmd_embed()

    elif command == "qmd-status":
        _cmd_qmd_status()

    elif command == "index":
        _cmd_index()

    elif command == "mcp":
        _cmd_mcp()

    elif command == "pi-install":
        _cmd_pi_install(args[1:])

    elif command == "distiller":
        _cmd_distiller(args[1:])

    elif command == "skill":
        _cmd_skill(args[1:])

    elif command == "promote":
        _cmd_lifecycle("promote", args[1:])

    elif command == "rehydrate":
        _cmd_rehydrate(args[1:])

    elif command == "install-service":
        _cmd_install_service()

    elif command == "uninstall-service":
        _cmd_uninstall_service()

    elif command == "cost":
        _cmd_cost(args[1:])

    else:
        print(f"Unknown command: {command}")
        _print_usage()
        sys.exit(1)


def _print_usage():
    """Panel-grouped help organised by category."""

    def _fmt_cmd(cmd: str) -> str:
        return f"strata {cmd}" if not cmd.startswith("--") else cmd

    groups = [
        (
            "SETUP",
            [
                (_fmt_cmd("init"), "Initialize directory structure"),
                (_fmt_cmd("config [get/set]"), "Show or modify configuration"),
                (_fmt_cmd("status"), "Show system state"),
            ],
        ),
        (
            "READING/WRITING",
            [
                (
                    _fmt_cmd("add <path> [content]"),
                    "Write content to 1st Stratum (or stdin)",
                ),
                (_fmt_cmd("read <path>"), "Read a 1st Stratum file"),
                (_fmt_cmd("list [path]"), "List 1st Stratum files and directories"),
                (_fmt_cmd("list-stratum-2"), "List 2nd Stratum (cooled) files"),
                (_fmt_cmd("index"), "Regenerate index.md"),
            ],
        ),
        (
            "SEARCHING",
            [
                (_fmt_cmd("search <query>"), "Search across all memory tiers"),
                (
                    _fmt_cmd("query <text>"),
                    "Search across all memory tiers (JSON output)",
                ),
            ],
        ),
        (
            "LIFECYCLE",
            [
                (_fmt_cmd("migrate"), "Run 1st -> 2nd Stratum migration"),
                (_fmt_cmd("promote"), "Move hot cooled files back to active"),
                (_fmt_cmd("evict"), "Run 2nd -> 3rd Stratum eviction"),
                (_fmt_cmd("maintenance"), "Run full lifecycle cycle"),
                (_fmt_cmd("forget <path>"), "Archive a cooled file to 3rd Stratum"),
                (
                    _fmt_cmd("rehydrate <id> [--target=active|cooled]"),
                    "Restore archived file to active or cooled",
                ),
                (_fmt_cmd("cost"), "Show estimated cost savings from Janitor"),
            ],
        ),
        (
            "DAEMON",
            [
                (_fmt_cmd("serve [--interval=N]"), "Start background Janitor daemon"),
                (_fmt_cmd("stop"), "Stop running daemon"),
                (_fmt_cmd("restart"), "Restart daemon"),
                (_fmt_cmd("install-service"), "Install systemd service"),
                (_fmt_cmd("uninstall-service"), "Uninstall systemd service"),
                (_fmt_cmd("history [--lines=N]"), "Show Janitor daemon log"),
                (
                    _fmt_cmd("distiller status"),
                    "Show distillation state and pending conversations",
                ),
                (_fmt_cmd("distiller run"), "Manually trigger LLM distillation"),
            ],
        ),
        (
            "AGENT INTEGRATION",
            [
                (_fmt_cmd("mcp"), "Start MCP protocol server (stdio)"),
                (
                    _fmt_cmd("skill install"),
                    "Install Strata skill for AI coding assistants",
                ),
                (_fmt_cmd("pi-install [--force]"), "Install Strata Pi extension"),
                (_fmt_cmd("--agent-help"), "Show agent usage guide"),
            ],
        ),
        (
            "QMD",
            [
                (_fmt_cmd("qmd-setup"), "Configure QMD collections (requires Node.js)"),
                (_fmt_cmd("qmd-embed"), "Generate QMD vector embeddings"),
                (_fmt_cmd("qmd-status"), "Show QMD index status"),
            ],
        ),
    ]
    print("Strata — Tiered Memory System")
    print()
    for title, cmds in groups:
        print(f"  {title}")
        for cmd, desc in cmds:
            print(f"    {cmd:<30} {desc}")
        print()


@contextlib.contextmanager
def _spinner(msg="Processing"):
    """\r-based rotating spinner. No-op when piped or in JSON mode."""
    if not sys.stdout.isatty() or _JSON_MODE:
        yield
        return
    stop_event = threading.Event()
    start = time.monotonic()
    chars = r"-\|/"

    def _spin():
        idx = 0
        while not stop_event.is_set():
            sys.stdout.write(f"\r{msg} {chars[idx]}")
            sys.stdout.flush()
            idx = (idx + 1) % len(chars)
            stop_event.wait(0.1)

    t = threading.Thread(target=_spin, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop_event.set()
        t.join(0.2)
        elapsed = time.monotonic() - start
        sys.stdout.write(f"\r{msg} ({elapsed:.0f}s)\n")
        sys.stdout.flush()


def _json_print(command: str, data):
    """Print success JSON with duration_ms."""
    elapsed = (time.monotonic() - _START_TIME) * 1000
    result = {
        "status": "success",
        "command": command,
        "data": data,
        "duration_ms": round(elapsed, 1),
    }
    print(json.dumps(result))


def _json_error(command: str, message: str):
    """Print error JSON and exit."""
    elapsed = (time.monotonic() - _START_TIME) * 1000
    result = {
        "status": "error",
        "command": command,
        "message": message,
        "duration_ms": round(elapsed, 1),
    }
    print(json.dumps(result))
    sys.exit(1)


def _config_get(config, key: str):
    """Resolve a dotted config key (supports nested attrs and dicts)."""
    parts = key.split(".")
    obj = config
    for part in parts:
        if isinstance(obj, dict):
            obj = obj[part]
        else:
            obj = getattr(obj, part)
    return obj


def _config_set(config, key: str, value):
    """Set a dotted config key."""
    parts = key.split(".")
    obj = config
    for part in parts[:-1]:
        if isinstance(obj, dict):
            obj = obj[part]
        else:
            obj = getattr(obj, part)
    if isinstance(obj, dict):
        obj[parts[-1]] = value
    else:
        setattr(obj, parts[-1], value)


def _parse_config_value(raw: str):
    """Parse a string into int/float/bool/JSON/string."""
    for fn in (int, float):
        try:
            return fn(raw)
        except (ValueError, TypeError):
            pass
    low = raw.lower()
    if low in ("true", "yes", "1"):
        return True
    if low in ("false", "no", "0"):
        return False
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    return raw


def _llm_config_path(config: StrataConfig) -> Path:
    """Return the path to the LLM config file (pi-config.json)."""
    return config.base_dir / "pi-config.json"


def _read_llm_config(config: StrataConfig) -> dict | None:
    """Read the LLM config from pi-config.json. Returns None if missing."""
    path = _llm_config_path(config)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("llm")
    except (json.JSONDecodeError, KeyError):
        return None


def _write_llm_config(config: StrataConfig, llm_cfg: dict) -> None:
    """Write the LLM config dict to pi-config.json, preserving other keys."""
    path = _llm_config_path(config)
    existing = {}
    if path.exists():
        with contextlib.suppress(json.JSONDecodeError):
            existing = json.loads(path.read_text())
    existing["llm"] = llm_cfg
    path.write_text(json.dumps(existing, indent=2) + "\n")


def _config_to_dict(config: StrataConfig) -> dict:
    """Serialise config as a plain dict for JSON output."""
    return {
        "base_dir": str(config.base_dir.resolve()),
        "active_dir": config.active_dir,
        "cooled_dir": config.cooled_dir,
        "search_backend": config.search_backend,
        "qmd_reranker": config.qmd_reranker,
        "stratum_3_archive": config.stratum_3_archive,
        "stratum_3_shadow_db": config.stratum_3_shadow_db,
        "decay_thresholds": config.decay_thresholds,
        "lru_days": config.lru_days,
        "lru_min_access_count": config.lru_min_access_count,
        "lru_decay_thresholds": config.lru_decay_thresholds,
        "active_file_patterns": config.active_file_patterns,
        "qmd_enabled": config.qmd_enabled,
        "qmd_collection_prefix": config.qmd_collection_prefix,
    }


def _with_strata(fn, config: StrataConfig | None = None):
    """Open Strata, call fn, close."""
    c = config or _config()
    with Strata(c) as s:
        fn(s)


def _qmd_onboarding(config: StrataConfig) -> None:
    """Interactive QMD search backend onboarding."""
    print()
    print("Select search backend:")
    print("  1) QMD with hybrid search (recommended) — uses BM25 + vector search")
    print("  2) QMD with LLM rerankers — better results, uses API credits")
    print("  3) FTS5 keyword search only — no external dependencies")
    if sys.stdin.isatty():
        try:
            choice = input("Choice [1/2/3]: ").strip()
        except (EOFError, OSError):
            choice = ""
    else:
        choice = ""
    if choice == "1":
        _try_install_qmd(config)
    elif choice == "2":
        _try_install_qmd(config)
        if config.search_backend == "qmd":
            _qmd_reranker_prompt(config)
    else:
        config.search_backend = "fts5"


def _try_install_qmd(config: StrataConfig) -> None:
    """Attempt to install QMD via npx with 30s timeout."""
    print("  Installing QMD (this may take a moment)...")
    try:
        result = subprocess.run(
            ["npx", "@tobilu/qmd"],
            timeout=30,
            capture_output=True,
        )
        if result.returncode == 0:
            print("  ✓ QMD ready")
        else:
            print(
                "  ⚠ QMD install failed. Install manually:"
            )
            print("    npm install -g @tobilu/qmd")
            config.search_backend = "fts5"
    except subprocess.TimeoutExpired:
        print("  ⚠ QMD install timed out after 30s. Install manually:")
        print("    npm install -g @tobilu/qmd")
        config.search_backend = "fts5"
    except FileNotFoundError:
        print(
            "  ⚠ npx not found. Install manually:"
        )
        print("    npm install -g @tobilu/qmd")
        config.search_backend = "fts5"


def _qmd_reranker_prompt(config: StrataConfig) -> None:
    """Prompt for LLM reranker provider URL."""
    try:
        print(
            "LLM reranker provider URL (e.g., openai://gpt-4o-mini, ollama://llama3):"
        )
        reranker = input().strip()
        if reranker:
            config.qmd_reranker = reranker
        print("LLM rerankers will use API credits or local compute")
    except (EOFError, OSError):
        pass


def _save_strata_config(config: StrataConfig) -> None:
    """Persist config choices to strata.json."""
    config_path = config.base_dir / "strata.json"
    # Load existing data to preserve any fields not explicitly managed
    data = {}
    if config_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            data = json.loads(config_path.read_text())
    data.update(
        {
            "search_backend": config.search_backend,
            "qmd_reranker": config.qmd_reranker,
            "lru_days": config.lru_days,
            "lru_min_access_count": config.lru_min_access_count,
            "decay_thresholds": config.decay_thresholds,
            "active_file_patterns": config.active_file_patterns,
        }
    )
    config_path.write_text(json.dumps(data, indent=2))


def _cmd_init(rest: list[str] | None = None):
    """Handle the ``init`` command: create directory structure.

    Resolution order for the base directory:
    1. ``$STRATA_HOME`` environment variable (always wins)
    2. ``--global`` / ``-g`` flag sets ``~/.strata/``
    3. ``--local`` / ``-l`` flag or default sets ``./strata_data/``

    If not ``--non-interactive``, runs QMD search backend onboarding.

    Args:
        rest: Remaining command-line arguments after ``init``.
    """
    explicit = rest or []
    non_interactive = "--non-interactive" in explicit
    env_home = os.environ.get("STRATA_HOME")
    if env_home:
        base_dir = Path(env_home)
    elif "--global" in explicit or "-g" in explicit:
        base_dir = Path.home() / ".strata"
    elif "--local" in explicit or "-l" in explicit:
        base_dir = Path("./strata_data")
    else:
        base_dir = Path("./strata_data")
    config = StrataConfig(base_dir=base_dir)
    with Strata(config) as s:
        s.s1.ensure_dirs()
        s.s2.ensure_dirs()
        s.s3.ensure_dirs()
    kind = "global" if base_dir == Path.home() / ".strata" else "local"

    if not non_interactive:
        _qmd_onboarding(config)

    _save_strata_config(config)

    # ── Post-init onboarding guide ──────────────────────────────────────────
    print()
    print(f"\u2713 Initialized {kind} Strata at {config.base_dir.resolve()}")
    print()
    print("  Next steps:")
    print()
    print("  1. Write your first memory:")
    print('     strata add hello.md "# Hello from Strata"')
    print()
    print("  2. Search across all three tiers:")
    print('     strata search "hello"')
    print()
    print("  3. Start the Janitor daemon for automatic memory lifecycle:")
    print("     strata serve          # foreground (Ctrl+C to stop)")
    print("     strata serve &        # background process")
    print("     strata install-service  # systemd service (persistent)")
    print()
    print("  4. Install the agent skill (for AI coding assistants):")
    print("     strata skill install --global")
    print()
    print("  Commands at a glance: strata --help")


def _cmd_add(rest: list[str]):
    """Add content to 1st Stratum active memory.

    Usage:
        strata add projects/kynd/notes.md "Some content here"
        echo "content" | strata add projects/kynd/notes.md
        strata add --file /path/to/file.md projects/kynd/notes.md
        strata add --text "Quick memory note"    # auto-routed to quick-note-<ts>.md
    """
    config = _config()

    # Parse --file flag
    file_content = None
    filtered: list[str] = []
    i = 0
    while i < len(rest):
        if rest[i] == "--file" and i + 1 < len(rest):
            try:
                file_content = Path(rest[i + 1]).read_text()
            except FileNotFoundError:
                if _JSON_MODE:
                    _json_error("add", f"File not found: {rest[i + 1]}")
                print(f"File not found: {rest[i + 1]}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                if _JSON_MODE:
                    _json_error("add", str(e))
                print(f"Error reading file: {e}", file=sys.stderr)
                sys.exit(1)
            i += 2
        else:
            filtered.append(rest[i])
            i += 1
    rest = filtered

    with Strata(config) as s:
        if not rest:
            if file_content is not None:
                path = f"quick-note-{time.monotonic_ns()}.md"
                s.write_active(path, file_content)
                written_path = str(s.s1._root / path)
                if _JSON_MODE:
                    _json_print(
                        "add",
                        {"path": path, "file": str(s.s1._root / path), "written": True},
                    )
                    return
                print(f"Written to: {written_path}")
                return
            # Read from stdin
            content = sys.stdin.read().strip()
            if not content:
                if _JSON_MODE:
                    _json_error("add", "No content provided")
                print("No content provided. Pipe content or pass path + content.")
                print("  echo 'my note' | strata add projects/notes.md")
                return
            path = f"quick-note-{time.monotonic_ns()}.md"
            s.write_active(path, content)
            written_path = str(s.s1._root / path)
            if _JSON_MODE:
                _json_print(
                    "add", {"path": path, "file": written_path, "written": True}
                )
                return
            print(f"Written to: {written_path}")
            return

        if rest[0] == "--text" and len(rest) >= 2:
            path = f"quick-note-{time.monotonic_ns()}.md"
            content = " ".join(rest[1:])
            s.write_active(path, content)
            written_path = str(s.s1._root / path)
            if _JSON_MODE:
                _json_print(
                    "add", {"path": path, "file": written_path, "written": True}
                )
                return
            print(f"Written to: {written_path}")
            return

        # Priority: inline text arg > --file > stdin
        if len(rest) >= 2:
            path = rest[0]
            content = " ".join(rest[1:])
        elif file_content is not None:
            path = rest[0]
            content = file_content
        else:
            path = rest[0]
            content = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
            if not content:
                if _JSON_MODE:
                    _json_error("add", "No content provided")
                print("Provide content as second argument or pipe it:")
                print(f"  strata add {path} 'your content'")
                print(f"  echo 'your content' | strata add {path}")
                return

        s.write_active(path, content)
        written_path = str(s.s1._root / path)
        if _JSON_MODE:
            _json_print("add", {"path": path, "file": written_path, "written": True})
            return
        print(f"Written to: {written_path}")


def _cmd_query(command: str, rest: list[str]):
    """Handle the ``search`` and ``query`` commands.

    ``search`` produces human-readable output; ``query`` produces JSON.

    Args:
        command: ``"search"`` or ``"query"``.
        rest: Remaining arguments (the search text).
    """
    query_text = " ".join(rest) if rest else ""
    if not query_text:
        if _JSON_MODE:
            _json_error(command, "No search text provided")
        print(f"Usage: strata {command} <search text>")
        return
    config = _config()
    with Strata(config) as s:
        results = s.query(query_text, top_k=10)
        if command == "search":
            if _JSON_MODE:
                _json_print("search", results)
                return
            _print_search_results(results)
        else:
            print(json.dumps(results, indent=2))


def _print_search_results(results: list[dict]):
    """Print search results in human-readable format.

    Each result is tagged with its stratum tier (ACTIVE, MEDIUM, ARCHIVE).
    Archived results that need rehydration are flagged with a note.

    Args:
        results: List of search result dicts from ``query_engine.search()``.
    """
    if not results:
        print("No results found.")
        return
    for i, r in enumerate(results, 1):
        tier_tag = {
            "stratum_1": "ACTIVE",
            "stratum_2": "MEDIUM",
            "stratum_3": "ARCHIVE",
        }.get(r["tier"], r["tier"])
        source = r.get("source", "?")
        content = r.get("content", "")
        score = r.get("score", 0)
        meta = r.get("metadata", {})

        sep = "\u00b7"
        print(f"\n  [{i}] [{tier_tag}] {sep} score={score:.2f} {sep} {source}")

        if content:
            preview = content[:120].replace("\n", " ").strip()
            print(f"       {preview}...")

        if r["tier"] == "stratum_3" and meta.get("_needs_rehydration"):
            print("       [in archive \u2014 use strata rehydrate <id> to restore]")


def _cmd_read(rest: list[str]):
    """Handle the ``read`` command: print a file's contents.

    Reads from any stratum (active -> cooled -> archive). When reading
    from the 2nd Stratum, access is tracked and the file may be
    automatically promoted back to active. When reading from the 3rd
    Stratum, the file is automatically rehydrated to active.

    Args:
        rest: Remaining arguments (expects ``<path>``).
    """
    if not rest:
        print("Usage: strata read <path>")
        return
    config = _config()
    with Strata(config) as s:
        try:
            result = s.read(rest[0])
            source = result.get("source", "active")
            if result.get("promoted"):
                count = result.get("access_count", 0)
                print(f"\u2b06 Promoted from cooled (accessed {count} times)\n")
            elif result.get("rehydrated"):
                print("\u2b06 Restored from archive to 1st Stratum (active)\n")
            elif source == "cooled":
                count = result.get("access_count", 0)
                print(
                    f"\u2192 Read from cooled (access {count}/{s.config.promotion_threshold})\n"
                )
            print(result["content"])
        except FileNotFoundError:
            print(f"File not found: {rest[0]}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


def _cmd_list(rest: list[str]):
    """Handle the ``list`` command: show 1st Stratum files and dirs.

    Args:
        rest: Remaining arguments (optional ``<path>`` to list).
    """
    path = rest[0] if rest else ""
    config = _config()
    with Strata(config) as s:
        entries = s.list_active(path)
        if not entries:
            print(f"Empty or not found: {path or '/'}")
            return
        for e in entries:
            t = "dir" if e["type"] == "directory" else "file"
            print(f"  [{t}] {e['path']} ({e['size']}b)")


def _cmd_list_stratum_2():
    """Handle the ``list-stratum-2`` command: show cooled files."""
    config = _config()
    with Strata(config) as s:
        files = s.s2.list_all()
        if not files:
            print("No 2nd Stratum files.")
            return
        for f in files:
            print(f"  {f['path']} ({f['size']}b, modified {f['modified'][:10]})")


def _cmd_forget(rest: list[str]):
    """Archive a file from 2nd Stratum to 3rd Stratum."""
    if not rest:
        print("Usage: strata forget <path>")
        return
    path = rest[0]
    config = _config()
    with Strata(config) as s:
        source = s.s2._root / path
        if not source.exists():
            print(f"File not found in 2nd Stratum: {path}")
            sys.exit(1)
        tags = [path.split("/")[0]] if "/" in path else []
        archive_path = s.s3.archive_file(source, path, tags=tags)
        source.unlink()
        print(f"Archived to: {archive_path}")


def _cmd_rehydrate(rest: list[str]):
    """Handle the ``rehydrate`` command: restore archived file.

    Usage:
        strata rehydrate <shadow_id> [--target=active|cooled]

    The shadow ID comes from search results (``archive:id`` field).
    By default restores to active/; use ``--target=cooled`` to restore
    to the cooled stratum instead.
    """
    if not rest:
        print("Usage: strata rehydrate <shadow_id> [--target=active|cooled]")
        return

    target_tier = "active"
    shadow_id = None
    for arg in rest:
        if arg.startswith("--target="):
            target_tier = arg.split("=", 1)[1]
            if target_tier not in ("active", "cooled"):
                print(
                    f"Invalid target: {target_tier} (use --target=active or --target=cooled)",
                    file=sys.stderr,
                )
                sys.exit(1)
        elif not arg.startswith("--"):
            shadow_id = arg

    if not shadow_id:
        print(
            "Usage: strata rehydrate <shadow_id> [--target=active|cooled]",
            file=sys.stderr,
        )
        sys.exit(1)

    config = _config()
    with Strata(config) as s:
        # Find shadow entry by id
        try:
            conn = s.s3._connect_shadow()
            row = conn.execute(
                "SELECT * FROM shadow_index WHERE id = ? OR original_path = ?",
                (shadow_id, shadow_id),
            ).fetchone()
        except Exception:
            row = None

        if not row:
            print(f"Shadow entry not found: {shadow_id}", file=sys.stderr)
            sys.exit(1)

        entry = dict(row)
        result = s.rehydrate(entry, target_tier=target_tier)
        if result is None:
            print(f"Could not read archive file for: {shadow_id}", file=sys.stderr)
            sys.exit(1)

        tier_name = {
            "active": "1st Stratum (active)",
            "cooled": "2nd Stratum (cooled)",
        }.get(target_tier, target_tier)
        print(f"Restored to {tier_name}: {result.get('original_path', '?')}")


def _cmd_lifecycle(command: str, rest: list[str]):
    """Handle lifecycle commands: ``migrate``, ``evict``, ``maintenance``.

    Supports the ``--dry-run`` flag to preview changes.

    Args:
        command: ``"migrate"``, ``"promote"``, ``"evict"``, or ``"maintenance"``.
        rest: Remaining arguments (e.g. ``--dry-run``).
    """
    dry_run = "--dry-run" in rest
    config = _config()
    with Strata(config) as s:
        s.s1.ensure_dirs()
        s.s3.ensure_dirs()
        if command == "migrate":
            with _spinner("Migrating"):
                results = s.migrate(dry_run=dry_run)
            if _JSON_MODE:
                _json_print(
                    "migrate",
                    {"files": results, "count": len(results), "dry_run": dry_run},
                )
                return
            print(json.dumps(results, indent=2))
            print(f"\nMigrated: {len(results)} files")
        elif command == "promote":
            with _spinner("Promoting"):
                results = s.promote(dry_run=dry_run)
            if _JSON_MODE:
                _json_print(
                    "promote",
                    {"files": results, "count": len(results), "dry_run": dry_run},
                )
                return
            print(json.dumps(results, indent=2))
            print(f"\nPromoted: {len(results)} files")
        elif command == "evict":
            with _spinner("Evicting"):
                results = s.evict(dry_run=dry_run)
            if _JSON_MODE:
                _json_print(
                    "evict",
                    {"memories": results, "count": len(results), "dry_run": dry_run},
                )
                return
            print(json.dumps(results, indent=2))
            print(f"\nEvicted: {len(results)} memories")
        elif command == "maintenance":
            with _spinner("Running maintenance"):
                result = s.run_maintenance(dry_run=dry_run)
            if _JSON_MODE:
                _json_print("maintenance", result)
                return
            print(json.dumps(result, indent=2))
            print(
                f"\nPromoted: {result.get('total_promoted') or len(result.get('promoted', []))}"
            )
            print(
                f"Migrated: {result.get('total_migrated') or len(result.get('migrated', []))}"
            )
            print(
                f"Evicted:  {result.get('total_evicted') or len(result.get('evicted', []))}"
            )


def _cmd_serve(rest: list[str]):
    """Handle the ``serve`` (and ``daemon``) command: start the Janitor.

    Supports ``--interval=N`` and ``--live`` flags.

    Args:
        rest: Remaining arguments after ``serve``.
    """
    interval = 900
    dry_run_first = True
    for arg in rest:
        if arg.startswith("--interval="):
            interval = int(arg.split("=")[1])
        elif arg == "--live":
            dry_run_first = False
        elif arg == "--help":
            print("Usage: strata serve [--interval=SECONDS] [--live]")
            print("  --interval=N   Seconds between maintenance cycles (default: 900)")
            print(
                "  --live         Skip initial dry-run, go straight to live operations"
            )
            return

    config = _config()
    status = get_daemon_status(config)
    if status["running"]:
        print(
            f"Daemon is already running (pid={status['pid']}). Use 'strata stop' first or 'strata restart'."
        )
        return

    daemon = StrataDaemon(
        config=config,
        interval_seconds=interval,
        dry_run_first=dry_run_first,
    )
    print(
        f"Starting Strata daemon (interval={interval}s, dry_run_first={dry_run_first})"
    )
    print(f"  Log:  {daemon._log_path.resolve()}")
    print(f"  PID:  {daemon._pid_path.resolve()}")
    print("Press Ctrl+C to stop.")
    daemon.start()


def _cmd_stop():
    """Handle the ``stop`` command: stop a running daemon."""
    from strata.daemon import stop_daemon

    config = _config()
    result = stop_daemon(config)
    print(result["message"])


def _cmd_install_service():
    """Handle the ``install-service`` command: install systemd user service.

    Copies the bundled ``contrib/strata.service`` to
    ``~/.config/systemd/user/strata.service`` and enables it.
    """
    import shutil

    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    target = systemd_dir / "strata.service"

    # Locate the bundled service file
    dev = Path(__file__).resolve().parent.parent / "contrib" / "strata.service"
    if dev.is_file():
        src = dev
    else:
        try:
            import importlib.resources as rsrc

            ref = rsrc.files("strata") / "contrib" / "strata.service"
            with rsrc.as_file(ref) as p:
                src = p.resolve()
        except Exception:
            print(
                "Error: could not locate strata.service bundle. Check your installation.",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        shutil.copy2(src, target)
    except OSError as e:
        print(f"Error: failed to install service: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\u2713 Installed systemd service to {target}")
    print()
    print("  Enable and start:")
    print("    systemctl --user daemon-reload")
    print("    systemctl --user enable --now strata")
    print()
    print("  Check status:")
    print("    systemctl --user status strata")
    print("    journalctl --user -u strata -f")


def _cmd_uninstall_service():
    """Handle the ``uninstall-service`` command: remove systemd user service."""
    target = Path.home() / ".config" / "systemd" / "user" / "strata.service"
    if not target.exists():
        print("No systemd service installed at {target}")
        return
    try:
        target.unlink()
    except OSError as e:
        print(f"Error: failed to remove service: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"\u2713 Removed {target}")
    print("  Run: systemctl --user daemon-reload")


def _cmd_status():
    """Handle the ``status`` command: show system state and daemon info."""
    config = _config()
    status = get_daemon_status(config)
    with Strata(config) as s:
        p1_count = len(s.s1.scan_stale_files())
        p2_count = s.s2.count()
        p3_count = s.s3.get_shadow_count()
        active_root = config.active_path().resolve()

    from strata.distiller import Distiller

    d = Distiller(config)
    llm_cfg = d._load_config()
    distiller_ready = d.check_available()
    distill_pending = d.get_pending_count()

    if _JSON_MODE:
        _json_print(
            "status",
            {
                "base_dir": str(config.base_dir.resolve()),
                "active_root": str(active_root),
                "stratum_1_stale": p1_count,
                "stratum_2_blocks": p2_count,
                "stratum_3_shadows": p3_count,
                "daemon_running": status["running"],
                "daemon_pid": status.get("pid"),
                "daemon_cycles": status.get("cycle_count", 0),
                "distill_llm_configured": llm_cfg is not None,
                "distill_available": distiller_ready,
                "distill_enabled": llm_cfg.get("enabled") if llm_cfg else False,
                "distill_pending": distill_pending,
            },
        )
        return

    print("Strata Memory System \u2014 Status")
    print(f"  Base directory: {config.base_dir.resolve()}")
    print(f"  Active root:    {active_root}")
    print("")
    print(f"  1st Stratum (Active):  {p1_count} stale file(s) pending")
    print(f"  2nd Stratum (Medium):  {p2_count} memory block(s)")
    print(f"  3rd Stratum (Archive): {p3_count} shadow entr(ies)")
    print("")
    if llm_cfg:
        if distiller_ready:
            flag = "ENABLED" if llm_cfg.get("enabled") else "DISABLED"
            print(
                f"  Distiller: {flag} ({llm_cfg.get('provider', '?')} / {llm_cfg.get('model', '?')})"
            )
        else:
            print("  Distiller: CONFIGURED (unavailable)")
    else:
        print("  Distiller: NOT CONFIGURED")
    print(f"  Pending conversations: {distill_pending}")
    print("")
    print(
        f"  Daemon: {'RUNNING (pid=' + str(status['pid']) + ')' if status['running'] else 'STOPPED'}"
    )

    if status["running"]:
        print(f"  Cycles completed: {status['cycle_count']}")
        if status["log_lines"]:
            print("  Recent log:")
            for line in status["log_lines"][-5:]:
                print(f"    {line}")


def _cmd_config(rest: list[str]):
    """Handle the ``config`` command: show or modify configuration.

    Subcommands:
        ``strata config``              Show all config values.
        ``strata config get <key>``    Get a specific value.
        ``strata config set <key> <v>`` Set a config value.

    Args:
        rest: Remaining arguments after ``config``.
    """
    config = _config()

    # No args — show all config
    if not rest:
        if _JSON_MODE:
            _json_print("config", _config_to_dict(config))
            return
        print("strata Configuration")
        print(f"{'=' * 40}")
        print(f"  base_dir:           {config.base_dir.resolve()}")
        print(f"  active_dir:         {config.active_dir}")
        print(f"  cooled_dir:         {config.cooled_dir}")
        print(f"  qmd_enabled:        {config.qmd_enabled}")
        print(f"  stratum_3_archive:     {config.stratum_3_archive}")
        print(f"  stratum_3_shadow_db:   {config.stratum_3_shadow_db}")
        print("")
        print("  Decay thresholds:")
        for pattern, days in sorted(config.decay_thresholds.items()):
            print(f"    /{pattern}:  {days} days")
        print("")
        print(
            f"  LRU eviction:       {config.lru_days} days, \u2264{config.lru_min_access_count} access(es)"
        )
        print(f"  QMD enabled:        {config.qmd_enabled}")
        print(f"  File patterns:      {', '.join(config.active_file_patterns)}")
        return

    # config get <key>
    if rest[0] == "get" and len(rest) >= 2:
        key = rest[1]
        # Route llm.* keys to pi-config.json
        if key == "llm" or key.startswith("llm."):
            llm_cfg = _read_llm_config(config)
            if llm_cfg is None:
                print("LLM not configured (no pi-config.json)", file=sys.stderr)
                sys.exit(1)
            if key == "llm":
                if _JSON_MODE:
                    _json_print("config", {"key": key, "value": llm_cfg})
                    return
                for k, v in llm_cfg.items():
                    print(f"  llm.{k} = {v!r}")
                return
            # key is llm.<subkey>
            sub = key.split(".", 1)[1]
            if sub not in llm_cfg:
                print(f"Unknown config key: {key}", file=sys.stderr)
                sys.exit(1)
            if _JSON_MODE:
                _json_print("config", {"key": key, "value": llm_cfg[sub]})
                return
            print(llm_cfg[sub])
            return
        try:
            value = _config_get(config, key)
        except (KeyError, AttributeError):
            if _JSON_MODE:
                _json_error("config", f"Unknown config key: {key}")
            print(f"Unknown config key: {key}", file=sys.stderr)
            sys.exit(1)
        if _JSON_MODE:
            _json_print("config", {"key": key, "value": value})
            return
        print(value)
        return

    # config set <key> <value>
    if rest[0] == "set" and len(rest) >= 2:
        key = rest[1]
        # If setting llm.apiKey with no value, prompt securely
        if len(rest) == 2 and key.endswith("apiKey"):
            import getpass

            raw_value = getpass.getpass("Enter API key: ")
            if not raw_value:
                print("No key provided, aborting.", file=sys.stderr)
                sys.exit(1)
        elif len(rest) < 3:
            if _JSON_MODE:
                _json_error("config", "Usage: strata config set <key> <value>")
            print("Usage: strata config set <key> <value>", file=sys.stderr)
            sys.exit(1)
        else:
            raw_value = " ".join(rest[2:])
        value = _parse_config_value(raw_value)
        # Route llm.* keys to pi-config.json
        if key == "llm" or key.startswith("llm."):
            llm_cfg = _read_llm_config(config) or {}
            if key == "llm":
                if not isinstance(value, dict):
                    print("llm value must be a JSON object", file=sys.stderr)
                    sys.exit(1)
                llm_cfg.clear()
                llm_cfg.update(value)
            else:
                sub = key.split(".", 1)[1]
                llm_cfg[sub] = value
            _write_llm_config(config, llm_cfg)
            if _JSON_MODE:
                _json_print("config", {"key": key, "value": value, "set": True})
                return
            print(
                f"Set llm.{key.split('.', 1)[1] if '.' in key else ''} = {value!r}"
                if "." in key
                else "Set llm config"
            )
            return
        # Validate top-level key
        top = key.split(".")[0]
        if not hasattr(config, top):
            if _JSON_MODE:
                _json_error("config", f"Unknown config key: {key}")
            print(f"Unknown config key: {key}", file=sys.stderr)
            sys.exit(1)
        try:
            _config_set(config, key, value)
        except (KeyError, AttributeError):
            if _JSON_MODE:
                _json_error("config", f"Cannot set config key: {key}")
            print(f"Cannot set config key: {key}", file=sys.stderr)
            sys.exit(1)
        _save_strata_config(config)
        if _JSON_MODE:
            _json_print("config", {"key": key, "value": value, "set": True})
            return
        print(f"Set config.{key} = {value!r}")
        return

    # Unknown subcommand
    if _JSON_MODE:
        _json_error("config", "Usage: strata config [get <key> | set <key> <value>]")
    print("Usage: strata config [get <key> | set <key> <value>]", file=sys.stderr)
    sys.exit(1)


def _cmd_history(rest: list[str]):
    """Handle the ``history`` command: show recent daemon log lines.

    Args:
        rest: Remaining arguments (supports ``--lines=N``).
    """
    lines = 20
    for arg in rest:
        if arg.startswith("--lines="):
            lines = int(arg.split("=")[1])

    config = _config()
    log_path = config.base_dir / "strata.log"
    if not log_path.exists():
        print("No daemon log found. Start the daemon with 'strata serve'.")
        return

    content = log_path.read_text(encoding="utf-8").strip()
    log_lines = content.split("\n")
    tail = log_lines[-lines:]
    print(f"Janitor Log ({len(tail)} of {len(log_lines)} lines):")
    print(f"{'=' * 60}")
    for line in tail:
        print(f"  {line}")


def _cmd_distiller(rest: list[str]):
    """Handle the ``distiller`` command: show distillation state or trigger a run.

    Subcommands:
        ``strata distiller status``    Show pending count and config state.
        ``strata distiller run``       Manually run LLM distillation.
    """
    config = _config()
    from strata.distiller import Distiller

    d = Distiller(config)
    cfg = d._load_config()

    # Subcommand dispatch
    sub = rest[0] if rest else ""

    if sub == "status":
        if _JSON_MODE:
            _json_print(
                "distiller",
                {
                    "available": d.check_available(),
                    "llm_configured": cfg is not None,
                    "enabled": cfg["enabled"] if cfg else False,
                    "provider": cfg["provider"] if cfg else None,
                    "model": cfg["model"] if cfg else None,
                    "pending": d.get_pending_count(),
                },
            )
            return

        print("Distiller Status")
        print("=" * 40)
        if cfg is None:
            print("  LLM:         NOT CONFIGURED")
            print("  Configure:   strata config set llm.apiKey <key>")
        elif not d.check_available():
            print("  LLM:         CONFIGURED (unavailable — check API key)")
            print(f"  Provider:    {cfg.get('provider', '?')}")
        else:
            print(f"  LLM:         {'ENABLED' if cfg.get('enabled') else 'DISABLED'}")
            print(f"  Provider:    {cfg.get('provider', '?')}")
            print(f"  Model:       {cfg.get('model', '?')}")
        print(f"  Pending:     {d.get_pending_count()} conversation(s)")
        print()
        print("  Tip: run 'strata distiller run' to manually trigger")
        return

    if sub == "run":
        dry = "--dry-run" in rest or "-n" in rest
        if dry:
            result = d.process(dry_run=True)
        else:
            result = d.process()

        if _JSON_MODE:
            _json_print("distiller", result)
            return

        status = result["status"]
        if status == "dry_run":
            print(f"Would process {result.get('would_process', 0)} conversation(s)")
            print("Pass --live to execute." if "--dry-run" not in rest else "")
        elif status == "ok":
            print(f"Processed {result['processed']} conversation(s)")
            print(f"Wrote {result['facts_written']} fact file(s)")
        elif status == "no_facts_extracted":
            print(
                f"Processed {result['processed']} conversation(s) — no facts extracted"
            )
        elif status == "skipped":
            reason = result.get("reason", "unknown")
            print(f"Skipped: {reason}")
            if reason == "llm_not_configured":
                print("Run 'strata config set llm.apiKey <key>' to configure.")
        elif status == "error":
            print(f"Error: {result.get('reason', 'unknown')}")
        else:
            print(f"Result: {result}")
        return

    # No subcommand / unknown
    print("Usage: strata distiller status|run", file=sys.stderr)
    sys.exit(1)


def _cmd_cost(rest: list[str]):
    """Show estimated cost savings from Janitor automation."""
    config = _config()
    from strata.tracking import CostTracker

    tracker = CostTracker(config)
    summary = tracker.get_summary()

    # Check for no daemon activity
    if "error" in summary:
        if _JSON_MODE:
            _json_print("cost", {"error": summary["error"]})
            return
        print(summary["error"])
        return

    if _JSON_MODE:
        _json_print("cost", summary)
        return

    # Formatted output (like _cmd_config pattern)
    print("Strata Cost Savings (Estimated)")
    print("=" * 40)
    print(f"  Daemon cycles:     {summary['daemon_cycles']['value']}")
    print(f"  Files migrated:    {summary['files_migrated']['value']}")
    print(f"  Files evicted:     {summary['files_evicted']['value']}")
    print(f"  LRU decisions:     {summary['lru_decisions']['value']}")
    print(f"  Tokens saved:      {summary['tokens_saved_estimate']['value']:,} tokens")
    print(f"  Savings range:     {summary['tokens_saved_range']['value']}")
    print()
    print(
        f"  Methodology: {summary.get('tokens_saved_estimate', {}).get('methodology', '')}"
    )
    print(
        f"  Disclaimer: {summary.get('tokens_saved_estimate', {}).get('disclaimer', '')}"
    )


def _cmd_index():
    """Regenerate the 1st Stratum index.md."""
    config = _config()
    with Strata(config) as s:
        s.generate_index()
    idx = config.active_path() / "index.md"
    if idx.exists():
        print(f"Index regenerated: {idx.resolve()}")
        print(idx.read_text()[:300])
    else:
        print("No active files to index.")


def _cmd_mcp():
    """Start MCP protocol server over stdio."""
    server = MCPServer()
    try:
        server.run_stdio()
    finally:
        server.close()


# ── Skill Install ──────────────────────────────────────────────────────────────


def _find_skill_dir() -> Path | None:
    """Locate the bundled strata skill directory for AI agents.

    Resolution order:
    1. Relative to this file (development install / editable mode)
    2. Via importlib.resources (installed package)
    """
    # Development / editable mode: relative to this script
    dev = Path(__file__).resolve().parent / "skills" / "strata"
    if dev.is_dir():
        return dev

    # Installed package: use importlib.resources
    try:
        import importlib.resources as rsrc

        ref = rsrc.files("strata") / "skills" / "strata"
        with rsrc.as_file(ref) as path:
            if path.is_dir():
                return path.resolve()
    except Exception:
        pass

    return None


# ── Pi Extension Install ─────────────────────────────────────────────────────


def _find_pi_skill_dir() -> Path | None:
    """Locate the bundled Strata Pi extension file.

    Resolution order:
    1. Relative to this file (development install / editable mode)
    2. Via importlib.resources (installed package)
    """
    # Development / editable mode: relative to project root
    dev = Path(__file__).resolve().parent.parent / "skills" / "pi" / "strata.ts"
    if dev.is_file():
        return dev

    # Installed package: use importlib.resources
    try:
        import importlib.resources as rsrc

        ref = rsrc.files("strata") / "skills" / "pi" / "strata.ts"
        with rsrc.as_file(ref) as path:
            if path.is_file():
                return path.resolve()
    except Exception:
        pass

    return None


def _cmd_pi_install(rest: list[str]):
    """Install the Strata Pi extension to ~/.pi/agent/extensions/strata.ts."""
    if not shutil.which("pi"):
        print("Error: 'pi' not found. Install Pi from https://pi.ai", file=sys.stderr)
        sys.exit(1)

    pi_ext_dir = Path.home() / ".pi" / "agent" / "extensions"
    pi_config = Path.home() / ".pi"

    if not pi_config.is_dir():
        print(
            "Warning: Pi config not found at ~/.pi/. Have you run Pi yet?",
            file=sys.stderr,
        )

    src = _find_pi_skill_dir()
    if src is None:
        print(
            "Error: Strata Pi extension not found. Reinstall strata-memory.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        pi_ext_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create {pi_ext_dir}: {e}", file=sys.stderr)
        sys.exit(1)

    dst = pi_ext_dir / "strata.ts"

    if dst.exists():
        force = "--force" in rest
        if not force:
            try:
                choice = input("Overwrite existing strata.ts? [y/N]: ").strip()
            except EOFError:
                choice = "n"
            if choice.lower() != "y":
                print("Aborted.")
                return

    shutil.copy2(src, dst)
    print(f"✓ Strata Pi extension installed to {dst}")
    print("  Run /reload in Pi to activate.")


def _cmd_skill(rest: list[str]):
    """Handle the ``skill`` command and its subcommands.

    Args:
        rest: Remaining arguments after ``skill``.
    """
    if not rest:
        print("Usage: strata skill install")
        print("")
        print("  Installs the Strata agent skill for AI coding assistants")
        print("  (OpenCode, Claude Code, PI, Cursor, Codex, etc.).")
        print("")
        print("  By default it runs the Vercel Labs skills CLI interactively —")
        print("  you'll be prompted to choose scope (global/project) and agents.")
        print("")
        print("Flags:")
        print("  --global   Skip interactive prompts, install globally to all agents")
        print("")
        print("Requires Node.js (npx). Uses 'npx skills add' from vercel-labs/skills.")
        return

    subcommand = rest[0]
    if subcommand == "install":
        _cmd_skill_install(rest[1:])
    else:
        print(f"Unknown skill subcommand: {subcommand}")
        print("Usage: strata skill install")
        sys.exit(1)


def _cmd_skill_install(rest: list[str]):
    """Install the Strata skill for AI coding assistants.

    Supports ``--global`` flag for non-interactive global install.
    Delegates to ``npx skills add`` (requires Node.js).

    Args:
        rest: Remaining arguments after ``skill install``.
    """
    skill_dir = _find_skill_dir()
    if skill_dir is None:
        print(
            "Error: Strata skill not found. Reinstall strata-memory.", file=sys.stderr
        )
        sys.exit(1)

    if not shutil.which("npx"):
        print(
            "Error: 'npx' not found. Install Node.js from https://nodejs.org/",
            file=sys.stderr,
        )
        print("Then run: strata skill install", file=sys.stderr)
        sys.exit(1)

    global_mode = "--global" in rest

    cmd = ["npx", "-y", "skills@latest", "add", str(skill_dir)]
    if global_mode:
        cmd.extend(["--all", "-g", "-y"])
        print("Installing Strata skill globally for all AI agents...")
        print(f"  Skill:    {skill_dir}")
    else:
        print("Launching interactive skill installer...")
        print(f"  Skill:    {skill_dir}")
        print("  Follow the prompts to choose scope (global/project) and agents.")
        print()

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(
            f"Error: Skill installation failed (exit code {result.returncode})",
            file=sys.stderr,
        )
        sys.exit(1)

    print()
    print("✓ Strata skill installed! It's now available to your AI assistants.")
    print("  Agents should auto-detect it. Try: strata --agent-help")


def _cmd_qmd_setup():
    """Configure QMD collections for all Strata directories."""
    config = _config()
    from strata.storage import QmdWrapper

    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed. Install it with: npm install -g @tobilu/qmd")
        return
    results = qmd.setup_collections()
    for r in results:
        print(f"  [{r['status']}] {r['name']}: {r.get('path', '')}")
    print("\nRun 'strata qmd-embed' to generate vector embeddings.")


def _cmd_qmd_embed():
    """Generate QMD vector embeddings."""
    config = _config()
    from strata.storage import QmdWrapper

    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed. Install it with: npm install -g @tobilu/qmd")
        return
    print("Generating embeddings (may take a while on first run)...")
    result = qmd.embed(force=False)
    print(result.get("output", "Done."))


def _cmd_qmd_status():
    """Show QMD index status."""
    config = _config()
    from strata.storage import QmdWrapper

    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed.")
        return
    result = qmd.get_status()
    print(result.get("output", "Unknown status."))


def _agent_help() -> str:
    """Return the full agent help text.

    The help text describes Strata's architecture, commands, and best
    practices for AI coding assistants.

    Returns:
        A markdown-formatted help string.
    """
    return """# Strata — Agent Help

Strata is a tiered memory system for AI agents. It stores memories as plain
markdown files and moves them between three strata based on age and access.

## Architecture

  strata_data/
  ├── active/     ← 1st Stratum: Agent reads/writes here (working memory)
  ├── cooled/     ← 2nd Stratum: Aged-out files, searchable (Janitor manages)
  └── archive/    ← 3rd Stratum: Cold storage + shadow index (keyword-retrievable)

- The agent ONLY reads and writes to the 1st Stratum (active/).
- The Janitor (background process) moves files from active/ to cooled/,
  and from cooled/ to archive/, based on configurable thresholds.
- The agent queries across ALL three strata via `strata search`.

## Principle

Start by reading `active/index.md`. It lists every file in the 1st Stratum
with its first heading as a description. Navigate to specific files by path.

For anything you can't find in the 1st Stratum, use `strata search`.
The cascade search checks all three strata automatically.

## Commands

### Reading & Writing (1st Stratum only)

  strata add <path> <content>
      Write a file. Creates parent dirs. Updates index.md.
      Example: strata add projects/koda/spec.md "# Koda Platform..."

  strata read <path>
      Read a file's full content.
      Example: strata read projects/koda/spec.md

  strata list [path]
      List files/directories in the 1st Stratum.
      Example: strata list projects

### Searching (ALL three strata)

  strata search <query>
      Human-readable search across active/ + cooled/ + archive/.
      Example: strata search "koda oauth2"

  strata query <query>
      Same as search but outputs JSON (for scripting).
      Example: strata query "postgresql pgvector"

### Lifecycle

  strata migrate
      Move stale files from active/ to cooled/ (configurable age threshold).
      No LLM calls — files stay as markdown.

  strata evict
      Move cold files from cooled/ to archive/ (configurable LRU threshold).
      Creates shadow index entry for retrieval.

  strata maintenance
      Run migrate + evict in one command.

### System

  strata status     Show system state (files per tier, daemon status)
  strata config     Show configuration (thresholds, paths)
  strata index      Regenerate the 1st Stratum index.md
  strata skill install
                    Install Strata skill for AI coding assistants.
                    Interactive by default (choose scope + agents).
                    Use --global for non-interactive global install.
                    Requires Node.js for 'npx skills add'.

### Daemon (Automatic Lifecycle)

  strata serve [--interval=N]
      Start the Janitor daemon. Runs migrate + evict every N seconds.
      Default interval: 900 (15 min). First cycle is a dry run.
      strata stop    Stop the daemon.
      strata restart Restart the daemon.
      strata history Show the daemon activity log.

### QMD Integration (optional hybrid search)

  Requires: npm install -g @tobilu/qmd

  strata qmd-setup  Add active/ + cooled/ as QMD collections
  strata qmd-embed  Generate vector embeddings
  strata qmd-status Check QMD index health

  When QMD is active, `strata search` uses BM25 + vector search (no LLM).

## Best Practices

1. READ index.md FIRST — it's the map of all active files.
2. Write markdown files with structured headings (# Title, ## Section).
3. Use the index.md auto-generated descriptions to find the right file.
4. Search across all strata when you can't find something in active/.
5. Trust the Janitor — it handles migrations automatically.
6. Files in cooled/ are read-only for the agent (query only).
   If you need to edit a cooled file, request rehydration.

## How It Works

- Migration is triggered by file age (default: 14 days for projects, 60 for entities).
- Eviction is triggered by LRU (default: 90 days since last access).
- The Shadow Index (shadow.db) tracks archived files by keyword for retrieval.
- Re-hydration restores archived files back to the 1st Stratum.
"""


if __name__ == "__main__":
    main()
