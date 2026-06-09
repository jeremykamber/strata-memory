from __future__ import annotations

from typing import Optional, List, Dict

from strata.config import StrataConfig
from strata.models import SearchResult
from strata.storage import (
    Stratum1Storage, Stratum2Storage, Stratum3Storage,
    QmdWrapper, _rrf_fuse,
)


class QueryEngine:
    """Cascading search across 1st Stratum -> 2nd Stratum -> 3rd Stratum.

    Uses QMD for hybrid search (BM25 + vector, no LLM) when available.
    Falls back to filesystem search when QMD is not installed.
    """

    def __init__(
        self,
        stratum_1: Stratum1Storage,
        stratum_2: Stratum2Storage,
        stratum_3: Stratum3Storage,
        config: StrataConfig,
    ):
        """Initialize the query engine with storage backends.

        Args:
            stratum_1: The 1st Stratum (active) storage backend.
            stratum_2: The 2nd Stratum (cooled) storage backend.
            stratum_3: The 3rd Stratum (archive) storage backend.
            config: Strata configuration with search backend settings.
        """
        self.s1 = stratum_1
        self.s2 = stratum_2
        self.s3 = stratum_3
        self.config = config
        self.qmd = QmdWrapper(config)
        self._qmd_ready = None

    def search(
        self,
        query: str,
        filters: Optional[dict] = None,
        top_k: int = 5,
    ) -> List[dict]:
        """Search across all three strata in cascade order.

        When QMD is available: uses hybrid BM25 + vector search (no LLM).
        When QMD is unavailable: falls back to filesystem grep-like search.
        Phase 3 (Shadow Index) is always searched via FTS5.
        """
        tags = None
        if filters and "tags" in filters:
            tags = filters["tags"]

        results = []

        if self._qmd_available():
            qmd_results = self.qmd.hybrid_search(query, top_k=top_k * 2)
            for r in qmd_results:
                filepath = r.get("file", "")
                tier = "stratum_1"
                if "strata_cooled" in r.get("collection", ""):
                    tier = "stratum_2"
                content = r.get("snippet", r.get("text", ""))
                results.append(SearchResult(
                    content=content,
                    tier=tier,
                    source=filepath,
                    score=r.get("score", 0.5),
                    metadata={"qmd_docid": r.get("docid", "")},
                ))
        else:
            results.extend(self._search_stratum_1(query, tags, top_k))
            results.extend(self._search_stratum_2(query, tags, top_k))

        results.extend(self._search_stratum_3(query, tags, top_k))
        results.sort(key=lambda r: r.score, reverse=True)
        return [r.to_dict() for r in results[:top_k]]

    def _qmd_available(self) -> bool:
        if self._qmd_ready is None:
            self._qmd_ready = self.qmd.check_available()
        return self._qmd_ready

    def _search_stratum_1(self, query: str, tags: list[str] | None, top_k: int) -> list[SearchResult]:
        return self._fs_search(self.s1._root, query, tags, top_k, "stratum_1")

    def _search_stratum_2(self, query: str, tags: list[str] | None, top_k: int) -> list[SearchResult]:
        results = self._fs_search(self.s2._root, query, tags, top_k, "stratum_2")
        for r in results:
            path = r.metadata.get("path", "")
            if path:
                self.s2.track_access(path)
        return results

    def _fs_search(self, root, query: str, tags: list[str] | None, top_k: int, tier: str) -> list[SearchResult]:
        if not root or not root.exists():
            return []
        terms = query.lower().split()
        matches = []
        for filepath in root.rglob("*"):
            if not filepath.is_file():
                continue
            rel = str(filepath.relative_to(root))
            rel_lower = rel.lower()

            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                content = ""
            content_lower = content.lower()

            score = 0.0
            for term in terms:
                if term in rel_lower:
                    score += 1.0
                if term in content_lower:
                    score += 0.5

            if tags:
                for t in tags:
                    if t.lower() in rel_lower or t.lower() in content_lower:
                        score += 0.3

            if score > 0:
                matches.append(SearchResult(
                    content=content[:500],
                    tier=tier,
                    source=rel,
                    score=score + 0.1,
                    metadata={"path": rel, "size": filepath.stat().st_size},
                ))
        return sorted(matches, key=lambda r: r.score, reverse=True)[:top_k]

    def _search_stratum_3(self, query: str, tags: list[str] | None, top_k: int) -> list[SearchResult]:
        try:
            entries = self.s3.search_shadow(query, top_k=top_k)
        except Exception:
            entries = []
        if tags:
            tag_entries = self.s3.search_shadow_by_tags(tags, top_k=top_k)
            seen = {e["id"] for e in entries}
            for te in tag_entries:
                if te["id"] not in seen:
                    entries.append(te)
                    seen.add(te["id"])
        results = []
        for i, entry in enumerate(entries):
            score = 0.5 / (i + 1)
            results.append(SearchResult(
                content=entry.get("summary_preview", ""),
                tier="stratum_3",
                source=f"archive:{entry.get('archive_path', '')}",
                score=score,
                metadata={
                    "id": entry.get("id"),
                    "shadow_id": entry.get("id"),
                    "memory_id": entry.get("original_path"),
                    "archive_path": entry.get("archive_path"),
                    "keywords": entry.get("keywords", "[]"),
                    "_needs_rehydration": True,
                },
            ))
        return results
