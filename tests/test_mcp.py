"""Tests for MCP server implementation."""

import json
import tempfile
from pathlib import Path

import pytest

from strata.config import StrataConfig
from strata.mcp_server import MCPServer


@pytest.fixture
def mcp_server(tmp_base):
    config = StrataConfig(base_dir=tmp_base)
    server = MCPServer(config)
    yield server
    server.close()


class TestMCPServer:

    def test_initialize(self, mcp_server):
        req = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}'
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        result = data["result"]
        assert result["serverInfo"]["name"] == "strata-memory"
        assert "tools" in result["capabilities"]

    def test_tools_list(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        tools = data["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "strata_read_active" in tool_names
        assert "strata_write_active" in tool_names
        assert "strata_list_active" in tool_names
        assert "strata_query" in tool_names
        assert "strata_forget" in tool_names

    def test_tools_call_read_error(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"strata_read_active","arguments":{"path":"nonexistent.md"}}}'
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert "result" in data
        assert "content" in data["result"]

    def test_tools_call_write(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "strata_write_active",
                "arguments": {"path": "projects/test.md", "content": "# MCP test"},
            },
        })
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert "result" in data
        content_str = data["result"]["content"][0]["text"]
        assert "written" in content_str

    def test_tools_call_query(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "strata_query",
                "arguments": {"query": "test"},
            },
        })
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert "result" in data

    def test_tools_list_has_schemas(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        tools = data["result"]["tools"]
        for t in tools:
            assert "name" in t
            assert "description" in t
            assert "inputSchema" in t
            assert "properties" in t["inputSchema"]

    def test_method_not_found(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = '{"jsonrpc":"2.0","id":2,"method":"bogus","params":{}}'
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert "error" in data
        assert data["error"]["code"] == -32601

    def test_parse_error(self, mcp_server):
        resp = mcp_server.run_once("not json at all")
        data = json.loads(resp)
        assert "error" in data
        assert data["error"]["code"] == -32700

    def test_not_initialized(self, mcp_server):
        req = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert "error" in data
        assert data["error"]["code"] == -32000

    def test_resources_list(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = '{"jsonrpc":"2.0","id":2,"method":"resources/list","params":{}}'
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert data["result"]["resources"] == []

    def test_shutdown(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = '{"jsonrpc":"2.0","id":2,"method":"shutdown","params":{}}'
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert data["result"] is None

    def test_unknown_tool_call(self, mcp_server):
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        mcp_server.run_once(init)
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {},
            },
        })
        resp = mcp_server.run_once(req)
        data = json.loads(resp)
        assert "content" in data["result"]
