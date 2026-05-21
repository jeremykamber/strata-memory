"""Minimal MCP (Model Context Protocol) server for Strata.

Implements the MCP protocol over stdio (JSON-RPC 2.0, line-delimited).
Zero external dependencies — uses only Python stdlib.

The MCP protocol spec: https://modelcontextprotocol.io
"""

from __future__ import annotations

import json
import sys
from typing import Optional

from strata import Strata
from strata.config import StrataConfig, detect_base_dir


def rpc_error(id_val, code: int, message: str, data=None) -> str:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return json.dumps({"jsonrpc": "2.0", "id": id_val, "error": err})


def rpc_result(id_val, result) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_val, "result": result})


def rpc_notification(method: str, params=None) -> str:
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
            tools.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "inputSchema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
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
            return rpc_result(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "serverInfo": {
                    "name": "strata-memory",
                    "version": "0.1.0",
                },
            })

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
            return rpc_result(req_id, {
                "isError": True,
                "content": [{"type": "text", "text": str(exc)}],
            })

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
        self.strata.close()


def main_stdio():
    """Entry point for stdio MCP server. Called via 'strata mcp'."""
    server = MCPServer()
    try:
        server.run_stdio()
    finally:
        server.close()
