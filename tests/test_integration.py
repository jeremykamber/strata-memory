from pathlib import Path

from strata import Strata
from strata.cli import main
from strata.config import StrataConfig


class TestStrataIntegration:
    def test_full_lifecycle(self, tmp_base):
        config = StrataConfig(
            base_dir=tmp_base,
            decay_thresholds={"*": 0},
            lru_days=0,
            lru_decay_thresholds={"*": 0},
        )
        strata = Strata(config)

        strata.write_active(
            "projects/kynd/requirements.md",
            "# Kynd Requirements\n\n- User auth via OAuth2\n- Dashboard with real-time updates\n- Payment processing via Stripe",
        )
        strata.write_active(
            "entities/joe.md",
            "# Joe Smith\n\nRole: Software Engineer\nSkills: React, Go, PostgreSQL",
        )

        entries = strata.list_active("projects")
        assert any(e["name"] == "kynd" for e in entries)

        migrated = strata.migrate(dry_run=False)
        assert len(migrated) >= 1

        files = strata.s2.list_all()
        assert len(files) >= 1

        query_results = strata.query("kynd requirements")
        assert len(query_results) >= 1
        assert query_results[0]["tier"] in ("stratum_1", "stratum_2")

        evicted = strata.evict(dry_run=False)
        assert len(evicted) >= 1

        query_archive = strata.query("kynd")
        assert len(query_archive) >= 1

        strata.close()

    def test_context_manager(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        with Strata(config) as s:
            s.write_active("projects/test.md", "# Test")
            assert s.read_active("projects/test.md") == "# Test"

    def test_query_tool_schema(self):
        config = StrataConfig(base_dir="/tmp/strata_test_schema")
        with Strata(config) as s:
            schema = s.query_tool_schema()
            assert schema["type"] == "function"
            assert "strata_query" in schema["function"]["name"]

    def test_tool_execution(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        with Strata(config) as s:
            result = s.tools.execute(
                "strata_write_active",
                {"path": "projects/test.md", "content": "# Tool test"},
            )
            assert result["status"] == "written"

            result = s.tools.execute("strata_read_active", {"path": "projects/test.md"})
            assert result["content"] == "# Tool test"

            result = s.tools.execute("strata_list_active", {"path": "projects"})
            assert len(result["entries"]) >= 1

            result = s.tools.execute("strata_query", {"query": "tool test"})
            assert "results" in result

    def test_unknown_tool(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        with Strata(config) as s:
            result = s.tools.execute("nonexistent_tool", {})
            assert "error" in result

    def test_cli_full_lifecycle(self, tmp_base, monkeypatch, capsys):
        monkeypatch.chdir(tmp_base)

        main(["init", "--non-interactive"])
        captured = capsys.readouterr()
        assert "Initialized" in captured.out
        assert (tmp_base / "strata_data" / "active" / "projects").exists()

        main(["config", "get", "search_backend"])
        captured = capsys.readouterr()
        assert captured.out.strip()

        main(["add", "projects/test.md", "# Test memory"])
        captured = capsys.readouterr()
        assert "Written" in captured.out
        assert (tmp_base / "strata_data" / "active" / "projects" / "test.md").exists()

        main(["search", "test"])
        captured = capsys.readouterr()
        assert "test" in captured.out or "ACTIVE" in captured.out

        main(["maintenance"])
        main(["status"])
        captured = capsys.readouterr()
        assert "Stratum" in captured.out

    def test_search_fallback_without_qmd(self, tmp_base, monkeypatch, capsys):
        """Search without QMD installed should fall back to filesystem grep."""
        monkeypatch.chdir(tmp_base)

        main(["init", "--non-interactive"])
        main(["add", "projects/fallback.md", "Fallback content"])
        main(["search", "fallback"])
        captured = capsys.readouterr()
        assert "fallback" in captured.out or "ACTIVE" in captured.out

    def test_pi_extension_file_exists(self):
        """Verify the Pi extension TypeScript file exists and has valid structure."""
        pi_path = Path(__file__).parent.parent / "skills" / "pi" / "strata.ts"

        assert pi_path.exists(), f"Pi extension not found at {pi_path}"
        content = pi_path.read_text()
        assert "import type { ExtensionAPI }" in content
        assert "export default function" in content
        assert 'pi.on("before_agent_start"' in content
        assert 'pi.on("agent_end"' in content
