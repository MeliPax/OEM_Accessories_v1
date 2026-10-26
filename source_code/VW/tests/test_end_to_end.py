"""Full runs of run_ingest.run() on the real data, into a temporary db/ folder."""

import pandas as pd
import pytest

import run_ingest
from conftest import SOURCE, replace_in

STEPS = ['config', 'ingest', 'staging', 'year_window', 'clean', 'parse', 'resolve', 'validate', 'write']


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


@pytest.fixture(scope='module')
def first_run(tmp_path_factory):
    db = tmp_path_factory.mktemp('db')
    status, summary = run_ingest.run(db_dir=db, run_id='run1')
    return db, status, summary


def test_row_counts_reconcile(first_run):
    db, status, summary = first_run
    assert status == 'ok'                                            # no flags on today's data
    assert summary['rows_staged'] == 323
    assert summary['rows_excluded_by_year'] == 54
    assert summary['rows_final'] == 269
    assert summary['rows_staged'] == summary['rows_final'] + summary['rows_excluded_by_year']
    assert summary['parsed_complete_pct'] == 100.0
    assert len(read(db / 'staging' / 'stg_vw_models.csv')) == 323
    assert len(read(db / 'final' / 'vehicles.csv')) == 269


def test_every_step_is_logged(first_run):
    db, _, _ = first_run
    steps = read(db / 'logs' / 'steps.csv')
    assert steps[steps['run_id'] == 'run1']['step'].tolist() == STEPS
    assert (db / 'logs' / 'runs' / 'run1.log').exists()
    assert (db / 'logs' / 'changes' / 'run1.csv').exists()
    assert (db / 'logs' / 'flags' / 'run1.csv').exists()


def test_every_value_is_traceable_in_the_change_log(first_run):
    db, _, _ = first_run
    vehicles = read(db / 'final' / 'vehicles.csv')
    changes = read(db / 'logs' / 'changes' / 'run1.csv')
    logged = {}
    for r in changes[changes['step'] == 'parse'].itertuples():
        logged.setdefault((r.vehicle_id, r.field), set()).add(r.after)
    for r in changes[changes['step'] == 'resolve'].itertuples():       # resolutions replace parsed values
        logged[(r.vehicle_id, r.field)] = set(r.after.split('|')) if r.after else set()
    taxonomy_cols = ['model', 'series', 'submodel', 'trim', 'special_edition', 'appearance_package',
                     'technology_package', 'performance_package', 'engine', 'transmission', 'drivetrain',
                     'body_style', 'battery_supplier', 'inventory_status']
    missing = []
    for row in vehicles.itertuples():
        for col in taxonomy_cols:
            cell = getattr(row, col)
            if cell and set(cell.split('|')) != logged.get((row.vehicle_id, col), set()):
                missing.append((row.vehicle_id, col, cell))
    assert missing == []


def test_excluded_rows_have_reasons(first_run):
    db, _, _ = first_run
    changes = read(db / 'logs' / 'changes' / 'run1.csv')
    excluded = changes[changes['rule'] == 'excluded']
    assert len(excluded) == 54
    assert (excluded['detail'] == '2019 < min_model_year 2020').all()


def test_no_flags_on_todays_data(first_run):
    db, _, _ = first_run
    flags = read(db / 'logs' / 'flags' / 'run1.csv')
    queue = read(db / 'review' / 'review_queue.csv')
    assert flags.empty and queue.empty     # Tiguan Black resolved; Atlas trim change on a reused code is allowed


def test_reused_model_number_with_trim_change_is_noted_not_flagged(first_run):
    db, _, _ = first_run
    run_log = (db / 'logs' / 'runs' / 'run1.log').read_text(encoding='utf-8')
    line = next(l for l in run_log.splitlines() if 'MODEL NUMBER REUSED WITH CHANGES (allowed)' in l)
    assert 'CMC4NR trim: Comfortline (2020); Highline (2021, 2022)' in line


def test_model_number_compare_list_is_configurable(config_copy, tmp_path):
    replace_in(config_copy / 'pipeline.yaml', 'compare: [model, submodel]', 'compare: [model, submodel, trim]')
    run_ingest.run(config_dir=config_copy, db_dir=tmp_path / 'db', run_id='strict')
    flags = read(tmp_path / 'db' / 'logs' / 'flags' / 'strict.csv')
    assert set(flags['value']) == {'CMC4NR', 'CMC4UR'} and len(flags) == 7


def test_unknown_compare_category_stops_the_run(config_copy, tmp_path):
    replace_in(config_copy / 'pipeline.yaml', 'compare: [model, submodel]', 'compare: [model, trims]')
    with pytest.raises(Exception, match='unknown category: trims'):
        run_ingest.run(config_dir=config_copy, db_dir=tmp_path / 'db', run_id='badcompare')


def test_lone_black_resolved_to_black_edition(first_run):
    db, _, _ = first_run
    vehicles = read(db / 'final' / 'vehicles.csv').set_index('vehicle_id')
    for vid in ['VW-2024-BJ2VVJ', 'VW-2025-RM1VPJ', 'VW-2026-RM1VPJ',
                'VW-2025-CL26SR', 'VW-2026-CL26SR', 'VW-2027-CL26SR']:
        assert vehicles.loc[vid, 'special_edition'] == 'Black Edition', vid
        assert 'Black' not in vehicles.loc[vid, 'appearance_package'].split('|'), vid
    assert vehicles.loc['VW-2025-DA1BPT', 'appearance_package'] == 'Black'      # Golf R: not offered


def test_rerun_changes_nothing(first_run):
    db, _, _ = first_run
    before = (db / 'final' / 'vehicles.csv').read_bytes()
    run_ingest.run(db_dir=db, run_id='run2')
    assert (db / 'final' / 'vehicles.csv').read_bytes() == before
    changes = read(db / 'logs' / 'changes' / 'run2.csv')
    assert changes[changes['step'] == 'write'].empty
    assert len(read(db / 'dq' / 'ingest_runs.csv')) == 2


def test_changing_one_keyword_changes_only_affected_rows(config_copy, tmp_path):
    db = tmp_path / 'db'
    run_ingest.run(config_dir=config_copy, db_dir=db, run_id='before')
    limited = read(db / 'final' / 'vehicles.csv')['inventory_status'].eq('Limited Availability').sum()
    replace_in(config_copy / 'keywords.yaml', 'value: Limited Availability', 'value: Limited')
    run_ingest.run(config_dir=config_copy, db_dir=db, run_id='after')
    changes = read(db / 'logs' / 'changes' / 'after.csv')
    db_changes = changes[changes['step'] == 'write']
    assert limited > 0 and len(db_changes) == limited
    assert set(db_changes['field']) == {'inventory_status'}
    assert set(db_changes['after']) == {'Limited'}


def test_max_model_year_caps_the_window(config_copy, tmp_path):
    replace_in(config_copy / 'pipeline.yaml', 'max_model_year:               #', 'max_model_year: 2024 #')
    _, summary = run_ingest.run(config_dir=config_copy, db_dir=tmp_path / 'db', run_id='capped')
    assert summary['rows_final'] == 197


def test_made_up_word_is_partial_with_one_unknown_token(tmp_path):
    source = tmp_path / 'source.csv'
    df = read(SOURCE)
    extra = pd.DataFrame([{'Description': 'Tiguan Highline Sparkle', 'Manufacturer': 'VOLKSWAGEN',
                           'ModelNumber': 'ZZ9TST', 'ModelYear': '2025'}])
    pd.concat([df, extra]).to_csv(source, index=False)
    _, summary = run_ingest.run(db_dir=tmp_path / 'db', source=source, run_id='madeup')
    vehicles = read(tmp_path / 'db' / 'final' / 'vehicles.csv')
    flags = read(tmp_path / 'db' / 'logs' / 'flags' / 'madeup.csv')
    row = vehicles[vehicles['model_number'] == 'ZZ9TST'].iloc[0]
    assert row['parse_status'] == 'partial' and row['unparsed_tokens'] == 'Sparkle'
    unknown = flags[flags['rule'] == 'unknown_token']
    assert len(unknown) == 1 and unknown.iloc[0]['value'] == 'Sparkle'
    assert summary['rows_final'] == 270


def test_broken_config_stops_the_run_and_is_logged(config_copy, tmp_path):
    replace_in(config_copy / 'keywords.yaml', '    - match: Highline\n', '    - match: Highline\n    - match: Highline\n')
    with pytest.raises(Exception, match='already defined'):
        run_ingest.run(config_dir=config_copy, db_dir=tmp_path / 'db', run_id='broken')
    steps = read(tmp_path / 'db' / 'logs' / 'steps.csv')
    assert steps.iloc[-1]['step'] == 'config' and steps.iloc[-1]['status'] == 'failed'
    assert 'FATAL' in (tmp_path / 'db' / 'logs' / 'runs' / 'broken.log').read_text(encoding='utf-8')
