import pandas as pd
import pytest

from pipeline.logging_helpers import end_run, start_run
from pipeline.parse_helpers import build_vehicles
from pipeline.validate_helpers import (build_review_queue, check_model_number_consistency, check_option_sets,
                                       check_required)


@pytest.fixture
def ctx(tmp_path):
    context = start_run({'min_model_year': 2020}, 'test', tmp_path, run_id='validate')
    yield context
    end_run(context)


@pytest.fixture
def make_vehicles(taxonomy):
    def _make(rows):
        df = pd.DataFrame(rows, columns=['model_number', 'model_year', 'description'])
        df['description_clean'] = df['description']
        return build_vehicles(df, taxonomy)
    return _make


def option_categories(taxonomy):
    return [c for c, s in taxonomy['categories'].items() if s['source'] == 'keywords' and c != 'inventory_status']


def test_value_outside_option_set_is_not_offered(ctx, make_vehicles, option_sets, taxonomy):
    vehicles = make_vehicles([['T1', '2025', 'Tiguan Execline'],        # Execline not offered on 2025 Tiguan
                              ['T2', '2025', 'Tiguan Highline R-Line']])   # fine
    assert check_option_sets(vehicles, option_sets, option_categories(taxonomy), ctx) == 1
    flag = ctx['flags'][0]
    assert (flag['code'], flag['vehicle_id'], flag['category'], flag['value']) == \
           ('VEH_VALID_OPTION_NOT_OFFERED', 'VW-2025-T1', 'trim', 'Execline')
    assert flag['message'] == 'Tiguan 2025 has trim = Execline, which its option set does not offer'
    assert 'config/vehicles/tiguan.yaml' in flag['checked'] and flag['fix'].startswith('1) ')


def test_unlisted_category_means_not_offered(ctx, make_vehicles, option_sets, taxonomy):
    vehicles = make_vehicles([['G1', '2025', 'Golf GTI Autobahn Manual']])   # 2025 GTI lists no transmission
    check_option_sets(vehicles, option_sets, option_categories(taxonomy), ctx)
    assert 'nothing (category not listed)' in ctx['flags'][0]['found']


def test_new_model_year_has_no_option_set(ctx, make_vehicles, option_sets, taxonomy):
    vehicles = make_vehicles([['T9', '2028', 'Tiguan Highline']])
    check_option_sets(vehicles, option_sets, option_categories(taxonomy), ctx)
    assert [f['code'] for f in ctx['flags']] == ['VEH_VALID_NOT_IN_CONFIG']
    assert 'declared: 2020-2020' in ctx['flags'][0]['found']


def test_model_number_consistency(ctx, make_vehicles):
    vehicles = make_vehicles([['RM1VPJ', '2026', 'Tiguan Comfortline R-Line Black'],
                              ['RM1VPJ', '2027', 'Tiguan Comfortline R-Line Black Edition'],
                              ['SHORT', '2023', 'Atlas Comfortline 2.0 TSI 4MOTION'],
                              ['SHORT', '2024', 'Atlas Comfortline']])        # shorter later: not flagged
    count = check_model_number_consistency(vehicles, ['model', 'submodel', 'trim', 'appearance_package'], ctx)
    assert count == 2 and {f['value'] for f in ctx['flags']} == {'RM1VPJ'}


def test_required_and_review_queue(ctx, make_vehicles):
    vehicles = make_vehicles([['P1', '2025', 'Polo Highline']])        # unknown model -> model empty
    assert check_required(vehicles, ctx) == 1
    queue = build_review_queue(ctx['flags'], vehicles)
    assert queue.iloc[0]['description_clean'] == 'Polo Highline'
