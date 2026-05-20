from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
        self.s1 = stratum_1
        self.s2 = stratum_2
        self.s3 = stratum_3
        self.config = config

    def migrate_1_to_2(self, dry_run: bool = False) -> list[dict]:
        """Move stale files from the 1st Stratum (active) to the 2nd (cooled)."""
        stale = self.s1.scan_stale_files()
        results = []
        for entry in stale:
            rel_path = entry["path"]
            source = self.s1._root / rel_path
            target = self.s2._root / rel_path

            if dry_run:
                results.append({"path": rel_path, "status": "would_migrate", "age_days": entry["age_days"]})
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(source), str(target))
                source.unlink()
                results.append({"path": rel_path, "status": "migrated", "age_days": entry["age_days"]})
            except Exception as exc:
                results.append({"path": rel_path, "status": "error", "error": str(exc)})

        if results:
            self.s1.generate_index()
        return results

    def evict_2_to_3(self, dry_run: bool = False) -> list[dict]:
        """Evict old files from the 2nd Stratum (cooled) to the 3rd (archive)."""
        candidates = self._get_lru_candidates()
        results = []
        for entry in candidates:
            rel_path = entry["path"]
            source = self.s2._root / rel_path

            if dry_run:
                results.append({"path": rel_path, "status": "would_evict", "age_days": entry["age_days"]})
                continue

            try:
                tags = self._infer_tags(rel_path)
                archive_path = self.s3.archive_file(source, rel_path, tags=tags)
                source.unlink()
                results.append({"path": rel_path, "status": "evicted", "archive_path": archive_path})
            except Exception as exc:
                results.append({"path": rel_path, "status": "error", "error": str(exc)})

        return results

    def rehydrate(self, shadow_entry: dict) -> Optional[dict]:
        """Restore an archived file back to the 1st Stratum (active)."""
        data = self.s3.hydrate(shadow_entry)
        if data is None:
            return None

        original_path = data.get("original_path", "restored.md")
        content = data.get("content", "")
        target = self.s1._root / original_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        self.s3.remove_shadow_entry(shadow_entry.get("id", ""))
        return data

    def _get_lru_candidates(self) -> list[dict]:
        """Find files in the cooled directory older than the LRU threshold."""
        candidates = []
        now = time.time()
        for filepath in self.s2._root.rglob("*"):
            if not filepath.is_file():
                continue
            rel = str(filepath.relative_to(self.s2._root))
            mtime = filepath.stat().st_mtime
            age_days = int((now - mtime) // 86400)
            if age_days >= self.config.lru_days:
                candidates.append({"path": rel, "age_days": age_days})
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



