import tempfile
import pytest
from pathlib import Path

from strata.config import StrataConfig
from strata.storage import Stratum1Storage, Stratum2Storage, Stratum3Storage
from strata.janitor import Janitor
from strata.query import QueryEngine


@pytest.fixture
def tmp_base():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def config(tmp_base):
    return StrataConfig(
        base_dir=tmp_base,
        decay_thresholds={"*": 0},
        lru_days=0,
        lru_min_access_count=0,
    )


@pytest.fixture
def stratum_1(config):
    p = Stratum1Storage(config)
    p.ensure_dirs()
    return p


@pytest.fixture
def stratum_2(config):
    p = Stratum2Storage(config)
    p.ensure_dirs()
    return p


@pytest.fixture
def stratum_3(config):
    p = Stratum3Storage(config)
    p.ensure_dirs()
    return p


@pytest.fixture
def janitor(stratum_1, stratum_2, stratum_3, config):
    return Janitor(stratum_1, stratum_2, stratum_3, config)


@pytest.fixture
def query_engine(stratum_1, stratum_2, stratum_3, config):
    return QueryEngine(stratum_1, stratum_2, stratum_3, config)
