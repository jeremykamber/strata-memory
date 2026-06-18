"""CLI tests using strata.cli.main with injected argv."""

import json
from pathlib import Path
from typing import List, Optional
from strata.cli import main


def test_cli_init(tmp_base, monkeypatch):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    assert (tmp_base / "strata_data" / "active" / "projects").exists()
    assert (tmp_base / "strata_data" / "active" / "entities").exists()
    assert (tmp_base / "strata_data" / "active" / "gtd").exists()


def test_cli_init_shows_daemon_mention(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    captured = capsys.readouterr()
    assert "daemon" in captured.out or "serve" in captured.out


def test_cli_init_non_interactive(tmp_base, monkeypatch, capsys):

    monkeypatch.chdir(tmp_base)
    main(["init", "--non-interactive"])
    captured = capsys.readouterr()
    assert "Select search backend" not in captured.out
    assert (tmp_base / "strata_data" / "active" / "projects").exists()
    config_path = tmp_base / "strata_data" / "strata.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data.get("search_backend") == "qmd"


def test_cli_init_qmd_onboarding_fts5(tmp_base, monkeypatch):
    import sys
    from io import StringIO

    class _TTYStringIO(StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", _TTYStringIO("3\n"))
    monkeypatch.chdir(tmp_base)
    main(["init"])
    config_path = tmp_base / "strata_data" / "strata.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data.get("search_backend") == "fts5"


def test_cli_init_npx_failure(tmp_base, monkeypatch, capsys):
    import subprocess
    import sys
    from io import StringIO

    class _TTYStringIO(StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", _TTYStringIO("1\n"))
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()),
    )
    monkeypatch.chdir(tmp_base)
    main(["init"])
    captured = capsys.readouterr()
    assert "npx not found" in captured.out
    config_path = tmp_base / "strata_data" / "strata.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data.get("search_backend") == "fts5"


def test_cli_help(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main([])
    captured = capsys.readouterr()
    assert "strata init" in captured.out


def test_cli_unknown_command(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    try:
        main(["bogus"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "Unknown command" in captured.out


def test_cli_add_path_content(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "projects/test.md", "# Test content"])
    captured = capsys.readouterr()
    assert "Written" in captured.out
    assert (tmp_base / "strata_data" / "active" / "projects" / "test.md").exists()


def test_cli_add_stdin(tmp_base, monkeypatch):
    monkeypatch.chdir(tmp_base)
    import sys
    from io import StringIO
    monkeypatch.setattr(sys, "stdin", StringIO("# Stdin content"))
    main(["init"])
    main(["add", "projects/stdin_test.md"])
    assert (tmp_base / "strata_data" / "active" / "projects" / "stdin_test.md").exists()


def test_cli_add_text(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "--text", "Quick note about something"])
    captured = capsys.readouterr()
    assert "Written" in captured.out


def test_cli_read(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "projects/readme.md", "Hello world"])
    main(["read", "projects/readme.md"])
    captured = capsys.readouterr()
    assert "Hello world" in captured.out


def test_cli_read_nonexistent(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    try:
        main(["read", "nonexistent.md"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_cli_list(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "projects/a.md", "a"])
    main(["list", "projects"])
    captured = capsys.readouterr()
    assert "a.md" in captured.out


def test_cli_search(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "projects/searchable.md", "This is searchable content"])
    main(["search", "searchable"])
    captured = capsys.readouterr()
    assert "searchable" in captured.out or "ACTIVE" in captured.out


def test_cli_query_json(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "projects/query_test.md", "Query test content"])
    main(["query", "query_test"])
    captured = capsys.readouterr()
    assert "tier" in captured.out


def test_cli_status(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["status"])
    captured = capsys.readouterr()
    assert "1st Stratum" in captured.out


def test_cli_config(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["config"])
    captured = capsys.readouterr()
    assert "base_dir" in captured.out
    assert "Decay thresholds" in captured.out


def test_cli_migrate_dry_run(tmp_base, monkeypatch):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "projects/migrate_me.md", "Old content"])
    main(["migrate", "--dry-run"])


def test_cli_list_stratum_2(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["list-stratum-2"])
    captured = capsys.readouterr()
    assert "No 2nd Stratum files" in captured.out or "Empty" in captured.out


def test_cli_history_no_log(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["history"])
    captured = capsys.readouterr()
    assert "No daemon log" in captured.out


def test_cli_forget_nonexistent(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    try:
        main(["forget", "nonexistent-id"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_cli_serve_help(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["serve", "--help"])
    captured = capsys.readouterr()
    assert "--interval" in captured.out


def test_cli_migrate(tmp_base, monkeypatch):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "projects/stale.md", "Stale content for migration"])
    main(["migrate"])


def test_cli_evict_dry_run(tmp_base, monkeypatch):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["evict", "--dry-run"])


def test_cli_maintenance(tmp_base, monkeypatch):
    monkeypatch.chdir(tmp_base)
    main(["init"])
    main(["add", "projects/maintenance_test.md", "Content"])
    main(["maintenance", "--dry-run"])


def _fake_npx_cmd(tmp_path, monkeypatch, extra_args: Optional[List[str]] = None) -> List[str]:
    """Run strata skill install with mocks and return the npx command that would execute."""
    import shutil
    import subprocess

    skill_dir = tmp_path / "skills" / "strata"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: strata-memory\ndescription: test\n---")

    from strata import cli as strata_cli
    monkeypatch.setattr(strata_cli, "_find_skill_dir", lambda: skill_dir)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/npx")

    captured_cmd: List[str] = []

    def fake_run(cmd, **kwargs):
        captured_cmd[:] = cmd
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    args = ["skill", "install"]
    if extra_args:
        args.extend(extra_args)
    main(args)
    return captured_cmd


def test_cli_skill_no_args(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    main(["skill"])
    captured = capsys.readouterr()
    assert "Usage" in captured.out or "install" in captured.out


def test_cli_skill_install_default(tmp_path, monkeypatch, capsys):
    cmd = _fake_npx_cmd(tmp_path, monkeypatch)
    assert "npx" in cmd
    assert "skills@latest" in cmd
    assert "add" in cmd
    assert "--all" not in cmd
    assert "-g" not in cmd
    captured = capsys.readouterr()
    assert "interactive" in captured.out


def test_cli_skill_install_global(tmp_path, monkeypatch, capsys):
    cmd = _fake_npx_cmd(tmp_path, monkeypatch, ["--global"])
    assert "--all" in cmd
    assert "-g" in cmd
    assert "-y" in cmd
    captured = capsys.readouterr()
    assert "global" in captured.out


def test_cli_skill_install_no_npx(tmp_base, monkeypatch, capsys):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)
    from strata import cli as strata_cli
    skill_dir = tmp_base / "skills" / "strata"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: strata-memory\ndescription: test\n---")
    monkeypatch.setattr(strata_cli, "_find_skill_dir", lambda: skill_dir)

    try:
        main(["skill", "install"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "npx" in captured.err or "Node.js" in captured.err


def test_cli_skill_bogus_subcommand(tmp_base, monkeypatch, capsys):
    monkeypatch.chdir(tmp_base)
    try:
        main(["skill", "bogus"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "Unknown" in captured.out or "bogus" in captured.out


def test_pi_install_no_pi(tmp_path, monkeypatch, capsys):
    """pi-install errors when pi CLI is not on PATH."""
    import shutil
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    try:
        main(["pi-install"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "pi" in captured.err


def test_pi_install_file_copy(tmp_path, monkeypatch, capsys):
    """pi-install copies the extension file to the correct destination."""
    import shutil
    from strata import cli as strata_cli

    src = tmp_path / "skills" / "pi" / "strata.ts"
    src.parent.mkdir(parents=True)
    src.write_text("export default function() {}")

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/pi" if cmd == "pi" else None)
    monkeypatch.setattr(strata_cli, "_find_pi_skill_dir", lambda: src)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    main(["pi-install", "--force"])

    dst = tmp_path / ".pi" / "agent" / "extensions" / "strata.ts"
    assert dst.exists()
    assert dst.read_text() == "export default function() {}"
    captured = capsys.readouterr()
    assert "installed" in captured.out


def test_pi_install_directory_creation(tmp_path, monkeypatch):
    """pi-install creates the extensions directory if it doesn't exist."""
    import shutil
    from strata import cli as strata_cli

    src = tmp_path / "skills" / "pi" / "strata.ts"
    src.parent.mkdir(parents=True)
    src.write_text("export default function() {}")

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/pi" if cmd == "pi" else None)
    monkeypatch.setattr(strata_cli, "_find_pi_skill_dir", lambda: src)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    main(["pi-install", "--force"])

    ext_dir = tmp_path / ".pi" / "agent" / "extensions"
    assert ext_dir.is_dir()


def test_pi_install_force_overwrite(tmp_path, monkeypatch, capsys):
    """pi-install --force overwrites an existing strata.ts without prompting."""
    import shutil
    from strata import cli as strata_cli

    src = tmp_path / "skills" / "pi" / "strata.ts"
    src.parent.mkdir(parents=True)
    src.write_text("new content")

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/pi" if cmd == "pi" else None)
    monkeypatch.setattr(strata_cli, "_find_pi_skill_dir", lambda: src)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    dst = tmp_path / ".pi" / "agent" / "extensions" / "strata.ts"
    dst.parent.mkdir(parents=True)
    dst.write_text("old content")

    main(["pi-install", "--force"])

    assert dst.read_text() == "new content"


def test_pi_install_overwrite_abort(tmp_path, monkeypatch, capsys):
    """pi-install without --force aborts when user declines overwrite."""
    import shutil
    from strata import cli as strata_cli

    src = tmp_path / "skills" / "pi" / "strata.ts"
    src.parent.mkdir(parents=True)
    src.write_text("new content")

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/pi" if cmd == "pi" else None)
    monkeypatch.setattr(strata_cli, "_find_pi_skill_dir", lambda: src)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    dst = tmp_path / ".pi" / "agent" / "extensions" / "strata.ts"
    dst.parent.mkdir(parents=True)
    dst.write_text("old content")

    main(["pi-install"])

    assert dst.read_text() == "old content"
    captured = capsys.readouterr()
    assert "Aborted" in captured.out
