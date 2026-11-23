import copy

import pandas as pd
import pytest

from conftest import replace_in
from pipeline import config_helpers as cfg
from pipeline.config_helpers import ConfigError
from pipeline.logging_helpers import end_run, start_run
from pipeline.parse_helpers import build_vehicles
from pipeline.resolve_helpers import apply_resolutions


@pytest.fixture
def ctx(tmp_path):
    context = start_run({'min_model_year': 2020}, 'test', tmp_path, run_id='resolve')
    yield context
    end_run(context)


@pytest.fixture
def resolve(taxonomy, option_sets):
    def _resolve(rows, ctx=None, sets=option_sets):
        df = pd.DataFrame(rows, columns=['model_number', 'model_year', 'description'])
        df['description_clean'] = df['description']
        out = apply_resolutions(build_vehicles(df, taxonomy), taxonomy, sets, ctx)
        return out.set_index('vehicle_id')
    return _resolve


def test_lone_black_becomes_black_edition_where_offered(ctx, resolve):
    out = resolve([['RM1VPJ', '2025', 'Tiguan Comfortline R-Line Black'],
                   ['RM1VPJ', '2027', 'Tiguan Comfortline R-Line Black Edition'],
                   ['CL26SR', '2025', 'Taos Comfortline Black']], ctx)
    tiguan, taos = out.loc['VW-2025-RM1VPJ'], out.loc['VW-2025-CL26SR']
    assert (tiguan['special_edition'], tiguan['appearance_package']) == ('Black Edition', 'R-Line')
    assert (taos['special_edition'], taos['appearance_package']) == ('Black Edition', '')
    assert tiguan['description_clean'] == 'Tiguan Comfortline R-Line Black'      # wording kept as evidence
    reasons = [c['detail'] for c in ctx['changes'] if c['vehicle_id'] == 'VW-2025-RM1VPJ']
    assert len(reasons) == 2 and 'vehicles/tiguan.yaml 2024-2026 offers special_edition Black Edition' in reasons[0]
    assert 'model number RM1VPJ is Black Edition in 2027' in reasons[0]


def test_black_stays_appearance_where_black_edition_is_not_offered(ctx, resolve):
    out = resolve([['DA1BPT', '2025', 'Golf R Black'],
                   ['CMD7PR', '2025', 'Atlas Cross Sport Comfortline R-Line Black']], ctx)
    assert out.loc['VW-2025-DA1BPT', 'appearance_package'] == 'Black'
    assert out.loc['VW-2025-CMD7PR', 'appearance_package'] == 'Black|R-Line'
    assert ctx['changes'] == [] and ctx['flags'] == []


def test_model_number_evidence_alone_only_suggests(ctx, resolve, option_sets):
    sets = copy.deepcopy(option_sets)
    for s in sets:                                   # take Black Edition away from Tiguan 2024-2026
        if s['model'] == 'Tiguan' and s['start'] == 2024:
            s['options']['special_edition'] = set()
            s['options']['appearance_package'] = {'Black', 'R-Line'}
    out = resolve([['RM1VPJ', '2025', 'Tiguan Comfortline R-Line Black'],
                   ['RM1VPJ', '2027', 'Tiguan Comfortline R-Line Black Edition']], ctx, sets)
    assert out.loc['VW-2025-RM1VPJ', 'appearance_package'] == 'Black|R-Line'
    assert [f['code'] for f in ctx['flags']] == ['VEH_RESOLVE_SUGGESTED']
    assert 'Black Edition in 2027' in ctx['flags'][0]['found']


def test_existing_special_edition_is_a_conflict(ctx, resolve):
    out = resolve([['T1', '2025', 'Tiguan Comfortline United Edition Black']], ctx)
    assert out.loc['VW-2025-T1', 'special_edition'] == 'United Edition'
    assert [f['code'] for f in ctx['flags']] == ['VEH_RESOLVE_CONFLICT']


def test_broken_resolution_fails_to_load(config_copy):
    replace_in(config_copy / 'keywords.yaml', 'to: { category: special_edition, value: Black Edition }',
               'to: { category: special_edition, value: Blak Edition }')
    with pytest.raises(ConfigError, match='to value "Blak Edition" is not produced'):
        cfg.validate_taxonomy(cfg.load_taxonomy(config_copy))


def test_resolution_needs_a_keyword_that_produces_from(config_copy):
    replace_in(config_copy / 'keywords.yaml', '  - match: Black               #', '  - match: Noir               #')
    with pytest.raises(ConfigError, match='no keyword "Noir" produces appearance_package = "Black"'):
        cfg.validate_taxonomy(cfg.load_taxonomy(config_copy))
