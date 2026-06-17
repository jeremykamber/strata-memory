

class TestStratum1Storage:

    def test_write_and_read(self, stratum_1):
        path = "projects/test.md"
        content = "# Test Project\nThis is a test."
        result = stratum_1.write(path, content)
        assert result.endswith(path)
        assert stratum_1.read(path) == content

    def test_write_creates_dirs(self, stratum_1):
        result = stratum_1.write("projects/deep/nested/file.md", "hello")
        assert stratum_1.read("projects/deep/nested/file.md") == "hello"

    def test_read_nonexistent(self, stratum_1):
        import pytest
        with pytest.raises(FileNotFoundError):
            stratum_1.read("nonexistent.md")

    def test_list_dir(self, stratum_1):
        stratum_1.write("projects/a.md", "a")
        stratum_1.write("projects/b.md", "b")
        stratum_1.write("entities/c.md", "c")
        entries = stratum_1.list_dir("projects")
        names = {e["name"] for e in entries}
        assert "a.md" in names
        assert "b.md" in names
        assert "c.md" not in names

    def test_list_dir_root(self, stratum_1):
        stratum_1.write("projects/x.md", "x")
        entries = stratum_1.list_dir()
        names = {e["name"] for e in entries}
        assert "projects" in names

    def test_delete_file(self, stratum_1):
        stratum_1.write("projects/tmp.md", "delete me")
        assert stratum_1.delete("projects/tmp.md") is True
        import pytest
        with pytest.raises(FileNotFoundError):
            stratum_1.read("projects/tmp.md")

    def test_delete_nonexistent(self, stratum_1):
        assert stratum_1.delete("nope.md") is False

    def test_delete_directory(self, stratum_1):
        stratum_1.write("projects/dir/a.md", "a")
        stratum_1.write("projects/dir/b.md", "b")
        assert stratum_1.delete("projects/dir") is True

    def test_path_traversal_blocked(self, stratum_1):
        import pytest
        with pytest.raises(ValueError):
            stratum_1.read("../etc/passwd")
        with pytest.raises(ValueError):
            stratum_1.write("../escape.md", "bad")

    def test_ensure_dirs_idempotent(self, stratum_1):
        stratum_1.ensure_dirs()
        stratum_1.ensure_dirs()

    def test_get_modified_days_ago(self, stratum_1):
        stratum_1.write("projects/new.md", "fresh")
        assert stratum_1.get_modified_days_ago("projects/new.md") == 0

    def test_path_exists(self, stratum_1):
        stratum_1.write("projects/exists.md", "yep")
        assert stratum_1.path_exists("projects/exists.md") is True
        assert stratum_1.path_exists("nonexistent.md") is False

    def test_scan_stale_files(self, stratum_1, config):
        config.decay_thresholds["*"] = 0
        stratum_1.write("projects/stale.md", "old content")
        stale = stratum_1.scan_stale_files()
        paths = [s["path"] for s in stale]
        assert "projects/stale.md" in paths

    def test_scan_stale_files_filters_by_pattern(self, stratum_1):
        stratum_1.write("projects/stale.py", "print('hello')")
        stale = stratum_1.scan_stale_files()
        paths = [s["path"] for s in stale]
        assert "projects/stale.py" not in paths
