import pandas as pd
import pytest

from pipeline.logging_helpers import (diff_frames, end_run, log_change, log_flag, prune_runs, run_step,
                                      start_run)

KEY = ['model_number', 'model_year']
SETTINGS = {'min_model_year': 2020, 'max_model_year': None, 'logging': {'keep_runs': 30}}


def frame(rows):
    return pd.DataFrame(rows, columns=['model_number', 'model_year', 'trim'])


# ---------------------------------------------------------------- diff_frames

def test_diff_frames_changed_added_removed_value():
    before = frame([['A', '2024', 'Highline'], ['B', '2024', ''], ['C', '2024', 'Trendline']])
    after = frame([['A', '2024', 'Execline'], ['B', '2024', 'Comfortline'], ['C', '2024', '']])
    changes = {c['model_number']: (c['before'], c['after']) for c in diff_frames(before, after, KEY, ['trim'])}
    assert changes == {'A': ('Highline', 'Execline'), 'B': ('', 'Comfortline'), 'C': ('Trendline', '')}


def test_diff_frames_ignores_rows_in_one_frame_only_and_unchanged():
    before = frame([['A', '2024', 'Highline'], ['GONE', '2024', 'x']])
    after = frame([['A', '2024', 'Highline'], ['NEW', '2024', 'y']])
    assert diff_frames(before, after, KEY, ['trim']) == []


def test_diff_frames_new_column_counts_as_added_values():
    before = frame([['A', '2024', 'Highline']])
    after = before.assign(drivetrain='AWD')
    assert diff_frames(before, after, KEY, ['drivetrain'])[0]['after'] == 'AWD'


# ---------------------------------------------------------------- a dummy two-step run

def test_two_step_run_writes_all_four_outputs(tmp_path):
    ctx = start_run(SETTINGS, 'dummy.csv', tmp_path, run_id='test_run')
    df = frame([['A', '2024', 'Highline'], ['B', '2019', 'Trendline']])

    def drop_old(d):
        return d[d['model_year'] >= '2020']

    def upgrade(d):
        d = d.copy()
        d.loc[d['model_number'] == 'A', 'trim'] = 'Execline'
        log_flag(ctx, 'upgrade', {'model_number': 'A', 'model_year': '2024'}, 'test_rule', 'warning',
                 'trim', 'Execline', 'just a test')
        return d

    kept = run_step(ctx, 'drop_old', drop_old, df, conditions={'min': 2020})
    run_step(ctx, 'upgrade', upgrade, kept, key_cols=KEY, watch_cols=['trim'])
    status = end_run(ctx)

    logs = tmp_path / 'logs'
    run_log = (logs / 'runs' / 'test_run.log').read_text(encoding='utf-8')
    steps = pd.read_csv(logs / 'steps.csv', dtype=str)
    changes = pd.read_csv(logs / 'changes' / 'test_run.csv', dtype=str, keep_default_na=False)
    flags = pd.read_csv(logs / 'flags' / 'test_run.csv', dtype=str, keep_default_na=False)

    assert status == 'ok_with_warnings'
    assert 'RUN START' in run_log and 'RUN END' in run_log and 'min=2020' in run_log
    assert list(steps['step']) == ['drop_old', 'upgrade']
    assert list(steps['rows_in']) == ['2', '1'] and list(steps['rows_out']) == ['1', '1']
    change = changes.iloc[0]
    assert (change['vehicle_id'], change['field'], change['before'], change['after'], change['rule']) == \
           ('VW-2024-A', 'trim', 'Highline', 'Execline', 'diff')
    assert list(flags['rule']) == ['test_rule'] and 'FLAG | rule=test_rule' in run_log


def test_explicit_change_is_not_logged_twice_by_the_diff(tmp_path):
    ctx = start_run(SETTINGS, 'dummy.csv', tmp_path, run_id='explicit')

    def upgrade(d):
        d = d.copy()
        d['trim'] = 'Execline'
        log_change(ctx, 'upgrade', {'model_number': 'A', 'model_year': '2024'}, 'trim',
                   'Highline', 'Execline', 'keyword_word', '"Execline"')
        return d

    run_step(ctx, 'upgrade', upgrade, frame([['A', '2024', 'Highline']]), key_cols=KEY, watch_cols=['trim'])
    end_run(ctx)
    assert [c['rule'] for c in ctx['changes']] == ['keyword_word']


def test_failing_step_logs_fatal_and_reraises(tmp_path):
    ctx = start_run(SETTINGS, 'dummy.csv', tmp_path, run_id='fails')

    def broken(_):
        raise ValueError('boom')

    with pytest.raises(ValueError):
        run_step(ctx, 'broken', broken, frame([]))
    assert end_run(ctx) == 'failed'
    run_log = (tmp_path / 'logs' / 'runs' / 'fails.log').read_text(encoding='utf-8')
    steps = pd.read_csv(tmp_path / 'logs' / 'steps.csv', dtype=str)
    assert 'FATAL | reason=boom | error_type=ValueError' in run_log
    assert steps.iloc[-1]['status'] == 'failed'


def test_ctx_none_runs_without_logging():
    df = frame([['A', '2024', 'Highline']])
    assert run_step(None, 'x', lambda d: d.assign(trim='S'), df)['trim'].tolist() == ['S']
    log_change(None, 'x', {}, 'trim', 'a', 'b', 'rule')
    log_flag(None, 'x', {}, 'rule', 'warning')


def test_same_second_runs_get_distinct_ids(tmp_path):
    first = start_run(SETTINGS, 'dummy.csv', tmp_path)
    second = start_run(SETTINGS, 'dummy.csv', tmp_path)
    end_run(first), end_run(second)
    assert first['run_id'] != second['run_id']


def test_prune_keeps_newest_runs_and_never_steps(tmp_path):
    logs = tmp_path / 'logs'
    for sub in ('runs', 'changes', 'flags'):
        (logs / sub).mkdir(parents=True)
        for i in range(31):
            (logs / sub / f'202610{i:02d}_000000.{"log" if sub == "runs" else "csv"}').write_text('x')
    (logs / 'steps.csv').write_text('x')
    prune_runs(logs, 30)
    assert len(list((logs / 'runs').iterdir())) == 30
    assert not (logs / 'runs' / '20261000_000000.log').exists()
    assert (logs / 'steps.csv').exists()
