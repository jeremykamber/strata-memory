"""Minimal MCP (Model Context Protocol) server for Strata.

Implements the MCP protocol over stdio (JSON-RPC 2.0, line-delimited).
Zero external pip dependencies — uses only Python stdlib.

The MCP protocol spec: https://modelcontextprotocol.io
"""

from __future__ import annotations

import json
import sys
from typing import Optional

from strata import Strata, __version__
from strata.config import StrataConfig, detect_base_dir


def rpc_error(id_val, code: int, message: str, data=None) -> str:
    """Build a JSON-RPC 2.0 error response.

    Args:
        id_val: The request ID (or ``None`` for parse errors).
        code: JSON-RPC error code (e.g. ``-32700``, ``-32601``).
        message: Human-readable error message.
        data: Optional additional error data.

    Returns:
        A JSON-RPC 2.0 error response string.
    """
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return json.dumps({"jsonrpc": "2.0", "id": id_val, "error": err})


def rpc_result(id_val, result) -> str:
    """Build a JSON-RPC 2.0 success response.

    Args:
        id_val: The request ID.
        result: The result payload (any JSON-serializable value).

    Returns:
        A JSON-RPC 2.0 result response string.
    """
    return json.dumps({"jsonrpc": "2.0", "id": id_val, "result": result})


def rpc_notification(method: str, params=None) -> str:
    """Build a JSON-RPC 2.0 notification (no ``id`` field).

    Args:
        method: The method name for the notification.
        params: Optional parameters payload.

    Returns:
        A JSON-RPC 2.0 notification string.
    """
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg)


class MCPServer:
    """Minimal MCP protocol server exposing Strata's memory tools.

    Supports stdio transport: read JSON-RPC requests from stdin,
    write responses to stdout. Compatible with any MCP client
    (Claude Code, OpenClaw VS Code, custom agents, etc.).
    """

    def __init__(self, config: Optional[StrataConfig] = None):
        """Initialize the MCP server.

        Creates the Strata instance and ensures the 1st and 3rd Stratum
        directories exist.

        Args:
            config: Optional configuration. Auto-detects if not provided.
        """
        self.config = config or StrataConfig(base_dir=detect_base_dir())
        self.strata = Strata(self.config)
        self.strata.s1.ensure_dirs()
        self.strata.s3.ensure_dirs()
        self._request_id = 0
        self._initialized = False

    @property
    def _tools(self) -> list[dict]:
        """Return tool definitions in MCP format."""
        schemas = self.strata.tools.all_schemas()
        tools = []
        for s in schemas:
            fn = s["function"]
            tools.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "inputSchema": fn.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                }
            )
        return tools

    def _handle_request(self, raw: str) -> Optional[str]:
        """Process a single JSON-RPC request and return the response (or None for notifications)."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return rpc_error(None, -32700, "Parse error")

        method = msg.get("method", "")
        params = msg.get("params", {})
        req_id = msg.get("id")

        if method == "initialize":
            self._initialized = True
            return rpc_result(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                    },
                    "serverInfo": {
                        "name": "strata-memory",
                        "version": __version__,
                    },
                },
            )

        if method == "notifications/initialized":
            return None

        if not self._initialized and method not in ("initialize",):
            return rpc_error(req_id, -32000, "Server not initialized")

        if method == "tools/list":
            return rpc_result(req_id, {"tools": self._tools})

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            return self._call_tool(req_id, tool_name, arguments)

        if method == "resources/list":
            return rpc_result(req_id, {"resources": []})

        if method == "shutdown":
            self.strata.close()
            return rpc_result(req_id, None)

        if method == "exit":
            self.strata.close()
            sys.exit(0)

        return rpc_error(req_id, -32601, f"Method not found: {method}")

    def _call_tool(self, req_id, tool_name: str, arguments: dict) -> str:
        """Execute a Strata tool via JSON-RPC and return the result.

        Args:
            req_id: The JSON-RPC request ID.
            tool_name: Name of the tool to call (e.g. ``strata_read_active``).
            arguments: Tool arguments dict.

        Returns:
            A JSON-RPC result response string.
        """
        try:
            result = self.strata.tools.execute(tool_name, arguments)
            content = []
            if "error" in result:
                content.append({"type": "text", "text": f"Error: {result['error']}"})
                return rpc_result(req_id, {"isError": True, "content": content})

            text = json.dumps(result, indent=2)
            content.append({"type": "text", "text": text})
            return rpc_result(req_id, {"content": content})
        except Exception as exc:
            return rpc_result(
                req_id,
                {
                    "isError": True,
                    "content": [{"type": "text", "text": str(exc)}],
                },
            )

    def run_stdio(self):
        """Run the MCP server over stdio (line-delimited JSON)."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            response = self._handle_request(line)
            if response is not None:
                sys.stdout.write(response + "\n")
                sys.stdout.flush()

    def run_once(self, request: str) -> str:
        """Process a single request string and return the response. Useful for testing."""
        response = self._handle_request(request.strip())
        return response or ""

    def close(self):
        """Close the Strata instance and release resources."""
        self.strata.close()


def main_stdio():
    """Entry point for stdio MCP server. Called via 'strata mcp'."""
    server = MCPServer()
    try:
        server.run_stdio()
    finally:
        server.close()
