from strata.config import StrataConfig


class TestStrataConfig:

    def test_config_search_backend_default(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        assert config.search_backend == "qmd"

    def test_config_qmd_enabled_property(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base, search_backend="qmd")
        assert config.qmd_enabled is True

    def test_config_qmd_enabled_property_false(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base, search_backend="fts5")
        assert config.qmd_enabled is False

    def test_config_lru_decay_thresholds(self, tmp_base):
        config = StrataConfig(
            base_dir=tmp_base,
            lru_decay_thresholds={"projects": 30, "*": 90},
        )
        assert config.get_lru_days("projects/foo.md") == 30
        assert config.get_lru_days("gtd/something.md") == 90

    def test_config_get_lru_days_default(self, tmp_base):
        config = StrataConfig(
            base_dir=tmp_base,
            lru_decay_thresholds={"projects": 30},
            lru_days=60,
        )
        assert config.get_lru_days("gtd/something.md") == 60

    def test_config_backward_compat_setter(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base, search_backend="fts5")
        assert config.qmd_enabled is False
        config.qmd_enabled = True
        assert config.search_backend == "qmd"
        assert config.qmd_enabled is True

    def test_config_is_qmd_available(self, tmp_base):
        config = StrataConfig(base_dir=tmp_base)
        assert config.is_qmd_available() is True
        config.search_backend = "fts5"
        assert config.is_qmd_available() is False
