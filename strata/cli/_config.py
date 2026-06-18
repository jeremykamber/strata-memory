"""Configuration helpers for the Strata CLI.

Shared config loading, parsing, and persistence functions used across
CLI commands.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from strata.config import StrataConfig, detect_base_dir


def load_config(**kwargs) -> StrataConfig:
    """Load StrataConfig, overlaying persisted values from strata.json."""
    if "base_dir" not in kwargs:
        kwargs["base_dir"] = detect_base_dir()
    config = StrataConfig(**kwargs)
    config_path = config.base_dir / "strata.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    return config


def save_strata_config(config: StrataConfig) -> None:
    """Persist user-facing config fields to strata.json."""
    config_path = config.base_dir / "strata.json"
    data = {}
    if config_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            data = json.loads(config_path.read_text())
    data.update(
        {
            "search_backend": config.search_backend,
            "qmd_reranker": config.qmd_reranker,
            "lru_days": config.lru_days,
            "lru_min_access_count": config.lru_min_access_count,
            "decay_thresholds": config.decay_thresholds,
            "active_file_patterns": config.active_file_patterns,
        }
    )
    config_path.write_text(json.dumps(data, indent=2))


def config_to_dict(config: StrataConfig) -> dict:
    """Serialize config as a plain dict for JSON output."""
    return {
        "base_dir": str(config.base_dir.resolve()),
        "active_dir": config.active_dir,
        "cooled_dir": config.cooled_dir,
        "search_backend": config.search_backend,
        "qmd_reranker": config.qmd_reranker,
        "stratum_3_archive": config.stratum_3_archive,
        "stratum_3_shadow_db": config.stratum_3_shadow_db,
        "decay_thresholds": config.decay_thresholds,
        "lru_days": config.lru_days,
        "lru_min_access_count": config.lru_min_access_count,
        "lru_decay_thresholds": config.lru_decay_thresholds,
        "active_file_patterns": config.active_file_patterns,
        "qmd_enabled": config.qmd_enabled,
        "qmd_collection_prefix": config.qmd_collection_prefix,
    }


def get_config_value(config: StrataConfig, key: str):
    """Resolve a dotted config key (supports nested attrs and dicts)."""
    parts = key.split(".")
    obj = config
    for part in parts:
        if isinstance(obj, dict):
            obj = obj[part]
        else:
            obj = getattr(obj, part)
    return obj


def set_config_value(config: StrataConfig, key: str, value) -> None:
    """Set a dotted config key."""
    parts = key.split(".")
    obj = config
    for part in parts[:-1]:
        if isinstance(obj, dict):
            obj = obj[part]
        else:
            obj = getattr(obj, part)
    if isinstance(obj, dict):
        obj[parts[-1]] = value
    else:
        setattr(obj, parts[-1], value)


def parse_config_value(raw: str):
    """Parse a string into int/float/bool/JSON/string."""
    for fn in (int, float):
        try:
            return fn(raw)
        except (ValueError, TypeError):
            pass
    low = raw.lower()
    if low in ("true", "yes", "1"):
        return True
    if low in ("false", "no", "0"):
        return False
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    return raw


def llm_config_path(config: StrataConfig) -> Path:
    """Return the path to the LLM config file (pi-config.json)."""
    return config.base_dir / "pi-config.json"


def read_llm_config(config: StrataConfig) -> dict | None:
    """Read the LLM config from pi-config.json. Returns None if missing."""
    path = llm_config_path(config)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("llm")
    except (json.JSONDecodeError, KeyError):
        return None


def write_llm_config(config: StrataConfig, llm_cfg: dict) -> None:
    """Write the LLM config dict to pi-config.json, preserving other keys."""
    path = llm_config_path(config)
    existing = {}
    if path.exists():
        with contextlib.suppress(json.JSONDecodeError):
            existing = json.loads(path.read_text())
    existing["llm"] = llm_cfg
    path.write_text(json.dumps(existing, indent=2) + "\n")



