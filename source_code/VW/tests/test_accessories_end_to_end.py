"""Full runs of the accessory pipeline on today's data, after a vehicle ingest into a temporary db/ folder.

acc_run uses the real config on 2026-10-28: accessories from current_year - 2 = 2024, vehicles from 2020.
acc_run_2020 sets the accessory min to 2020, the vehicle window."""

import re
import shutil

import pandas as pd
import pytest

import run_accessories
import run_ingest
from conftest import CONFIG_DIR, replace_in
from datetime import date
from pipeline import config_helpers as cfg
from pipeline.accessory_helpers import build_accessory_model_dict, export_accessories, run_pipeline
from pipeline.logging_helpers import PipelineFatal

TODAY = date(2026, 10, 28)       # current_year 2026: accessories from 2024
STEPS = ['config', 'ingest', 'part_numbers', 'staging', 'year_window', 'clean_text', 'dedupe', 'part_number_review',
         'clean', 'resolve_names', 'lookup', 'build_dict', 'coverage', 'validate', 'verify', 'export']
MISSES = {                                               # accessories 2024+
    'volkswagen|id.4|(base)|2026': 'ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN',
    'volkswagen|id. buzz|(base)|2026': 'ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN',
}
MISSES_2020 = {                                          # accessories 2020+ (the shared window)
    'volkswagen|arteon|(base)|2022': 'ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN',
    'volkswagen|arteon|(base)|2023': 'ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN',
    'volkswagen|id.4|(base)|2026': 'ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN',
    'volkswagen|id. buzz|(base)|2026': 'ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN',
    'volkswagen|atlas|(base)|2020': 'ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN',
    'volkswagen|golf|r|2020': 'ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN',
    'volkswagen|golf|r|2021': 'ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN',
}


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


@pytest.fixture(scope='module')
def acc_run(tmp_path_factory):
    db = tmp_path_factory.mktemp('db')
    out = tmp_path_factory.mktemp('output')
    run_ingest.run(db_dir=db, run_id='ingest1')
    status, summary, model_dict = run_pipeline(db_dir=db, run_id='acc1', output_dir=out, today=TODAY)
    return db, out, status, summary, model_dict


@pytest.fixture(scope='module')
def acc_run_2020(tmp_path_factory):
    config = tmp_path_factory.mktemp('config2020')
    shutil.copytree(CONFIG_DIR, config, dirs_exist_ok=True)
    replace_in(config / 'pipeline.yaml', '    min_model_year: current_year - 2', '    min_model_year: 2020')
    db = tmp_path_factory.mktemp('db2020')
    out = tmp_path_factory.mktemp('output2020')
    run_ingest.run(db_dir=db, run_id='ingest1')
    status, summary, model_dict = run_pipeline(config_dir=config, db_dir=db, run_id='acc2020', output_dir=out)
    return db, out, status, summary, model_dict


def test_every_step_is_logged_and_rows_reconcile(acc_run):
    db, _, status, summary, _ = acc_run
    steps = read(db / 'logs' / 'steps.csv')
    assert steps[steps['run_id'] == 'acc1']['step'].tolist() == STEPS
    assert status == 'ok_with_errors'                     # ID.4 and ID. Buzz 2026 are errors to review
    assert (summary['rows_read'], summary['rows_staged'], summary['rows_in_window'], summary['rows_unique']) == \
           (24396, 20399, 9675, 1028)
    assert (summary['model_names'], summary['unknown_model_names']) == (10, 0)
    runs = read(db / 'dq' / 'accessory_runs.csv').iloc[-1]
    assert (runs['run_id'], runs['min_model_year'], runs['max_model_year']) == ('acc1', '2024', '')


def test_the_accessory_window_is_2024_while_vehicles_stay_at_2020(acc_run):
    """Every accessory step sees only vehicles in its window: no 2020-2023 vehicle is looked up or checked."""
    db, *_, model_dict = acc_run
    vehicles = read(db / 'final' / 'vehicles.csv')
    assert vehicles['model_year'].astype(int).min() == 2020 and len(vehicles) == 269
    log = (db / 'logs' / 'runs' / 'acc1.log').read_text(encoding='utf-8')
    assert 'VEHICLE WINDOW | window=2024..(no max) [min = current_year - 2] | in_window=' in log
    rows = pd.concat(model_dict.values())
    assert rows.loc[rows['vehicle_id'] != '', 'vehicle_id'].str[3:7].astype(int).min() == 2024
    review = read(db / 'review' / 'accessory_review.csv')
    assert pd.to_numeric(review['year'], errors='coerce').dropna().min() >= 2024
    assert min(d['applicable_year'].min() for d in model_dict.values()) == 2024       # 2018-2026 -> 2024-2026
    flags = read(db / 'logs' / 'flags' / 'acc1.csv')
    window = flags[flags['code'] == 'ACCESS_YEAR_OUT_OF_WINDOW']
    assert len(window) == 1 and '2024..(no max)' in window['found'].iloc[0] + window['checked'].iloc[0]


def test_lookup_finds_27_of_29_keys_and_explains_the_2_misses(acc_run):
    db, _, _, summary, _ = acc_run
    assert (summary['keys'], summary['keys_found'], summary['keys_missed']) == (29, 27, 2)
    report = read(db / 'dq' / 'accessory_lookup.csv')
    missed = report[report['code'] != '']
    assert dict(zip(missed['match_key'], missed['code'])) == MISSES
    flags = read(db / 'logs' / 'flags' / 'acc1.csv')
    lookup_flags = flags[flags['code'].str.startswith('ACCESS_LOOKUP_')]
    assert len(lookup_flags) == 2                                         # once per key, not per part
    for _, flag in lookup_flags.iterrows():
        assert '/final/vehicles.csv model=' in flag['checked'] and '2) config/vehicles/' in flag['checked']
        assert 'drafted from data, not reviewed' in flag['checked'] and flag['fix'].startswith('1) ')


def test_vehicles_without_parts_are_the_2027_vehicles(acc_run):
    """Coverage checks vehicle years inside the accessory window only: 2020-2023 vehicles are not flagged."""
    db, _, _, summary, _ = acc_run
    assert summary['vehicles_without_parts'] == 14
    assert 'ACCESS_COVER_MODEL_NO_PARTS' not in set(read(db / 'logs' / 'flags' / 'acc1.csv')['code'])
    flags = read(db / 'logs' / 'flags' / 'acc1.csv')
    cover = flags[flags['code'] == 'ACCESS_COVER_VEHICLE_NO_PARTS']
    assert sorted(s.split(' - ')[0] for s in cover['subject']) == [
        'volkswagen|atlas|(base)|2027', 'volkswagen|jetta|(base)|2027', 'volkswagen|jetta|gli|2027',
        'volkswagen|taos|(base)|2027', 'volkswagen|tiguan|(base)|2027']


def test_dict_unmatched_rows_equal_the_review_part_rows(acc_run):
    db, _, _, summary, model_dict = acc_run
    assert list(model_dict) == ['Atlas', 'Atlas Cross Sport', 'GTI', 'Golf R', 'ID. Buzz', 'ID.4', 'Jetta',
                                'Jetta GLI', 'Taos', 'Tiguan']
    unmatched = pd.concat([d[d['model_number'] == ''] for d in model_dict.values()])
    review = read(db / 'review' / 'accessory_review.csv')
    assert len(unmatched) == summary['unmatched_part_years'] == len(review[review['type'] == 'part']) == 93
    assert set(unmatched['match_status']) == set(MISSES.values())
    assert len(review[review['type'] == 'vehicle']) == 14 and summary['review_rows'] == len(review) == 109


def test_verified_facts_outside_the_window_are_not_reported_unused(acc_run):
    db, _, _, summary, _ = acc_run
    flags = read(db / 'logs' / 'flags' / 'acc1.csv')
    assert not flags['code'].isin(['ACCESS_VERIFY_ENTRY_UNUSED', 'ACCESS_VERIFY_CONTRADICTED']).any()
    assert (summary['flags_verified'], summary['verified_contradicted']) == (0, 0)
    log = (db / 'logs' / 'runs' / 'acc1.log').read_text(encoding='utf-8')
    assert ('OUTSIDE WINDOW | window=2024..(no max) [min = current_year - 2] | facts=2 | '
            'entries=arteon.yaml #1, golf.yaml #1') in log


# ---------------------------------------------------------------- the shared 2020 window (override removed)

def test_without_the_override_accessories_use_the_shared_window(acc_run_2020):
    db, _, status, summary, model_dict = acc_run_2020
    assert status == 'ok_with_errors'                     # 3 of the 7 missing keys are still errors to review
    assert (summary['rows_in_window'], summary['rows_unique'], summary['model_names']) == (13051, 1357, 14)
    assert (summary['keys'], summary['keys_found'], summary['keys_missed']) == (71, 64, 7)
    report = read(db / 'dq' / 'accessory_lookup.csv')
    missed = report[report['code'] != '']
    assert dict(zip(missed['match_key'], missed['code'])) == MISSES_2020
    assert read(db / 'dq' / 'accessory_runs.csv').iloc[-1]['min_model_year'] == '2020'
    golf = model_dict['Golf']                                                        # base Golf only (A2)
    assert set(golf['model_number']) == {'AU22M2', 'AU22MS', 'AU23M2', 'AU23MS'}
    assert model_dict['GTI']['applicable_year'].min() >= 2020                        # clipped (D15)
    rows = golf[golf['vehicle_id'] == 'VW-2020-AU22M2']
    assert len(rows) and set(rows['variant']) == {'Comfortline Manual 5-Door'}


def test_dict_unmatched_rows_equal_the_review_part_rows_plus_the_verified_ones(acc_run_2020):
    db, _, _, summary, model_dict = acc_run_2020
    assert len(model_dict) == 14 and 'GTI' in model_dict and 'Golf' in model_dict
    unmatched = pd.concat([d[d['model_number'] == ''] for d in model_dict.values()])
    review = read(db / 'review' / 'accessory_review.csv')
    parts = review[review['type'] == 'part']
    verified = unmatched[unmatched['match_status'] == 'never_offered']
    assert len(unmatched) == summary['unmatched_part_years'] == 451                  # nothing deleted
    assert len(verified) == 226 and len(parts) == 451 - 226                          # Golf R 108 + Arteon 118
    assert set(unmatched['match_status']) == set(MISSES_2020.values()) | {'never_offered'}
    assert len(review[review['type'] == 'vehicle']) == 14


def test_verified_facts_turn_four_lookup_errors_into_info(acc_run_2020):
    db, _, _, summary, _ = acc_run_2020
    flags = read(db / 'logs' / 'flags' / 'acc2020.csv')
    lookup = flags[flags['code'].str.startswith('ACCESS_LOOKUP_')]
    verified = lookup[lookup['verified_entry'] != '']
    assert sorted(verified['record']) == ['volkswagen|arteon|(base)|2022', 'volkswagen|arteon|(base)|2023',
                                          'volkswagen|golf|r|2020', 'volkswagen|golf|r|2021']
    assert set(verified['severity']) == {'info'} and set(verified['original_severity']) == {'error'}
    assert set(verified['verified_entry']) == {'arteon.yaml #1', 'golf.yaml #1'}
    assert sorted(lookup.loc[lookup['severity'] == 'error', 'record']) == [
        'volkswagen|atlas|(base)|2020', 'volkswagen|id. buzz|(base)|2026', 'volkswagen|id.4|(base)|2026']
    report = read(db / 'dq' / 'verified_flags.csv')
    assert len(report) == 4 and set(report['verified_by']) == {'P.M'} and (report['reason'] != '').all()
    assert (summary['flags_verified'], summary['verified_contradicted'], summary['review_rows']) == (4, 0, 241)
    assert not flags['code'].isin(['ACCESS_VERIFY_ENTRY_UNUSED', 'ACCESS_VERIFY_CONTRADICTED']).any()


def test_dict_shape(acc_run):
    *_, model_dict = acc_run
    gti = model_dict['GTI']
    assert not {'year_range', 'min_year', 'max_year'} & set(gti.columns)            # A11
    assert {'model_number', 'variant', 'vehicle_id', 'applicable_year', 'match_key'} <= set(gti.columns)
    assert 'trim' not in gti.columns and (gti['model_number'] == '').sum() == 0 and (gti['variant'] != '').all()
    assert (gti['model_name_clean'] == 'Golf GTI').all() and (gti['submodel'] == 'GTI').all()
    assert sorted(gti['applicable_year'].unique()) == [2024, 2025, 2026]             # clipped (D15)


@pytest.mark.parametrize('model, vehicle_id, variant', [
    ('GTI', 'VW-2024-CD1PU2', 'Performance'),
    ('GTI', 'VW-2025-DA1AUZ', 'Autobahn'),
    ('GTI', 'VW-2024-CD19UZ', 'Base'),                     # no field beyond model + submodel
    ('Atlas', 'VW-2026-CA37PR', 'Peak Edition'),            # raw text says "Atlas Peak": same label every year
])
def test_variant_describes_each_vehicle(acc_run, model, vehicle_id, variant):
    *_, model_dict = acc_run
    rows = model_dict[model][model_dict[model]['vehicle_id'] == vehicle_id]
    assert len(rows) and set(rows['variant']) == {variant}


def test_export_has_a_sheet_per_model_with_the_configured_columns(acc_run):
    _, out, _, summary, model_dict = acc_run
    path = out / 'acc1.xlsx'
    assert summary['export_sheets'] == 10 and path.exists()
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    assert list(sheets) == list(model_dict)
    spec = cfg.load_accessory_config(CONFIG_DIR, cfg.load_settings(CONFIG_DIR))
    for name, sheet in sheets.items():
        assert list(sheet.columns) == list(spec['export']['columns'].values())
        assert sheet['Model Number'].notna().all()                                   # matched rows only (A13)
        assert len(sheet) == int((model_dict[name]['model_number'] != '').sum())
    assert set(sheets['GTI']['Year']) == {'2024', '2025', '2026'} and set(sheets['ID. Buzz']['Year']) == {'2025'}


def test_every_exported_model_number_traces_to_a_lookup_line(acc_run):
    db, _, _, _, model_dict = acc_run
    run_log = (db / 'logs' / 'runs' / 'acc1.log').read_text(encoding='utf-8')
    logged = {}
    for line in run_log.splitlines():
        m = re.search(r'LOOKUP OK \| match_key=(.+?) \| .*\| model_numbers=(.*)$', line)
        if m:
            logged[m.group(1)] = set(m.group(2).split(', '))
    for df in model_dict.values():
        matched = df[df['model_number'] != '']
        for key, numbers in matched.groupby('match_key')['model_number']:
            assert set(numbers) <= logged[key], key


def test_rerun_gives_identical_reports_and_export(acc_run, tmp_path):
    db, out, *_ = acc_run
    lookup = (db / 'dq' / 'accessory_lookup.csv').read_bytes()
    review = (db / 'review' / 'accessory_review.csv').read_bytes()
    run_pipeline(db_dir=db, run_id='acc2', output_dir=out, today=TODAY)
    assert (db / 'dq' / 'accessory_lookup.csv').read_bytes() == lookup
    assert (db / 'review' / 'accessory_review.csv').read_bytes() == review
    first = pd.read_excel(out / 'acc1.xlsx', sheet_name=None)
    second = pd.read_excel(out / 'acc2.xlsx', sheet_name=None)
    assert all(first[s].equals(second[s]) for s in first)


def test_part_numbers_are_proven_by_make_and_model(acc_run):
    """Idea 008 on today's file: 704 rows of 3 parts lost their zeros and are restored; nothing else differs."""
    db, out, _, summary, model_dict = acc_run
    assert (summary['part_numbers_restored'], summary['part_numbers_unproven']) == (704, 0)
    report = read(db / 'dq' / 'part_number_check.csv')
    assert report.groupby('part_number_check')['rows'].apply(lambda r: r.astype(int).sum()).to_dict() ==         {'restored': 704, 'same': 23692}
    restored = report[report['part_number_check'] == 'restored']
    assert dict(zip(restored['part_number_source'], restored['part_number'])) ==         {'61122': '000061122', '71200': '000071200', '72709': '000072709'}
    assert (report['make_model'] == report['make_model_part_number'] + report['make_model_model_name']).all()

    review = read(db / 'review' / 'accessory_review.csv')
    pn = review[review['type'] == 'part_number']                       # in scope only: 1 part, 10 rows (P13)
    assert pn['code'].tolist() == ['ACCESS_STGNG_PART_NUMBER_RESTORED'] and pn['part_number'].tolist() == ['000071200']
    assert pn['message'].iloc[0].endswith('restored to 000071200 from make&model (10 rows)')

    rows = pd.concat(model_dict.values())
    assert '71200' not in set(rows['part_number']) and set(rows.loc[rows['part_number_source'] == '71200',
                                                                   'part_number']) == {'000071200'}
    atlas = pd.read_excel(out / 'acc1.xlsx', sheet_name='Atlas', dtype=str)
    assert '000071200' in set(atlas['Part Number'])


def test_comments_are_clean_and_keep_the_raw_text(acc_run):
    """Idea 007 on today's file (2024+): 34 distinct comments change; no markup or pipes are left."""
    db, out, _, summary, model_dict = acc_run
    assert (summary['texts_cleaned'], summary['links_flagged']) == (34, 0)
    rows = pd.concat(model_dict.values())
    comments = set(rows['comments']) - {''}
    assert not [c for c in comments if '<' in c or '|' in c or 'salsify' in c or ' ' in c]
    assert any('https://www.vwhub.com/snetljct/en/web/vw/adhesive Always install' in c for c in comments)
    assert (rows['comments_source'] != rows['comments']).any() and 'comments_source' in rows.columns


def test_labour_time_is_exported_in_hours(acc_run):
    """Idea 006: minutes -> hours, 2 decimals; the 0.4 value on 3QF601025KAX1 is flagged for review."""
    db, out, _, summary, model_dict = acc_run
    rows = pd.concat(model_dict.values())
    pairs = set(zip(rows['labor_time_source'], rows['labor_time']))
    assert {(25.0, 0.42), (250.0, 4.17), (0.0, 0.0), (0.4, 0.01)} <= pairs
    assert summary['unit_suspects'] == 1
    review = read(db / 'review' / 'accessory_review.csv')
    value = review[review['type'] == 'value']
    assert value['code'].tolist() == ['ACCESS_CLEAN_UNIT_SUSPECT'] and value['part_number'].tolist() == ['3QF601025KAX1']
    gti = pd.read_excel(out / 'acc1.xlsx', sheet_name='GTI')
    assert 'Labour Time (hours)' in gti.columns and gti['Labour Time (hours)'].max() < 10


def test_notebook_entry_point_without_export(acc_run):
    db, *_ = acc_run
    model_dict = build_accessory_model_dict(db_dir=db, export=False, today=TODAY)
    assert len(model_dict) == 10


def test_locked_export_file_stops_the_run(acc_run, monkeypatch, tmp_path):
    *_, model_dict = acc_run
    spec = cfg.load_accessory_config(CONFIG_DIR, cfg.load_settings(CONFIG_DIR))

    def locked(*args, **kwargs):
        raise PermissionError('in use')

    monkeypatch.setattr(pd, 'ExcelWriter', locked)
    with pytest.raises(PipelineFatal) as error:
        export_accessories(model_dict, spec, 'locked', tmp_path)
    assert error.value.code == 'ACCESS_EXPORT_FILE_LOCKED' and 'Close the file' in str(error.value)


def test_missing_vehicle_db_is_fatal(tmp_path):
    with pytest.raises(PipelineFatal, match='ACCESS_DB_NOT_FOUND'):
        run_pipeline(db_dir=tmp_path / 'empty', run_id='nodb', export=False)


def test_terminal_runner_reports_config_errors(config_copy, tmp_path, capsys):
    replace_in(config_copy / 'accessories.yaml', '    variant: Variant ', '    variants: Variant ')
    assert run_accessories.main(['--config-dir', str(config_copy), '--db-dir', str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "CONFG_UNKNOWN_REFERENCE: accessories.yaml: export column 'variants' is not in the dict" in err
    assert 'fix:' in err
