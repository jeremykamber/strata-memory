"""Serve/daemon command: start the background Janitor daemon."""

from __future__ import annotations

from strata.cli._config import load_config
from strata.daemon import StrataDaemon, get_daemon_status

name = "serve"
aliases = ["daemon"]


def run(args: list[str]) -> None:
    interval = 900
    dry_run_first = True
    for arg in args:
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

    config = load_config()
    status = get_daemon_status(config)
    if status["running"]:
        print(
            f"Daemon is already running (pid={status['pid']}). "
            "Use 'strata stop' first or 'strata restart'."
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
