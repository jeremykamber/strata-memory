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

import sys
import time

from strata.cli import _json
from strata.cli._config import load_config
from strata.cli.help import print_usage, agent_help
from strata.cli.registry import CommandRegistry, CommandNotFound

# ── Global state for JSON mode (backward compat) ─────────────────────────────
_JSON_MODE = False
_START_TIME = 0.0


# ── Backward-compat aliases for code that imports from strata.cli ────────────
def _config(**kwargs):
    """Legacy alias for load_config()."""
    return load_config(**kwargs)


# ── Registry setup ───────────────────────────────────────────────────────────
_registry = CommandRegistry()


def _build_registry():
    """Register all commands. Called once at module load."""
    from strata.cli.commands import init as cmd_init
    from strata.cli.commands import add as cmd_add
    from strata.cli.commands import search as cmd_search
    from strata.cli.commands import read as cmd_read
    from strata.cli.commands import list_cmd as cmd_list
    from strata.cli.commands import forget as cmd_forget
    from strata.cli.commands import rehydrate as cmd_rehydrate
    from strata.cli.commands import lifecycle as cmd_lifecycle
    from strata.cli.commands import serve as cmd_serve
    from strata.cli.commands import stop as cmd_stop
    from strata.cli.commands import status as cmd_status
    from strata.cli.commands import config_cmd as cmd_config
    from strata.cli.commands import history as cmd_history
    from strata.cli.commands import qmd as cmd_qmd
    from strata.cli.commands import index_cmd as cmd_index
    from strata.cli.commands import mcp_cmd as cmd_mcp
    from strata.cli.commands import pi_install as cmd_pi_install
    from strata.cli.commands import distiller as cmd_distiller
    from strata.cli.commands import skill as cmd_skill
    from strata.cli.commands import cost as cmd_cost
    from strata.cli.commands import install_service as cmd_install_service
    from strata.cli.commands import uninstall_service as cmd_uninstall_service

    _registry.register("init", cmd_init.run)
    _registry.register("add", cmd_add.run)
    _registry.register("search", cmd_search.run, aliases=["query"])
    _registry.register("read", cmd_read.run)
    _registry.register("list", cmd_list.run)
    _registry.register("list-stratum-2", lambda a: cmd_list.list_stratum_2())
    _registry.register("forget", cmd_forget.run)
    _registry.register("rehydrate", cmd_rehydrate.run)
    _registry.register("migrate", lambda a: cmd_lifecycle.run(["migrate"] + a))
    _registry.register("promote", lambda a: cmd_lifecycle.run(["promote"] + a))
    _registry.register("evict", lambda a: cmd_lifecycle.run(["evict"] + a))
    _registry.register("maintenance", lambda a: cmd_lifecycle.run(["maintenance"] + a))
    _registry.register("serve", cmd_serve.run, aliases=["daemon"])
    _registry.register("stop", cmd_stop.run)
    _registry.register("status", cmd_status.run)
    _registry.register("config", cmd_config.run)
    _registry.register("history", cmd_history.run)
    _registry.register("qmd-setup", lambda a: cmd_qmd.run(["setup"] + a))
    _registry.register("qmd-embed", lambda a: cmd_qmd.run(["embed"] + a))
    _registry.register("qmd-status", lambda a: cmd_qmd.run(["status"] + a))
    _registry.register("index", cmd_index.run)
    _registry.register("mcp", cmd_mcp.run)
    _registry.register("pi-install", cmd_pi_install.run)
    _registry.register("distiller", cmd_distiller.run)
    _registry.register("skill", cmd_skill.run)
    _registry.register("cost", cmd_cost.run)
    _registry.register("install-service", cmd_install_service.run)
    _registry.register("uninstall-service", cmd_uninstall_service.run)


_build_registry()


def main(argv: list[str] | None = None):
    """Entry point for the Strata CLI.

    Parses command-line arguments, detects global flags (``--json``,
    ``--agent``), dispatches to the appropriate command handler.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).
    """
    global _JSON_MODE, _START_TIME
    _START_TIME = time.monotonic()
    _json.set_start_time(_START_TIME)

    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print_usage()
        return

    # Parse global flags before command dispatch
    filtered: list[str] = []
    for a in args:
        if a in ("--json", "--agent"):
            _JSON_MODE = True
            _json.set_mode(True)
        else:
            filtered.append(a)
    args = filtered

    if not args:
        print_usage()
        return

    # Handle help requests before command dispatch
    if args[0] in ("--help", "-h", "help"):
        print_usage()
        return

    if args[0] in ("--agent-help", "agent-help"):
        if _JSON_MODE:
            _json.json_print("agent-help", {"help": agent_help()})
            return
        print(agent_help())
        return

    command = args[0]
    rest = args[1:]

    # Special: restart dispatches to stop then serve
    if command == "restart":
        _registry.run("stop", [])
        _registry.run("serve", rest)
        return

    try:
        _registry.run(command, rest)
    except CommandNotFound:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


# ── Backward-compat aliases ──────────────────────────────────────────────────
def _print_usage():
    print_usage()


def _agent_help() -> str:
    return agent_help()
