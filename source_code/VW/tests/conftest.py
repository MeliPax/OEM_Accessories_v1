import shutil
import sys
from pathlib import Path

import pytest

VW_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VW_DIR))

from pipeline import config_helpers as cfg  # noqa: E402
from pipeline import storage_helpers as store  # noqa: E402

CONFIG_DIR = VW_DIR / 'config'
SOURCE = VW_DIR / 'datasets' / 'vw_models_data.csv'


@pytest.fixture(scope='session')
def taxonomy():
    return cfg.validate_taxonomy(cfg.load_taxonomy(CONFIG_DIR))


@pytest.fixture(scope='session')
def option_sets(taxonomy):
    return cfg.load_option_sets(CONFIG_DIR, taxonomy)


@pytest.fixture(scope='session')
def settings():
    """The vehicle ingest's settings (window 2020+)."""
    return cfg.dataset_settings(cfg.load_settings(CONFIG_DIR), 'vw_models')


@pytest.fixture
def config_copy(tmp_path):
    """A writable copy of config/ for tests that break or change it."""
    target = tmp_path / 'config'
    shutil.copytree(CONFIG_DIR, target)
    return target


def run_file(db_dir, layer, name, run_id):
    """The file a run wrote: db/<layer>/<name>_<run_id>.csv."""
    return store.table_path(db_dir, layer, name, run_id)


def replace_in(path, old, new):
    text = Path(path).read_text(encoding='utf-8')
    assert old in text, f'{old!r} not found in {path}'
    Path(path).write_text(text.replace(old, new, 1), encoding='utf-8')
