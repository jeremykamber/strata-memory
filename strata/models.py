from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class MemoryBlock:
    """A compressed memory record that lives in 2nd Stratum medium-term storage."""

    id: str = field(default_factory=_new_id)
    summary: str = ""
    source_path: str = ""
    entity_tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    last_accessed: str = field(default_factory=_now)
    access_count: int = 0
    tier: str = "stratum_2"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> MemoryBlock:
        return cls(**data)

    def touch(self):
        self.last_accessed = _now()
        self.access_count += 1


@dataclass
class SearchResult:
    """A single search hit from any tier."""

    content: str = ""
    tier: str = ""
    source: str = ""
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShadowEntry:
    """Lightweight entry in the 3rd Stratum Shadow Index."""

    id: str = field(default_factory=_new_id)
    original_memory_id: str = ""
    keywords: list = field(default_factory=list)
    archive_path: str = ""
    summary_preview: str = ""
    evicted_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ShadowEntry:
        return cls(**data)
