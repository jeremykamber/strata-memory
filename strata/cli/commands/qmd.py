"""``qmd`` command group: QMD hybrid search integration.

Subcommands:
  qmd-setup   Configure QMD collections for all Strata directories
  qmd-embed   Generate QMD vector embeddings
  qmd-status  Show QMD index status
"""

from __future__ import annotations

import sys

from strata.cli._config import load_config


name = "qmd"


def _cmd_qmd_setup() -> None:
    """Configure QMD collections for all Strata directories."""
    config = load_config()
    from strata.storage import QmdWrapper

    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed. Install it with: npm install -g @tobilu/qmd")
        return
    results = qmd.setup_collections()
    for r in results:
        print(f"  [{r['status']}] {r['name']}: {r.get('path', '')}")
    print("\nRun 'strata qmd-embed' to generate vector embeddings.")


def _cmd_qmd_embed() -> None:
    """Generate QMD vector embeddings."""
    config = load_config()
    from strata.storage import QmdWrapper

    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed. Install it with: npm install -g @tobilu/qmd")
        return
    print("Generating embeddings (may take a while on first run)...")
    result = qmd.embed(force=False)
    print(result.get("output", "Done."))


def _cmd_qmd_status() -> None:
    """Show QMD index status."""
    config = load_config()
    from strata.storage import QmdWrapper

    qmd = QmdWrapper(config)
    if not qmd.check_available():
        print("QMD is not installed.")
        return
    result = qmd.get_status()
    print(result.get("output", "Unknown status."))


def run(args: list[str]) -> None:
    """Dispatch to the appropriate QMD subcommand.

    Args:
        args: Remaining arguments after ``qmd``. The first element
              should be ``setup``, ``embed``, or ``status``.
    """
    if not args:
        print("Usage: strata qmd-setup|qmd-embed|qmd-status")
        print("")
        print("  qmd-setup   Configure QMD collections")
        print("  qmd-embed   Generate QMD vector embeddings")
        print("  qmd-status  Show QMD index status")
        return

    sub = args[0]

    if sub == "setup":
        _cmd_qmd_setup()
    elif sub == "embed":
        _cmd_qmd_embed()
    elif sub == "status":
        _cmd_qmd_status()
    else:
        print(f"Unknown qmd subcommand: {sub}", file=sys.stderr)
        print("Usage: strata qmd-setup|qmd-embed|qmd-status", file=sys.stderr)
        sys.exit(1)
