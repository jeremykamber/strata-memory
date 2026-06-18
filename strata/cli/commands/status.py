"""Status command: show system state and daemon info."""

from __future__ import annotations

from strata import Strata
from strata.cli._config import load_config
from strata.cli._json import json_print, is_json_mode
from strata.daemon import get_daemon_status
from strata.distiller import Distiller

name = "status"


def run(args: list[str]) -> None:
    config = load_config()
    status = get_daemon_status(config)
    with Strata(config) as s:
        p1_count = len(s.s1.scan_stale_files())
        p2_count = s.s2.count()
        p3_count = s.s3.get_shadow_count()
        active_root = config.active_path().resolve()

    d = Distiller(config)
    llm_cfg = d._load_config()
    distiller_ready = d.check_available()
    distill_pending = d.get_pending_count()

    if is_json_mode():
        json_print(
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
                f"  Distiller: {flag} ({llm_cfg.get('provider', '?')} / "
                f"{llm_cfg.get('model', '?')})"
            )
        else:
            print("  Distiller: CONFIGURED (unavailable)")
    else:
        print("  Distiller: NOT CONFIGURED")
    print(f"  Pending conversations: {distill_pending}")
    print("")
    daemon_status = f"RUNNING (pid={status['pid']})" if status["running"] else "STOPPED"
    print(f"  Daemon: {daemon_status}")

    if status["running"]:
        print(f"  Cycles completed: {status['cycle_count']}")
        if status["log_lines"]:
            print("  Recent log:")
            for line in status["log_lines"][-5:]:
                print(f"    {line}")
