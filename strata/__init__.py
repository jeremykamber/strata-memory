"""
Strata: A Tiered Memory System for AI Agents.

Tiers:
    1st Stratum (Active Shell):    Filesystem-based markdown for active working context.
    2nd Stratum (Medium-Term):     Aged-out markdown files, still on disk.
    3rd Stratum (Cold Archive):    Flat-file storage with a lightweight Shadow Index.
"""

__version__ = "0.2.0"

from typing import Optional, List

from strata.config import StrataConfig, detect_base_dir
from strata.storage import Stratum1Storage, Stratum2Storage, Stratum3Storage, QmdWrapper
from strata.janitor import Janitor
from strata.query import QueryEngine
from strata.tools import StrataTools


class Strata:
    """Top-level API for Strata memory system. Coordinates all three tiers."""

    def __init__(self, config: Optional[StrataConfig] = None):
        """Initialize a Strata instance.

        Args:
            config: Configuration object. If ``None``, auto-detects the
                base directory and uses default settings.
        """
        if config is None:
            config = StrataConfig(base_dir=detect_base_dir())
        self.config = config
        self.s1 = Stratum1Storage(self.config)
        self.s2 = Stratum2Storage(self.config)
        self.s3 = Stratum3Storage(self.config)
        self.janitor = Janitor(self.s1, self.s2, self.s3, self.config)
        self.query_engine = QueryEngine(self.s1, self.s2, self.s3, self.config)
        self.qmd = QmdWrapper(self.config)
        self.tools = StrataTools(self)

    def read_active(self, path: str) -> str:
        """Read a file from the 1st Stratum (active memory).

        Args:
            path: Path relative to the active directory root.

        Returns:
            The full file contents as a string.

        Raises:
            FileNotFoundError: If the path does not exist.
            IsADirectoryError: If the path is a directory.
        """
        return self.s1.read(path)

    def write_active(self, path: str, content: str) -> str:
        """Write a file to the 1st Stratum (active memory).

        Creates parent directories as needed. Regenerates the index
        automatically after writing.

        Args:
            path: Path relative to the active directory root.
            content: File content to write.

        Returns:
            The absolute path to the written file.
        """
        return self.s1.write(path, content)

    def list_active(self, path: str = "") -> List[dict]:
        """List files and directories in the 1st Stratum.

        Args:
            path: Optional subdirectory path relative to active root.
                Defaults to the root.

        Returns:
            A list of dicts with keys: name, path, type, size, modified.
        """
        return self.s1.list_dir(path)

    def delete_active(self, path: str) -> bool:
        """Delete a file or directory from the 1st Stratum.

        Regenerates the index after deletion.

        Args:
            path: Path relative to the active directory root.

        Returns:
            ``True`` if the path was deleted, ``False`` if it did not
            exist.
        """
        return self.s1.delete(path)

    def list_cooled(self) -> List[dict]:
        """List all files in the 2nd Stratum (cooled memory).

        Returns:
            A list of dicts with keys: path, size, modified.
        """
        return self.s2.list_all()

    def generate_index(self):
        """Regenerate the 1st Stratum ``index.md`` master map."""
        self.s1.generate_index()

    def query(self, text: str, filters: Optional[dict] = None, top_k: int = 5) -> List[dict]:
        """Search across all three memory tiers.

        When QMD is available, uses hybrid BM25 + vector search.
        Falls back to filesystem grep and FTS5 shadow index search.

        Args:
            text: Natural language search query.
            filters: Optional dict with filter keys (e.g. ``tags``).
            top_k: Maximum results to return (default: 5).

        Returns:
            A list of result dicts sorted by relevance score.
        """
        return self.query_engine.search(text, filters=filters, top_k=top_k)

    def query_tool_schema(self) -> dict:
        """Return the OpenAI-compatible schema for the ``strata_query`` tool.

        Returns:
            A function-calling schema dict.
        """
        return self.tools.query_schema()

    def migrate(self, dry_run: bool = False) -> list[dict]:
        """Move stale files from the 1st Stratum to the 2nd Stratum.

        Args:
            dry_run: If ``True``, preview which files would be migrated
                without moving them.

        Returns:
            A list of result dicts, one per migrated file.
        """
        return self.janitor.migrate_1_to_2(dry_run=dry_run)

    def evict(self, dry_run: bool = False) -> list[dict]:
        """Evict cold files from the 2nd Stratum to the 3rd Stratum.

        Args:
            dry_run: If ``True``, preview which files would be evicted
                without moving them.

        Returns:
            A list of result dicts, one per evicted file.
        """
        return self.janitor.evict_2_to_3(dry_run=dry_run)

    def run_maintenance(self, dry_run: bool = False) -> dict:
        """Run both migration and eviction in a single cycle.

        Args:
            dry_run: If ``True``, preview changes without applying them.

        Returns:
            A dict with ``migrated``, ``evicted``, ``total_migrated``,
            and ``total_evicted`` keys.
        """
        migrated = self.migrate(dry_run=dry_run)
        evicted = self.evict(dry_run=dry_run)
        return {"migrated": migrated, "evicted": evicted, "total_migrated": len(migrated), "total_evicted": len(evicted)}

    def close(self):
        """Release resources (closes the 3rd Stratum shadow index connection)."""
        self.s3.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
