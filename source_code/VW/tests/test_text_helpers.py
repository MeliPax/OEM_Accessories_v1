"""Comment cleaning (idea 007) and labour units (idea 006), on small hand-made values from today's file."""

import pandas as pd
import pytest

from conftest import CONFIG_DIR
from pipeline import config_helpers as cfg
from pipeline.accessory_helpers import clean_text_columns, convert_units, remove_duplicates
from pipeline.logging_helpers import end_run, start_run
from pipeline.text_helpers import clean_text, find_links

SALSIFY = 'https://app.salsify.com/catalogs/fde773be-fbbd-410b-99ab-5178d20956b6'
HUB = 'https://www.vwhub.com/snetljct/en/web/vw/adhesive'


@pytest.fixture(scope='module')
def spec(settings):
    return cfg.load_accessory_config(CONFIG_DIR, settings)


@pytest.fixture(scope='module')
def rules(spec):
    return spec['text_cleaning']


@pytest.fixture
def ctx(tmp_path, settings):
    c = start_run(settings, 'test', tmp_path, run_id='txt', pipeline='vw_accessories')
    yield c
    end_run(c)


# ---------------------------------------------------------------- clean_text, rule by rule

@pytest.mark.parametrize('before, after, fired', [
    ('|Installs in top left of trunk. ||Weight limit 10 lbs. (5kg)||Not for vehicles with Fender Amplifier',
     'Installs in top left of trunk. Weight limit 10 lbs. (5kg). Not for vehicles with Fender Amplifier.',
     ['pipes', 'sentence_end']),
    ('<p>Only for PR Code 9TG, 9TJ, 9TL</p>Always install the product.',
     'Only for PR Code 9TG, 9TJ, 9TL. Always install the product.', ['html_tags', 'sentence_end']),
    ('<b>Do not attempt activation!</b><br>Always install.', 'Do not attempt activation! Always install.',
     ['html_tags']),
    ('<p>warranty claim process .</p><p>Always install.</p>', 'warranty claim process. Always install.',
     ['html_tags', 'space_before_punctuation']),
    ('<p>CargoTech sold separately.</p><p></p><p>Related Products: 000061166B </p>',
     'CargoTech sold separately. Related Products: 000061166B.', ['html_tags', 'sentence_end']),
    ('Factory floor jack adapter \xa0for replacement only.', 'Factory floor jack adapter for replacement only.',
     ['spaces']),
    ('Rock &amp; road', 'Rock & road.', ['html_entities', 'sentence_end']),
    ('Always install the product.', 'Always install the product.', []),                  # nothing to do
])
def test_each_rule(rules, before, after, fired):
    result = clean_text(before, rules)
    assert result['text'] == after and result['rules'] == fired


def test_a_space_before_a_dot_inside_a_part_reference_is_kept(rules):
    text = 'Fits with the Oettinger roof spoiler (5G0.071.644.B .GRU) only'
    assert clean_text(text, rules)['text'] == text + '.'


def test_salsify_link_is_replaced_and_the_sentence_kept(rules):
    result = clean_text(f'<p>Visit {SALSIFY} for additional product information.</p>', rules)
    assert result['text'] == 'Visit Thule.com for additional product information.'
    assert result['links'] == [(SALSIFY, 'replaced', 'Thule.com')]
    assert result['rules'][0] == f'link_rule: {SALSIFY} -> Thule.com'


def test_vwhub_links_are_kept_whole_with_no_full_stop_added(rules):
    result = clean_text(f'Visit the hyperlink.<br>{HUB}<p>Always install.</p>', rules)
    assert result['text'] == f'Visit the hyperlink. {HUB} Always install.'
    assert result['links'] == [(HUB, 'allowed', '')]


def test_links_stop_at_a_tag_and_before_trailing_punctuation():
    assert [u for *_, u in find_links(f'{HUB}</p><p>Always')] == [HUB]
    assert [u for *_, u in find_links('see https://example.com/a.')] == ['https://example.com/a']


def test_other_links_are_reported_and_kept(rules):
    result = clean_text('See https://example.com/fit-guide for details', rules)
    assert result['text'] == 'See https://example.com/fit-guide for details.'
    assert result['links'] == [('https://example.com/fit-guide', 'unreviewed', '')]


def test_unknown_tags_are_removed_and_reported(rules):
    result = clean_text('<table>Front set of 2.</table>', rules)
    assert result['text'] == 'Front set of 2.' and result['unknown_tags'] == {'table'}
    assert clean_text('<b>Bold.</b>', rules)['unknown_tags'] == set()                   # in remove_tags


# ---------------------------------------------------------------- the clean_text step

def frame(*items):
    return pd.DataFrame([{'source_row': n, 'part_number': p, 'model_name': m, 'comments': c}
                         for n, (p, m, c) in enumerate(items, start=3)])


def test_step_cleans_each_distinct_text_once_and_keeps_the_raw_text(spec, ctx):
    df, review = clean_text_columns(frame(('P1', 'Golf', '<p>A.</p>'), ('P2', 'Jetta', '<p>A.</p>'),
                                          ('P3', 'Golf', '')), spec, ctx)
    assert df['comments'].tolist() == ['A.', 'A.', ''] and df['comments_source'].tolist() == ['<p>A.</p>'] * 2 + ['']
    changes = [c for c in ctx['changes'] if c['step'] == 'clean_text']
    assert len(changes) == 1 and changes[0]['rule'] == 'html_tags' and changes[0]['detail'] == '2 rows'
    assert review == []


def test_step_flags_unreviewed_links_for_review(spec, ctx):
    _, review = clean_text_columns(frame(('P1', 'Golf', 'See https://example.com/x')), spec, ctx)
    assert [f['code'] for f in ctx['flags']] == ['ACCESS_CLEAN_UNREVIEWED_LINK']
    assert ctx['flags'][0]['severity'] == 'warning' and 'host example.com' in ctx['flags'][0]['found']
    assert len(review) == 1 and review[0]['type'] == 'value' and review[0]['part_number'] == 'P1'


def test_markup_only_copies_become_one_row_after_dedupe(spec, ctx):
    df, _ = clean_text_columns(frame(('P1', 'Golf', '<p>A.</p>'), ('P1', 'Golf', 'A.')), spec, ctx)
    assert len(remove_duplicates(df, ctx)) == 1                                          # C5


# ---------------------------------------------------------------- units (ideas 006, 013)

def labour(*values):
    return pd.DataFrame([{'source_row': n, 'part_number': f'P{n}', 'model_name': 'Golf', 'labor_time_source': v}
                         for n, v in enumerate(values, start=3)])


def test_time_units_become_hours_in_a_new_labor_hours_column(spec, ctx):
    assert spec['units']['columns']['labor_time_source']['factor'] == 1 / 100
    df, review = convert_units(labour(0, 10, 25, 250, 300, None), spec, ctx)
    assert df['labor_hours'].tolist()[:5] == [0.0, 0.1, 0.25, 2.5, 3.0] and pd.isna(df['labor_hours'].iloc[5])
    assert df['labor_time_source'].tolist()[:5] == [0, 10, 25, 250, 300]          # read value kept unchanged
    assert 'labor_time' not in df.columns and 'labor_time_source_source' not in df.columns
    changes = [(c['before'], c['after']) for c in ctx['changes'] if c['rule'] == 'unit_convert']
    assert changes == [('10', '0.1'), ('25', '0.25'), ('250', '2.5'), ('300', '3')]  # 0 stays 0, not logged
    assert review == [] and ctx['flags'] == []


def test_suspect_values_are_flagged_and_left_empty(spec, ctx):
    df, review = convert_units(labour(0.4, 0.4, 1200, 50), spec, ctx)
    assert pd.isna(df['labor_hours'].iloc[:3]).all() and df['labor_hours'].iloc[3] == 0.5
    assert df['labor_time_source'].tolist() == [0.4, 0.4, 1200, 50]
    found = sorted(f['found'] for f in ctx['flags'])
    assert found == ['above 1000 time_units', 'not a whole number of time_units',
                     'not a whole number of time_units']
    assert ctx['flags'][0]['message'] == ('Part P3: labor_time_source 0.4 time_units looks like the wrong unit '
                                          '(not a whole number of time_units); labor_hours left empty, not '
                                          'converted to hours (1 row)')
    changes = [(c['before'], c['after']) for c in ctx['changes'] if c['rule'] == 'unit_convert']
    assert changes == [('50', '0.5')]                                       # suspect values not logged as changed
    assert {r['code'] for r in review} == {'ACCESS_CLEAN_UNIT_SUSPECT'}
