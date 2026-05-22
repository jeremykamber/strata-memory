from pathlib import Path


class TestStratum3Storage:

    def test_archive_and_search_shadow(self, stratum_3, tmp_base):
        src = tmp_base / "test.md"
        src.write_text("# Koda platform v2 with React frontend")
        archive_path = stratum_3.archive_file(src, "projects/koda.md", tags=["koda", "react"])
        assert archive_path.endswith(".json")

        results = stratum_3.search_shadow("react")
        assert len(results) >= 1

    def test_search_shadow_by_tags(self, stratum_3, tmp_base):
        src = tmp_base / "funding.md"
        src.write_text("# Funding round closed for Kynd")
        stratum_3.archive_file(src, "projects/kynd.md", tags=["kynd", "funding"])

        results = stratum_3.search_shadow_by_tags(["funding"])
        assert len(results) >= 1
        assert "Funding" in results[0].get("summary_preview", "")

    def test_hydrate(self, stratum_3, tmp_base):
        src = tmp_base / "design.md"
        src.write_text("# Design system migration")
        stratum_3.archive_file(src, "design/ui.md", tags=["design", "ui"])

        shadow_results = stratum_3.search_shadow("design")
        assert len(shadow_results) >= 1

        hydrated = stratum_3.hydrate(shadow_results[0])
        assert hydrated is not None
        assert hydrated["original_path"] == "design/ui.md"
        assert "# Design system migration" in hydrated["content"]

    def test_hydrate_missing_file(self, stratum_3):
        entry = {
            "id": "test-id",
            "original_path": "test-mid",
            "archive_path": "/nonexistent/file.json",
            "keywords": "[]",
            "summary_preview": "",
            "evicted_at": "2025-01-01",
        }
        result = stratum_3.hydrate(entry)
        assert result is None

    def test_get_shadow_count(self, stratum_3, tmp_base):
        assert stratum_3.get_shadow_count() == 0
        src = tmp_base / "count.md"
        src.write_text("# Count test")
        stratum_3.archive_file(src, "count.md")
        assert stratum_3.get_shadow_count() == 1

    def test_archive_preserves_content(self, stratum_3, tmp_base):
        src = tmp_base / "plan.md"
        src.write_text("# Full content preserved")
        stratum_3.archive_file(src, "projects/kynd/plan.md", tags=["kynd"])

        results = stratum_3.search_shadow("kynd")
        assert len(results) >= 1
        hydrated = stratum_3.hydrate(results[0])
        assert hydrated is not None
        assert hydrated["original_path"] == "projects/kynd/plan.md"
        assert "# Full content preserved" in hydrated["content"]
