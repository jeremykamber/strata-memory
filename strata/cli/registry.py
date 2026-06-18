"""Command registry for the Strata CLI.

Maps command names to their handler modules. Each command module exports
``name`` (str) and ``run(args: list[str]) -> None``.
"""

from __future__ import annotations



class CommandNotFound(Exception):
    """Raised when no command matches the given name."""


class CommandRegistry:
    """A simple registry that maps command names to handler modules.

    Each entry has:
    - ``name`` — primary command name
    - ``aliases`` — optional alternative names
    - ``run`` — callable ``run(args: list[str]) -> None``
    """

    def __init__(self):
        self._entries: dict[str, dict] = {}

    def register(self, name: str, run, aliases: list[str] | None = None) -> None:
        """Register a command handler.

        Args:
            name: Primary command name.
            run: Callable accepting ``args: list[str]``.
            aliases: Optional alternative names for the same handler.
        """
        self._entries[name] = {"name": name, "run": run, "aliases": aliases or []}
        for alias in aliases or []:
            self._entries[alias] = {"name": name, "run": run, "aliases": []}

    def resolve(self, name: str) -> dict | None:
        """Look up a command by name or alias. Returns None if not found."""
        return self._entries.get(name)

    def run(self, name: str, args: list[str]) -> None:
        """Resolve and execute a command. Raises CommandNotFound if missing."""
        entry = self.resolve(name)
        if entry is None:
            raise CommandNotFound(name)
        entry["run"](args)

    def commands(self) -> list[dict]:
        """Return all unique command entries (no aliases)."""
        seen: set[str] = set()
        result: list[dict] = []
        for name, entry in self._entries.items():
            if name == entry["name"] and name not in seen:
                seen.add(name)
                result.append(entry)
        return result
