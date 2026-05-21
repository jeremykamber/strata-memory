from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strata import Strata


class StrataTools:
    """Agent tool definitions in OpenAI-compatible function calling format.

    These tools give any LLM agent a standard interface to interact with
    the Strata memory system, regardless of harness (OpenAI, Anthropic,
    OpenClaw, custom).
    """

    def __init__(self, strata: "Strata"):
        self.strata = strata

    def all_schemas(self) -> list[dict]:
        return [
            self.read_active_schema(),
            self.write_active_schema(),
            self.list_active_schema(),
            self.query_schema(),
            self.forget_schema(),
        ]

    def read_active_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "strata_read_active",
                "description": "Read a file from the 1st Stratum (active memory). Use for current project context, active entities, GTD tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to the active directory (e.g. 'projects/kynd/requirements.md')",
                        }
                    },
                    "required": ["path"],
                },
            },
        }

    def write_active_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "strata_write_active",
                "description": "Write a file to the 1st Stratum (active memory). Creates parent directories as needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to the active directory (e.g. 'projects/kynd/notes.md')",
                        },
                        "content": {
                            "type": "string",
                            "description": "Full file content to write",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        }

    def list_active_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "strata_list_active",
                "description": "List files and directories in the 1st Stratum (active memory). Use to discover available context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path relative to active root (default: root)",
                            "default": "",
                        }
                    },
                },
            },
        }

    def query_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "strata_query",
                "description": "Search across all memory tiers (1st Stratum active files, 2nd Stratum cooled, 3rd Stratum archive). Uses hybrid BM25 + vector search when QMD is available.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional entity tags to filter by (e.g. ['kynd', 'react', 'funding'])",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum results to return per tier",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    def forget_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "strata_forget",
                "description": "Explicitly move a file from the 2nd Stratum (cooled) to the 3rd (cold archive). Use when the agent knows data is no longer needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path in the cooled directory to archive (from strata_query results)",
                        },
                    },
                    "required": ["path"],
                },
            },
        }

    def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name with the given arguments."""
        handlers = {
            "strata_read_active": self._handle_read_active,
            "strata_write_active": self._handle_write_active,
            "strata_list_active": self._handle_list_active,
            "strata_query": self._handle_query,
            "strata_forget": self._handle_forget,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return handler(arguments)
        except Exception as exc:
            return {"error": str(exc)}

    def _handle_read_active(self, args: dict) -> dict:
        content = self.strata.read_active(args["path"])
        return {"content": content}

    def _handle_write_active(self, args: dict) -> dict:
        path = self.strata.write_active(args["path"], args["content"])
        return {"path": path, "status": "written"}

    def _handle_list_active(self, args: dict) -> dict:
        entries = self.strata.list_active(args.get("path", ""))
        return {"entries": entries}

    def _handle_query(self, args: dict) -> dict:
        results = self.strata.query(
            args["query"],
            filters={"tags": args.get("tags")},
            top_k=args.get("top_k", 5),
        )
        return {"results": results}

    def _handle_forget(self, args: dict) -> dict:
        path = args["path"]
        source = self.strata.s2._root / path
        if not source.exists():
            return {"error": f"File not found in 2nd Stratum: {path}"}
        tags = [path.split("/")[0]] if "/" in path else []
        archive_path = self.strata.s3.archive_file(source, path, tags=tags)
        source.unlink()
        return {"path": path, "archive_path": archive_path, "status": "archived"}
