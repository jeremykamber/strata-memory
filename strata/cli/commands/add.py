"""Add content to 1st Stratum active memory."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from strata import Strata
from strata.cli._config import load_config
from strata.cli._json import is_json_mode, json_error, json_print

name = "add"


def run(args: list[str]) -> None:
    """Add content to 1st Stratum active memory.

    Usage:
        strata add projects/kynd/notes.md "Some content here"
        echo "content" | strata add projects/kynd/notes.md
        strata add --file /path/to/file.md projects/kynd/notes.md
        strata add --text "Quick memory note"    # auto-routed to quick-note-<ts>.md
    """
    config = load_config()

    # Parse --file flag
    file_content = None
    filtered: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--file" and i + 1 < len(args):
            try:
                file_content = Path(args[i + 1]).read_text()
            except FileNotFoundError:
                if is_json_mode():
                    json_error("add", f"File not found: {args[i + 1]}")
                print(f"File not found: {args[i + 1]}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                if is_json_mode():
                    json_error("add", str(e))
                print(f"Error reading file: {e}", file=sys.stderr)
                sys.exit(1)
            i += 2
        else:
            filtered.append(args[i])
            i += 1
    args = filtered

    with Strata(config) as s:
        if not args:
            if file_content is not None:
                path = f"quick-note-{time.monotonic_ns()}.md"
                s.write_active(path, file_content)
                written_path = str(s.s1._root / path)
                if is_json_mode():
                    json_print(
                        "add",
                        {
                            "path": path,
                            "file": str(s.s1._root / path),
                            "written": True,
                        },
                    )
                    return
                print(f"Written to: {written_path}")
                return
            # Read from stdin
            content = sys.stdin.read().strip()
            if not content:
                if is_json_mode():
                    json_error("add", "No content provided")
                print("No content provided. Pipe content or pass path + content.")
                print("  echo 'my note' | strata add projects/notes.md")
                return
            path = f"quick-note-{time.monotonic_ns()}.md"
            s.write_active(path, content)
            written_path = str(s.s1._root / path)
            if is_json_mode():
                json_print("add", {"path": path, "file": written_path, "written": True})
                return
            print(f"Written to: {written_path}")
            return

        if args[0] == "--text" and len(args) >= 2:
            path = f"quick-note-{time.monotonic_ns()}.md"
            content = " ".join(args[1:])
            s.write_active(path, content)
            written_path = str(s.s1._root / path)
            if is_json_mode():
                json_print("add", {"path": path, "file": written_path, "written": True})
                return
            print(f"Written to: {written_path}")
            return

        # Priority: inline text arg > --file > stdin
        if len(args) >= 2:
            path = args[0]
            content = " ".join(args[1:])
        elif file_content is not None:
            path = args[0]
            content = file_content
        else:
            path = args[0]
            content = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
            if not content:
                if is_json_mode():
                    json_error("add", "No content provided")
                print("Provide content as second argument or pipe it:")
                print(f"  strata add {path} 'your content'")
                print(f"  echo 'your content' | strata add {path}")
                return

        s.write_active(path, content)
        written_path = str(s.s1._root / path)
        if is_json_mode():
            json_print("add", {"path": path, "file": written_path, "written": True})
            return
        print(f"Written to: {written_path}")
