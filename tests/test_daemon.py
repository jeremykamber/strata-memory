"""Tests for StrataDaemon."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from strata.config import StrataConfig
from strata.daemon import StrataDaemon, get_daemon_status


class TestStrataDaemon:

    def test_run_once(self, tmp_base):
        config = StrataConfig(
            base_dir=tmp_base,
            decay_thresholds={"*": 0},
            lru_days=30,
        )
        daemon = StrataDaemon(config=config)
        result = daemon.run_once(dry_run=True)
        assert "migrated" in result
        assert "evicted" in result

    def test_run_once_live(self, tmp_base):
        from strata.models import MemoryBlock
        config = StrataConfig(
            base_dir=tmp_base,
            decay_thresholds={"*": 0},
            lru_days=30,
        )
        daemon = StrataDaemon(config=config)

        from strata import Strata
        with Strata(config) as s:
            s.write_active("projects/test.md", "# Test Project\nSome content")
        result = daemon.run_once(dry_run=False)
        assert len(result.get("migrated", [])) >= 1

    def test_run_once_eviction(self, tmp_base):
        from strata import Strata
        from strata.models import MemoryBlock
        from datetime import datetime, timezone, timedelta

        config = StrataConfig(
            base_dir=tmp_base,
            decay_thresholds={"*": 100},
            lru_days=0,
            lru_min_access_count=0,
        )
        daemon = StrataDaemon(config=config)

        from strata.storage import Stratum2Storage
        s2 = Stratum2Storage(config)
        s2.ensure_dirs()
        s2.write("projects/old.md", "# Old evictable memory")

        result = daemon.run_once(dry_run=False)
        assert len(result.get("evicted", [])) >= 1

    def test_get_daemon_status_not_running(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        status = get_daemon_status(config)
        assert status["running"] is False
        assert status["pid"] is None

    def test_daemon_start_stop(self, tmp_base):
        config = StrataConfig(
            base_dir=tmp_base,
            decay_thresholds={"*": 100},
            lru_days=100,
        )
        daemon = StrataDaemon(
            config=config,
            interval_seconds=1,
            dry_run_first=False,
        )

        from threading import Thread
        t = Thread(target=daemon.start, daemon=True)
        t.start()

        time.sleep(0.5)

        status = get_daemon_status(config)
        assert status["running"] is True

        daemon.stop()
        t.join(timeout=3)
        assert not t.is_alive()

        status = get_daemon_status(config)
        assert status["running"] is False

    def test_daemon_logging(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        daemon = StrataDaemon(config=config, interval_seconds=1)
        daemon.run_once(dry_run=True)

        log_path = tmp_base / "strata.log"
        assert log_path.exists()
        content = log_path.read_text()
        assert "Starting maintenance" in content

    def test_daemon_dry_run_first(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        daemon = StrataDaemon(config=config, interval_seconds=3600)
        daemon.run_once(dry_run=True)
        log_path = tmp_base / "strata.log"
        assert log_path.exists()

    def test_config_path_detection(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        daemon = StrataDaemon(config=config)
        assert daemon._log_path == tmp_base / "strata.log"
        assert daemon._pid_path == tmp_base / "strata.pid"

    def test_custom_paths(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        daemon = StrataDaemon(
            config=config,
            log_file="/tmp/strata_test_custom.log",
            pid_file="/tmp/strata_test_custom.pid",
        )
        try:
            assert str(daemon._log_path) == "/tmp/strata_test_custom.log"
            assert str(daemon._pid_path) == "/tmp/strata_test_custom.pid"
        finally:
            Path("/tmp/strata_test_custom.log").unlink(missing_ok=True)
            Path("/tmp/strata_test_custom.pid").unlink(missing_ok=True)

    def test_run_once_logs_activity(self, tmp_base):
        from strata import Strata
        config = StrataConfig(
            base_dir=tmp_base,
            decay_thresholds={"*": 0},
        )
        daemon = StrataDaemon(config=config)

        with Strata(config) as s:
            s.write_active("projects/log_test.md", "# Log Test")

        result = daemon.run_once(dry_run=True)
        log_path = tmp_base / "strata.log"
        assert log_path.exists()
        log_content = log_path.read_text()
        assert "Cycle" in log_content

    def test_get_daemon_status_with_log(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)

        log_path = tmp_base / "strata.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("2026-01-01 [INFO] Starting maintenance (DRY RUN)\n")

        status = get_daemon_status(config)
        assert len(status["log_lines"]) >= 1
        assert status["cycle_count"] >= 1

    def test_get_daemon_status_stale_pid(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        pid_path = tmp_base / "strata.pid"
        pid_path.write_text("99999999")

        status = get_daemon_status(config)
        assert status["running"] is False
        assert not pid_path.exists()

    def test_get_daemon_status_invalid_pid(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        pid_path = tmp_base / "strata.pid"
        pid_path.write_text("not_a_number")

        status = get_daemon_status(config)
        assert status["running"] is False
        assert not pid_path.exists()

    def test_stop_daemon_not_running(self, tmp_base):
        from strata.daemon import stop_daemon
        config = StrataConfig(base_dir=tmp_base)
        result = stop_daemon(config)
        assert result["stopped"] is False
        assert "No PID file" in result["message"]

    def test_stop_daemon_stale_pid(self, tmp_base):
        from strata.daemon import stop_daemon
        config = StrataConfig(base_dir=tmp_base)
        pid_path = tmp_base / "strata.pid"
        pid_path.write_text("99999999")

        result = stop_daemon(config)
        assert result["stopped"] is False
        assert not pid_path.exists()
