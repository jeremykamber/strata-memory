"""CLI command modules for the Strata memory system.

Each module exports:
- ``name`` (str): Primary command name.
- ``aliases`` (list[str], optional): Alternative names.
- ``run(args: list[str]) -> None``: Called by the registry on dispatch.
"""
