from __future__ import annotations

import shutil
import time

from strata.config import StrataConfig
from strata.storage import Stratum1Storage, Stratum2Storage, Stratum3Storage


class Janitor:
    """Lifecycle management for Strata memory tiers.

    The Janitor moves markdown files between strata based on age and
    access patterns. No LLM calls, no compression — files stay as files.
    """

    def __init__(
        self,
        stratum_1: Stratum1Storage,
        stratum_2: Stratum2Storage,
        stratum_3: Stratum3Storage,
        config: StrataConfig,
    ):
        """Initialize the Janitor with storage backends and configuration.

        Args:
            stratum_1: The 1st Stratum (active) storage backend.
            stratum_2: The 2nd Stratum (cooled) storage backend.
            stratum_3: The 3rd Stratum (archive) storage backend.
            config: Strata configuration with decay and LRU thresholds.
        """
        self.s1 = stratum_1
        self.s2 = stratum_2
        self.s3 = stratum_3
        self.config = config

    def migrate_1_to_2(self, dry_run: bool = False) -> list[dict]:
        """Move stale files from the 1st Stratum (active) to the 2nd (cooled).

        Args:
            dry_run: If ``True``, preview which files would be migrated
                without moving them.

        Returns:
            A list of result dicts with keys: path, status, age_days
            (and error on failure).
        """
        stale = self.s1.scan_stale_files()
        results = []
        for entry in stale:
            rel_path = entry["path"]
            source = self.s1._root / rel_path
            target = self.s2._root / rel_path

            if dry_run:
                results.append(
                    {
                        "path": rel_path,
                        "status": "would_migrate",
                        "age_days": entry["age_days"],
                    }
                )
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(source), str(target))
                source.unlink()
                self.s2.init_access_tracking(rel_path)
                results.append(
                    {
                        "path": rel_path,
                        "status": "migrated",
                        "age_days": entry["age_days"],
                    }
                )
            except Exception as exc:
                results.append({"path": rel_path, "status": "error", "error": str(exc)})

        if results:
            self.s1.generate_index()
        return results

    def evict_2_to_3(self, dry_run: bool = False) -> list[dict]:
        """Evict old files from the 2nd Stratum (cooled) to the 3rd (archive).

        Args:
            dry_run: If ``True``, preview which files would be evicted
                without moving them.

        Returns:
            A list of result dicts with keys: path, status, age_days,
            archive_path (and error on failure).
        """
        candidates = self._get_lru_candidates()
        results = []
        for entry in candidates:
            rel_path = entry["path"]
            source = self.s2._root / rel_path

            if dry_run:
                results.append(
                    {
                        "path": rel_path,
                        "status": "would_evict",
                        "age_days": entry["age_days"],
                    }
                )
                continue

            try:
                tags = self._infer_tags(rel_path)
                archive_path = self.s3.archive_file(source, rel_path, tags=tags)
                source.unlink()
                self.s2.remove_access_tracking(rel_path)
                results.append(
                    {
                        "path": rel_path,
                        "status": "evicted",
                        "archive_path": archive_path,
                    }
                )
            except Exception as exc:
                results.append({"path": rel_path, "status": "error", "error": str(exc)})

        return results

    def promote_2_to_1(self, dry_run: bool = False) -> list[dict]:
        """Promote frequently-accessed cooled files back to active.

                Scans cooled files that have access tracking data. If a file's
                access count meets or exceeds ``promotion_threshold``, it gets
                moved back to the 1st Stratum (active) so the agent can
                read and write it directly again.

                Args:
                    dry_run: If ``True``, preview promotions without moving.

        n        Returns:
                    A list of result dicts with keys: path, status, access_count.
        """
        threshold = self.config.promotion_threshold
        access_data = self.s2._get_access_data()
        results = []

        for rel_path, entry in access_data.items():
            if entry.get("access_count", 0) < threshold:
                continue

            source = self.s2._root / rel_path
            if not source.exists():
                continue

            if dry_run:
                results.append(
                    {
                        "path": rel_path,
                        "status": "would_promote",
                        "access_count": entry["access_count"],
                        "threshold": threshold,
                    }
                )
                continue

            try:
                content = source.read_text(encoding="utf-8")
                target = self.s1._root / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                source.unlink()
                self.s2.remove_access_tracking(rel_path)
                results.append(
                    {
                        "path": rel_path,
                        "status": "promoted",
                        "access_count": entry["access_count"],
                    }
                )
            except Exception as exc:
                results.append({"path": rel_path, "status": "error", "error": str(exc)})

        if results:
            self.s1.generate_index()
        return results

    def rehydrate(self, shadow_entry: dict, target_tier: str = "active") -> dict | None:
        """Restore an archived file back to the 1st or 2nd Stratum.

        Reads the archived content from the 3rd Stratum and writes it
        to the selected target tier. Removes the shadow index entry on
        success.

        Args:
            shadow_entry: A dict from the shadow index containing at
                least ``id``, ``archive_path``, and metadata.
            target_tier: Target stratum — ``"active"`` (1st, default) or
                ``"cooled"`` (2nd).

        Returns:
            The rehydrated data dict, or ``None`` if the archive file
            could not be read.
        """
        data = self.s3.hydrate(shadow_entry)
        if data is None:
            return None

        original_path = data.get("original_path", "restored.md")
        content = data.get("content", "")

        if target_tier == "cooled":
            target = self.s2._root / original_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self.s2.init_access_tracking(original_path)
        else:
            target = self.s1._root / original_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self.s1.generate_index()

        self.s3.remove_shadow_entry(shadow_entry.get("id", ""))
        return data

    def run_maintenance(self, dry_run: bool = False) -> dict:
        """Run the full lifecycle: promote, migrate, evict.

        Executes in this order:
        1. Promote: move heavily-accessed cooled files back to active
        2. Migrate: move stale active files to cooled
        3. Evict:  move old cooled files to archive

        Args:
            dry_run: If ``True``, preview all operations without changes.

        Returns:
            A dict with ``promoted``, ``migrated``, ``evicted`` arrays
            and totals.
        """
        promoted = self.promote_2_to_1(dry_run=dry_run)
        migrated = self.migrate_1_to_2(dry_run=dry_run)
        evicted = self.evict_2_to_3(dry_run=dry_run)
        return {
            "promoted": promoted,
            "migrated": migrated,
            "evicted": evicted,
            "total_promoted": len(promoted),
            "total_migrated": len(migrated),
            "total_evicted": len(evicted),
        }

    def _get_lru_candidates(self) -> list[dict]:
        """Find files in the cooled directory eligible for LRU eviction.

        A candidate must satisfy both conditions:
          1. (now - last_accessed) >= config.get_lru_days(path)
          2. access_count <= config.lru_min_access_count

        If no tracking entry exists, falls back to mtime for last_accessed
        and access_count=0 (conservative — always evictable).
        """
        candidates = []
        now = time.time()
        access_data = self.s2._get_access_data()
        for filepath in self.s2._root.rglob("*"):
            if not filepath.is_file():
                continue
            rel = str(filepath.relative_to(self.s2._root))
            entry = access_data.get(rel)
            if entry is None:
                last_accessed = filepath.stat().st_mtime
                access_count = 0
            else:
                last_accessed = entry["last_accessed"]
                access_count = entry["access_count"]
            age_days = int((now - last_accessed) // 86400)
            lru_days = self.config.get_lru_days(rel)
            if (
                age_days >= lru_days
                and access_count <= self.config.lru_min_access_count
            ):
                candidates.append(
                    {
                        "path": rel,
                        "age_days": age_days,
                        "access_count": access_count,
                        "last_accessed": last_accessed,
                    }
                )
        return candidates

    @staticmethod
    def _infer_tags(path: str) -> list[str]:
        parts = path.replace("\\", "/").split("/")
        tags = []
        if parts:
            tags.append(parts[0])
        stem = parts[-1] if parts else ""
        if "." in stem:
            name = stem.rsplit(".", 1)[0]
            name = name.replace("_", " ").replace("-", " ").title()
            tags.append(name)
        return tags
