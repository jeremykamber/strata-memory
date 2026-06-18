"""History command: show recent daemon log lines."""

from __future__ import annotations

from strata.cli._config import load_config

name = "history"


def run(args: list[str]) -> None:
    lines = 20
    for arg in args:
        if arg.startswith("--lines="):
            lines = int(arg.split("=")[1])

    config = load_config()
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
