"""Background Janitor daemon for automatic memory lifecycle management.

Provides the :class:`StrataDaemon` class which runs maintenance cycles
on a configurable interval, and module-level helper functions for
checking daemon status and stopping the daemon from the CLI.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from strata import Strata
from strata.config import StrataConfig, detect_base_dir


class StrataDaemon:
    """Background Janitor daemon for automatic memory lifecycle management.

    Runs on a configurable interval, executing 1st Stratum -> 2nd Stratum migration
    and 2nd Stratum -> 3rd Stratum eviction automatically. The daemon is the key
    component that makes Strata a "set and forget" memory system.
    """

    def __init__(
        self,
        config: Optional[StrataConfig] = None,
        interval_seconds: int = 900,
        log_file: Optional[str] = None,
        pid_file: Optional[str] = None,
        dry_run_first: bool = True,
    ):
        """Initialize the daemon.

        Args:
            config: Optional configuration. Auto-detects base directory
                if not provided.
            interval_seconds: Sleep time between maintenance cycles
                (default: 900, i.e. 15 minutes).
            log_file: Custom path for the daemon log file. Defaults to
                ``<base_dir>/strata.log``.
            pid_file: Custom path for the PID file. Defaults to
                ``<base_dir>/strata.pid``.
            dry_run_first: If ``True`` (default), the first cycle runs
                as a dry run.
        """
        self.config = config or StrataConfig(base_dir=detect_base_dir())
        self.interval = interval_seconds
        self._log_path = (
            Path(log_file) if log_file else self.config.base_dir / "strata.log"
        )
        self._pid_path = (
            Path(pid_file) if pid_file else self.config.base_dir / "strata.pid"
        )
        self.dry_run_first = dry_run_first
        self._running = False
        self._cycle_count = 0
        self._strata: Optional[Strata] = None
        self._logger: Optional[logging.Logger] = None

    def start(self):
        """Start the daemon loop. Blocks until interrupted."""
        self._setup_logging()
        self._write_pid()
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except ValueError:
            pass

        self._running = True
        self._strata = Strata(self.config)
        self._strata.s1.ensure_dirs()
        self._strata.s3.ensure_dirs()

        self._log(
            "info",
            f"Strata daemon started (interval={self.interval}s, pid={os.getpid()})",
        )
        self._log("info", f"  Base dir:   {self.config.base_dir.resolve()}")
        self._log("info", f"  Active:     {self.config.active_path().resolve()}")
        self._log("info", f"  Cooled:     {self.config.cooled_path().resolve()}")
        self._log("info", f"  Decay:      {self.config.decay_thresholds}")
        self._log(
            "info",
            f"  LRU:        {self.config.lru_days}d / {self.config.lru_min_access_count} accesses",
        )

        first_cycle = True
        while self._running:
            dry_run = self.dry_run_first and first_cycle
            self._run_cycle(dry_run=dry_run)
            first_cycle = False
            self._cycle_count += 1

            if self._running:
                self._log("debug", f"Sleeping {self.interval}s until next cycle...")
                for _ in range(self.interval):
                    if not self._running:
                        break
                    time.sleep(1)

        self._cleanup()

    def run_once(self, dry_run: bool = False) -> dict:
        """Execute a single maintenance cycle without starting the loop."""
        if self._logger is None:
            self._setup_logging()
        self._strata = Strata(self.config)
        self._strata.s1.ensure_dirs()
        self._strata.s3.ensure_dirs()
        result = self._run_cycle(dry_run=dry_run)
        self._strata.close()
        return result

    def stop(self):
        """Signal the daemon to stop gracefully."""
        self._running = False

    def _run_cycle(self, dry_run: bool = False) -> dict:
        label = "DRY RUN" if dry_run else "LIVE"
        self._log(
            "info", f"[Cycle {self._cycle_count + 1}] Starting maintenance ({label})"
        )

        try:
            result = self._strata.run_maintenance(dry_run=dry_run)
            distilled = result.get("distilled", {})
            migrated = result.get("total_migrated", len(result.get("migrated", [])))
            evicted = result.get("total_evicted", len(result.get("evicted", [])))

            distill_status = distilled.get("status", "skipped")
            distill_count = distilled.get("processed", 0)
            if distill_status == "ok":
                facts = distilled.get("facts_written", 0)
                self._log(
                    "info",
                    f"[Cycle {self._cycle_count + 1}] Distilled: {distill_count} conversations ({facts} facts written)",
                )
            elif distill_status == "dry_run" and distilled.get("would_process", 0) > 0:
                self._log(
                    "info",
                    f"[Cycle {self._cycle_count + 1}] Would distill: {distilled['would_process']} conversations",
                )

            self._log(
                "info",
                f"[Cycle {self._cycle_count + 1}] Migrated: {migrated}, Evicted: {evicted}",
            )

            if dry_run and (migrated > 0 or evicted > 0):
                details = []
                for m in result.get("migrated", []):
                    details.append(f"  would migrate: {m.get('path', '?')}")
                for e in result.get("evicted", []):
                    details.append(f"  would evict:   {e.get('memory_id', '?')[:8]}")
                if details:
                    self._log("info", "Dry-run details:\n" + "\n".join(details))

            if not dry_run:
                self._log_cost_data(self._cycle_count + 1, migrated, evicted)

            return result
        except Exception as exc:
            self._log("error", f"[Cycle {self._cycle_count + 1}] Failed: {exc}")
            return {"error": str(exc)}

    def _log_cost_data(self, cycle_num: int, migrated: int, evicted: int) -> None:
        """Append a cost tracking line to strata_cost.log after a live cycle."""
        cost_log = self.config.base_dir / "strata_cost.log"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"CYCLE:{cycle_num}:{migrated}:{evicted}:{timestamp}\n"
        try:
            with open(cost_log, "a") as f:
                f.write(line)
        except OSError:
            self._log("warning", f"Could not write cost data to {cost_log}")

    def _setup_logging(self):
        if self._logger is not None:
            return
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("strata.daemon")
        logger.setLevel(logging.DEBUG)

        class _SafeFileHandler(logging.FileHandler):
            def emit(self, record):
                try:
                    super().emit(record)
                except Exception:
                    pass

        class _SafeStreamHandler(logging.StreamHandler):
            def emit(self, record):
                try:
                    super().emit(record)
                except Exception:
                    pass

        fh = _SafeFileHandler(str(self._log_path), encoding="utf-8")
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(fh)

        sh = _SafeStreamHandler(sys.stderr)
        sh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(sh)
        self._logger = logger

    def _log(self, level: str, message: str):
        if self._logger:
            getattr(self._logger, level, self._logger.info)(message)

    def _write_pid(self):
        self._pid_path.parent.mkdir(parents=True, exist_ok=True)
        self._pid_path.write_text(str(os.getpid()), encoding="utf-8")

    def _handle_signal(self, signum, frame):
        sig_name = signal.Signals(signum).name
        self._log("info", f"Received {sig_name}, shutting down gracefully...")
        self._running = False

    def _cleanup(self):
        if self._strata:
            try:
                self._strata.close()
            except Exception:
                pass
        if self._pid_path.exists():
            try:
                self._pid_path.unlink()
            except Exception:
                pass
        self._log("info", "Daemon stopped")


def get_daemon_status(config: StrataConfig) -> dict:
    """Check if a daemon is running and return status info."""
    pid_path = config.base_dir / "strata.pid"
    log_path = config.base_dir / "strata.log"
    status = {"running": False, "pid": None, "log_lines": [], "cycle_count": 0}

    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            status["running"] = True
            status["pid"] = pid
        except (OSError, ValueError):
            pid_path.unlink(missing_ok=True)

    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        status["log_lines"] = lines[-20:]
        status["cycle_count"] = sum(1 for l in lines if "Starting maintenance" in l)

    return status


def stop_daemon(config: StrataConfig) -> dict:
    """Stop a running daemon by sending SIGTERM to its PID."""
    pid_path = config.base_dir / "strata.pid"
    result = {"stopped": False, "pid": None, "message": ""}

    if not pid_path.exists():
        result["message"] = "No PID file found. Daemon is not running."
        return result

    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                break
        result["stopped"] = True
        result["pid"] = pid
        result["message"] = f"Daemon (pid={pid}) stopped."
        pid_path.unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        pid_path.unlink(missing_ok=True)
        result["message"] = f"Could not stop daemon: {exc}"

    return result
