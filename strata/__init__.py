"""
Strata: A Tiered Memory System for AI Agents.

Tiers:
    1st Stratum (Active Shell):    Filesystem-based markdown for active working context.
    2nd Stratum (Medium-Term):     Aged-out markdown files, still on disk.
    3rd Stratum (Cold Archive):    Flat-file storage with a lightweight Shadow Index.
"""

from __future__ import annotations

__version__ = "0.3.0b1"

from strata.config import StrataConfig, detect_base_dir
from strata.distiller import Distiller
from strata.storage import Stratum1Storage, Stratum2Storage, Stratum3Storage, QmdWrapper
from strata.janitor import Janitor
from strata.query import QueryEngine
from strata.tools import StrataTools


class Strata:
    """Top-level API for Strata memory system. Coordinates all three tiers."""

    def __init__(self, config: StrataConfig | None = None):
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
        self.distiller = Distiller(self.config)
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

    def read(self, path: str) -> dict:
        """Read a file from any stratum, cascading active -> cooled -> archive.

        When a file is read from the 2nd Stratum (cooled), its access is
        tracked. If the access count reaches the promotion threshold, the
        file is automatically moved back to the 1st Stratum (active).

        When a file is read from the 3rd Stratum (archive), it is
        automatically rehydrated back to the 1st Stratum so the agent can
        work with it directly.

        Args:
            path: Path relative to the target stratum root.

        Returns:
            A dict with:
            - ``content``: The full file contents.
            - ``source``: ``"active"``, ``"cooled"``, or ``"archive"``.
            - ``promoted``: ``True`` if the file was auto-promoted from cooled.
            - ``rehydrated``: ``True`` if the file was auto-restored from archive.
            - ``access_count``: Current access count (cooled reads only).

        Raises:
            FileNotFoundError: If the path does not exist in any stratum.
        """
        # 1st Stratum — fast path, no tracking needed
        try:
            content = self.s1.read(path)
            return {"content": content, "source": "active"}
        except FileNotFoundError:
            pass

        # 2nd Stratum — track access, auto-promote on threshold
        try:
            content = self.s2.read(path)
            entry = self.s2.track_access(path)
            count = entry.get("access_count", 0)
            threshold = self.config.promotion_threshold
            if count >= threshold:
                # Promote: copy to active, remove from cooled
                target = self.s1._root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                source = self.s2._root / path
                source.unlink()
                self.s2.remove_access_tracking(path)
                self.s1.generate_index()
                return {
                    "content": content,
                    "source": "cooled",
                    "promoted": True,
                    "access_count": count,
                }
            return {
                "content": content,
                "source": "cooled",
                "promoted": False,
                "access_count": count,
            }
        except FileNotFoundError:
            pass

        # 3rd Stratum — find in shadow index, rehydrate to active
        try:
            conn = self.s3._connect_shadow()
            row = conn.execute(
                "SELECT * FROM shadow_index WHERE original_path = ?",
                (path,),
            ).fetchone()
            if row:
                entry = dict(row)
                data = self.janitor.rehydrate(entry, target_tier="active")
                if data:
                    return {
                        "content": data.get("content", ""),
                        "source": "archive",
                        "rehydrated": True,
                    }
        except Exception:
            pass

        raise FileNotFoundError(f"File not found in any stratum: {path}")

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

    def list_active(self, path: str = "") -> list[dict]:
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

    def list_cooled(self) -> list[dict]:
        """List all files in the 2nd Stratum (cooled memory).

        Returns:
            A list of dicts with keys: path, size, modified.
        """
        return self.s2.list_all()

    def generate_index(self):
        """Regenerate the 1st Stratum ``index.md`` master map."""
        self.s1.generate_index()

    def query(
        self, text: str, filters: dict | None = None, top_k: int = 5
    ) -> list[dict]:
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

    def promote(self, dry_run: bool = False) -> list[dict]:
        """Promote frequently-accessed cooled files back to the 1st Stratum.

        Args:
            dry_run: If ``True``, preview promotions without moving.

        Returns:
            A list of result dicts, one per promoted file.
        """
        return self.janitor.promote_2_to_1(dry_run=dry_run)

    def rehydrate(self, shadow_entry: dict, target_tier: str = "active") -> dict | None:
        """Restore an archived file to the 1st or 2nd Stratum.

        Args:
            shadow_entry: A dict from the shadow index with ``id`` and
                ``archive_path``.
            target_tier: ``"active"`` (1st, default) or ``"cooled"`` (2nd).

        Returns:
            The rehydrated data dict, or ``None`` if the archive file
            could not be read.
        """
        return self.janitor.rehydrate(shadow_entry, target_tier=target_tier)

    def run_maintenance(self, dry_run: bool = False) -> dict:
        """Run the full lifecycle cycle: distill, promote, migrate, then evict.

        Executes in order:
        1. Distill: extract facts from new conversation transcripts (daemon only)
        2. Promote: move heavily-accessed cooled files back to active
        3. Migrate: move stale active files to cooled
        4. Evict:  move old cooled files to archive

        Distill runs first so conversation transcripts are processed
        before they could be promoted or migrated to cooled/.

        Args:
            dry_run: If ``True``, preview changes without applying them.

        Returns:
            A dict with ``distilled``, ``promoted``, ``migrated``,
            ``evicted`` arrays and totals.
        """
        distilled = self.distiller.process(dry_run=dry_run)
        promoted = self.promote(dry_run=dry_run)
        migrated = self.migrate(dry_run=dry_run)
        evicted = self.evict(dry_run=dry_run)
        return {
            "distilled": distilled,
            "promoted": promoted,
            "migrated": migrated,
            "evicted": evicted,
            "total_promoted": len(promoted),
            "total_migrated": len(migrated),
            "total_evicted": len(evicted),
        }

    def close(self):
        """Release resources (closes the 3rd Stratum shadow index connection)."""
        self.s3.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
