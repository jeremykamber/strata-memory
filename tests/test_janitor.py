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

    def test_promote_2_to_1_dry_run(self, stratum_1, stratum_2, janitor):
        stratum_1.write("projects/hot.md", "# Hot file")
        janitor.migrate_1_to_2(dry_run=False)
        assert stratum_2.path_exists("projects/hot.md")

        # Track accesses to exceed promotion_threshold (default: 3)
        for _ in range(3):
            janitor.s2.track_access("projects/hot.md")

        results = janitor.promote_2_to_1(dry_run=True)
        promoted = [r for r in results if r["status"] == "would_promote"]
        assert len(promoted) >= 1
        assert promoted[0]["path"] == "projects/hot.md"
        # File should still be in cooled during dry run
        assert stratum_2.path_exists("projects/hot.md")

    def test_promote_2_to_1(self, stratum_1, stratum_2, janitor):
        stratum_1.write("projects/hot.md", "# Hot file content")
        janitor.migrate_1_to_2(dry_run=False)
        assert stratum_2.path_exists("projects/hot.md")

        # Track accesses to exceed promotion_threshold (default: 3)
        for _ in range(3):
            janitor.s2.track_access("projects/hot.md")

        results = janitor.promote_2_to_1(dry_run=False)
        promoted = [r for r in results if r["status"] == "promoted"]
        assert len(promoted) >= 1
        assert promoted[0]["path"] == "projects/hot.md"
        # File should be back in active
        assert stratum_1.path_exists("projects/hot.md")
        assert not stratum_2.path_exists("projects/hot.md")
        # Content should be preserved
        content = stratum_1.read("projects/hot.md")
        assert "Hot file content" in content

    def test_promote_skips_cold(self, stratum_1, stratum_2, janitor):
        stratum_1.write("projects/cold.md", "# Cold file")
        janitor.migrate_1_to_2(dry_run=False)
        assert stratum_2.path_exists("projects/cold.md")

        # Only 1 access, below threshold of 3
        janitor.s2.track_access("projects/cold.md")

        results = janitor.promote_2_to_1(dry_run=False)
        promoted = [r for r in results if r["status"] == "promoted"]
        assert len(promoted) == 0
        # File should stay in cooled
        assert stratum_2.path_exists("projects/cold.md")

    def test_rehydrate_to_cooled(self, stratum_1, stratum_2, stratum_3, janitor):
        stratum_1.write("projects/ref.md", "# Reference memory")
        janitor.migrate_1_to_2(dry_run=False)
        janitor.evict_2_to_3(dry_run=False)

        shadow_results = stratum_3.search_shadow("reference")
        assert len(shadow_results) >= 1

        # Rehydrate to cooled (2nd stratum)
        data = janitor.rehydrate(shadow_results[0], target_tier="cooled")
        assert data is not None
        assert "# Reference memory" in data.get("content", "")
        # File should be in cooled, not active
        assert stratum_2.path_exists("projects/ref.md")
        assert not stratum_1.path_exists("projects/ref.md")

    def test_run_maintenance_promotes_before_migrate(
        self, stratum_1, stratum_2, janitor, config
    ):
        # Write a file and migrate it to cooled (threshold is 0 from fixture)
        stratum_1.write("projects/rotating.md", "# Rotating content")
        janitor.migrate_1_to_2(dry_run=False)
        assert stratum_2.path_exists("projects/rotating.md")

        # Access it enough to trigger promotion
        for _ in range(3):
            janitor.s2.track_access("projects/rotating.md")

        # Raise migration threshold so promoted file stays put
        config.decay_thresholds["*"] = 100

        # Full maintenance should promote it back, not re-migrate
        result = janitor.run_maintenance(dry_run=False)
        assert result["total_promoted"] >= 1
        assert result["total_migrated"] == 0
        # File should be back in active
        assert stratum_1.path_exists("projects/rotating.md")
        assert not stratum_2.path_exists("projects/rotating.md")
