class TestStratum2Storage:

    def test_write_and_read(self, stratum_2):
        stratum_2.write("projects/test.md", "# Test\ncontent")
        assert stratum_2.read("projects/test.md") == "# Test\ncontent"

    def test_write_creates_dirs(self, stratum_2):
        stratum_2.write("projects/deep/nested/file.md", "hello")
        assert stratum_2.read("projects/deep/nested/file.md") == "hello"

    def test_read_nonexistent(self, stratum_2):
        import pytest
        with pytest.raises(FileNotFoundError):
            stratum_2.read("nonexistent.md")

    def test_delete(self, stratum_2):
        stratum_2.write("projects/tmp.md", "delete me")
        assert stratum_2.delete("projects/tmp.md") is True

    def test_path_traversal_blocked(self, stratum_2):
        import pytest
        with pytest.raises(ValueError):
            stratum_2.read("../etc/passwd")

    def test_list_all(self, stratum_2):
        stratum_2.write("projects/a.md", "a")
        stratum_2.write("projects/b.md", "b")
        entries = stratum_2.list_all()
        assert len(entries) == 2

    def test_count(self, stratum_2):
        assert stratum_2.count() == 0
        stratum_2.write("projects/a.md", "a")
        assert stratum_2.count() == 1

    def test_move_from(self, stratum_2, tmp_base):
        src = tmp_base / "source.md"
        src.write_text("# Moved content")
        result = stratum_2.move_from(src, "moved/file.md")
        assert stratum_2.read("moved/file.md") == "# Moved content"

    def test_ensure_dirs_idempotent(self, stratum_2):
        stratum_2.ensure_dirs()
        stratum_2.ensure_dirs()

    def test_path_exists(self, stratum_2):
        stratum_2.write("projects/exists.md", "yep")
        assert stratum_2.path_exists("projects/exists.md") is True
        assert stratum_2.path_exists("nope.md") is False

    def test_delete_nonexistent(self, stratum_2):
        assert stratum_2.delete("nope.md") is False
