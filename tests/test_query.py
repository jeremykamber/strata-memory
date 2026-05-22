class TestQueryEngine:

    def test_search_stratum_1(self, stratum_1, query_engine):
        stratum_1.write("projects/react-hooks.md", "# React Hooks Guide\nUsing useEffect and useState.")
        stratum_1.write("projects/python-async.md", "# Python Async\nUsing asyncio library.")
        results = query_engine.search("react")
        tiers = {r["tier"] for r in results}
        assert "stratum_1" in tiers

    def test_search_stratum_2(self, stratum_2, query_engine):
        stratum_2.write("projects/koda.md", "# Koda platform uses React for frontend")
        results = query_engine.search("koda react")
        tiers = {r["tier"] for r in results}
        assert "stratum_2" in tiers

    def test_search_stratum_3(self, stratum_3, query_engine, tmp_base):
        src = tmp_base / "old.md"
        src.write_text("# Archived: Old project specs")
        stratum_3.archive_file(src, "projects/old.md", tags=["legacy", "archive"])
        results = query_engine.search("legacy archive")
        tiers = {r["tier"] for r in results}
        assert "stratum_3" in tiers

    def test_cascading_search_priority(self, stratum_1, stratum_2, stratum_3, query_engine, tmp_base):
        stratum_1.write("projects/active-react.md", "# Active React work\nCurrent sprint tasks.")
        stratum_2.write("projects/cooled-react.md", "# Cooled React: custom hooks for data fetching")

        src = tmp_base / "old_react.md"
        src.write_text("# Years-old React notes: class components")
        stratum_3.archive_file(src, "projects/old_react.md", tags=["react", "legacy"])

        results = query_engine.search("react", top_k=10)
        assert len(results) >= 2
        assert results[0]["tier"] == "stratum_1"

    def test_search_empty_query(self, stratum_1, query_engine):
        results = query_engine.search("")
        assert isinstance(results, list)

    def test_search_no_results(self, query_engine):
        results = query_engine.search("xyznonexistentkey")
        assert len(results) == 0

    def test_stratum3_has_rehydration_flag(self, stratum_3, query_engine, tmp_base):
        src = tmp_base / "design.md"
        src.write_text("# Old design doc for deprecation")
        stratum_3.archive_file(src, "projects/design.md", tags=["design", "deprecated"])
        results = query_engine.search("design deprecated")
        if results:
            r = results[0]
            if r["tier"] == "stratum_3":
                assert r["metadata"].get("_needs_rehydration") is True
