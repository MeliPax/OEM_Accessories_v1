import pytest

from pipeline.parse_helpers import build_matchers, parse_description, split_multi_value, to_cell, tokenize


@pytest.fixture(scope='module')
def parse(taxonomy):
    matchers = build_matchers(taxonomy)

    def _parse(description):
        p = parse_description(description, matchers)
        out = {'model': p['model'], 'series': p['series'], 'submodel': p['submodel']}
        out.update({c: to_cell(v) for c, v in p['values'].items() if v})
        return {k: v for k, v in out.items() if v}, p
    return _parse


# golden examples from the taxonomy guide (normalized values: DSG -> "DSG Dual-Clutch")
@pytest.mark.parametrize('description, expected', [
    ('Golf GTI Autobahn DSG', {'model': 'Golf', 'series': 'Performance', 'submodel': 'GTI', 'trim': 'Autobahn',
                               'transmission': 'DSG Dual-Clutch'}),
    ('Golf R', {'model': 'Golf', 'series': 'Performance', 'submodel': 'R'}),
    ('Golf Alltrack Highline', {'model': 'Golf', 'series': 'Adventure', 'submodel': 'Alltrack', 'trim': 'Highline'}),
    ('Golf Alltrack Execline DSG', {'model': 'Golf', 'series': 'Adventure', 'submodel': 'Alltrack',
                                    'trim': 'Execline', 'transmission': 'DSG Dual-Clutch'}),
    ('Atlas Cross Sport Highline', {'model': 'Atlas', 'submodel': 'Cross Sport', 'trim': 'Highline'}),
    ('Golf GTI Autobahn Performance DSG', {'model': 'Golf', 'series': 'Performance', 'submodel': 'GTI',
                                           'trim': 'Autobahn', 'performance_package': 'Performance',
                                           'transmission': 'DSG Dual-Clutch'}),
    ('Taos Highline IQ Drive', {'model': 'Taos', 'trim': 'Highline', 'technology_package': 'IQ.DRIVE'}),
    ('Atlas Comfortline 2.0 TSI 4MOTION', {'model': 'Atlas', 'trim': 'Comfortline', 'engine': '2.0L TSI',
                                           'drivetrain': 'AWD'}),
])
def test_golden_examples(parse, description, expected):
    values, p = parse(description)
    assert values == expected
    assert p['parse_status'] == 'complete'


def test_black_edition_is_special_edition_black_alone_is_appearance(parse):
    assert parse('Tiguan Comfortline R-Line Black Edition')[0] == {
        'model': 'Tiguan', 'trim': 'Comfortline', 'special_edition': 'Black Edition', 'appearance_package': 'R-Line'}
    assert parse('Tiguan Comfortline R-Line Black')[0] == {
        'model': 'Tiguan', 'trim': 'Comfortline', 'appearance_package': 'Black|R-Line'}


def test_longest_model_phrase_wins(parse):
    assert parse('ID. Buzz 1st Edition 4MOTION')[0] == {
        'model': 'ID. Buzz', 'special_edition': '1st Edition', 'drivetrain': 'AWD'}
    assert parse('ID.4 PRO S AWD')[0] == {'model': 'ID.4', 'trim': 'PRO S', 'drivetrain': 'AWD'}


def test_golf_r_is_not_r_line(parse):
    assert parse('Golf R Black')[0]['submodel'] == 'R'
    values = parse('Tiguan Highline R-Line')[0]
    assert 'submodel' not in values and values['appearance_package'] == 'R-Line'


def test_model_scope(parse):
    assert parse('ID.4 S')[0]['trim'] == 'S'
    values, p = parse('Jetta S')                     # "S" is only a trim on ID.4
    assert 'trim' not in values and p['unparsed'] == ['S'] and p['parse_status'] == 'partial'


def test_case_insensitive_and_normalized(parse):
    assert parse('ID.4 Pro RWD w/SK On Battery')[0] == {
        'model': 'ID.4', 'trim': 'PRO', 'drivetrain': 'RWD', 'battery_supplier': 'SK On'}
    assert parse('ID.4 Pro RWD w/LG Battery')[0]['battery_supplier'] == 'LG Energy Solution'


def test_inventory_status_and_stripped_punctuation(parse):
    values, p = parse('Atlas Highline 3.6 FSI 4MOTION *Ltd Avail*')
    assert values['inventory_status'] == 'Limited Availability' and p['parse_status'] == 'complete'


@pytest.mark.parametrize('description, expected', [
    ('Beetle Coupe Dune Auto', {'model': 'Beetle', 'body_style': 'Coupe', 'special_edition': 'Dune',
                                'transmission': 'Automatic'}),
    ('Beetle Convertible Dune Auto', {'model': 'Beetle', 'body_style': 'Convertible', 'special_edition': 'Dune',
                                      'transmission': 'Automatic'}),
    ('Beetle Coupe Wolfsburg Edition', {'model': 'Beetle', 'body_style': 'Coupe',
                                        'special_edition': 'Wolfsburg Edition'}),
    ('Beetle Convertible Wolfsburg Edition', {'model': 'Beetle', 'body_style': 'Convertible',
                                              'special_edition': 'Wolfsburg Edition'}),
])
def test_2019_beetle_words(parse, description, expected):
    assert parse(description)[0] == expected


def test_edition_never_alone(parse):
    values, p = parse('Atlas Edition')
    assert p['unparsed'] == ['Edition'] and 'special_edition' not in values


def test_unknown_model_fails(parse):
    _, p = parse('Polo Highline')
    assert p['parse_status'] == 'failed' and p['unparsed'] == ['Polo', 'Highline']


def test_single_value_conflict_detected(parse):
    _, p = parse('Tiguan Comfortline Highline')
    assert p['conflicts'] == {'trim': {'Comfortline', 'Highline'}}


def test_tokenize_and_multi_value_cells():
    assert tokenize(' Atlas  *Ltd Avail* ') == ['Atlas', 'Ltd', 'Avail']
    assert to_cell({'R-Line', 'Black'}) == 'Black|R-Line'
    assert split_multi_value('Black|R-Line') == ['Black', 'R-Line']
    assert split_multi_value('') == [] and split_multi_value(None) == []
