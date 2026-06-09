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

    Args:
        project_path: Optional explicit project path to check for
            local ``strata_data/``. Defaults to the current working
            directory.

    Returns:
        The resolved base directory path.
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
    """Configuration for a Strata memory system instance.

    Controls directory layout, decay thresholds for migration, LRU
    eviction parameters, file patterns, and QMD search backend settings.
    """

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
    lru_decay_thresholds: dict = field(default_factory=lambda: {"*": 90})

    active_file_patterns: list = field(default_factory=lambda: ["*.md", "*.txt", "*.json", "*.yaml", "*.yml"])

    qmd_enabled: bool = False
    qmd_collection_prefix: str = "strata_"
    search_backend: str = "qmd"
    qmd_reranker: Optional[str] = None
    qmd_reranker_warning_shown: bool = False

    def __post_init__(self):
        if isinstance(self.base_dir, str):
            self.base_dir = Path(self.base_dir)
        # Backward compat: if explicitly set, qmd_enabled maps to search_backend
        # The property setter handles this during __init__

    @property
    def qmd_enabled(self) -> bool:  # noqa: F811 — field for __init__ compat; property shadows at runtime
        """Whether QMD search is active. Derived from search_backend."""
        return self.search_backend == "qmd"

    @qmd_enabled.setter
    def qmd_enabled(self, value: bool) -> None:
        # Backward compat setter — maps old boolean to search_backend
        if value:
            self.search_backend = "qmd"

    def active_path(self) -> Path:
        """Return the resolved path to the 1st Stratum (active) directory."""
        return self.base_dir / self.active_dir

    def cooled_path(self) -> Path:
        """Return the resolved path to the 2nd Stratum (cooled) directory."""
        return self.base_dir / self.cooled_dir

    def stratum_3_archive_path(self) -> Path:
        """Return the resolved path to the 3rd Stratum archive directory."""
        return self.base_dir / self.stratum_3_archive

    def stratum_3_shadow_path(self) -> Path:
        """Return the resolved path to the 3rd Stratum shadow index database."""
        return self.base_dir / self.stratum_3_shadow_db

    def get_decay_days(self, path: str) -> int:
        """Return the decay threshold in days for the given path.

        Uses the first path component as a key into ``decay_thresholds``,
        falling back to the ``"*"`` default.

        Args:
            path: Relative file or directory path.

        Returns:
            Number of days before the file is considered stale.
        """
        rel = path.strip("/")
        parts = rel.split("/")
        if parts and parts[0] in self.decay_thresholds:
            return self.decay_thresholds[parts[0]]
        return self.decay_thresholds.get("*", 30)

    def get_lru_days(self, path: str) -> int:
        """LRU decay threshold for *path*; falls back to ``"*"`` then ``lru_days``."""
        rel = path.strip("/")
        parts = rel.split("/")
        if parts and parts[0] in self.lru_decay_thresholds:
            return self.lru_decay_thresholds[parts[0]]
        default = self.lru_decay_thresholds.get("*")
        return default if default is not None else self.lru_days

    def is_qmd_available(self) -> bool:
        """Check whether QMD search backend is currently enabled.

        Returns:
            ``True`` if ``search_backend`` is set to ``"qmd"``.
        """
        return self.search_backend == "qmd"
