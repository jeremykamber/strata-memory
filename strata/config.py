import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def detect_base_dir(project_path: Optional[Path] = None) -> Path:
    """Auto-detect the best base directory for Strata.

    Resolution order:
    1. STRATA_HOME environment variable (always wins)
    2. ./strata_data/ in the current/project directory (project-local)
    3. ~/.strata/ (global fallback)
    """
    env = os.environ.get("STRATA_HOME")
    if env:
        return Path(env)

    cwd = project_path or Path.cwd()
    local = cwd / "strata_data"
    if local.exists():
        return local

    return Path.home() / ".strata"


@dataclass
class StrataConfig:

    base_dir: Path = Path("./strata_data")
    active_dir: str = "active"
    cooled_dir: str = "cooled"
    stratum_3_archive: str = "archive"
    stratum_3_shadow_db: str = "stratum_3_shadow.db"

    decay_thresholds: dict = field(default_factory=lambda: {
        "projects": 14,
        "entities": 60,
        "gtd": 7,
        "*": 30,
    })

    lru_days: int = 90
    lru_min_access_count: int = 1

    active_file_patterns: list = field(default_factory=lambda: ["*.md", "*.txt", "*.json", "*.yaml", "*.yml"])

    qmd_enabled: bool = False
    qmd_collection_prefix: str = "strata_"

    def __post_init__(self):
        if isinstance(self.base_dir, str):
            self.base_dir = Path(self.base_dir)

    def active_path(self) -> Path:
        return self.base_dir / self.active_dir

    def cooled_path(self) -> Path:
        return self.base_dir / self.cooled_dir

    def stratum_3_archive_path(self) -> Path:
        return self.base_dir / self.stratum_3_archive

    def stratum_3_shadow_path(self) -> Path:
        return self.base_dir / self.stratum_3_shadow_db

    def get_decay_days(self, path: str) -> int:
        rel = path.strip("/")
        parts = rel.split("/")
        if parts and parts[0] in self.decay_thresholds:
            return self.decay_thresholds[parts[0]]
        return self.decay_thresholds.get("*", 30)
