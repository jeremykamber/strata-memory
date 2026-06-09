"""Tests for CostTracker and the `strata cost` CLI command."""

from pathlib import Path

from strata.config import StrataConfig
from strata.tracking import CostTracker
from strata.cli import main


def test_cost_tracker_empty(tmp_base):
    """CostTracker with no daemon log returns error and zero-value keys."""
    config = StrataConfig(base_dir=tmp_base)
    tracker = CostTracker(config)
    result = tracker.get_summary()

    assert "error" in result
    assert "No daemon activity yet" in result["error"]
    assert result["daemon_cycles"]["value"] == 0
    assert result["files_migrated"]["value"] == 0
    assert result["files_evicted"]["value"] == 0
    assert result["tokens_saved_estimate"]["value"] == 0
    assert result["tokens_saved_range"]["value"] == "0 - 0"


def test_cost_tracker_with_data(tmp_base):
    """Synthetic daemon log: verify migrated/evicted counts and token calculation."""
    log_path = tmp_base / "strata.log"
    log_path.write_text(
        "2026-01-15 [Cycle 1] Starting maintenance (LIVE)\n"
        "2026-01-15 [Cycle 1] Migrated: 5, Evicted: 2\n"
    )

    config = StrataConfig(base_dir=tmp_base)
    tracker = CostTracker(config)
    result = tracker.get_summary()

    assert result["daemon_cycles"]["value"] == 1
    assert result["files_migrated"]["value"] == 5
    assert result["files_evicted"]["value"] == 2
    assert result["lru_decisions"]["value"] == 2
    assert result["tokens_saved_estimate"]["value"] == 11000


def test_cost_tracker_ranges(tmp_base):
    """Verify tokens_saved_range has lower-upper format with ±20%."""
    log_path = tmp_base / "strata.log"
    log_path.write_text(
        "2026-01-15 [Cycle 1] Starting maintenance (LIVE)\n"
        "2026-01-15 [Cycle 1] Migrated: 10, Evicted: 4\n"
    )

    config = StrataConfig(base_dir=tmp_base)
    tracker = CostTracker(config)
    result = tracker.get_summary()

    range_val = result["tokens_saved_range"]["value"]
    assert isinstance(range_val, str)
    assert " - " in range_val
    parts = range_val.split(" - ")
    assert len(parts) == 2
    lower, upper = parts[0].strip(), parts[1].strip()
    assert "," in lower or lower.isdigit()
    assert "," in upper or upper.isdigit()
    assert int(lower.replace(",", "")) == 17600
    assert int(upper.replace(",", "")) == 26400


def test_cost_tracker_disclaimer(tmp_base):
    """Every sub-dict in the result contains a disclaimer with 'approximate'."""
    log_path = tmp_base / "strata.log"
    log_path.write_text(
        "2026-01-15 [Cycle 1] Starting maintenance (LIVE)\n"
        "2026-01-15 [Cycle 1] Migrated: 3, Evicted: 1\n"
    )

    config = StrataConfig(base_dir=tmp_base)
    tracker = CostTracker(config)
    result = tracker.get_summary()

    assert "disclaimer" in result["tokens_saved_estimate"]
    disc = result["tokens_saved_estimate"]["disclaimer"]
    assert "approximate" in disc.lower()


def test_cost_tracker_multiple_cycles(tmp_base):
    """Synthetic log with 3+ cycles verifies accumulative counting."""
    log_path = tmp_base / "strata.log"
    log_path.write_text(
        "2026-01-15 [Cycle 1] Starting maintenance (LIVE)\n"
        "2026-01-15 [Cycle 1] Migrated: 5, Evicted: 2\n"
        "2026-01-15 [Cycle 2] Starting maintenance (LIVE)\n"
        "2026-01-15 [Cycle 2] Migrated: 3, Evicted: 1\n"
        "2026-01-15 [Cycle 3] Starting maintenance (LIVE)\n"
        "2026-01-15 [Cycle 3] Migrated: 0, Evicted: 0\n"
    )

    config = StrataConfig(base_dir=tmp_base)
    tracker = CostTracker(config)
    result = tracker.get_summary()

    assert result["daemon_cycles"]["value"] == 3
    assert result["files_migrated"]["value"] == 8
    assert result["files_evicted"]["value"] == 3
    assert result["tokens_saved_estimate"]["value"] == 17500
    assert "14,000 - 21,000" in result["tokens_saved_range"]["value"]


def test_cost_tracker_zero_values(tmp_base):
    """Synthetic log with 0 migrations/evictions yields zero token savings."""
    log_path = tmp_base / "strata.log"
    log_path.write_text(
        "2026-01-15 [Cycle 1] Starting maintenance (LIVE)\n"
        "2026-01-15 [Cycle 1] Migrated: 0, Evicted: 0\n"
    )

    config = StrataConfig(base_dir=tmp_base)
    tracker = CostTracker(config)
    result = tracker.get_summary()

    assert result["daemon_cycles"]["value"] == 1
    assert result["files_migrated"]["value"] == 0
    assert result["files_evicted"]["value"] == 0
    assert result["tokens_saved_estimate"]["value"] == 0
    assert result["tokens_saved_range"]["value"] == "0 - 0"


def test_cost_cli_command(tmp_base, monkeypatch, capsys):
    """Run `strata cost` via CLI main() and verify formatted output."""
    monkeypatch.setenv("STRATA_HOME", str(tmp_base))

    log_path = tmp_base / "strata.log"
    log_path.write_text(
        "2026-01-15 [Cycle 1] Starting maintenance (LIVE)\n"
        "2026-01-15 [Cycle 1] Migrated: 5, Evicted: 2\n"
    )

    main(["cost"])
    captured = capsys.readouterr()

    assert "Strata Cost Savings" in captured.out
    assert "Daemon cycles:" in captured.out
    assert "Files migrated:" in captured.out
    assert "Files evicted:" in captured.out
    assert "LRU decisions:" in captured.out
    assert "Tokens saved:" in captured.out
    assert "11,000 tokens" in captured.out
    assert "Savings range:" in captured.out
    assert "Methodology:" in captured.out
    assert "Disclaimer:" in captured.out
