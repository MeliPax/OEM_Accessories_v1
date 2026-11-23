"""Part numbers kept exactly as the source (idea 008): one small hand-made case per split result, S1-S11."""

import openpyxl
import pandas as pd
import pytest

from conftest import CONFIG_DIR
from pipeline import config_helpers as cfg
from pipeline import storage_helpers as store
from pipeline.accessory_helpers import (check_part_numbers, check_unproven_share, export_accessories,
                                        flag_part_numbers, prove_part_number, read_accessories, remove_duplicates,
                                        split_check_value, stage_accessories)
from pipeline.logging_helpers import PipelineFatal, end_run, start_run
from test_accessory_helpers import SOURCE_COLUMNS, part


@pytest.fixture(scope='module')
def spec(settings):
    return cfg.load_accessory_config(CONFIG_DIR, settings)


@pytest.fixture
def ctx(tmp_path, settings):
    c = start_run(settings, 'test', tmp_path, run_id='pn', pipeline='vw_accessories')
    yield c
    end_run(c)


def rows(*items):
    """items: (stockCode, stored_as, make&model, model[, status]) -> rows as read_accessories returns them."""
    return pd.DataFrame([{'source_row': n, 'part_number': stock, 'part_number_stored_as': stored,
                          'make_model': mm, 'model_name': model, 'status': rest[0] if rest else 'Active'}
                         for n, (stock, stored, mm, model, *rest) in enumerate(items, start=3)])


def checked(spec, ctx, *items):
    return check_part_numbers(rows(*items), spec, ctx)


# ---------------------------------------------------------------- the split

def test_split_removes_the_rows_own_model_name_from_the_end():
    assert split_check_value('000019819CAlltrack', 'Alltrack') == ('000019819C', 'Alltrack')
    assert split_check_value('000072709City Golf', 'City Golf') == ('000072709', 'City Golf')
    assert split_check_value('000072709City Golf', 'Golf') == ('000072709City ', 'Golf')    # only its own name
    assert split_check_value('Atlas', 'Atlas') == ('', '') and split_check_value('', 'GTI') == ('', '')


@pytest.mark.parametrize('stock, mm, model, result, used', [
    ('000019819C', '000019819CGTI', 'GTI', 'same', '000019819C'),                      # S1
    ('71200', '000071200Atlas', 'Atlas', 'restored', '000071200'),                     # S2
    ('71200', '000071201Atlas', 'Atlas', 'mismatch', '71200'),                         # S3
    ('71200', '100071200Atlas', 'Atlas', 'mismatch', '71200'),                         # S3: not only zeros
    ('71200', '', 'Atlas', 'no_check_value', '71200'),                                 # S4
    ('71200', '000071200Atlas', 'Atlas Cross Sport', 'suffix_not_at_end', '71200'),    # S5
    ('71200', 'Atlas', 'Atlas', 'no_part_left', '71200'),                              # S6
    ('', '000071200Atlas', 'Atlas', 'no_stock_code', ''),                              # S7
    ('000 071200', '000 071200Atlas', 'Atlas', 'unexpected_characters', '000 071200'),  # S8
])
def test_each_split_result(spec, stock, mm, model, result, used):
    assert prove_part_number(stock, mm, model, spec['part_number'])[:2] == (result, used)


def test_a_part_number_is_never_padded(spec):
    """71200 stays 71200 unless make&model itself holds the zeros (P6)."""
    assert prove_part_number('71200', '71200Atlas', 'Atlas', spec['part_number'])[:2] == ('same', '71200')
    never = {**spec['part_number'], 'restore': 'never'}
    assert prove_part_number('71200', '000071200Atlas', 'Atlas', never)[:2] == ('mismatch', '71200')


def test_check_adds_the_split_columns_and_restores_only_proven_numbers(spec, ctx):
    out, report = checked(spec, ctx, ('71200', 'number', '000071200Atlas', 'Atlas'),
                          ('71200', 'number', '000071200Atlas', 'Atlas'),
                          ('000019819C', 'text', '000019819CGTI', 'GTI'),
                          ('61122', 'number', '', 'Golf'))
    assert out['part_number'].tolist() == ['000071200', '000071200', '000019819C', '61122']
    assert out['part_number_source'].tolist() == ['71200', '71200', '000019819C', '61122']
    assert out['make_model_part_number'].tolist() == ['000071200', '000071200', '000019819C', '']
    assert out['make_model_model_name'].tolist() == ['Atlas', 'Atlas', 'GTI', '']
    assert out['part_number_check'].tolist() == ['restored', 'restored', 'same', 'no_check_value']
    assert len(report) == 3 and report['rows'].sum() == 4                    # once per distinct combination
    restore = [c for c in ctx['changes'] if c['rule'] == 'restore_leading_zeros']
    assert [(c['before'], c['after']) for c in restore] == [('71200', '000071200')]
    assert '2 rows' in restore[0]['detail'] and 'stored as number' in restore[0]['detail']


@pytest.mark.parametrize('mm, model, hint', [
    ('000071200atlas', 'Atlas', 'ends with "atlas", not "Atlas" (case differs)'),
    ('000071200AtlasCross Sport', 'Atlas Cross Sport', 'only when spaces are ignored'),
    ('000071200Atlas', 'Atlas Cross Sport', 'ends with another model name, "Atlas"'),
    ('000071200Polo', 'Atlas Cross Sport', 'no known model name ends it'),
])
def test_suffix_not_at_end_explains_why_without_using_it(spec, ctx, mm, model, hint):
    out, report = checked(spec, ctx, ('71200', 'number', mm, model), ('1', 'text', '1Atlas', 'Atlas'))
    assert out.loc[0, 'part_number'] == '71200' and out.loc[0, 'part_number_check'] == 'suffix_not_at_end'
    assert hint in report.loc[report['part_number_source'] == '71200', 'reason'].iloc[0]


# ---------------------------------------------------------------- flags + review (in scope only)

def test_flags_per_result_with_severity_from_how_it_was_stored(spec, ctx):
    out, report = checked(spec, ctx, ('71200', 'number', '000071200Atlas', 'Atlas'),
                          ('71200', 'number', '000071200Atlas', 'Golf'),          # make&model wrong for Golf
                          ('P9', 'text', 'P9Jetta', 'Taos'),
                          ('72709', 'number', '000072709Golf', 'Golf'),
                          ('72709', 'number', '000072708Jetta', 'Jetta'))
    review = flag_part_numbers(out, report, ctx)
    found = {(f['value'], f['code']): f for f in ctx['flags']}
    assert sorted(found) == [('71200', 'ACCESS_STGNG_PART_NUMBER_RESTORED'),
                             ('71200', 'ACCESS_STGNG_PART_NUMBER_UNVERIFIED_NUMBER'),
                             ('72709', 'ACCESS_STGNG_PART_NUMBER_MISMATCH'),
                             ('72709', 'ACCESS_STGNG_PART_NUMBER_RESTORED'),
                             ('P9', 'ACCESS_STGNG_PART_NUMBER_UNVERIFIED')]
    assert found[('71200', 'ACCESS_STGNG_PART_NUMBER_UNVERIFIED_NUMBER')]['severity'] == 'error'      # P9
    assert found[('P9', 'ACCESS_STGNG_PART_NUMBER_UNVERIFIED')]['severity'] == 'info'
    restored = found[('71200', 'ACCESS_STGNG_PART_NUMBER_RESTORED')]
    assert restored['message'] == ('Part number 71200 lost its leading zeros in the accessory file; restored to '
                                   '000071200 from make&model (1 row)')
    assert restored['severity'] == 'warning' and restored['record'] == 'ACC-3-000071200'
    assert found[('72709', 'ACCESS_STGNG_PART_NUMBER_MISMATCH')]['found'] == \
        'make&model holds "000072708", stockCode holds "72709"'
    assert {r['type'] for r in review} == {'part_number'} and len(review) == 5


def test_two_spellings_of_one_part_are_flagged(spec, ctx):
    out, report = checked(spec, ctx, ('71200', 'number', '000071200Atlas', 'Atlas'),
                          ('000071200', 'text', '000071200Golf', 'Golf'))
    flag_part_numbers(out, report, ctx)
    inconsistent = [f for f in ctx['flags'] if f['code'] == 'ACCESS_STGNG_PART_NUMBER_INCONSISTENT']
    assert len(inconsistent) == 1 and inconsistent[0]['found'] == '"000071200" (1 row), "71200" (1 row)'
    assert inconsistent[0]['message'] == 'Part number 000071200 is written 2 ways in stockCode: 000071200, 71200'


def test_rows_out_of_scope_are_counted_not_flagged(spec, ctx):
    out, report = checked(spec, ctx, ('61122', 'number', '000061122Golf', 'Golf', 'Inactive'),
                          ('P1', 'text', 'P1Golf', 'Golf'))
    review = flag_part_numbers(out[out['status'] == 'Active'], report, ctx)       # P13
    assert review == [] and ctx['flags'] == []


def test_too_many_unproven_rows_stop_the_run(spec, ctx):
    items = [('P1', 'text', 'P1Golf', 'Golf')] * 98 + [('P2', 'text', '', 'Golf')] * 2
    _, report = checked(spec, ctx, *items)
    with pytest.raises(PipelineFatal) as error:
        check_unproven_share(report, spec, ctx)                                    # 2% > 1%
    assert error.value.code == 'ACCESS_STGNG_PART_NUMBER_SPLIT_RATE'
    assert 'no_check_value 2' in ctx['flags'][-1]['found']
    _, report = checked(spec, ctx, *[items[0]] * 99 + [items[-1]])                 # 1 of 100 is allowed
    assert check_unproven_share(report, spec, ctx) == 0.01


# ---------------------------------------------------------------- read, staging, dedupe, export

def test_read_keeps_how_excel_stored_the_part_number(tmp_path, spec, ctx):
    path = tmp_path / 'n.xlsx'
    number = {**part(), 'stockCode': 71200, 'make&model': '000071200GTI'}
    pd.DataFrame([number, part('000019819C')], columns=SOURCE_COLUMNS).to_excel(path, index=False, startrow=1)
    df = read_accessories(path, spec, ctx)
    assert df['part_number'].tolist() == ['71200', '000019819C']
    assert df['part_number_stored_as'].tolist() == ['number', 'text']


def test_missing_make_model_column_stops_the_run(tmp_path, spec, ctx):
    path = tmp_path / 'm.xlsx'
    pd.DataFrame([part()]).drop(columns=['make&model']).to_excel(path, index=False, startrow=1)   # S10
    with pytest.raises(PipelineFatal, match='make&model') as error:
        read_accessories(path, spec, ctx)
    assert error.value.code == 'ACCESS_SRC_COLUMN_MISSING'


def test_empty_stock_code_shows_the_number_but_never_fills_it(spec, ctx):
    out, _ = checked(spec, ctx, ('', 'empty', '000071200Atlas', 'Atlas'))
    frame = out.assign(make='Volkswagen', year_range='2021')
    staged = stage_accessories(frame, {**spec, 'keep_rows': {}}, 'Volkswagen', ctx)
    assert staged.empty and ctx['flags'][0]['code'] == 'ACCESS_STGNG_MISSING_PART_NUMBER'
    assert 'make&model holds "000071200", not filled in' in ctx['flags'][0]['found']


def test_restored_and_text_copies_are_one_row_after_dedupe(spec, ctx):
    out, _ = checked(spec, ctx, ('71200', 'number', '000071200Atlas', 'Atlas'),
                     ('000071200', 'text', '000071200Atlas', 'Atlas'))
    kept = remove_duplicates(out, ctx)
    assert len(kept) == 1 and not [f for f in ctx['flags'] if f['code'] == 'ACCESS_STGNG_DUPLICATE_CONFLICT']


def test_export_writes_part_numbers_as_excel_text(tmp_path, spec):
    frame = pd.DataFrame([{c: '' for c in spec['export']['columns']}])
    frame = frame.assign(part_number='000071200', model_number='CA37PR', applicable_year=2024)
    path, _ = export_accessories({'Atlas': frame}, spec, 'pn', tmp_path)
    cell = openpyxl.load_workbook(path)['Atlas']['A2']
    assert cell.value == '000071200' and cell.data_type == 's' and cell.number_format == '@'


def test_append_row_adds_new_columns_without_shifting(tmp_path):
    store.append_row({'run_id': 'a', 'rows': 1}, tmp_path, 'dq', 'runs')
    store.append_row({'run_id': 'b', 'restored': 5, 'rows': 2}, tmp_path, 'dq', 'runs')
    table = pd.read_csv(tmp_path / 'dq' / 'runs.csv', dtype=str, keep_default_na=False)
    assert list(table.columns) == ['run_id', 'rows', 'restored']
    assert table.values.tolist() == [['a', '1', ''], ['b', '2', '5']]
