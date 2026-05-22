class TestJanitor:

    def test_migrate_1_to_2_dry_run(self, stratum_1, stratum_2, janitor):
        stratum_1.write("projects/test.md", "# Test\nSome content here.")
        stratum_1.write("projects/active.md", "# Active\nStill relevant.")
        results = janitor.migrate_1_to_2(dry_run=True)
        assert len(results) > 0
        assert results[0]["status"] == "would_migrate"

    def test_migrate_1_to_2(self, stratum_1, stratum_2, janitor):
        stratum_1.write("projects/stale.md", "# Stale\nThis file is old.")
        results = janitor.migrate_1_to_2(dry_run=False)
        assert len(results) >= 1
        assert results[0]["status"] == "migrated"
        assert not stratum_1.path_exists("projects/stale.md")
        assert stratum_2.path_exists("projects/stale.md")

    def test_migrate_skips_active(self, stratum_1, stratum_2, janitor, config):
        config.decay_thresholds["*"] = 100
        stratum_1.write("projects/fresh.md", "# Fresh\nNew content.")
        results = janitor.migrate_1_to_2()
        migrated = [r for r in results if r["status"] == "migrated"]
        assert len(migrated) == 0

    def test_evict_2_to_3_dry_run(self, stratum_2, stratum_3, janitor):
        stratum_2.write("projects/old.md", "# Old content")
        results = janitor.evict_2_to_3(dry_run=True)
        assert len(results) >= 1
        assert results[0]["status"] == "would_evict"

    def test_evict_2_to_3(self, stratum_2, stratum_3, janitor):
        stratum_2.write("projects/old.md", "# Old content")
        results = janitor.evict_2_to_3(dry_run=False)
        assert len(results) >= 1
        assert results[0]["status"] == "evicted"
        assert not stratum_2.path_exists("projects/old.md")

    def test_rehydrate(self, stratum_1, stratum_2, stratum_3, janitor, tmp_base):
        stratum_1.write("projects/test.md", "# Archived memory")
        janitor.migrate_1_to_2(dry_run=False)
        janitor.evict_2_to_3(dry_run=False)

        shadow_results = stratum_3.search_shadow("archived")
        assert len(shadow_results) >= 1

        data = janitor.rehydrate(shadow_results[0])
        assert data is not None
        assert "# Archived memory" in data.get("content", "")
        assert stratum_1.path_exists("projects/test.md")

    def test_infer_tags(self, janitor):
        tags = janitor._infer_tags("projects/kynd-dashboard/requirements.md")
        assert "projects" in tags

    def test_evict_removes_from_s2(self, stratum_2, stratum_3, janitor):
        stratum_2.write("projects/removable.md", "# Removable")
        janitor.evict_2_to_3(dry_run=False)
        assert not stratum_2.path_exists("projects/removable.md")
