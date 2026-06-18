"""Handle the ``index`` command: regenerate the 1st Stratum index.md."""

from __future__ import annotations

from strata import Strata
from strata.cli._config import load_config

name = "index"


def run(args: list[str]) -> None:
    """Regenerate the 1st Stratum index.md."""
    config = load_config()
    with Strata(config) as s:
        s.generate_index()
    idx = config.active_path() / "index.md"
    if idx.exists():
        print(f"Index regenerated: {idx.resolve()}")
        print(idx.read_text()[:300])
    else:
        print("No active files to index.")
