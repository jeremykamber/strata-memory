"""CLI package for the Strata memory system.

The entry point ``strata.cli:main`` resolves through this module.
Command handlers live under ``strata/cli/commands/`` and are dispatched
via the registry.
"""

from __future__ import annotations

from strata._cli_main import main  # noqa: F401
