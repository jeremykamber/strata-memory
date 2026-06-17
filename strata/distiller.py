"""Background LLM-powered distillation of conversation transcripts.

The :class:`Distiller` reads raw conversation transcripts from
``pi/conversations/`` (written by the Pi extension's ``agent_end``
hook), sends new batches to a configured small LLM, and writes
extracted fact files to ``pi/facts/``.

Distillation runs inside the daemon's maintenance cycle. The Distiller
gracefully degrades when ``pi-config.json`` is missing or the API is
unreachable — it never crashes the daemon.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from strata.config import StrataConfig


# ────────────────────────────────────────────────────────────
#  Default configuration
# ────────────────────────────────────────────────────────────

DEFAULT_LLM_CONFIG = {
    "enabled": False,
    "provider": "openai",
    "model": "gpt-4o-mini",
    "apiKey": "",
    "temperature": 0.0,
    "maxTokens": 500,
}

PROVIDER_DEFAULTS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "openrouter": "openai/gpt-4o-mini",
}

WELL_KNOWN_ENV_VARS = {
    "openai": ["STRATA_OPENAI_API_KEY", "OPENAI_API_KEY"],
    "anthropic": ["STRATA_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"],
    "openrouter": ["STRATA_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"],
}

# ────────────────────────────────────────────────────────────
#  Extraction prompt
# ────────────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are a knowledge extraction system. Your job is to read AI assistant conversation transcripts and extract standalone facts worth persisting.

A fact IS worth extracting when it contains:
- Key decisions or architectural choices
- Technical details (code patterns, API endpoints, configuration)
- User preferences, requirements, or constraints
- Project-specific knowledge or domain concepts
- Action items, tasks, deadlines, or plans
- Explanations, rationale, or reasoning useful to recall later
- Important facts about people, companies, tools, or systems

A fact is NOT worth extracting for:
- Simple greetings or sign-offs
- Generic acknowledgments without substance
- Trivial or obvious statements
- Repetitive or redundant content already captured

For each fact, output a bullet point with:
- **Category** in square brackets: [projects], [entities], [gtd], [reference], [general]
- **Title** followed by a colon
- **One-sentence description**

Example output:
- [projects] Database migration strategy: Decided to use Alembic for schema migrations instead of raw SQL to maintain version control.
- [gtd] Review PR #42 by Friday: Jeremy needs to review the authentication refactor PR before the sprint closes.
- [reference] Redis cache invalidation pattern: Cache keys are invalidated on write, not on read, using a write-through strategy.

If no facts are worth extracting, respond with exactly: No significant facts to extract."""


# ────────────────────────────────────────────────────────────
#  Distiller class
# ────────────────────────────────────────────────────────────


class Distiller:
    """Background LLM-powered conversation distillation.

    Follows the ``QmdWrapper`` pattern for graceful degradation:
    lazy availability check, all external calls wrapped in
    try/except returning status dicts.

    Args:
        config: Strata configuration for base directory resolution.
        pi_config_path: Optional explicit path to ``pi-config.json``.
            Defaults to ``<base_dir>/pi-config.json``.
    """

    def __init__(
        self,
        config: StrataConfig,
        pi_config_path: Path | None = None,
    ):
        self.config = config
        self._pi_config_path = pi_config_path
        self._llm_config: dict | None = None
        self._available: bool | None = None
        self._base = config.base_dir.resolve()

    # ── Public API ──────────────────────────────────────────

    def check_available(self) -> bool:
        """Check whether a valid LLM configuration exists.

        Returns ``True`` when ``pi-config.json`` has a valid ``llm``
        block with ``enabled: true`` and a resolvable API key.
        Result is cached after first check.
        """
        if self._available is not None:
            return self._available
        cfg = self._load_config()
        self._available = bool(cfg and cfg.get("enabled"))
        return self._available

    def get_pending_count(self) -> int:
        """Return the number of undistilled conversation transcripts.

        Does not call the LLM. Returns the count of ``*.md`` files
        in ``active/pi/conversations/`` not yet recorded in the
        distill state sidecar.
        """
        return len(self._find_new_conversations())

    def process(self, dry_run: bool = False) -> dict:
        """Run the distill cycle.

        Scans for new conversation transcripts, sends them to the
        configured LLM in one batch, and writes extracted facts.

        Args:
            dry_run: If ``True``, report undistilled count without
                calling the LLM or writing any files.

        Returns:
            A status dict with keys:
            - ``status``: ``"ok"``, ``"skipped"``, ``"no_facts"``,
              ``"error"``, or ``"dry_run"``.
            - ``processed``: Number of transcripts processed.
            - ``facts_written``: Number of fact files written (absent
              if none).
            - ``reason``: Explanation when skipped (absent on success).
        """
        if not self.check_available():
            return {"status": "skipped", "reason": "llm_not_configured", "processed": 0}

        new_convs = self._find_new_conversations()
        if not new_convs:
            return {
                "status": "skipped",
                "reason": "no_new_conversations",
                "processed": 0,
            }

        pending = len(new_convs)

        if dry_run:
            return {"status": "dry_run", "would_process": pending}

        # Build the batch payload
        transcripts: list[dict[str, str]] = []
        for rel_path in new_convs:
            full_path = self._active_dir() / rel_path
            try:
                content = full_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            transcripts.append({"path": rel_path, "content": content})

        if not transcripts:
            return {
                "status": "skipped",
                "reason": "all_files_unreadable",
                "processed": 0,
            }

        # Call the LLM
        result = self._call_llm(transcripts)
        if result.get("error"):
            return {
                "status": "error",
                "reason": result["error"],
                "processed": 0,
            }

        fact_content = result.get("content", "").strip()

        # Mark as distilled regardless of whether facts were found
        conv_paths = [t["path"] for t in transcripts]
        self._mark_distilled(conv_paths)

        if not fact_content or fact_content == "No significant facts to extract.":
            return {
                "status": "no_facts_extracted",
                "processed": pending,
                "facts_written": 0,
            }

        # Write the fact file
        written = self._write_fact(fact_content)
        return {
            "status": "ok",
            "processed": pending,
            "facts_written": written,
        }

    # ── Configuration loading ───────────────────────────────

    def _load_config(self) -> dict | None:
        """Load and parse the ``pi-config.json`` LLM block.

        Returns the effective LLM configuration dict, or ``None``
        if the file is missing, malformed, or disabled.
        """
        if self._llm_config is not None:
            return self._llm_config

        config_path = (
            self._pi_config_path
            if self._pi_config_path
            else self._base / "pi-config.json"
        )

        try:
            raw = config_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._llm_config = None
            return None

        llm = parsed.get("llm", {})
        if not llm.get("enabled"):
            self._llm_config = None
            return None

        provider = str(llm.get("provider", DEFAULT_LLM_CONFIG["provider"]))
        model = str(
            llm.get("model")
            or PROVIDER_DEFAULTS.get(provider)
            or DEFAULT_LLM_CONFIG["model"]
        )
        api_key = self._resolve_api_key(str(llm.get("apiKey", "")), provider)

        if not api_key:
            self._llm_config = None
            return None

        self._llm_config = {
            "enabled": True,
            "provider": provider,
            "model": model,
            "apiKey": api_key,
            "temperature": float(
                llm.get("temperature", DEFAULT_LLM_CONFIG["temperature"])
            ),
            "maxTokens": int(llm.get("maxTokens", DEFAULT_LLM_CONFIG["maxTokens"])),
        }
        return self._llm_config

    @staticmethod
    def _resolve_api_key(raw_key: str, provider: str) -> str:
        """Resolve the effective API key.

        Resolution order:
        1. Direct string (not starting with ``${``)
        2. ``${ENV_VAR}`` reference
        3. Well-known env var names per provider

        Args:
            raw_key: The ``apiKey`` value from config.
            provider: Provider name (``"openai"``, ``"anthropic"``,
                ``"openrouter"``).

        Returns:
            The resolved API key, or empty string if none found.
        """
        # Direct key
        if raw_key and not raw_key.startswith("${"):
            return raw_key

        # Env-var reference: "${STRATA_OPENAI_API_KEY}"
        if raw_key.startswith("${") and raw_key.endswith("}"):
            var_name = raw_key[2:-1]
            return os.environ.get(var_name, "")

        # Well-known env vars per provider
        for var_name in WELL_KNOWN_ENV_VARS.get(provider, []):
            value = os.environ.get(var_name)
            if value:
                return value

        return ""

    # ── Conversation scanning ───────────────────────────────

    def _active_dir(self) -> Path:
        return self._base / "active"

    def _conversations_dir(self) -> Path:
        return self._active_dir() / "pi" / "conversations"

    def _distill_state_path(self) -> Path:
        return self._active_dir() / "pi" / "distill_state.json"

    def _find_new_conversations(self) -> list[str]:
        """Find conversation transcripts not yet marked as distilled.

        Returns relative paths (relative to ``active/``) of
        ``*.md`` files in ``pi/conversations/`` that are not
        recorded in ``distill_state.json``.
        """
        conv_dir = self._conversations_dir()
        if not conv_dir.is_dir():
            return []

        state = self._load_distill_state()

        new_files: list[str] = []
        try:
            for date_dir in sorted(conv_dir.iterdir()):
                if not date_dir.is_dir():
                    continue
                for fpath in sorted(date_dir.iterdir()):
                    if fpath.suffix != ".md":
                        continue
                    # Relative to active/
                    rel = str(fpath.relative_to(self._active_dir()))
                    if rel not in state.get("conversations", {}):
                        new_files.append(rel)
        except (OSError, ValueError):
            return []

        return new_files

    # ── Distill state management ─────────────────────────────

    def _load_distill_state(self) -> dict:
        """Load the distill state sidecar.

        Returns an empty state dict when the file is missing or
        corrupted (matching the ``stratum_2_access.json`` pattern).
        """
        path = self._distill_state_path()
        if not path.exists():
            return {"conversations": {}, "last_checked": None}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "conversations" in data:
                return data
            return {"conversations": {}, "last_checked": None}
        except (json.JSONDecodeError, OSError):
            return {"conversations": {}, "last_checked": None}

    def _save_distill_state(self, data: dict):
        """Write the distill state sidecar.

        Uses the same read-modify-write pattern as
        :meth:`Stratum2Storage._save_access_data`.
        """
        self._distill_state_path().parent.mkdir(parents=True, exist_ok=True)
        self._distill_state_path().write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _mark_distilled(self, conv_paths: list[str]):
        """Record conversation paths as having been distilled."""
        state = self._load_distill_state()
        now = datetime.now(timezone.utc).isoformat()
        for path in conv_paths:
            state.setdefault("conversations", {})[path] = {
                "distilled_at": now,
            }
        state["last_checked"] = now
        self._save_distill_state(state)

    # ── LLM API calls ───────────────────────────────────────

    def _call_llm(self, transcripts: list[dict[str, str]]) -> dict:
        """Send all new transcripts to the configured LLM.

        Args:
            transcripts: List of ``{"path": ..., "content": ...}``
                dicts for undistilled conversations.

        Returns:
            A dict with ``content`` (extracted text) on success,
            or ``error`` (message) on failure.
        """
        cfg = self._load_config()
        if not cfg:
            return {"error": "no_config"}

        joined = "\n\n==========\n\n".join(
            f"=== Transcript: {t['path']} ===\n\n{t['content']}" for t in transcripts
        )

        provider = cfg["provider"]
        try:
            if provider == "openai":
                return self._call_openai(cfg, joined)
            elif provider == "anthropic":
                return self._call_anthropic(cfg, joined)
            elif provider == "openrouter":
                return self._call_openrouter(cfg, joined)
            else:
                return {"error": f"unsupported_provider: {provider}"}
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            return {"error": f"http_error: {e}"}
        except (OSError, json.JSONDecodeError) as e:
            return {"error": f"response_error: {e}"}

    def _call_openai(self, cfg: dict, user_text: str) -> dict:
        """Call the OpenAI chat completions API."""
        payload = json.dumps(
            {
                "model": cfg["model"],
                "messages": [
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "temperature": cfg["temperature"],
                "max_tokens": cfg["maxTokens"],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg['apiKey']}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        return {"content": content or ""}

    def _call_anthropic(self, cfg: dict, user_text: str) -> dict:
        """Call the Anthropic messages API."""
        payload = json.dumps(
            {
                "model": cfg["model"],
                "max_tokens": cfg["maxTokens"],
                "system": EXTRACTION_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_text}],
                "temperature": cfg["temperature"],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": cfg["apiKey"],
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data.get("content", [{}])[0].get("text")
        return {"content": content or ""}

    def _call_openrouter(self, cfg: dict, user_text: str) -> dict:
        """Call the OpenRouter API (OpenAI-compatible)."""
        payload = json.dumps(
            {
                "model": cfg["model"],
                "messages": [
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "temperature": cfg["temperature"],
                "max_tokens": cfg["maxTokens"],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg['apiKey']}",
                "HTTP-Referer": "https://github.com/jeremykamber/strata-memory",
                "X-Title": "Strata Memory",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        return {"content": content or ""}

    # ── Fact file writing ───────────────────────────────────

    def _facts_dir(self) -> Path:
        return self._active_dir() / "pi" / "facts"

    def _write_fact(self, content: str) -> int:
        """Write a single fact file for the current batch.

        Determines the next sequential number in the day's directory
        and writes the LLM output as a markdown file.

        Args:
            content: Extracted fact content from the LLM.

        Returns:
            Number of files written (always 1 on success).
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        facts_dir = self._facts_dir() / date_str
        facts_dir.mkdir(parents=True, exist_ok=True)

        # Determine the next sequential number
        existing = []
        try:
            for f in facts_dir.iterdir():
                if f.suffix == ".md" and f.stem[0:3].isdigit():
                    existing.append(int(f.stem.split("-")[0]))
        except OSError:
            pass

        seq = max(existing) + 1 if existing else 1
        title = f"distilled-knowledge-{seq:03d}"
        filename = f"{seq:03d}-{title}.md"

        # Build full markdown content
        header = (
            f"# Distilled Knowledge — {date_str} (batch {seq})\n\n"
            f"*Extracted by Strata distillation ({now.isoformat()})*\n\n"
            f"---\n\n"
        )
        full_content = header + content + "\n"

        file_path = facts_dir / filename
        file_path.write_text(full_content, encoding="utf-8")
        return 1
