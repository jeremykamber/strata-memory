"""QMD setup and configuration management.

Provides the :class:`QmdSetup` class for auto-installing QMD, configuring
LLM reranker providers, and migrating from legacy configuration formats.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from strata.config import StrataConfig

_SUPPORTED_RERANKERS = ["openai", "anthropic", "ollama", "local"]


class QmdSetup:
    """QMD lifecycle helpers: auto-install, reranker config, legacy migration.

    All methods are safe to call even when QMD is not installed — they
    return ``False`` or a status dict rather than raising.
    """

    def __init__(self, config: StrataConfig):
        """Initialize the QMD setup helper.

        Args:
            config: Active Strata configuration for path resolution.
        """
        self.config = config

    # ── Install ────────────────────────────────────────────────────────────

    def ensure_installed(self) -> bool:
        """Ensure the QMD CLI is available on the system.

        Returns ``True`` if ``qmd`` is already on ``PATH`` or was
        successfully installed via ``npx @tobilu/qmd`` (30-second
        timeout).  Prints a warning and returns ``False`` on failure.
        """
        if shutil.which("qmd") is not None:
            return True
        try:
            result = subprocess.run(
                ["npx", "@tobilu/qmd"],
                timeout=30,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            print(
                "⚠ QMD auto-install failed (npx not available or timed out).\n"
                "  Install manually: npm install -g @tobilu/qmd",
            )
            return False

        if result.returncode == 0:
            return True

        print(
            "⚠ QMD auto-install completed but returned a non-zero exit.\n"
            "  Install manually: npm install -g @tobilu/qmd",
        )
        return False

    # ── Reranker Configuration ─────────────────────────────────────────────

    def configure_reranker(self, provider: str) -> bool:
        """Set an LLM reranker provider for QMD hybrid search.

        Supported providers: ``openai``, ``anthropic``, ``ollama``, ``local``.

        Prints a cost/disclaimer warning before applying the change.
        Returns ``True`` on success, ``False`` if the provider is unsupported.
        """
        if provider not in _SUPPORTED_RERANKERS:
            print(
                f"Unsupported provider: {provider}. "
                f"Supported: {', '.join(_SUPPORTED_RERANKERS)}",
            )
            return False

        print(
            "⚠ LLM rerankers use API credits (cloud providers) or "
            "local compute (Ollama / local GGUF models).\n"
            "  Costs depend on query volume and model size.",
        )
        self.config.qmd_reranker = provider
        return True

    # ── Legacy Config Migration ────────────────────────────────────────────

    def migrate_from_old_config(self) -> dict:
        """Detect and document migration from legacy configuration.

        Reads ``.strata_config.json`` from the base directory and checks
        whether it uses the old ``qmd_enabled`` boolean style (``True`` /
        ``False``) instead of the current ``search_backend`` string.

        This is a *documentation-only* migration — the current config
        object already has the right values from :class:`StrataConfig`
        field defaults.  The method reports what *would* change.

        Returns a summary dict:

        ``{"migrated": False}``
            No old-style config found or already using ``search_backend``.

        ``{"migrated": True, "old_backend": ..., "new_backend": ..., "changes": [...]}``
            Old-style ``qmd_enabled`` was detected and mapped.
        """
        config_path = self.config.base_dir / ".strata_config.json"
        if not config_path.exists():
            return {"migrated": False}

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"migrated": False}

        if "search_backend" in data:
            return {"migrated": False}

        if "qmd_enabled" in data:
            old_val = data["qmd_enabled"]
            new_backend = "qmd" if old_val else "fts5"
            changes = [
                f"qmd_enabled={old_val!r} → search_backend={new_backend!r}",
            ]
            return {
                "migrated": True,
                "old_backend": "qmd_enabled",
                "new_backend": new_backend,
                "changes": changes,
            }

        return {"migrated": False}
