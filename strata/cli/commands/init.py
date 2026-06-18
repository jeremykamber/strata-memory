"""Initialize directory structure for the Strata memory system."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from strata import Strata
from strata.cli._config import save_strata_config
from strata.config import StrataConfig

name = "init"


def run(args: list[str]) -> None:
    """Handle the ``init`` command: create directory structure.

    Resolution order for the base directory:
    1. ``$STRATA_HOME`` environment variable (always wins)
    2. ``--global`` / ``-g`` flag sets ``~/.strata/``
    3. ``--local`` / ``-l`` flag or default sets ``./strata_data/``

    If not ``--non-interactive``, runs QMD search backend onboarding.

    Args:
        args: Remaining command-line arguments after ``init``.
    """
    explicit = args or []
    non_interactive = "--non-interactive" in explicit
    env_home = os.environ.get("STRATA_HOME")
    if env_home:
        base_dir = Path(env_home)
    elif "--global" in explicit or "-g" in explicit:
        base_dir = Path.home() / ".strata"
    elif "--local" in explicit or "-l" in explicit:
        base_dir = Path("./strata_data")
    else:
        base_dir = Path("./strata_data")
    config = StrataConfig(base_dir=base_dir)
    with Strata(config) as s:
        s.s1.ensure_dirs()
        s.s2.ensure_dirs()
        s.s3.ensure_dirs()
    kind = "global" if base_dir == Path.home() / ".strata" else "local"

    if not non_interactive:
        # ── QMD search backend onboarding (inlined from _qmd_onboarding) ──
        print()
        print("Select search backend:")
        print("  1) QMD with hybrid search (recommended) — uses BM25 + vector search")
        print("  2) QMD with LLM rerankers — better results, uses API credits")
        print("  3) FTS5 keyword search only — no external dependencies")
        if sys.stdin.isatty():
            try:
                choice = input("Choice [1/2/3]: ").strip()
            except (EOFError, OSError):
                choice = ""
        else:
            choice = ""
        if choice == "1":
            # Inlined from _try_install_qmd
            print("  Installing QMD (this may take a moment)...")
            try:
                result = subprocess.run(
                    ["npx", "@tobilu/qmd"],
                    timeout=30,
                    capture_output=True,
                )
                if result.returncode == 0:
                    print("  ✓ QMD ready")
                else:
                    print("  ⚠ QMD install failed. Install manually:")
                    print("    npm install -g @tobilu/qmd")
                    config.search_backend = "fts5"
            except subprocess.TimeoutExpired:
                print("  ⚠ QMD install timed out after 30s. Install manually:")
                print("    npm install -g @tobilu/qmd")
                config.search_backend = "fts5"
            except FileNotFoundError:
                print("  ⚠ npx not found. Install manually:")
                print("    npm install -g @tobilu/qmd")
                config.search_backend = "fts5"
        elif choice == "2":
            # Inlined from _try_install_qmd
            print("  Installing QMD (this may take a moment)...")
            try:
                result = subprocess.run(
                    ["npx", "@tobilu/qmd"],
                    timeout=30,
                    capture_output=True,
                )
                if result.returncode == 0:
                    print("  ✓ QMD ready")
                else:
                    print("  ⚠ QMD install failed. Install manually:")
                    print("    npm install -g @tobilu/qmd")
                    config.search_backend = "fts5"
            except subprocess.TimeoutExpired:
                print("  ⚠ QMD install timed out after 30s. Install manually:")
                print("    npm install -g @tobilu/qmd")
                config.search_backend = "fts5"
            except FileNotFoundError:
                print("  ⚠ npx not found. Install manually:")
                print("    npm install -g @tobilu/qmd")
                config.search_backend = "fts5"
            if config.search_backend == "qmd":
                # Inlined from _qmd_reranker_prompt
                try:
                    print(
                        "LLM reranker provider URL (e.g., openai://gpt-4o-mini, ollama://llama3):"
                    )
                    reranker = input().strip()
                    if reranker:
                        config.qmd_reranker = reranker
                    print("LLM rerankers will use API credits or local compute")
                except (EOFError, OSError):
                    pass
        else:
            config.search_backend = "fts5"

    save_strata_config(config)

    # ── Post-init onboarding guide ──────────────────────────────────────────
    print()
    print(f"✓ Initialized {kind} Strata at {config.base_dir.resolve()}")
    print()
    print("  Next steps:")
    print()
    print("  1. Write your first memory:")
    print('     strata add hello.md "# Hello from Strata"')
    print()
    print("  2. Search across all three tiers:")
    print('     strata search "hello"')
    print()
    print("  3. Start the Janitor daemon for automatic memory lifecycle:")
    print("     strata serve          # foreground (Ctrl+C to stop)")
    print("     strata serve &        # background process")
    print("     strata install-service  # systemd service (persistent)")
    print()
    print("  4. Install the agent skill (for AI coding assistants):")
    print("     strata skill install --global")
    print()
    print("  Commands at a glance: strata --help")
