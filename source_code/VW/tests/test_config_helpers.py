import re
from datetime import date

import pandas as pd
import pytest

from conftest import CONFIG_DIR, SOURCE, replace_in
from pipeline import config_helpers as cfg
from pipeline.clean_helpers import clean_value
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
    ('pipeline.yaml', 'min_model_year: 2020', 'min_model_year: twenty',
     'datasets.vw_models.min_model_year must be a 4-digit year or current_year - N'),
    ('pipeline.yaml', '    max_model_year:\n  accessories:', '    max_model_year: 2019\n  accessories:',
     'datasets.vw_models.max_model_year .2019. is before its min_model_year .2020.'),
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


# ---------------------------------------------------------------- codes, review status, accessories.yaml

def test_config_problems_carry_their_codes(config_copy):
    replace_in(config_copy / 'pipeline.yaml', 'min_model_year: 2020', 'min_model_year: twenty')
    with pytest.raises(ConfigError) as error:
        cfg.load_settings(config_copy)
    assert error.value.problems[0][0] == 'CONFG_VALUE_INVALID'
    assert 'CONFG_VALUE_INVALID: datasets.vw_models.min_model_year must be a 4-digit year' in str(error.value)


def test_vehicle_file_status_is_checked(config_copy):
    replace_in(config_copy / 'vehicles' / 'golf.yaml', 'status: drafted', 'status: approved')
    with pytest.raises(ConfigError, match='status must be one of drafted, reviewed'):
        load_all(config_copy)


def test_vehicle_years_per_model_and_submodel(option_sets):
    years = cfg.vehicle_years(option_sets)
    assert years[('Golf', None)] == {'years': {2020, 2021}, 'files': 'golf.yaml', 'status': 'drafted'}
    assert min(years[('Golf', 'R')]['years']) == 2022 and max(years[('Arteon', None)]['years']) == 2021


def test_accessory_config_is_valid(settings):
    spec = cfg.load_accessory_config(CONFIG_DIR, settings)
    assert spec['renames']['stockCode'] == 'part_number' and spec['types']['msrp'] == 'number'
    assert list(spec['export']['columns'].values())[-3:] == ['Variant', 'Year', 'Model Number']
    assert spec['variant']['fields'][0] == 'trim' and spec['variant']['base_label'] == 'Base'
    pn = spec['part_number']
    assert spec['renames']['make&model'] == 'make_model' and pn['source_column'] == 'stockCode'
    assert pn['pattern'].fullmatch('000071200') and not pn['pattern'].fullmatch('000 071200')
    assert spec['types']['part_number'] == 'text'               # idea 008: never typed as a number


@pytest.mark.parametrize('old, new, message', [
    ('    variant: Variant ', '    variants: Variant ', "export column 'variants' is not in the dict"),
    ('    - special_edition\n', '    - special_editon\n', "variant field 'special_editon' is not a category"),
    ('base_label: Base ', 'base_label: "" ', 'variant.base_label is empty'),
    ('base_when: all_fields_empty', 'base_when: sometimes', 'variant.base_when must be one of all_fields_empty'),
    ('greater_than: [[msrp, cost]]', 'greater_than: [[msrp, costs]]', "unknown column 'costs'"),
    ('header_row: 2 ', 'header_row: 0 ', 'header_row must be a row number'),
    ('{ name: msrp, type: number }', '{ name: msrp, type: money }', 'type must be one of text, number'),
    ('file_name: "{run_id}.xlsx"', 'file_name: "accessories.xlsx"', 'must contain {run_id}'),
    ('restore: leading_zeros_only ', 'restore: pad ', 'part_number.restore must be one of leading_zeros_only, never'),
    ('max_unproven_share: 0.01 ', 'max_unproven_share: 5 ', 'part_number.max_unproven_share must be a share'),
    ('suffix_column: model_name ', 'suffix_column: model ', "part_number.suffix_column 'model' is not a pipeline"),
    ('allowed_characters: A-Z0-9 ', 'allowed_characters: Z-A ', 'allowed_characters'),
    ('  dealerNotes:', '  make&model:         { name: mm, type: text }\n  dealerNotes:',
     "check_column 'make&model' is already read as 'mm'"),
    ('      target_unit: hours ', '      target_unit: days ', "target_unit 'days' is not in units.definitions"),
    ('    minutes: 60', '    minutes: 0', 'units.definitions.minutes must be a number above 0'),
    ('      decimals: 2 ', '      decimals: -1 ', 'decimals must be a whole number from 0 to 10'),
    ('  columns: [comments]', '  columns: [msrp]', "text_cleaning.columns 'msrp' is not a text column"),
    ('      match_type: exact ', '      match_type: regex ', 'match_type must be one of exact, prefix'),
    ('      replace_with: Thule.com', '      replace_with: ""', 'link_rules #1: replace_with is empty'),
    ('remove_tags: [b,', 'remove_tags: [p, b,', 'tags p are both separators and remove_tags'),
])
def test_broken_accessory_config_is_rejected(config_copy, settings, old, new, message):
    replace_in(config_copy / 'accessories.yaml', old, new)
    with pytest.raises(ConfigError, match=re.escape(message)):
        cfg.load_accessory_config(config_copy, settings)


def test_shared_gti_alias_leaves_vw_descriptions_unchanged(taxonomy):
    descriptions = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)['Description'].unique()
    without = {k: v for k, v in taxonomy['aliases'].items() if k != 'GTI'}
    assert 'GTI' in taxonomy['aliases']
    assert all(clean_value(d, taxonomy['aliases'])[0] == clean_value(d, without)[0] for d in descriptions)


# ---------------------------------------------------------------- per-dataset year window

ON_2026, ON_2027 = date(2026, 10, 28), date(2027, 1, 2)
ACC_MIN = '    min_model_year: current_year - 2'
VEH_MAX = '    max_model_year:\n  accessories:'


def test_each_pipeline_has_its_own_window_and_the_accessory_min_moves_with_the_year():
    settings = cfg.load_settings(CONFIG_DIR, today=ON_2026)
    vehicles, accessories = (cfg.dataset_settings(settings, d) for d in ('vw_models', 'accessories'))
    assert (vehicles['min_model_year'], vehicles['max_model_year'], vehicles['window']) == (2020, None, '2020..(no max)')
    assert (accessories['min_model_year'], accessories['max_model_year']) == (2024, None)
    assert accessories['window'] == '2024..(no max) [min = current_year - 2]'
    assert cfg.dataset_settings(cfg.load_settings(CONFIG_DIR, today=ON_2027), 'accessories')['min_model_year'] == 2025


@pytest.mark.parametrize('value, year', [(2020, 2020), ('current_year', 2026), ('current_year - 2', 2024),
                                         ('current_year+1', 2027), ('current_year - x', None), ('2020', None),
                                         (True, None), (None, None)])
def test_year_value(value, year):
    assert cfg.year_value(value, 2026) == year


def test_an_empty_accessory_max_takes_the_vehicle_max(config_copy):
    replace_in(config_copy / 'pipeline.yaml', VEH_MAX, '    max_model_year: 2025\n  accessories:')
    settings = cfg.load_settings(config_copy, today=ON_2026)
    assert cfg.dataset_settings(settings, 'accessories')['window'] == '2024..2025 [min = current_year - 2]'


@pytest.mark.parametrize('old, new, message', [
    (ACC_MIN, '    min_model_year: 2018',
     'datasets.accessories.min_model_year (2018) is before datasets.vw_models.min_model_year (2020)'),
    (ACC_MIN, '    min_model_year: current_year - 7',
     'datasets.accessories.min_model_year (2019) is before datasets.vw_models.min_model_year (2020)'),
    (ACC_MIN, '    min_model_year: soon',
     "datasets.accessories.min_model_year must be a 4-digit year or current_year - N, got 'soon'"),
    (ACC_MIN, '    min_model_year:', 'datasets.accessories.min_model_year is required'),
    ('    max_model_year:\n    within:', '    max_model_year: current_year - 5\n    within:',
     'datasets.accessories.max_model_year (2021) is before its min_model_year (2024)'),
    ('    max_model_year:\n    within:', '    max_model_year: 2026\n    within:',
     'datasets.accessories.max_model_year (2026) goes past datasets.vw_models.max_model_year (2025)'),
    ('    max_model_year: 2025\n  accessories:', '    max_model_year: 2023\n  accessories:',
     'datasets.accessories: no year left (min 2024, max 2023 from datasets.vw_models)'),
    ('    within: vw_models ', '    within: vw_modelz ', "datasets.accessories.within names unknown dataset 'vw_modelz'"),
    ('sources:', 'min_model_year: 2020\nsources:', 'min_model_year is set per dataset now'),
])
def test_a_broken_year_window_is_rejected(config_copy, old, new, message):
    replace_in(config_copy / 'pipeline.yaml', VEH_MAX, '    max_model_year: 2025\n  accessories:')
    replace_in(config_copy / 'pipeline.yaml', old, new)
    with pytest.raises(ConfigError, match=re.escape(message)):
        cfg.load_settings(config_copy, today=ON_2026)


# ---------------------------------------------------------------- verified facts (idea 009)

def load_verified(config_dir):
    taxonomy, option_sets = load_all(config_dir)
    return cfg.load_verified(config_dir, taxonomy, option_sets)


def test_real_verified_facts(taxonomy, option_sets):
    facts = cfg.load_verified(CONFIG_DIR, taxonomy, option_sets)
    assert {(f['label'], f['model'], f['submodel'], tuple(sorted(f['years']))) for f in facts} == {
        ('golf.yaml #1', 'Golf', 'R', (2020, 2021)), ('arteon.yaml #1', 'Arteon', None, (2022, 2023))}
    assert {f['verified_by'] for f in facts} == {'P.M'}


@pytest.mark.parametrize('old, new, message', [
    ('    verified_by: P.M\n', '', 'golf.yaml verified #1: verified_by is required'),
    ('    verified_on: 2026-10-28', '    verified_on: yesterday', 'verified_on must be a date YYYY-MM-DD'),
    ('  - submodel: R\n    never_offered:', '  - submodel: RS\n    never_offered:', "submodel 'RS' is not defined"),
    ('      years: [2020, 2021]\n    reason', '      years: [2021, 2022]\n    reason',
     'Golf R never offered in [2022], but its option sets declare those years (the file says both)'),
    ('      years: [2020, 2021]\n    reason', '      year: [2020, 2021]\n    reason',
     'never_offered.year is not a keyword category'),
    ('    never_offered:\n      years: [2020, 2021]\n', '    never_offered:\n      transmission: [Manual]\n',
     'never_offered.transmission needs the years it applies to'),
    ('    reason: Golf R', '    because: x\n    reason: Golf R', '"because" is not a verified field'),
    ('    never_offered:\n      years: [2020, 2021]\n',
     '    no_parts_expected:\n      years: [2020]\n      until: 2027-06-30\n',
     'no_parts_expected years [2020] are not declared for Golf R'),
])
def test_broken_verified_entry_is_rejected(config_copy, old, new, message):
    replace_in(config_copy / 'vehicles' / 'golf.yaml', old, new)
    with pytest.raises(ConfigError, match=re.escape(message)):
        load_verified(config_copy)


def test_an_option_the_option_set_offers_cannot_be_never_offered(config_copy):
    replace_in(config_copy / 'vehicles' / 'golf.yaml', '    never_offered:\n      years: [2020, 2021]\n',
               '    years: [2022]\n    never_offered:\n      transmission: [Manual]\n')
    with pytest.raises(ConfigError, match=re.escape('Golf R 2022: transmission "Manual" is never offered here, '
                                                    'but the option set offers it')):
        load_verified(config_copy)
