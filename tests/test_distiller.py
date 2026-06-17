"""Tests for the Distiller module (background LLM distillation)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


from strata.config import StrataConfig
from strata.distiller import Distiller


# ── Helpers ────────────────────────────────────────────────


def _make_config(base_dir: Path) -> StrataConfig:
    return StrataConfig(base_dir=base_dir)


def _make_pi_config(base_dir: Path, **overrides) -> dict:
    """Write a pi-config.json with the given LLM overrides."""
    cfg = {
        "llm": {
            "enabled": True,
            "provider": "openai",
            "model": "gpt-4o-mini",
            "apiKey": "sk-test-key",
            "temperature": 0.0,
            "maxTokens": 500,
        }
    }
    cfg["llm"].update(overrides)
    return cfg


def _write_pi_config(base_dir: Path, llm_cfg: dict) -> Path:
    path = base_dir / "pi-config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"llm": llm_cfg}, indent=2))
    return path


def _write_conversation(
    base_dir: Path, date_str: str, content: str, suffix: str = "test"
) -> Path:
    """Write a conversation transcript and return its path."""
    conv_dir = base_dir / "active" / "pi" / "conversations" / date_str
    conv_dir.mkdir(parents=True, exist_ok=True)
    path = conv_dir / f"20260617T143022-{suffix}.md"
    path.write_text(content)
    return path


def _count_facts(base_dir: Path) -> int:
    """Count fact files under active/pi/facts/."""
    facts_dir = base_dir / "active" / "pi" / "facts"
    if not facts_dir.exists():
        return 0
    count = 0
    for date_dir in facts_dir.iterdir():
        if date_dir.is_dir():
            count += sum(1 for f in date_dir.iterdir() if f.suffix == ".md")
    return count


# ── Tests ──────────────────────────────────────────────────


class TestDistillerConfig:
    """Tests for configuration loading and availability checks."""

    def test_check_available_no_config(self):
        """Distiller should not be available when pi-config.json is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            config = _make_config(Path(tmp))
            d = Distiller(config)
            assert d.check_available() is False

    def test_check_available_disabled(self):
        """Distiller should not be available when llm.enabled is false."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {
                "enabled": False,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "apiKey": "sk-test",
            }
            _write_pi_config(cfg_dir, llm_cfg)
            config = _make_config(cfg_dir)
            d = Distiller(config)
            assert d.check_available() is False

    def test_check_available_no_api_key(self):
        """Distiller should not be available when no API key is resolvable."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "apiKey": "",
            }
            _write_pi_config(cfg_dir, llm_cfg)
            config = _make_config(cfg_dir)
            d = Distiller(config)
            assert d.check_available() is False

    def test_check_available_valid(self):
        """Distiller should be available with a valid config and API key."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "apiKey": "sk-real-key",
            }
            _write_pi_config(cfg_dir, llm_cfg)
            config = _make_config(cfg_dir)
            d = Distiller(config)
            assert d.check_available() is True

    def test_api_key_env_var_resolution(self):
        """Distiller should resolve API keys from environment variables."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            # Reference an env var
            llm_cfg = {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "apiKey": "${STRATA_TEST_KEY}",
            }
            _write_pi_config(cfg_dir, llm_cfg)
            os.environ["STRATA_TEST_KEY"] = "resolved-key"
            try:
                config = _make_config(cfg_dir)
                d = Distiller(config)
                assert d.check_available() is True
            finally:
                os.environ.pop("STRATA_TEST_KEY", None)

    def test_malformed_config(self):
        """Distiller should handle malformed pi-config.json gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            bad_path = cfg_dir / "pi-config.json"
            bad_path.write_text("not valid json")
            config = _make_config(cfg_dir)
            d = Distiller(config)
            assert d.check_available() is False


class TestDistillerConversationScanning:
    """Tests for finding and tracking new conversations."""

    def test_get_pending_count_no_conversations(self):
        """No conversations should mean zero pending."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            config = _make_config(cfg_dir)
            d = Distiller(config)
            assert d.get_pending_count() == 0

    def test_get_pending_count_with_undistilled(self):
        """New conversations should appear as pending."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            _write_conversation(
                cfg_dir, "2026-06-17", "# Hello\nSample transcript content."
            )
            config = _make_config(cfg_dir)
            d = Distiller(config)
            assert d.get_pending_count() == 1

    def test_get_pending_count_after_distill(self):
        """Conversations marked as distilled should not appear as pending."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            conv_path = _write_conversation(cfg_dir, "2026-06-17", "# Hello")

            config = _make_config(cfg_dir)
            d = Distiller(config)

            # Manually mark as distilled
            state_path = cfg_dir / "active" / "pi" / "distill_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            rel = str(conv_path.relative_to(cfg_dir / "active"))
            state_path.write_text(
                json.dumps(
                    {
                        "conversations": {rel: {"distilled_at": "2026-06-17T14:30:00"}},
                        "last_checked": "2026-06-17T14:30:00",
                    }
                )
            )

            assert d.get_pending_count() == 0

    def test_corrupted_distill_state(self):
        """Corrupted distill_state.json should reprocess from scratch."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            _write_conversation(cfg_dir, "2026-06-17", "# Hello")

            # Write corrupted state
            state_path = cfg_dir / "active" / "pi" / "distill_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text("{invalid json")

            config = _make_config(cfg_dir)
            d = Distiller(config)
            assert d.get_pending_count() == 1

    def test_non_md_files_ignored(self):
        """Non-markdown files in conversations/ should be ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)

            conv_dir = cfg_dir / "active" / "pi" / "conversations" / "2026-06-17"
            conv_dir.mkdir(parents=True, exist_ok=True)
            (conv_dir / "note.txt").write_text("not a conversation")

            config = _make_config(cfg_dir)
            d = Distiller(config)
            assert d.get_pending_count() == 0


class TestDistillerProcess:
    """Tests for the process() method."""

    def test_process_no_config(self):
        """process() should skip when config is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            config = _make_config(Path(tmp))
            d = Distiller(config)
            result = d.process()
            assert result["status"] == "skipped"
            assert "llm_not_configured" in result["reason"]

    def test_process_dry_run(self):
        """Dry run should report count without calling the LLM."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            _write_conversation(cfg_dir, "2026-06-17", "# Hello")
            config = _make_config(cfg_dir)
            d = Distiller(config)
            result = d.process(dry_run=True)
            assert result["status"] == "dry_run"
            assert result["would_process"] == 1

            # State should not be modified after dry run
            assert d.get_pending_count() == 1

    def test_process_no_new_conversations(self):
        """Process should skip when all conversations are already distilled."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            config = _make_config(cfg_dir)
            d = Distiller(config)
            result = d.process()
            assert result["status"] == "skipped"
            assert "no_new_conversations" in result["reason"]

    def test_fact_file_written(self, monkeypatch):
        """Process should write a fact file on successful LLM response."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            _write_conversation(cfg_dir, "2026-06-17", "# Test conversation")

            config = _make_config(cfg_dir)
            d = Distiller(config)

            # Mock the LLM call to return a known result
            def mock_call(transcripts):
                return {
                    "content": "- [reference] Test fact: This is a test fact extracted from the transcript."
                }

            monkeypatch.setattr(d, "_call_llm", mock_call)

            result = d.process()
            assert result["status"] == "ok"
            assert result["processed"] == 1
            assert result["facts_written"] == 1
            assert _count_facts(cfg_dir) == 1

            # Conversation should be marked as distilled
            assert d.get_pending_count() == 0

    def test_no_facts_to_extract(self, monkeypatch):
        """When LLM returns 'No significant facts', no fact file is written."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            _write_conversation(cfg_dir, "2026-06-17", "# Trivial content")

            config = _make_config(cfg_dir)
            d = Distiller(config)

            def mock_call(transcripts):
                return {"content": "No significant facts to extract."}

            monkeypatch.setattr(d, "_call_llm", mock_call)

            result = d.process()
            assert result["status"] == "no_facts_extracted"
            assert result["processed"] == 1
            assert result["facts_written"] == 0
            assert _count_facts(cfg_dir) == 0

            # Conversations should still be marked as distilled
            assert d.get_pending_count() == 0

    def test_api_error_leaves_state_unmodified(self, monkeypatch):
        """On API error, conversations should NOT be marked as distilled."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            _write_conversation(cfg_dir, "2026-06-17", "# Test")

            config = _make_config(cfg_dir)
            d = Distiller(config)

            def mock_call(transcripts):
                return {"error": "http_error: 500 Server Error"}

            monkeypatch.setattr(d, "_call_llm", mock_call)

            result = d.process()
            assert result["status"] == "error"
            assert result["processed"] == 0

            # Conversation should NOT be marked as distilled
            assert d.get_pending_count() == 1

    def test_multiple_conv_in_batch(self, monkeypatch):
        """Multiple undistilled conversations should be processed in one batch."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {"enabled": True, "provider": "openai", "apiKey": "sk-test"}
            _write_pi_config(cfg_dir, llm_cfg)
            _write_conversation(
                cfg_dir, "2026-06-17", "# First conversation", suffix="first"
            )
            _write_conversation(
                cfg_dir, "2026-06-17", "# Second conversation", suffix="second"
            )

            config = _make_config(cfg_dir)
            d = Distiller(config)

            call_count = 0

            def mock_call(transcripts):
                nonlocal call_count
                call_count += 1
                assert len(transcripts) == 2  # Both sent in one batch
                return {
                    "content": "- [reference] Batch fact: Extracted from two transcripts."
                }

            monkeypatch.setattr(d, "_call_llm", mock_call)

            result = d.process()
            assert result["status"] == "ok"
            assert result["processed"] == 2
            assert result["facts_written"] == 1
            assert call_count == 1
            assert d.get_pending_count() == 0


class TestDistillerProviderRouting:
    """Tests for LLM provider routing."""

    def test_unsupported_provider(self):
        """Unsupported provider should return error gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {
                "enabled": True,
                "provider": "nonexistent",
                "model": "foo",
                "apiKey": "sk-test",
            }
            _write_pi_config(cfg_dir, llm_cfg)
            _write_conversation(cfg_dir, "2026-06-17", "# Test")

            config = _make_config(cfg_dir)
            d = Distiller(config)
            result = d.process()
            assert result["status"] == "error"
            assert "unsupported_provider" in result["reason"]

    def test_provider_model_default(self):
        """Provider-specific default model should apply when model is not set."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            llm_cfg = {
                "enabled": True,
                "provider": "anthropic",
                "model": "",
                "apiKey": "sk-test",
            }
            _write_pi_config(cfg_dir, llm_cfg)
            config = _make_config(cfg_dir)
            d = Distiller(config)
            cfg = d._load_config()
            assert cfg is not None
            assert cfg["provider"] == "anthropic"
            # Should fall back to provider default
            assert cfg["model"] == "claude-3-5-haiku-latest"
