import pandas as pd
import pytest

from pipeline import storage_helpers as store
from pipeline.logging_helpers import PipelineFatal, end_run, start_run
from pipeline.lookup_helpers import (INDEX_COLUMNS, coverage, fetch, load_vehicle_index, lookup_report, match_key,
                                     variant_label, year_span)

VERSION = 'v1'
VARIANT = {'fields': ['trim', 'transmission'], 'separator': ' ', 'multi_value_separator': ' ', 'base_label': 'Base',
           'base_when': 'all_fields_empty'}


def vehicles_db(db_dir, rows, version=VERSION):
    """rows: (model, submodel, year, model_number[, trim])"""
    df = pd.DataFrame([{'vehicle_id': f'VW-{y}-{n}', 'model': m, 'submodel': s, 'model_year': str(y),
                        'model_number': n, 'trim': (t[0] if t else ''), 'transmission': '', 'taxonomy_version': version}
                       for m, s, y, n, *t in rows], columns=INDEX_COLUMNS + ['trim', 'transmission'])
    store.write_table(df, db_dir, 'final', 'vehicles')
    return db_dir


def load(db_dir, ctx):
    return load_vehicle_index(db_dir, VERSION, VARIANT, ctx)


@pytest.fixture
def ctx(tmp_path, settings):
    c = start_run(settings, 'test', tmp_path, run_id='lookup', pipeline='vw_accessories')
    yield c
    end_run(c)


def declared(**entries):
    """declared(Golf_GTI=[2020, 2022]) -> {('Golf', 'GTI'): {...}}; a key without _ is the base model."""
    out = {}
    for name, (start, end) in entries.items():
        model, _, submodel = name.partition('_')
        out[(model, submodel or None)] = {'years': set(range(start, end + 1)), 'files': f'{model.lower()}.yaml',
                                          'status': 'drafted'}
    return out


# ---------------------------------------------------------------- helpers

def test_match_key_and_year_span():
    assert match_key('Volkswagen', 'Golf', 'GTI', 2023) == 'volkswagen|golf|gti|2023'
    assert match_key('Volkswagen', 'Atlas', None, 2020) == 'volkswagen|atlas|(base)|2020'
    assert year_span([2020, 2021, 2023, 2025, 2026]) == '2020-2021, 2023, 2025-2026' and year_span([]) == 'none'


def test_variant_label_follows_the_configured_order_and_base_rule():
    variant = {**VARIANT, 'fields': ['trim', 'special_edition', 'appearance_package', 'transmission']}
    assert variant_label({'trim': '', 'special_edition': '40th Anniversary', 'transmission': 'Automatic'},
                         variant) == '40th Anniversary Automatic'
    assert variant_label({'trim': 'Comfortline', 'appearance_package': 'Black|R-Line'}, variant) ==         'Comfortline Black R-Line'
    assert variant_label({'trim': ''}, variant) == 'Base'
    assert variant_label({'trim': ''}, {**variant, 'base_label': 'Standard'}) == 'Standard'


# ---------------------------------------------------------------- the vehicle index

def test_index_groups_once_and_reads_only_what_it_needs(tmp_path, ctx):
    vehicles_db(tmp_path, [('Golf', 'GTI', 2023, 'AU2', 'Autobahn'), ('Golf', 'GTI', 2023, 'AU1'),
                           ('Golf', '', 2021, 'AU22M2', 'Comfortline')])
    index = load(tmp_path, ctx)
    assert [v['model_number'] for v in index['index'][('Golf', 'GTI', 2023)]] == ['AU1', 'AU2']
    assert [v['variant'] for v in index['index'][('Golf', 'GTI', 2023)]] == ['Base', 'Autobahn']
    assert index['known_years'] == {('Golf', 'GTI'): [2023], ('Golf', None): [2021]}
    assert ctx['flags'] == []


def test_missing_db_and_missing_column_are_fatal(tmp_path, ctx):
    with pytest.raises(PipelineFatal) as missing:
        load(tmp_path, ctx)
    assert missing.value.code == 'ACCESS_DB_NOT_FOUND' and 'run_ingest.py' in str(missing.value)
    store.write_table(pd.DataFrame({'model': ['Golf']}), tmp_path, 'final', 'vehicles')
    with pytest.raises(PipelineFatal) as column:
        load(tmp_path, ctx)
    assert column.value.code == 'ACCESS_DB_COLUMN_MISSING'


def test_stale_db_and_failed_last_ingest_are_warned(tmp_path, ctx):
    vehicles_db(tmp_path, [('Golf', 'GTI', 2023, 'AU1')], version='old')
    store.append_row({'run_id': 'vw_ingest_20261027_090000', 'status': 'ok_with_errors'}, tmp_path, 'dq',
                     'ingest_runs')
    load(tmp_path, ctx)
    assert [f['code'] for f in ctx['flags']] == ['ACCESS_DB_STALE', 'ACCESS_DB_LAST_INGEST_NOT_OK']
    assert ctx['flags'][0]['message'] == ('The vehicle DB was built with config version old, '
                                          'but the config is now v1')


# ---------------------------------------------------------------- every row of the idea-004 lookup table

DB = [('Golf', 'GTI', 2020, 'G20'), ('Golf', 'GTI', 2022, 'G22'), ('Golf', 'R', 2022, 'R22'),
      ('Arteon', '', 2021, 'A21'), ('Tiguan', '', 2024, 'T24')]
CONFIG = declared(Golf_GTI=(2020, 2023), Golf_R=(2022, 2026), Arteon=(2020, 2021), Beetle=(2015, 2019))


@pytest.mark.parametrize('key, code, attached', [
    (('Golf', 'GTI', 2020), '', ['G20']),                                         # in DB + declared
    (('Tiguan', None, 2024), 'ACCESS_LOOKUP_NO_CONFIG_FOR_MODEL', ['T24']),        # in DB, no config at all
    (('Golf', 'GTI', 2021), 'ACCESS_LOOKUP_IN_CONFIG_NOT_IN_DB', []),              # declared, DB has no 2021
    (('Golf', 'R', 2027), 'ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN', []),
    (('Golf', 'R', 2020), 'ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN', []),
    (('Beetle', None, 2021), 'ACCESS_LOOKUP_MODEL_NOT_IN_DB', []),                 # config, but never in the DB
    (('Passat', None, 2021), 'ACCESS_LOOKUP_NO_CONFIG_FOR_MODEL', []),
])
def test_each_lookup_case_gets_its_code(tmp_path, ctx, taxonomy, key, code, attached):
    index = load(vehicles_db(tmp_path, DB), ctx)
    result = fetch({key: 3}, index, CONFIG, taxonomy, ctx)[key]
    assert [v['model_number'] for v in result['vehicles']] == attached
    assert (result['issue']['code'] if result['issue'] else '') == code
    assert result['match_status'] == ('matched' if attached else code)
    assert [f['code'] for f in ctx['flags']] == ([code] if code else [])


def test_in_db_not_in_config_still_attaches(tmp_path, ctx, taxonomy):
    index = load(vehicles_db(tmp_path, DB + [('Golf', 'GTI', 2024, 'G24')]), ctx)
    result = fetch({('Golf', 'GTI', 2024): 2}, index, CONFIG, taxonomy, ctx)[('Golf', 'GTI', 2024)]
    assert result['match_status'] == 'matched' and result['issue']['code'] == 'ACCESS_LOOKUP_IN_DB_NOT_IN_CONFIG'
    assert ctx['flags'][0]['severity'] == 'warning'


def test_year_in_a_gap(tmp_path, ctx, taxonomy):
    index = load(vehicles_db(tmp_path, DB), ctx)
    gap_config = {**CONFIG, ('Golf', 'GTI'): {**CONFIG[('Golf', 'GTI')], 'years': {2020, 2022}}}
    result = fetch({('Golf', 'GTI', 2021): 1}, index, gap_config, taxonomy, ctx)[('Golf', 'GTI', 2021)]
    assert result['issue']['code'] == 'ACCESS_LOOKUP_YEAR_IN_GAP'


def test_flag_states_both_checks_and_the_config_status(tmp_path, ctx, taxonomy):
    index = load(vehicles_db(tmp_path, DB), ctx)
    fetch({('Golf', 'R', 2020): 54}, index, CONFIG, taxonomy, ctx)
    flag = ctx['flags'][0]
    assert flag['subject'] == 'volkswagen|golf|r|2020 - 54 parts'
    assert flag['message'] == ('Accessory file lists Golf R for 2020, but neither the vehicle DB nor the config '
                               'has it before 2022')
    assert 'model=Golf submodel=R year=2020 -> 0 rows (known years 2022)' in flag['checked']
    assert 'golf.yaml Golf R declared 2022-2026 -> 2020 not declared (drafted from data, not reviewed)' \
        in flag['checked']
    assert flag['fix'].startswith('1) Confirm with the data source whether Golf R 2020 exists')


def test_lookup_report_has_one_row_per_key(tmp_path, ctx, taxonomy):
    index = load(vehicles_db(tmp_path, DB), ctx)
    report = lookup_report(fetch({('Golf', 'GTI', 2020): 1, ('Golf', 'R', 2020): 1}, index, CONFIG, taxonomy, ctx))
    assert report['match_key'].tolist() == ['volkswagen|golf|gti|2020', 'volkswagen|golf|r|2020']
    assert report['model_numbers'].tolist() == ['G20', ''] and report['in_config'].tolist() == ['yes', 'no']


# ---------------------------------------------------------------- coverage

def test_vehicles_without_parts_are_flagged_once_per_key(tmp_path, ctx, taxonomy):
    index = load(vehicles_db(tmp_path, DB + [('Golf', 'GTI', 2022, 'G22B')]), ctx)
    rows = coverage(index, {('Golf', 'GTI', 2020): 4, ('Golf', 'R', 2022): 1, ('Tiguan', None, 2024): 1},
                    taxonomy, ctx)
    assert [f['code'] for f in ctx['flags']] == ['ACCESS_COVER_MODEL_NO_PARTS', 'ACCESS_COVER_VEHICLE_NO_PARTS']
    assert ctx['flags'][1]['message'] == '2 Golf GTI 2022 vehicles in the vehicle DB get no accessory parts'
    assert ctx['flags'][1]['found'] == '0 parts; Golf GTI accessories cover 2020'
    assert sorted(r['model_number'] for r in rows) == ['A21', 'G22', 'G22B']
