import json
import shutil
import subprocess

from strata.config import StrataConfig
from strata.qmd_setup import QmdSetup


class TestQmdSetup:

    def test_qmd_setup_ensure_installed_already_available(self, tmp_base, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/qmd")
        config = StrataConfig(base_dir=tmp_base)
        qmd = QmdSetup(config)
        assert qmd.ensure_installed() is True

    def test_qmd_setup_ensure_installed_no_npx(self, tmp_base, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda x: None)

        def _raise_not_found(*args, **kwargs):
            raise FileNotFoundError("npx not found")

        monkeypatch.setattr(subprocess, "run", _raise_not_found)
        config = StrataConfig(base_dir=tmp_base)
        qmd = QmdSetup(config)
        assert qmd.ensure_installed() is False

    def test_qmd_setup_ensure_installed_npx_fails(self, tmp_base, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda x: None)
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(args[0], returncode=1),
        )
        config = StrataConfig(base_dir=tmp_base)
        qmd = QmdSetup(config)
        assert qmd.ensure_installed() is False

    def test_qmd_setup_ensure_installed_success(self, tmp_base, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda x: None)
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(args[0], returncode=0),
        )
        config = StrataConfig(base_dir=tmp_base)
        qmd = QmdSetup(config)
        assert qmd.ensure_installed() is True

    def test_qmd_setup_configure_reranker_valid(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        qmd = QmdSetup(config)
        assert qmd.configure_reranker("openai") is True
        assert config.qmd_reranker == "openai"

    def test_qmd_setup_configure_reranker_invalid(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        qmd = QmdSetup(config)
        assert qmd.configure_reranker("bogus") is False

    def test_qmd_setup_migrate_old_config(self, tmp_base):
        config_path = tmp_base / ".strata_config.json"
        config_path.write_text(json.dumps({"qmd_enabled": True}))
        config = StrataConfig(base_dir=tmp_base)
        qmd = QmdSetup(config)
        result = qmd.migrate_from_old_config()
        assert result["migrated"] is True
        assert result["old_backend"] == "qmd_enabled"
        assert result["new_backend"] == "qmd"
        assert "qmd_enabled=True" in result["changes"][0]
