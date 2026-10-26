"""Break a clean description into taxonomy values, using the vocabulary (models.yaml, keywords.yaml).

Parse order for one description (deterministic, longest match first):
    1. model phrase at the start (ID. Buzz before ID.4), then a submodel phrase for that model
    2. keyword phrases and words over the remaining tokens, longest first, honouring model scope
    3. leftovers -> unparsed_tokens; parse_status = complete / partial / failed
"""

import pandas as pd

from pipeline.logging_helpers import log_change, log_flag, vehicle_id

STRIP_CHARS = '*(),'
MULTI_SEPARATOR = '|'


# ---------------------------------------------------------------- matchers

def build_matchers(taxonomy):
    """Pre-compute model phrases and keyword entries, sorted longest first."""
    model_phrases = []
    for model, spec in taxonomy['models'].items():
        model_tokens = model.lower().split()
        model_phrases.append({'tokens': model_tokens, 'model': model, 'submodel': None, 'series': None,
                              'match': model})
        for submodel, sub_spec in ((spec or {}).get('submodels') or {}).items():
            model_phrases.append({'tokens': model_tokens + str(submodel).lower().split(), 'model': model,
                                  'submodel': str(submodel), 'series': (sub_spec or {}).get('series'),
                                  'match': f'{model} {submodel}'})
    model_phrases.sort(key=lambda m: -len(m['tokens']))

    keywords = [{**kw, 'tokens': kw['match'].lower().split(), 'scope': set(kw['models'])}
                for kw in taxonomy['keywords']]
    keywords.sort(key=lambda k: -len(k['tokens']))      # stable: file order among equal lengths

    keyword_categories = [n for n, c in taxonomy['categories'].items() if c.get('source') == 'keywords']
    multi = {n for n, c in taxonomy['categories'].items() if c.get('multi_value')}
    return {'models': model_phrases, 'keywords': keywords, 'make': taxonomy['make'],
            'keyword_categories': keyword_categories, 'multi_value': multi}


def tokenize(description):
    """Split on spaces and strip * ( ) , around each word; empty pieces are dropped."""
    if not isinstance(description, str):
        return []
    return [t for t in (w.strip(STRIP_CHARS) for w in description.split()) if t]


# ---------------------------------------------------------------- parsing

def match_model(tokens, matchers):
    """Longest model (+ submodel) phrase at the start. Returns (match dict or None, remaining tokens)."""
    lowered = [t.lower() for t in tokens]
    for phrase in matchers['models']:
        n = len(phrase['tokens'])
        if lowered[:n] == phrase['tokens']:
            return phrase, tokens[n:]
    return None, tokens


def classify_tokens(tokens, matchers, model):
    """Scan left to right; at each position try keyword entries longest first (model scope respected).
    Returns (matches, unparsed): matches are dicts with category, value, match, kind."""
    lowered = [t.lower() for t in tokens]
    matches, unparsed = [], []
    i = 0
    while i < len(tokens):
        for kw in matchers['keywords']:
            n = len(kw['tokens'])
            if lowered[i:i + n] == kw['tokens'] and (not kw['scope'] or model in kw['scope']):
                matches.append({'category': kw['category'], 'value': kw['value'],
                                'match': ' '.join(tokens[i:i + n]), 'kind': kw['kind']})
                i += n
                break
        else:
            unparsed.append(tokens[i])
            i += 1
    return matches, unparsed


def parse_description(description, matchers):
    """Parse one clean description. Returns a dict with model, series, submodel, a set of values per
    keyword category, the matches (for logging), unparsed tokens, conflicts and parse_status."""
    tokens = tokenize(description)
    model_match, rest = match_model(tokens, matchers)
    result = {'model': None, 'series': None, 'submodel': None, 'model_match': None,
              'values': {c: set() for c in matchers['keyword_categories']},
              'matches': [], 'unparsed': [], 'conflicts': {}}

    if model_match is None:
        result['unparsed'] = tokens
        result['parse_status'] = 'failed'
        return result

    result.update(model=model_match['model'], submodel=model_match['submodel'],
                  series=model_match['series'], model_match=model_match['match'])
    matches, unparsed = classify_tokens(rest, matchers, model_match['model'])
    for m in matches:
        result['values'][m['category']].add(m['value'])
    result['matches'] = matches
    result['unparsed'] = unparsed
    result['conflicts'] = {c: v for c, v in result['values'].items()
                           if len(v) > 1 and c not in matchers['multi_value']}
    result['parse_status'] = 'complete' if not unparsed else 'partial'
    return result


def to_cell(values):
    """A set of values as one cell: sorted and joined with '|'; empty set -> ''."""
    return MULTI_SEPARATOR.join(sorted(values)) if values else ''


def split_multi_value(cell):
    """The only reader of the '|' format: 'IQ.DRIVE|R-Line' -> ['IQ.DRIVE', 'R-Line']; '' -> []."""
    if cell is None or (not isinstance(cell, str) and pd.isna(cell)) or cell == '':
        return []
    return str(cell).split(MULTI_SEPARATOR)


# ---------------------------------------------------------------- pipeline step

VEHICLE_COLUMNS = ['vehicle_id', 'make', 'model_number', 'model_year', 'description_raw', 'description_clean',
                   'model', 'series', 'submodel']
LINEAGE_COLUMNS = ['unparsed_tokens', 'parse_status', 'source_file', 'taxonomy_version']


def vehicle_columns(taxonomy):
    keyword_categories = [n for n, c in taxonomy['categories'].items() if c.get('source') == 'keywords']
    return VEHICLE_COLUMNS + keyword_categories + LINEAGE_COLUMNS


def build_vehicles(df, taxonomy, ctx=None, step='parse'):
    """Pipeline step: parse each unique clean description once, join back to the rows, and build
    the vehicles table. Logs every filled value with the keyword that filled it, and flags
    unknown words and single-value conflicts."""
    matchers = build_matchers(taxonomy)
    parsed = {d: parse_description(d, matchers) for d in df['description_clean'].unique()}

    rows = []
    for _, src in df.iterrows():
        p = parsed[src['description_clean']]
        vid = vehicle_id(src['model_year'], src['model_number'])
        row = {'vehicle_id': vid, 'make': taxonomy['make'], 'model_number': src['model_number'],
               'model_year': src['model_year'], 'description_raw': src['description'],
               'description_clean': src['description_clean'],
               'model': p['model'] or '', 'series': p['series'] or '', 'submodel': p['submodel'] or ''}
        for category, values in p['values'].items():
            row[category] = to_cell(values)
        row.update(unparsed_tokens=' '.join(p['unparsed']), parse_status=p['parse_status'],
                   source_file=src.get('source_file', ''), taxonomy_version=taxonomy['version'])
        rows.append(row)
        _log_parse(ctx, step, row, p)

    return pd.DataFrame(rows, columns=vehicle_columns(taxonomy))


def _log_parse(ctx, step, row, p):
    if ctx is None:
        return
    key = {'vehicle_id': row['vehicle_id'], 'model_number': row['model_number'], 'model_year': row['model_year']}
    if p['model']:
        log_change(ctx, step, key, 'model', '', p['model'], 'model_phrase', f'"{p["model_match"]}"')
        if p['submodel']:
            log_change(ctx, step, key, 'submodel', '', p['submodel'], 'model_phrase', f'"{p["model_match"]}"')
        if p['series']:
            log_change(ctx, step, key, 'series', '', p['series'], 'models_yaml_series',
                       f'series of {p["model"]} {p["submodel"]}')
    for m in p['matches']:
        log_change(ctx, step, key, m['category'], '', m['value'], f'keyword_{m["kind"]}', f'"{m["match"]}"')

    if p['parse_status'] == 'failed':
        log_flag(ctx, step, key, 'no_model_match', 'error', 'model', '',
                 f'"{row["description_clean"]}" does not start with a model in models.yaml')
    for token in p['unparsed'] if p['parse_status'] != 'failed' else []:
        log_flag(ctx, step, key, 'unknown_token', 'warning', '', token,
                 f'"{token}" in "{row["description_clean"]}" matches no keyword')
    for category, values in p['conflicts'].items():
        log_flag(ctx, step, key, 'single_value_conflict', 'warning', category, to_cell(values),
                 f'{category} allows one value, found {len(values)}')
