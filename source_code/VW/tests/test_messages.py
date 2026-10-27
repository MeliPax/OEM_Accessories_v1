import re

import pytest

from conftest import CONFIG_DIR, VW_DIR, replace_in
from pipeline.message_helpers import MessageError, load_messages, message_for

CODE_IN_SOURCE = re.compile(r"""['"]((?:CONFG|VEH|ACCESS)_[A-Z0-9_]+)['":]""")


def codes_used_in_code():
    files = list((VW_DIR / 'pipeline').glob('*.py')) + list(VW_DIR.glob('run_*.py'))
    return {code for f in files for code in CODE_IN_SOURCE.findall(f.read_text(encoding='utf-8'))}


def test_catalogue_loads_and_every_entry_fills():
    catalogue = load_messages(CONFIG_DIR / 'messages.yaml')
    for code, entry in catalogue.items():
        facts = {name: f'<{name}>' for name in entry.get('facts') or []}
        filled = message_for(catalogue, code, **facts)
        assert filled['message'] and filled['causes'] and filled['fix'], code
        assert '{' not in filled['message'], code


def test_every_code_used_in_the_code_is_in_the_catalogue():
    catalogue = load_messages(CONFIG_DIR / 'messages.yaml')
    missing = codes_used_in_code() - set(catalogue)
    assert not missing, f'codes used in pipeline/ but not in messages.yaml: {sorted(missing)}'


def test_every_catalogue_entry_is_used():
    catalogue = load_messages(CONFIG_DIR / 'messages.yaml')
    unused = set(catalogue) - codes_used_in_code()
    assert not unused, f'messages.yaml entries no code raises: {sorted(unused)}'


def test_missing_fact_and_unknown_code_fail_loudly():
    catalogue = load_messages(CONFIG_DIR / 'messages.yaml')
    with pytest.raises(MessageError, match='facts'):
        message_for(catalogue, 'VEH_PARSE_UNKNOWN_WORD', token='x')
    with pytest.raises(MessageError, match='not defined'):
        message_for(catalogue, 'VEH_DOES_NOT_EXIST')


@pytest.mark.parametrize('old, new, problem', [
    ('severity: warning', 'severity: loud', 'severity must be one of'),
    ('facts: [token, description]', 'facts: [token]', "placeholders ['description']"),
    ('VEH_PARSE_UNKNOWN_WORD:', 'veh_parse_unknown_word:', 'code must look like'),
])
def test_broken_catalogue_is_rejected(config_copy, old, new, problem):
    replace_in(config_copy / 'messages.yaml', old, new)
    with pytest.raises(MessageError, match=re.escape(problem)):
        load_messages(config_copy / 'messages.yaml')
