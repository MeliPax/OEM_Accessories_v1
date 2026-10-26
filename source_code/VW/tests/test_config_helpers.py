import pytest

from conftest import replace_in
from pipeline import config_helpers as cfg
from pipeline.config_helpers import ConfigError


def load_all(config_dir):
    cfg.load_settings(config_dir)
    taxonomy = cfg.validate_taxonomy(cfg.load_taxonomy(config_dir))
    return taxonomy, cfg.load_option_sets(config_dir, taxonomy)


def test_real_config_is_valid(taxonomy, option_sets, settings):
    assert settings['min_model_year'] == 2020 and settings['max_model_year'] is None
    assert len(taxonomy['categories']) == 15
    assert {s['model'] for s in option_sets} == {'Arteon', 'Atlas', 'e-Golf', 'Golf', 'ID. Buzz', 'ID.4',
                                                 'Jetta', 'Passat', 'Taos', 'Tiguan'}


def test_export_definitions(tmp_path, taxonomy, option_sets):
    counts = cfg.export_definitions(taxonomy, option_sets, tmp_path)
    assert set(counts) == {'dim_category', 'dim_keyword', 'dim_model', 'dim_option_set', 'dim_resolution'}
    assert counts['dim_resolution'] == 1
    assert counts['dim_keyword'] == len(taxonomy['keywords'])
    assert (tmp_path / 'dim_keyword.csv').exists()


@pytest.mark.parametrize('file, old, new, message', [
    ('pipeline.yaml', 'min_model_year: 2020', 'min_model_year: twenty', 'min_model_year must be a 4-digit year'),
    ('pipeline.yaml', 'max_model_year:               #', 'max_model_year: 2019 #', 'is before min_model_year'),
    ('pipeline.yaml', 'year_rule: single_year', 'year_rule: yearly', 'year_rule must be one of'),
    ('keywords.yaml', 'trim:\n  phrases:', 'trims:\n  phrases:', 'section "trims" is not a category'),
    ('keywords.yaml', '    - match: Highline\n', '    - match: Highline\n    - match: highline\n',
     'is already defined under trim'),
    ('keywords.yaml', '      models: [ID.4]           # "S"', '      models: [ID.5]           # "S"',
     'unknown model "ID.5"'),
    ('keywords.yaml', '    - match: Dune', '    - match: Edition', '"Edition" is never stored alone'),
    ('keywords.yaml', '    - match: Turbo', '    - match: Twin Turbo', 'put it under phrases'),
])
def test_broken_config_fails_with_readable_error(config_copy, file, old, new, message):
    replace_in(config_copy / file, old, new)
    with pytest.raises(ConfigError, match=message):
        load_all(config_copy)


def test_option_set_value_must_exist_in_vocabulary(config_copy):
    replace_in(config_copy / 'vehicles' / 'tiguan.yaml', 'trim: [Comfortline, Highline, Trendline]',
               'trim: [Comfortline, Highline, Trendlne]')
    with pytest.raises(ConfigError, match='trim value "Trendlne" is not produced by any keyword'):
        load_all(config_copy)


def test_option_set_years_must_not_overlap(config_copy):
    replace_in(config_copy / 'vehicles' / 'tiguan.yaml', 'years: [2021, 2021]', 'years: [2020, 2021]')
    with pytest.raises(ConfigError, match=r'\[2020, 2020\] and \[2020, 2021\] overlap'):
        load_all(config_copy)


def test_option_set_unknown_submodel(config_copy):
    replace_in(config_copy / 'vehicles' / 'golf.yaml', 'submodel: R\n', 'submodel: RS\n')
    with pytest.raises(ConfigError, match="submodel 'RS' is not defined for Golf"):
        load_all(config_copy)


def test_taxonomy_version_changes_with_config(config_copy):
    before = cfg.taxonomy_version(config_copy)
    replace_in(config_copy / 'keywords.yaml', '    - match: Turbo', '    - match: Turbo\n    - match: Biturbo')
    assert cfg.taxonomy_version(config_copy) != before
