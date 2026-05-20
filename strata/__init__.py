"""
Strata: A Tiered Memory System for AI Agents.

Tiers:
    1st Stratum (Active Shell):    Filesystem-based markdown for active working context.
    2nd Stratum (Medium-Term):     Aged-out markdown files, still on disk.
    3rd Stratum (Cold Archive):    Flat-file storage with a lightweight Shadow Index.
"""

__version__ = "0.1.0"

from typing import Optional, List

from strata.config import StrataConfig
from strata.storage import Stratum1Storage, Stratum2Storage, Stratum3Storage, QmdWrapper
from strata.janitor import Janitor
from strata.query import QueryEngine
from strata.tools import StrataTools


class Strata:
    """Top-level API for Strata memory system. Coordinates all three tiers."""

    def __init__(self, config: Optional[StrataConfig] = None):
        self.config = config or StrataConfig()
        self.s1 = Stratum1Storage(self.config)
        self.s2 = Stratum2Storage(self.config)
        self.s3 = Stratum3Storage(self.config)
        self.janitor = Janitor(self.s1, self.s2, self.s3, self.config)
        self.query_engine = QueryEngine(self.s1, self.s2, self.s3, self.config)
        self.qmd = QmdWrapper(self.config)
        self.tools = StrataTools(self)

    def read_active(self, path: str) -> str:
        return self.s1.read(path)

    def write_active(self, path: str, content: str) -> str:
        return self.s1.write(path, content)

    def list_active(self, path: str = "") -> List[dict]:
        return self.s1.list_dir(path)

    def delete_active(self, path: str) -> bool:
        return self.s1.delete(path)

    def list_cooled(self) -> List[dict]:
        return self.s2.list_all()

    def generate_index(self):
        self.s1.generate_index()

    def query(self, text: str, filters: Optional[dict] = None, top_k: int = 5) -> List[dict]:
        return self.query_engine.search(text, filters=filters, top_k=top_k)

    def query_tool_schema(self) -> dict:
        return self.tools.query_schema()

    def migrate(self, dry_run: bool = False) -> list[dict]:
        return self.janitor.migrate_1_to_2(dry_run=dry_run)

    def evict(self, dry_run: bool = False) -> list[dict]:
        return self.janitor.evict_2_to_3(dry_run=dry_run)

    def run_maintenance(self, dry_run: bool = False) -> dict:
        migrated = self.migrate(dry_run=dry_run)
        evicted = self.evict(dry_run=dry_run)
        return {"migrated": migrated, "evicted": evicted, "total_migrated": len(migrated), "total_evicted": len(evicted)}

    def close(self):
        self.s3.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
