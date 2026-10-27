"""The flag message catalogue: config/messages.yaml (planning/ideas/004_error_message_catalogue_design.md).

Every flag and fatal has a code (<PIPELINE>_<STAGE>_<WHAT>, e.g. VEH_PARSE_UNKNOWN_WORD). Its severity and
wording (message, causes, fix) live in messages.yaml; the code only passes the facts:

    entry = message_for(catalogue, 'VEH_PARSE_UNKNOWN_WORD', token='Rline', description='Tiguan Rline')
    entry['message']   # 'Word "Rline" in "Tiguan Rline" matches no keyword'
"""

import re
import string
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'config' / 'messages.yaml'
SEVERITIES = ('fatal', 'error', 'warning', 'info')
CODE_PATTERN = re.compile(r'^(CONFG|VEH|ACCESS)_[A-Z0-9]+(_[A-Z0-9]+)*$')
FIELDS = ('severity', 'message', 'causes', 'fix')

_default = None


class MessageError(Exception):
    """messages.yaml is broken, or the code asked for a code / fact it doesn't define."""


def load_messages(path=DEFAULT_PATH):
    """Read and check messages.yaml. Returns {code: entry}."""
    path = Path(path)
    if not path.exists():
        raise MessageError(f'messages.yaml: file not found ({path})')
    try:
        with open(path, encoding='utf-8') as f:
            catalogue = yaml.safe_load(f) or {}
    except yaml.YAMLError as error:
        raise MessageError(f'messages.yaml: not valid YAML ({error})') from error

    errors = []
    for code, entry in catalogue.items():
        if not CODE_PATTERN.match(str(code)):
            errors.append(f'{code}: code must look like <CONFG|VEH|ACCESS>_<STAGE>_<WHAT>, upper case')
        entry = entry or {}
        missing = [f for f in FIELDS if not entry.get(f)]
        if missing:
            errors.append(f'{code}: missing {", ".join(missing)}')
            continue
        if entry['severity'] not in SEVERITIES:
            errors.append(f'{code}: severity must be one of {", ".join(SEVERITIES)}, got {entry["severity"]!r}')
        for field in ('causes', 'fix'):
            if not isinstance(entry[field], list):
                errors.append(f'{code}: {field} must be a list')
        unknown = placeholders(entry) - set(entry.get('facts') or [])
        if unknown:
            errors.append(f'{code}: placeholders {sorted(unknown)} are not listed under facts')
    if errors:
        raise MessageError('messages.yaml: ' + f'{len(errors)} problem(s)\n  - ' + '\n  - '.join(errors))
    return catalogue


def default_messages():
    """The catalogue in config/messages.yaml, loaded once (used when no ctx carries one)."""
    global _default
    if _default is None:
        _default = load_messages()
    return _default


def placeholders(entry):
    """The {fact} names used in an entry's message, causes and fix."""
    texts = [entry.get('message') or ''] + list(entry.get('causes') or []) + list(entry.get('fix') or [])
    return {name for text in texts for _, name, _, _ in string.Formatter().parse(str(text)) if name}


def message_for(catalogue, code, **facts):
    """The entry for code with its texts filled from facts: {code, severity, message, causes, fix}."""
    if code not in catalogue:
        raise MessageError(f'{code}: not defined in messages.yaml')
    entry = catalogue[code]
    needed = set(entry.get('facts') or [])
    missing = needed - set(facts)
    if missing:
        raise MessageError(f'{code}: facts {sorted(missing)} not passed')
    values = {k: _text(v) for k, v in facts.items()}
    return {'code': code, 'severity': entry['severity'],
            'message': str(entry['message']).format(**values),
            'causes': [str(c).format(**values) for c in entry['causes']],
            'fix': [str(s).format(**values) for s in entry['fix']]}


def join_causes(causes):
    return '  '.join(f'{chr(ord("a") + i)}) {c}' for i, c in enumerate(causes))


def join_fix(fix):
    return '  '.join(f'{i}) {s}' for i, s in enumerate(fix, start=1))


def describe(catalogue, code, **facts):
    """Multi-line text for a code (used for fatals and config errors): message, causes, fix."""
    m = message_for(catalogue, code, **facts)
    return f'{code}: {m["message"]}\n  causes: {join_causes(m["causes"])}\n  fix:    {join_fix(m["fix"])}'


def _text(value):
    if isinstance(value, (set, frozenset, list, tuple)):
        return ', '.join(str(v) for v in value)
    return '' if value is None else str(value)
