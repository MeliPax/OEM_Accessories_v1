import pandas as pd
import pytest

from conftest import CONFIG_DIR
from pipeline import config_helpers as cfg
from pipeline.accessory_helpers import (check_quality, clean_accessories, read_accessories, remove_duplicates,
                                        resolve_names, sheet_name, stage_accessories, unique_keys)
from pipeline.logging_helpers import PipelineFatal, end_run, start_run

SOURCE_COLUMNS = ['stockCode', 'make name', 'model', 'make&model', 'year range', 'status', 'productDescription',
                  'dealerNotes', 'MSRP', 'cost', 'laborTime']


def part(stock='P1', model='GTI', years='2019-2021', status='Active', make='Volkswagen', desc='Floor Mats',
         msrp='100', cost='60', labor='0.5', notes=''):
    return {'stockCode': stock, 'make name': make, 'model': model, 'make&model': stock + model, 'year range': years,
            'status': status, 'productDescription': desc, 'dealerNotes': notes, 'MSRP': msrp, 'cost': cost,
            'laborTime': labor}


def write_file(path, rows, header_row=2):
    pd.DataFrame(rows, columns=SOURCE_COLUMNS).to_excel(path, index=False, startrow=header_row - 1)
    return path


@pytest.fixture(scope='module')
def spec(settings):
    return cfg.load_accessory_config(CONFIG_DIR, settings)


@pytest.fixture
def ctx(tmp_path, settings):
    c = start_run(settings, 'test', tmp_path, run_id='acc', pipeline='vw_accessories')
    yield c
    end_run(c)


def codes(ctx):
    return [f['code'] for f in ctx['flags']]


# ---------------------------------------------------------------- read

def test_read_promotes_the_header_row_and_keeps_configured_columns(tmp_path, spec, ctx):
    df = read_accessories(write_file(tmp_path / 'a.xlsx', [part(), part('P2')]), spec, ctx)
    assert list(df.columns) == ['source_row'] + list(spec['renames'].values()) + ['part_number_stored_as']
    assert df['part_number'].tolist() == ['P1', 'P2'] and df['source_row'].tolist() == [3, 4]
    assert df['make_model'].tolist() == ['P1GTI', 'P2GTI'] and set(df['part_number_stored_as']) == {'text'}


def test_read_fatals_name_the_problem(tmp_path, spec, ctx):
    with pytest.raises(PipelineFatal) as missing_file:
        read_accessories(tmp_path / 'nope.xlsx', spec, ctx)
    assert missing_file.value.code == 'ACCESS_SRC_FILE_NOT_FOUND'

    shifted = write_file(tmp_path / 'b.xlsx', [part()], header_row=4)
    with pytest.raises(PipelineFatal) as header:
        read_accessories(shifted, spec, ctx)
    assert header.value.code == 'ACCESS_SRC_HEADER_NOT_FOUND'

    no_cost = tmp_path / 'c.xlsx'
    pd.DataFrame([part()]).drop(columns=['cost']).to_excel(no_cost, index=False, startrow=1)
    with pytest.raises(PipelineFatal, match='cost') as column:
        read_accessories(no_cost, spec, ctx)
    assert column.value.code == 'ACCESS_SRC_COLUMN_MISSING'

    with pytest.raises(PipelineFatal) as sheet:
        read_accessories(write_file(tmp_path / 'd.xlsx', [part()]), {**spec, 'sheet': 'Accessories'}, ctx)
    assert sheet.value.code == 'ACCESS_SRC_SHEET_NOT_FOUND' and 'Sheet1' in str(ctx['flags'][-1]['found'])


# ---------------------------------------------------------------- staging

def staged(tmp_path, spec, ctx, rows):
    return stage_accessories(read_accessories(write_file(tmp_path / 's.xlsx', rows), spec, ctx), spec,
                             'Volkswagen', ctx)


def test_staging_keeps_active_rows_and_splits_the_year_range(tmp_path, spec, ctx):
    df = staged(tmp_path, spec, ctx, [part(years='2019-2021'), part('P2', years='2024'),
                                      part('P3', status='Inactive')])
    assert df['part_number'].tolist() == ['P1', 'P2']
    assert df[['min_year', 'max_year']].values.tolist() == [[2019, 2021], [2024, 2024]]
    assert codes(ctx) == []                                     # Inactive is left out, not flagged


def test_staging_flags_and_leaves_out_bad_rows(tmp_path, spec, ctx):
    df = staged(tmp_path, spec, ctx, [part(stock=''), part('P2', model=''), part('P3', make='Audi'),
                                      part('P4', status='Pending'), part('P5', years='20x9'),
                                      part('P6', years='2022-2020'), part('OK')])
    assert df['part_number'].tolist() == ['OK']
    assert codes(ctx) == ['ACCESS_STGNG_MISSING_PART_NUMBER', 'ACCESS_STGNG_MISSING_MODEL_NAME',
                          'ACCESS_STGNG_MAKE_MISMATCH', 'ACCESS_STGNG_STATUS_UNEXPECTED',
                          'ACCESS_YEAR_RANGE_INVALID', 'ACCESS_YEAR_RANGE_REVERSED']
    assert ctx['flags'][3]['message'] == 'Source row 6: status "Pending" is not a known status; row left out'


def test_exact_copies_are_removed_and_conflicting_copies_flagged(tmp_path, spec, ctx):
    df = staged(tmp_path, spec, ctx, [part(), part(), part(), part('P2', msrp='100'), part('P2', msrp='120')])
    out = remove_duplicates(df, ctx)
    assert out['part_number'].tolist() == ['P1', 'P2', 'P2']
    assert codes(ctx) == ['ACCESS_STGNG_DUPLICATE_CONFLICT'] and 'msrp=120' in ctx['flags'][0]['found']
    excluded = [c for c in ctx['changes'] if c['rule'] == 'excluded']
    assert [c['detail'] for c in excluded] == ['exact copy of source row 3'] * 2


# ---------------------------------------------------------------- clean + resolve

def test_clean_types_numbers_and_applies_the_shared_aliases(tmp_path, spec, ctx, taxonomy):
    df = staged(tmp_path, spec, ctx, [part(msrp='$100'), part('P2', model='Golf')])
    out = clean_accessories(df, spec, taxonomy['aliases'], ctx)
    assert pd.isna(out.loc[0, 'msrp']) and out.loc[1, 'msrp'] == 100
    assert codes(ctx) == ['ACCESS_CLEAN_NOT_NUMERIC']
    assert out['model_name_clean'].tolist() == ['Golf GTI', 'Golf']      # Golf alone is never touched


@pytest.mark.parametrize('name, model, submodel', [
    ('GTI', 'Golf', 'GTI'), ('Golf', 'Golf', ''), ('Golf R', 'Golf', 'R'), ('Atlas Cross Sport', 'Atlas', 'Cross Sport'),
    ('Jetta GLI', 'Jetta', 'GLI'), ('ID. Buzz', 'ID. Buzz', ''), ('e-Golf', 'e-Golf', '')])
def test_resolve_names_matches_whole_names(tmp_path, spec, ctx, taxonomy, name, model, submodel):
    df = clean_accessories(staged(tmp_path, spec, ctx, [part(model=name)]), spec, taxonomy['aliases'], ctx)
    out = resolve_names(df, taxonomy, ctx)
    assert (out.loc[0, 'model'], out.loc[0, 'submodel']) == (model, submodel) and codes(ctx) == []


@pytest.mark.parametrize('name', ['Polo', 'Tiguan Allspace'])
def test_unknown_names_are_flagged_not_guessed(tmp_path, spec, ctx, taxonomy, name):
    df = clean_accessories(staged(tmp_path, spec, ctx, [part(model=name)]), spec, taxonomy['aliases'], ctx)
    out = resolve_names(df, taxonomy, ctx)
    assert out.loc[0, 'model'] == '' and codes(ctx) == ['ACCESS_LOOKUP_UNKNOWN_MODEL_NAME']


def test_unique_keys_are_clipped_to_the_window(tmp_path, spec, ctx, taxonomy, settings):
    df = clean_accessories(staged(tmp_path, spec, ctx, [part(years='2018-2021'), part('P2', years='2021')]),
                           spec, taxonomy['aliases'], ctx)
    keys = unique_keys(resolve_names(df, taxonomy, ctx), settings)
    assert keys == {('Golf', 'GTI', 2020): 1, ('Golf', 'GTI', 2021): 2}


# ---------------------------------------------------------------- data quality + export names

def test_quality_rules_and_fitment_hints(tmp_path, spec, ctx, taxonomy):
    df = staged(tmp_path, spec, ctx, [part(msrp='50', cost='60'), part('P2', cost='0', labor='-1'),
                                      part('P3', desc='Front Mud Flaps, not for R-Line')])
    check_quality(clean_accessories(df, spec, taxonomy['aliases'], ctx), spec, ctx)
    assert codes(ctx) == ['ACCESS_DQ_VALUE_NOT_ABOVE', 'ACCESS_DQ_VALUE_ZERO', 'ACCESS_DQ_VALUE_NEGATIVE',
                          'ACCESS_DQ_FITMENT_HINT']
    assert ctx['flags'][0]['message'] == 'msrp 50 is not above cost 60'
    assert ctx['flags'][-1]['severity'] == 'info'


def test_sheet_names_follow_excel_rules():
    used = set()
    assert sheet_name('ID.4', used) == 'ID.4'
    assert sheet_name('Golf/GTI: [Performance]', used) == 'Golf GTI   Performance'
    long = 'A' * 40
    assert sheet_name(long, used) == 'A' * 31 and sheet_name(long, used) == 'A' * 29 + '~2'
