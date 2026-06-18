"""``mcp`` command: start the MCP protocol server over stdio.

Starts the Strata MCP server, which provides tool-based access
to the memory tiers via the Model Context Protocol.
"""

from __future__ import annotations

from strata.mcp_server import MCPServer


name = "mcp"


def run(args: list[str]) -> None:
    """Start MCP protocol server over stdio."""
    server = MCPServer()
    try:
        server.run_stdio()
    finally:
        server.close()
