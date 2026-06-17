from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from strata.config import StrataConfig
from strata.models import ShadowEntry


# ────────────────────────────────────────────────────────────
#  1ST STRATUM — Active Shell (Filesystem)
# ────────────────────────────────────────────────────────────


class Stratum1Storage:
    """Filesystem-backed active memory. The agent's working context."""

    def __init__(self, config: StrataConfig):
        """Initialize the 1st Stratum storage.

        Args:
            config: Strata configuration with active directory path.
        """
        self.config = config
        self._root = config.active_path().resolve()

    def ensure_dirs(self):
        """Create the active directory if it doesn't exist, then regenerate the index.

        No boilerplate subdirectories are created — the AI is free to
        organise files however it sees fit.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        self.generate_index()

    def _resolve(self, path: str) -> Path:
        full = (self._root / path).resolve()
        root = self._root.resolve()
        if not str(full).startswith(str(root)):
            raise ValueError(f"Path traversal blocked: {path}")
        return full

    def read(self, path: str) -> str:
        """Read a file from the 1st Stratum.

        Args:
            path: Path relative to the active directory root.

        Returns:
            The full file contents as a string.

        Raises:
            FileNotFoundError: If the path does not exist.
            IsADirectoryError: If the path is a directory.
        """
        p = self._resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"1st Stratum path not found: {path}")
        if p.is_dir():
            raise IsADirectoryError(f"Path is a directory: {path}")
        return p.read_text(encoding="utf-8")

    def write(self, path: str, content: str) -> str:
        """Write a file to the 1st Stratum.

        Creates parent directories as needed. Regenerates the index
        automatically. Writing to the index.md itself is a no-op.

        Args:
            path: Path relative to the active directory root.
            content: File content to write.

        Returns:
            The absolute path to the written file.
        """
        p = self._resolve(path)
        if str(p.resolve()) == str((self._root / "index.md").resolve()):
            return str(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        self.generate_index()
        return str(p)

    def delete(self, path: str) -> bool:
        """Delete a file or directory from the 1st Stratum.

        Regenerates the index after deletion.

        Args:
            path: Path relative to the active directory root.

        Returns:
            ``True`` if the path was deleted, ``False`` if it did not exist.
        """
        p = self._resolve(path)
        if not p.exists():
            return False
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        self.generate_index()
        return True

    def list_dir(self, path: str = "") -> list[dict]:
        """List files and directories in the 1st Stratum.

        Args:
            path: Optional subdirectory path relative to active root.
                Defaults to the root.

        Returns:
            A list of dicts with keys: name, path, type, size, modified.
        """
        p = self._resolve(path)
        if not p.exists():
            return []
        entries = []
        for child in sorted(p.iterdir()):
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(self._root)),
                    "type": "directory" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else 0,
                    "modified": datetime.fromtimestamp(
                        child.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
        return entries

    def get_modified_days_ago(self, path: str) -> int:
        """Return the number of days since a file was last modified.

        Args:
            path: Path relative to the active directory root.

        Returns:
            Days since modification, or ``0`` if the path does not exist.
        """
        p = self._resolve(path)
        if not p.exists():
            return 0
        mtime = p.stat().st_mtime
        age = time.time() - mtime
        return int(age // 86400)

    def scan_stale_files(self) -> list[dict]:
        """Scan the 1st Stratum for files exceeding their decay threshold.

        Uses ``active_file_patterns`` to filter relevant files and
        ``get_decay_days`` to determine the threshold per path.

        Returns:
            A list of dicts with keys: path, age_days, threshold, size.
        """
        stale = []
        for filepath in self._root.rglob("*"):
            if not filepath.is_file():
                continue
            patterns = self.config.active_file_patterns
            if not any(filepath.match(p) for p in patterns):
                continue
            rel = str(filepath.relative_to(self._root))
            days = self.get_modified_days_ago(rel)
            threshold = self.config.get_decay_days(rel)
            if days >= threshold:
                stale.append(
                    {
                        "path": rel,
                        "age_days": days,
                        "threshold": threshold,
                        "size": filepath.stat().st_size,
                    }
                )
        return stale

    def path_exists(self, path: str) -> bool:
        """Check whether a path exists in the 1st Stratum.

        Args:
            path: Path relative to the active directory root.

        Returns:
            ``True`` if the path exists.
        """
        return self._resolve(path).exists()

    def generate_index(self):
        """Regenerate index.md — the master map for AI agents."""
        if not self._root.exists():
            return
        lines = ["# Strata — Active Memory Index", ""]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"_Last updated: {now}_")
        lines.append("")
        lines.append(
            "This index lists every file in active memory. Read this first to find"
        )
        lines.append(
            "relevant context, then navigate to specific files by path. The AI"
        )
        lines.append(
            "should organise files however it sees fit — create directories as"
        )
        lines.append("needed. There are no pre-determined folders; the structure grows")
        lines.append("organically with use.")
        lines.append("")
        lines.append("---")
        lines.append("")

        for subdir_name in sorted([d.name for d in self._root.iterdir() if d.is_dir()]):
            subdir_path = self._root / subdir_name
            files = sorted([f for f in subdir_path.rglob("*") if f.is_file()])
            if not files:
                continue
            lines.append(f"## {subdir_name.capitalize()}")
            lines.append("")
            for filepath in files:
                rel = filepath.relative_to(self._root)
                title = ""
                summary = ""
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                    lines_in = content.split("\n")
                    for i, line in enumerate(lines_in):
                        s = line.strip()
                        if s.startswith("# ") and not s.startswith("# Strata"):
                            title = f" — {s.lstrip('# ').strip()}"
                            # Grab the next non-empty line as a brief summary
                            for j in range(i + 1, min(i + 3, len(lines_in))):
                                nxt = lines_in[j].strip()
                                if nxt and not nxt.startswith("#"):
                                    summary = nxt[:80].rstrip(".")
                                    break
                            break
                    if not title:
                        # No heading — use the first non-empty line
                        for line in lines_in:
                            s = line.strip()
                            if s:
                                summary = s[:80].rstrip(".")
                                break
                except Exception:
                    pass
                full = f"- `{rel}`{title}"
                if summary:
                    full += f"\n  {summary}"
                lines.append(full)
            lines.append("")

        self._root.joinpath("index.md").write_text("\n".join(lines), encoding="utf-8")


# ────────────────────────────────────────────────────────────
#  2ND STRATUM — Cooled (Filesystem, aged-out files)
# ────────────────────────────────────────────────────────────


class Stratum2Storage:
    """Filesystem-backed cooled memory. Stale files from the 1st Stratum
    are moved here by the Janitor. Files remain as plain markdown —
    searchable via QMD or directly by the agent."""

    def __init__(self, config: StrataConfig):
        """Initialize the 2nd Stratum storage.

        Args:
            config: Strata configuration with cooled directory path.
        """
        self.config = config
        self._root = config.cooled_path().resolve()

    def ensure_dirs(self):
        """Create the cooled directory if it does not exist."""
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        full = (self._root / path).resolve()
        root = self._root.resolve()
        if not str(full).startswith(str(root)):
            raise ValueError(f"Path traversal blocked: {path}")
        return full

    def read(self, path: str) -> str:
        """Read a file from the 2nd Stratum.

        Args:
            path: Path relative to the cooled directory root.

        Returns:
            The full file contents as a string.

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        p = self._resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"2nd Stratum path not found: {path}")
        return p.read_text(encoding="utf-8")

    def write(self, path: str, content: str) -> str:
        """Write a file to the 2nd Stratum.

        Creates parent directories as needed.

        Args:
            path: Path relative to the cooled directory root.
            content: File content to write.

        Returns:
            The absolute path to the written file.
        """
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return str(p)

    def move_from(self, source_path: Path, rel_target: str) -> str:
        """Move a file from an external path into the cooled directory.

        Args:
            source_path: Absolute path to the source file.
            rel_target: Relative path within the cooled directory.

        Returns:
            The absolute path to the destination file.
        """
        target = self._root / rel_target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source_path), str(target))
        return str(target)

    def delete(self, path: str) -> bool:
        """Delete a file or directory from the 2nd Stratum.

        Args:
            path: Path relative to the cooled directory root.

        Returns:
            ``True`` if the path was deleted, ``False`` if it did not exist.
        """
        p = self._resolve(path)
        if not p.exists():
            return False
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return True

    def list_all(self) -> list[dict]:
        """List all files in the 2nd Stratum.

        Returns:
            A list of dicts with keys: path, size, modified.
        """
        entries = []
        for filepath in sorted(self._root.rglob("*")):
            if not filepath.is_file():
                continue
            rel = str(filepath.relative_to(self._root))
            entries.append(
                {
                    "path": rel,
                    "size": filepath.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        filepath.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
        return entries

    def count(self) -> int:
        """Return the total number of files in the 2nd Stratum.

        Returns:
            File count.
        """
        return sum(1 for _ in self._root.rglob("*") if _.is_file())

    def path_exists(self, path: str) -> bool:
        """Check whether a path exists in the 2nd Stratum.

        Args:
            path: Path relative to the cooled directory root.

        Returns:
            ``True`` if the path exists.
        """
        return self._resolve(path).exists()

    # ── Access Tracking (LRU sidecar) ──────────────────────────

    def _access_sidecar_path(self) -> Path:
        return self.config.base_dir / "stratum_2_access.json"

    def _get_access_data(self) -> dict:
        path = self._access_sidecar_path()
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _save_access_data(self, data: dict):
        self._access_sidecar_path().write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def track_access(self, path: str) -> dict:
        """Record an access event for a cooled file.

        Increments the access count and updates the last_accessed
        timestamp in the LRU sidecar.

        Args:
            path: Relative path to the file in the cooled directory.

        Returns:
            The updated access entry dict.
        """
        data = self._get_access_data()
        entry = data.get(path, {"access_count": 0, "last_accessed": 0})
        entry["access_count"] += 1
        entry["last_accessed"] = time.time()
        data[path] = entry
        self._save_access_data(data)
        return entry

    def init_access_tracking(self, path: str):
        """Initialize the LRU access tracking entry for a newly migrated file.

        Args:
            path: Relative path to the file in the cooled directory.
        """
        data = self._get_access_data()
        data[path] = {"access_count": 0, "last_accessed": time.time()}
        self._save_access_data(data)

    def remove_access_tracking(self, path: str):
        """Remove the LRU access tracking entry for a file.

        Called after a file is evicted to the 3rd Stratum.

        Args:
            path: Relative path to the file in the cooled directory.
        """
        data = self._get_access_data()
        data.pop(path, None)
        self._save_access_data(data)

    def close(self):
        """No-op for 2nd Stratum (no persistent connections to close)."""
        pass


# ────────────────────────────────────────────────────────────
#  3RD STRATUM — Cold Archive + Shadow Index
# ────────────────────────────────────────────────────────────


class Stratum3Storage:
    """Cold archive with flat-file JSON storage + SQLite Shadow Index.

    When a file is evicted from the 2nd Stratum, its content is saved
    as a JSON blob in the archive directory and a lightweight keyword
    entry is created in the Shadow Index for future retrieval.
    """

    def __init__(self, config: StrataConfig):
        """Initialize the 3rd Stratum storage.

        Args:
            config: Strata configuration with archive and shadow paths.
        """
        self.config = config
        self._archive_dir = config.stratum_3_archive_path()
        self._shadow_path = config.stratum_3_shadow_path()
        self._conn: Optional[sqlite3.Connection] = None

    def ensure_dirs(self):
        """Create the archive directory if it does not exist."""
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    def _connect_shadow(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._shadow_path))
            self._conn.row_factory = sqlite3.Row
            self._init_shadow_schema()
        return self._conn

    def _init_shadow_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS shadow_index (
                id TEXT PRIMARY KEY,
                original_path TEXT NOT NULL,
                keywords TEXT DEFAULT '[]',
                archive_path TEXT NOT NULL,
                summary_preview TEXT DEFAULT '',
                evicted_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_shadow_keywords
                ON shadow_index(original_path);

            CREATE VIRTUAL TABLE IF NOT EXISTS shadow_fts USING fts5(
                keywords, summary_preview,
                content='shadow_index',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS shadow_ai AFTER INSERT ON shadow_index BEGIN
                INSERT INTO shadow_fts(rowid, keywords, summary_preview)
                VALUES (new.rowid, new.keywords, new.summary_preview);
            END;

            CREATE TRIGGER IF NOT EXISTS shadow_ad AFTER DELETE ON shadow_index BEGIN
                INSERT INTO shadow_fts(shadow_fts, rowid, keywords, summary_preview)
                VALUES ('delete', old.rowid, old.keywords, old.summary_preview);
            END;
        """)

    def archive_file(
        self, source_path: Path, original_rel_path: str, tags: list[str] | None = None
    ) -> str:
        """Save a file's content into the cold archive and index it."""
        self.ensure_dirs()
        content = source_path.read_text(encoding="utf-8")
        doc_id = str(abs(hash(str(source_path))))[-12:]
        filename = f"{doc_id}.json"
        filepath = self._archive_dir / filename
        data = {
            "original_path": original_rel_path,
            "content": content,
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "tags": tags or [],
        }
        filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")

        entry = ShadowEntry(
            original_memory_id=original_rel_path,
            keywords=tags or [],
            archive_path=str(filepath),
            summary_preview=content[:200] if content else "",
        )
        self._index_entry(entry)
        return str(filepath)

    def _index_entry(self, entry: ShadowEntry):
        conn = self._connect_shadow()
        conn.execute(
            """INSERT OR REPLACE INTO shadow_index
               (id, original_path, keywords, archive_path, summary_preview, evicted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.original_memory_id,
                json.dumps(entry.keywords),
                entry.archive_path,
                entry.summary_preview,
                entry.evicted_at,
            ),
        )
        conn.commit()

    def search_shadow(self, query: str, top_k: int = 5) -> list[dict]:
        """Search the shadow index by full-text query.

        Uses SQLite FTS5 for keyword search against archived file
        summaries and keywords.

        Args:
            query: Free-text search query.
            top_k: Maximum results to return (default: 5).

        Returns:
            A list of matching shadow index row dicts.
        """
        conn = self._connect_shadow()
        clean = query.replace('"', "").replace("'", "")
        try:
            rows = conn.execute(
                """SELECT si.* FROM shadow_index si
                   JOIN shadow_fts fts ON si.rowid = fts.rowid
                   WHERE shadow_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (clean, top_k),
            ).fetchall()
        except Exception:
            return []
        return [dict(r) for r in rows]

    def search_shadow_by_tags(self, tags: list[str], top_k: int = 5) -> list[dict]:
        """Search the shadow index by tag keywords.

        Performs LIKE searches against the keywords JSON column for
        each tag, deduplicating results.

        Args:
            tags: List of tag strings to search for.
            top_k: Maximum results to return (default: 5).

        Returns:
            A list of matching shadow index row dicts.
        """
        conn = self._connect_shadow()
        results = []
        for tag in tags:
            like = f'%"{tag}"%'
            rows = conn.execute(
                "SELECT * FROM shadow_index WHERE keywords LIKE ? LIMIT ?",
                (like, top_k),
            ).fetchall()
            for r in rows:
                d = dict(r)
                if d["id"] not in {x["id"] for x in results}:
                    results.append(d)
        return results[:top_k]

    def hydrate(self, shadow_entry: dict) -> Optional[dict]:
        """Read archived content and return it. Does NOT remove from shadow index."""
        archive_path = shadow_entry.get("archive_path", "")
        if not os.path.exists(archive_path):
            return None
        data = json.loads(Path(archive_path).read_text(encoding="utf-8"))
        return data

    def remove_shadow_entry(self, entry_id: str):
        """Remove a shadow index entry by ID.

        Args:
            entry_id: The shadow entry ID to remove.
        """
        conn = self._connect_shadow()
        conn.execute("DELETE FROM shadow_index WHERE id = ?", (entry_id,))
        conn.commit()

    def get_shadow_count(self) -> int:
        """Return the total number of entries in the shadow index.

        Returns:
            Shadow entry count.
        """
        conn = self._connect_shadow()
        return conn.execute("SELECT COUNT(*) FROM shadow_index").fetchone()[0]

    def close(self):
        """Close the SQLite shadow index connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# ────────────────────────────────────────────────────────────
#  QMD WRAPPER — Optional hybrid search via QMD CLI
# ────────────────────────────────────────────────────────────


class QmdWrapper:
    """Wrapper around the QMD CLI for hybrid search.

    QMD (by Tobias Lütke) provides BM25 full-text search, vector semantic
    search, and optional LLM re-ranking — all local via GGUF models.

    Requires: npm install -g @tobilu/qmd
    Docs: https://github.com/tobi/qmd
    """

    def __init__(self, config: StrataConfig):
        """Initialize the QMD wrapper.

        Args:
            config: Strata configuration with QMD settings.
        """
        self.config = config
        self._available: Optional[bool] = None

    def check_available(self) -> bool:
        """Check if QMD CLI is installed and accessible."""
        if self._available is not None:
            return self._available
        try:
            subprocess.run(
                ["qmd", "--version"],
                capture_output=True,
                timeout=5,
            )
            self._available = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._available = False
        return self._available

    def setup_collections(self, progress_cb=None) -> list[dict]:
        """Add all Strata directories as QMD collections."""
        results = []
        dirs = [
            ("strata_active", self.config.active_path(), "1st Stratum (active)"),
            ("strata_cooled", self.config.cooled_path(), "2nd Stratum (cooled)"),
        ]
        for name, path, desc in dirs:
            path = path.resolve()
            if not path.exists():
                continue
            try:
                r = subprocess.run(
                    ["qmd", "collection", "add", str(path), "--name", name],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                results.append(
                    {
                        "name": name,
                        "path": str(path),
                        "status": "ok" if r.returncode == 0 else "error",
                        "output": r.stderr.strip(),
                    }
                )
            except Exception as e:
                results.append({"name": name, "status": "error", "error": str(e)})
        return results

    def embed(self, force: bool = False) -> dict:
        """Generate vector embeddings for all collections."""
        try:
            cmd = ["qmd", "embed"]
            if force:
                cmd.append("-f")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                "status": "ok" if r.returncode == 0 else "error",
                "output": r.stderr.strip(),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def update_index(self) -> dict:
        """Re-index all collections (refresh FTS)."""
        try:
            r = subprocess.run(
                ["qmd", "update"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {
                "status": "ok" if r.returncode == 0 else "error",
                "output": r.stderr.strip(),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """BM25 full-text search via QMD. No LLM involvement."""
        try:
            r = subprocess.run(
                ["qmd", "search", query, "--json", "-n", str(top_k)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode != 0:
                return []
            return json.loads(r.stdout) if r.stdout.strip() else []
        except Exception:
            return []

    def vector_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Vector semantic search via QMD. No LLM involvement."""
        try:
            r = subprocess.run(
                ["qmd", "vsearch", query, "--json", "-n", str(top_k)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode != 0:
                return []
            return json.loads(r.stdout) if r.stdout.strip() else []
        except Exception:
            return []

    def hybrid_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Hybrid search: BM25 + vector, fused via RRF in Python.
        No LLM expansion or re-ranking."""
        fts_results = self.search(query, top_k=top_k * 2)
        vec_results = self.vector_search(query, top_k=top_k * 2)
        return _rrf_fuse(fts_results, vec_results, top_k)

    def get_status(self) -> dict:
        """Get QMD index status."""
        try:
            r = subprocess.run(
                ["qmd", "status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {"status": "ok", "output": r.stderr.strip()}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ────────────────────────────────────────────────────────────
#  RRF Fusion Utility
# ────────────────────────────────────────────────────────────


def _rrf_fuse(*result_lists: list[dict], top_k: int = 5, k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: combine multiple ranked result lists.

    Each result list contributes scores inversely proportional to rank.
    Results are deduplicated by ``docid`` (or ``file`` if ``docid`` is
    absent).

    Args:
        *result_lists: One or more ranked result lists to fuse.
        top_k: Maximum results to return after fusion.
        k: RRF constant (default: 60). Higher values give more weight
            to top-ranked items.

    Returns:
        A single fused list of result dicts, sorted by fused score
        descending.
    """
    scores: dict[str, dict] = {}
    for rank, results in enumerate(result_lists):
        for pos, r in enumerate(results):
            docid = r.get("docid", r.get("file", str(pos)))
            if docid not in scores:
                scores[docid] = {"docid": docid, "score": 0.0, "source": r}
            scores[docid]["score"] += 1.0 / (k + pos + 1)

    sorted_results = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
    return [s["source"] for s in sorted_results[:top_k]]
