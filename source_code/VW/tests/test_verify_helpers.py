"""Human-verified vehicle facts (idea 009): exact matching, downgrades, contradictions, expiry, unused facts."""

from datetime import date

import pandas as pd
import pytest

from pipeline.logging_helpers import end_run, log_flag, start_run
from pipeline.verify_helpers import (accessory_contradictions, drop_verified, facts_in_window, match_flag,
                                     vehicle_contradictions, verify_flags)

GOLF_R = {'file': 'golf.yaml', 'entry': 1, 'label': 'golf.yaml #1', 'model': 'Golf', 'submodel': 'R',
          'vehicle': 'Golf R', 'kind': 'never_offered', 'years': {2020, 2021}, 'category': '', 'values': set(),
          'until': '', 'reason': 'Golf R returned for 2022', 'verified_by': 'P.M', 'verified_on': '2026-10-28'}
TAOS_2027 = {**GOLF_R, 'file': 'taos.yaml', 'label': 'taos.yaml #1', 'model': 'Taos', 'submodel': None,
             'vehicle': 'Taos', 'kind': 'no_parts_expected', 'years': {2027}, 'until': '2027-06-30'}
GTI_MANUAL = {**GOLF_R, 'label': 'golf.yaml #2', 'submodel': 'GTI', 'vehicle': 'Golf GTI', 'years': {2025},
              'category': 'transmission', 'values': {'Manual'}}
BEFORE, AFTER = date(2026, 10, 28), date(2027, 7, 1)


@pytest.fixture
def ctx(tmp_path, settings):
    c = start_run(settings, 'test', tmp_path, run_id='ver', pipeline='vw_accessories')
    yield c
    end_run(c)


def lookup_flag(ctx, model, submodel, year, code='ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN'):
    key = f'volkswagen|{model.lower()}|{(submodel or "(base)").lower()}|{year}'
    return log_flag(ctx, 'lookup', {'record': key, 'model': model, 'submodel': submodel or '', 'model_year': year},
                    code, subject=key, vehicle=f'{model} {submodel or ""}'.strip(), year=year, first=2022)


def cover_flag(ctx, model, year):
    key = f'volkswagen|{model.lower()}|(base)|{year}'
    return log_flag(ctx, 'coverage', {'record': key, 'model': model, 'submodel': '', 'model_year': year},
                    'ACCESS_COVER_VEHICLE_NO_PARTS', subject=key, count=5, vehicle=model, year=year)


# ---------------------------------------------------------------- matching

def test_only_an_exact_model_submodel_and_year_matches(ctx):
    codes = {'ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN'}
    assert match_flag(lookup_flag(ctx, 'Golf', 'R', 2020), [GOLF_R], codes) is GOLF_R
    assert match_flag(lookup_flag(ctx, 'Golf', 'R', 2022), [GOLF_R], codes) is None           # other year
    assert match_flag(lookup_flag(ctx, 'Golf', 'GTI', 2020), [GOLF_R], codes) is None         # other submodel
    assert match_flag(lookup_flag(ctx, 'Golf', None, 2020), [GOLF_R], codes) is None          # base Golf


def test_codes_that_are_not_verifiable_are_never_touched(ctx):
    flag = log_flag(ctx, 'lookup', {'record': 'k', 'model': 'Golf', 'submodel': 'R', 'model_year': 2020},
                    'ACCESS_LOOKUP_NO_CONFIG_FOR_MODEL', vehicle='Golf R')
    rows, verified = verify_flags(ctx, [GOLF_R], today=BEFORE)
    assert flag['severity'] == 'error' and rows == [] and verified == set()


def test_an_option_fact_never_explains_a_lookup_flag(ctx):
    flag = lookup_flag(ctx, 'Golf', 'GTI', 2025)
    verify_flags(ctx, [GTI_MANUAL], today=BEFORE)
    assert flag['severity'] == 'error'


# ---------------------------------------------------------------- the verify step

def test_a_covered_flag_drops_to_info_and_keeps_its_record(ctx):
    flag = lookup_flag(ctx, 'Golf', 'R', 2020)
    rows, verified = verify_flags(ctx, [GOLF_R], today=BEFORE)
    assert (flag['severity'], flag['original_severity'], flag['verified_entry']) == ('info', 'error', 'golf.yaml #1')
    assert verified == {('ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN', 'volkswagen|golf|r|2020')}
    assert rows[0]['verified_by'] == 'P.M' and rows[0]['reason'] and rows[0]['entry'] == 'golf.yaml #1'
    assert flag in ctx['flags']                                                              # never deleted


def test_no_parts_expected_holds_until_its_date_then_the_flag_comes_back(ctx):
    flag = cover_flag(ctx, 'Taos', 2027)
    verify_flags(ctx, [TAOS_2027], today=BEFORE)
    assert flag['severity'] == 'info'

    later = cover_flag(ctx, 'Taos', 2027)
    verify_flags(ctx, [TAOS_2027], today=AFTER)
    assert later['severity'] == 'warning'
    assert any(f['code'] == 'ACCESS_VERIFY_EXPIRED' and f['severity'] == 'warning' for f in ctx['flags'])


def test_a_fact_that_matches_nothing_is_reported(ctx):
    verify_flags(ctx, [GOLF_R], today=BEFORE)
    unused = [f for f in ctx['flags'] if f['code'] == 'ACCESS_VERIFY_ENTRY_UNUSED']
    assert len(unused) == 1 and unused[0]['severity'] == 'info' and unused[0]['record'] == 'golf.yaml #1'


def test_facts_outside_the_window_are_set_aside():
    inside, outside = facts_in_window([GOLF_R, TAOS_2027], {'min_model_year': 2024, 'max_model_year': None})
    assert inside == [TAOS_2027] and outside == [GOLF_R]
    assert facts_in_window([GOLF_R], {'min_model_year': 2021, 'max_model_year': None}) == ([GOLF_R], [])


def test_review_rows_of_verified_flags_are_left_out():
    rows = [{'code': 'C', 'match_key': 'a'}, {'code': 'C', 'match_key': 'b'}, {'code': 'D', 'match_key': 'a'}]
    assert drop_verified(rows, {('C', 'a')}) == rows[1:]


# ---------------------------------------------------------------- contradictions

def test_vehicles_in_the_db_for_a_never_offered_year_are_an_error(ctx):
    index = {'index': {('Golf', 'R', 2021): [{'model_number': 'CD1RZ1'}]}}
    assert accessory_contradictions(ctx, [GOLF_R], index, 'Volkswagen') == 1
    flag = ctx['flags'][-1]
    assert flag['code'] == 'ACCESS_VERIFY_CONTRADICTED' and flag['severity'] == 'error'
    assert flag['record'] == 'volkswagen|golf|r|2021' and 'CD1RZ1' in flag['found']


def vehicles(*rows):
    return pd.DataFrame([{'vehicle_id': f'VW-{y}-{n}', 'model': m, 'submodel': s, 'model_year': y,
                          'transmission': t, 'description_clean': f'{m} {s} {t}'} for m, s, y, n, t in rows])


def test_a_vehicle_in_the_export_contradicts_a_never_offered_year_or_option(ctx):
    df = vehicles(('Golf', 'R', 2021, 'R1', 'Manual'), ('Golf', 'R', 2022, 'R2', 'Manual'),
                  ('Golf', 'GTI', 2025, 'G1', 'Manual'), ('Golf', 'GTI', 2025, 'G2', 'Automatic'))
    assert vehicle_contradictions(ctx, [GOLF_R, GTI_MANUAL], df) == 2
    found = sorted((f['vehicle_id'], f['code'], f['severity']) for f in ctx['flags'])
    assert found == [('VW-2021-R1', 'VEH_VERIFY_CONTRADICTED', 'error'),
                     ('VW-2025-G1', 'VEH_VERIFY_CONTRADICTED', 'error')]
    assert 'Golf GTI with transmission Manual' in ctx['flags'][1]['message']
