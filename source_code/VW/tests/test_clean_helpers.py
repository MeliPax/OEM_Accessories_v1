import pandas as pd

from pipeline.clean_helpers import apply_aliases, clean_text_column, clean_value, remove_repeated_words

ALIASES = {'Atlas Sport Cross': 'Atlas Cross Sport'}


def test_apply_aliases_whole_words_case_insensitive():
    assert apply_aliases('atlas sport cross Highline', ALIASES) == 'Atlas Cross Sport Highline'
    assert apply_aliases('Atlas Sport Crossover', ALIASES) == 'Atlas Sport Crossover'
    assert apply_aliases(None, ALIASES) is None


def test_remove_repeated_words_keeps_first_occurrence():
    assert remove_repeated_words('Golf R Golf R Black') == 'Golf R Black'
    assert remove_repeated_words('ID. Buzz ID. Buzz 1st Edition') == 'ID. Buzz 1st Edition'
    assert remove_repeated_words('  Jetta GLI gli ') == 'Jetta GLI'


def test_clean_value_explains_each_rule():
    cleaned, steps = clean_value('Atlas Sport Cross  Atlas Highline', ALIASES)
    assert cleaned == 'Atlas Cross Sport Highline'
    assert [s[0] for s in steps] == ['alias', 'trim_spaces', 'remove_repeated_words']
    assert steps[0][3] == 'Atlas Sport Cross -> Atlas Cross Sport'
    assert steps[2][3] == 'removed: Atlas'


def test_clean_value_unchanged_has_no_steps():
    assert clean_value('Tiguan Highline', ALIASES) == ('Tiguan Highline', [])


def test_clean_text_column_matches_notebook_behaviour():
    df = pd.DataFrame({'Description': ['Golf R Golf R', 'Atlas Sport Cross Execline']})
    out = clean_text_column(df, 'Description', aliases=ALIASES)
    assert out['Description_clean'].tolist() == ['Golf R', 'Atlas Cross Sport Execline']
    assert df.columns.tolist() == ['Description']        # input not modified
