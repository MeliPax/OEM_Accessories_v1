"""Load and validate the YAML config, and export the flattened definition tables.

Config kinds (see planning/ideas/001_vw_model_ingest_design.md):
    pipeline.yaml                run settings (year window, sources, logging)
    categories.yaml              taxonomy levels
    models.yaml, keywords.yaml   VOCABULARY: what words mean
    vehicles/*.yaml              AVAILABILITY: which options each model has, per year range

Every validation problem raises ConfigError with a readable message; a broken config stops the run.
"""

import hashlib
import re
from pathlib import Path

import pandas as pd
import yaml

YEAR_RULES = {'single_year': ['year_column'], 'range_overlap': ['start_column', 'end_column']}
REVIEW_STATUSES = ('drafted', 'reviewed')     # vehicles/*.yaml: drafted from data, or checked by a person
CONFIG_FILES = ['pipeline.yaml', 'categories.yaml', 'models.yaml', 'keywords.yaml']


class ConfigError(Exception):
    """A config file is missing or invalid. .problems is a list of (code, text), one per problem;
    each code is a CONFG_ entry in messages.yaml (causes and fix)."""

    def __init__(self, text, problems=None):
        super().__init__(text)
        self.problems = problems if problems is not None else [_split_code(text)]


def _split_code(text):
    """'CONFG_VALUE_INVALID: problem' -> ('CONFG_VALUE_INVALID', 'problem')."""
    code, sep, rest = str(text).partition(': ')
    return (code, rest) if sep and code.startswith('CONFG_') else ('CONFG_VALUE_INVALID', str(text))


def read_yaml(path):
    path = Path(path)
    if not path.exists():
        raise ConfigError(f'CONFG_FILE_NOT_FOUND: {path.name}: file not found ({path})')
    try:
        with open(path, encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as error:
        raise ConfigError(f'CONFG_YAML_INVALID: {path.name}: not valid YAML ({error})') from error


# ---------------------------------------------------------------- pipeline.yaml

def load_settings(config_dir):
    """Read pipeline.yaml and check the year window, dataset rules and logging block."""
    settings = read_yaml(Path(config_dir) / 'pipeline.yaml')
    errors = []

    min_year = settings.get('min_model_year')
    max_year = settings.get('max_model_year')
    if not _is_year(min_year):
        errors.append(f'CONFG_VALUE_INVALID: min_model_year must be a 4-digit year, got {min_year!r}')
    if max_year is not None and not _is_year(max_year):
        errors.append(f'CONFG_VALUE_INVALID: max_model_year must be a 4-digit year or empty, got {max_year!r}')
    if _is_year(min_year) and _is_year(max_year) and max_year < min_year:
        errors.append(f'CONFG_VALUE_INVALID: max_model_year ({max_year}) is before min_model_year ({min_year})')

    for name, dataset in (settings.get('datasets') or {}).items():
        rule = (dataset or {}).get('year_rule')
        if rule not in YEAR_RULES:
            errors.append(f'CONFG_VALUE_INVALID: datasets.{name}.year_rule must be one of {sorted(YEAR_RULES)}, got {rule!r}')
            continue
        for key in YEAR_RULES[rule]:
            if not dataset.get(key):
                errors.append(f'CONFG_VALUE_INVALID: datasets.{name}: year_rule {rule} needs {key}')

    logging_block = settings.get('logging') or {}
    keep_runs = logging_block.get('keep_runs', 30)
    if not isinstance(keep_runs, int) or keep_runs < 1:
        errors.append(f'CONFG_VALUE_INVALID: logging.keep_runs must be a positive whole number, got {keep_runs!r}')

    _raise_if(errors, 'pipeline.yaml')
    return settings


def _is_year(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1000 <= value <= 9999


# ---------------------------------------------------------------- taxonomy

def load_taxonomy(config_dir):
    """Read categories, models and keywords into plain dicts, flattening keywords into entries."""
    config_dir = Path(config_dir)
    categories = read_yaml(config_dir / 'categories.yaml').get('categories') or {}
    models_cfg = read_yaml(config_dir / 'models.yaml')
    keywords_cfg = read_yaml(config_dir / 'keywords.yaml')

    resolutions = [
        {'match': str((r or {}).get('match', '')),
         'from_category': ((r or {}).get('from') or {}).get('category'),
         'from_value': str(((r or {}).get('from') or {}).get('value', '')),
         'to_category': ((r or {}).get('to') or {}).get('category'),
         'to_value': str(((r or {}).get('to') or {}).get('value', '')),
         'when': (r or {}).get('when')}
        for r in keywords_cfg.pop('resolutions', None) or []]

    keywords = []
    for category, section in keywords_cfg.items():
        for kind in ('phrases', 'words'):
            for entry in (section or {}).get(kind) or []:
                entry = entry or {}
                match = entry.get('match')
                keywords.append({
                    'category': category,
                    'kind': kind[:-1],                      # phrase / word
                    'match': None if match is None else str(match),
                    'value': str(entry.get('value', match)),
                    'models': [str(m) for m in entry.get('models') or []],
                })

    return {
        'categories': categories,
        'make': models_cfg.get('make'),
        'models': models_cfg.get('models') or {},
        'aliases': models_cfg.get('aliases') or {},
        'keywords': keywords,
        'keyword_sections': list(keywords_cfg),
        'resolutions': resolutions,
        'version': taxonomy_version(config_dir),
    }


def validate_taxonomy(taxonomy):
    """Fail with a readable message if the vocabulary is inconsistent."""
    errors = []
    categories = taxonomy['categories']
    models = taxonomy['models']

    for name, cat in categories.items():
        for key in ('source', 'multi_value', 'use_for_matching'):
            if key not in (cat or {}):
                errors.append(f'CONFG_VALUE_INVALID: categories.yaml: {name} is missing {key}')
    keyword_categories = {n for n, c in categories.items() if (c or {}).get('source') == 'keywords'}

    if not taxonomy['make']:
        errors.append(f'CONFG_VALUE_INVALID: models.yaml: make is missing')
    if not models:
        errors.append(f'CONFG_VALUE_INVALID: models.yaml: no models defined')

    for section in taxonomy['keyword_sections']:
        if section not in categories:
            errors.append(f'CONFG_UNKNOWN_REFERENCE: keywords.yaml: section "{section}" is not a category in categories.yaml')
        elif section not in keyword_categories:
            errors.append(f'CONFG_VALUE_INVALID: keywords.yaml: section "{section}" is a {categories[section]["source"]} '
                          f'category; it cannot be filled from keywords')

    seen = {}
    for kw in taxonomy['keywords']:
        where = f'keywords.yaml: {kw["category"]} {kw["kind"]} "{kw["match"]}"'
        if not kw['match'] or not kw['match'].strip():
            errors.append(f'CONFG_VALUE_INVALID: keywords.yaml: {kw["category"]} has an entry without match')
            continue
        words = kw['match'].split()
        if kw['kind'] == 'word' and len(words) != 1:
            errors.append(f'CONFG_VALUE_INVALID: {where} has {len(words)} words; put it under phrases')
        if kw['kind'] == 'phrase' and len(words) < 2:
            errors.append(f'CONFG_VALUE_INVALID: {where} is a single word; put it under words')
        if kw['match'].strip().lower() == 'edition':
            errors.append(f'CONFG_VALUE_INVALID: {where}: "Edition" is never stored alone; use an edition phrase')
        for model in kw['models']:
            if model not in models:
                errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: models scope names unknown model "{model}"')
        scope = tuple(sorted(kw['models']))
        key = (kw['match'].lower(), scope)
        if key in seen:
            errors.append(f'CONFG_DUPLICATE_ENTRY: {where} is already defined under {seen[key]}')
        seen[key] = kw['category']

    for model, spec in models.items():
        for submodel, sub_spec in ((spec or {}).get('submodels') or {}).items():
            if sub_spec is not None and not isinstance(sub_spec, dict):
                errors.append(f'CONFG_VALUE_INVALID: models.yaml: {model} {submodel} must be a mapping like {{ series: ... }}')

    errors += _resolution_errors(taxonomy, keyword_categories)
    _raise_if(errors, 'taxonomy')
    return taxonomy


RESOLUTION_CONDITIONS = {'option_set_offers'}


def _resolution_errors(taxonomy, keyword_categories):
    """A resolution must re-read a value the vocabulary really produces, into a value it can produce."""
    errors = []
    values = keyword_values(taxonomy)
    produces = {(kw['match'].lower(), kw['category'], kw['value']) for kw in taxonomy['keywords'] if kw['match']}
    for r in taxonomy['resolutions']:
        where = f'keywords.yaml: resolution "{r["match"]}"'
        if r['when'] not in RESOLUTION_CONDITIONS:
            errors.append(f'CONFG_VALUE_INVALID: {where}: when must be one of {sorted(RESOLUTION_CONDITIONS)}, got {r["when"]!r}')
        for side in ('from', 'to'):
            category, value = r[f'{side}_category'], r[f'{side}_value']
            if category not in keyword_categories:
                errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: {side} category {category!r} is not a keyword category')
            elif value not in values.get(category, set()):
                errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: {side} value "{value}" is not produced by any {category} keyword')
        if (r['match'].lower(), r['from_category'], r['from_value']) not in produces:
            errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: no keyword "{r["match"]}" produces '
                          f'{r["from_category"]} = "{r["from_value"]}"')
    return errors


def taxonomy_version(config_dir):
    """Short hash of the vocabulary + availability files, so outputs record which config made them."""
    config_dir = Path(config_dir)
    digest = hashlib.sha1()
    for path in [config_dir / n for n in CONFIG_FILES[1:]] + sorted((config_dir / 'vehicles').glob('*.yaml')):
        if path.exists():
            digest.update(path.name.encode())
            digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()[:10]


def keyword_values(taxonomy):
    """{category: set of normalized values} the vocabulary can produce."""
    values = {}
    for kw in taxonomy['keywords']:
        values.setdefault(kw['category'], set()).add(kw['value'])
    return values


# ---------------------------------------------------------------- option sets

def load_option_sets(config_dir, taxonomy):
    """Read config/vehicles/*.yaml into a flat list of option sets, and validate them."""
    vehicles_dir = Path(config_dir) / 'vehicles'
    files = sorted(vehicles_dir.glob('*.yaml'))
    if not files:
        raise ConfigError(f'CONFG_NO_VEHICLE_FILES: vehicles/: no option-set files found in {vehicles_dir}')

    models = taxonomy['models']
    allowed = keyword_values(taxonomy)
    keyword_categories = set(allowed) | {n for n, c in taxonomy['categories'].items()
                                         if (c or {}).get('source') == 'keywords'}
    option_sets, errors = [], []

    for path in files:
        doc = read_yaml(path)
        model = doc.get('model')
        where = f'vehicles/{path.name}'
        if doc.get('make') != taxonomy['make']:
            errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: make {doc.get("make")!r} does not match models.yaml ({taxonomy["make"]!r})')
        status = doc.get('status', 'drafted')
        if status not in REVIEW_STATUSES:
            errors.append(f'CONFG_VALUE_INVALID: {where}: status must be one of {", ".join(REVIEW_STATUSES)}, '
                          f'got {status!r}')
        if model not in models:
            errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: model {model!r} is not in models.yaml')
            continue
        submodels = (models[model] or {}).get('submodels') or {}

        for i, entry in enumerate(doc.get('option_sets') or [], start=1):
            entry = entry or {}
            submodel = entry.get('submodel')
            label = f'{where} set {i} ({model}{" " + str(submodel) if submodel else ""})'
            if submodel is not None and str(submodel) not in submodels:
                errors.append(f'CONFG_UNKNOWN_REFERENCE: {label}: submodel {submodel!r} is not defined for {model} in models.yaml')
            years = entry.get('years')
            if (not isinstance(years, list) or len(years) != 2 or not all(_is_year(y) for y in years)
                    or years[1] < years[0]):
                errors.append(f'CONFG_VALUE_INVALID: {label}: years must be [start, end] with 4-digit years, got {years!r}')
                continue
            options = {}
            for key, vals in entry.items():
                if key in ('submodel', 'years'):
                    continue
                if key not in keyword_categories:
                    errors.append(f'CONFG_UNKNOWN_REFERENCE: {label}: "{key}" is not a keyword category')
                    continue
                if key == 'inventory_status':
                    errors.append(f'CONFG_VALUE_INVALID: {label}: inventory_status is metadata, not an option')
                    continue
                vals = [str(v) for v in (vals or [])]
                for v in vals:
                    if v not in allowed.get(key, set()):
                        errors.append(f'CONFG_UNKNOWN_REFERENCE: {label}: {key} value "{v}" is not produced by any keyword '
                                      f'(known: {", ".join(sorted(allowed.get(key, []))) or "none"})')
                options[key] = set(vals)
            option_sets.append({'file': path.name, 'model': model,
                                'submodel': None if submodel is None else str(submodel),
                                'start': years[0], 'end': years[1], 'options': options, 'status': status})

    # no overlapping year ranges for the same model + submodel
    by_group = {}
    for s in option_sets:
        by_group.setdefault((s['model'], s['submodel']), []).append(s)
    for (model, submodel), group in by_group.items():
        group.sort(key=lambda s: s['start'])
        for a, b in zip(group, group[1:]):
            if b['start'] <= a['end']:
                errors.append(f'CONFG_DUPLICATE_ENTRY: vehicles/{a["file"]}: {model}{" " + submodel if submodel else ""} '
                              f'years [{a["start"]}, {a["end"]}] and [{b["start"]}, {b["end"]}] overlap')

    _raise_if(errors, 'option sets')
    return option_sets


def vehicle_years(option_sets):
    """{(model, submodel): {'years': set, 'files': 'golf.yaml', 'status': 'drafted'}} from the option sets:
    the years config declares for each model / submodel (submodel None = base model)."""
    years = {}
    for s in option_sets:
        entry = years.setdefault((s['model'], s['submodel']), {'years': set(), 'files': set(), 'status': set()})
        entry['years'].update(range(s['start'], s['end'] + 1))
        entry['files'].add(s['file'])
        entry['status'].add(s['status'])
    return {k: {'years': v['years'], 'files': ', '.join(sorted(v['files'])),
                'status': 'reviewed' if v['status'] == {'reviewed'} else 'drafted'} for k, v in years.items()}


def find_option_set(option_sets, model, submodel, year):
    """The option set covering this model / submodel / year, or None."""
    for s in option_sets:
        if s['model'] == model and s['submodel'] == submodel and s['start'] <= year <= s['end']:
            return s
    return None


# ---------------------------------------------------------------- accessories.yaml

ACCESSORY_TYPES = ('text', 'number')
ACCESSORY_REQUIRED = ['part_number', 'make', 'model_name', 'year_range', 'status']
# columns the accessory pipeline adds to the dict (usable in export / sort_by)
ACCESSORY_DERIVED = ['model_name_clean', 'model', 'submodel', 'applicable_year', 'match_key', 'model_number',
                     'vehicle_id', 'variant', 'match_status', 'part_number_source', 'part_number_check']
PART_NUMBER_RESTORE = ('leading_zeros_only', 'never')
CHECK_COLUMN_NAME = 'make_model'               # pipeline name of part_number.check_column
VARIANT_BASE_RULES = ('all_fields_empty',)     # when the variant gets base_label
DQ_RULES = {'greater_than': 'pairs', 'not_null': 'columns', 'numeric_non_zero': 'columns',
            'numeric_non_negative': 'columns'}


def load_accessory_config(config_dir, settings):
    """Read accessories.yaml and check it against itself and pipeline.yaml. Returns the spec dict with
    'source' (path from sources.accessories) and 'renames' {source column: pipeline column}."""
    spec = read_yaml(Path(config_dir) / 'accessories.yaml')
    where = 'accessories.yaml'
    errors = []

    source = (settings.get('sources') or {}).get('accessories')
    if not source:
        errors.append(f'CONFG_VALUE_INVALID: pipeline.yaml: sources.accessories is missing')
    if 'accessories' not in (settings.get('datasets') or {}):
        errors.append(f'CONFG_VALUE_INVALID: pipeline.yaml: datasets.accessories (year rule) is missing')
    header_row = spec.get('header_row')
    if not isinstance(header_row, int) or isinstance(header_row, bool) or header_row < 1:
        errors.append(f'CONFG_VALUE_INVALID: {where}: header_row must be a row number (1 = first row), '
                      f'got {header_row!r}')
    if not isinstance(spec.get('sheet', 0), (int, str)):
        errors.append(f'CONFG_VALUE_INVALID: {where}: sheet must be a sheet index or name')

    columns = spec.get('columns') or {}
    renames, types = {}, {}
    for src, col in columns.items():
        col = col or {}
        if not col.get('name'):
            errors.append(f'CONFG_VALUE_INVALID: {where}: columns.{src} has no name')
            continue
        if col.get('type', 'text') not in ACCESSORY_TYPES:
            errors.append(f'CONFG_VALUE_INVALID: {where}: columns.{src} type must be one of '
                          f'{", ".join(ACCESSORY_TYPES)}, got {col.get("type")!r}')
        if col['name'] in renames.values():
            errors.append(f'CONFG_DUPLICATE_ENTRY: {where}: two source columns are renamed to {col["name"]}')
        renames[str(src)] = col['name']
        types[col['name']] = col.get('type', 'text')
    for name in ACCESSORY_REQUIRED:
        if name not in renames.values():
            errors.append(f'CONFG_VALUE_INVALID: {where}: columns must include one renamed to {name}')

    part_number = _part_number_spec(spec.get('part_number'), columns, renames, types, where, errors)

    known = set(renames.values())
    for col in (spec.get('keep_rows') or {}):
        if col not in known:
            errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: keep_rows.{col} is not a pipeline column '
                          f'(known: {", ".join(sorted(known))})')
    for rule, items in (spec.get('dq_rules') or {}).items():
        if rule not in DQ_RULES:
            errors.append(f'CONFG_VALUE_INVALID: {where}: dq_rules.{rule} is not a rule '
                          f'(known: {", ".join(DQ_RULES)})')
            continue
        names = [c for pair in items for c in pair] if DQ_RULES[rule] == 'pairs' else list(items or [])
        for name in names:
            if name not in known:
                errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: dq_rules.{rule} names unknown column {name!r} '
                              f'(known: {", ".join(sorted(known))})')

    export = spec.get('export') or {}
    usable = known | set(ACCESSORY_DERIVED)
    if not export.get('columns'):
        errors.append(f'CONFG_VALUE_INVALID: {where}: export.columns is empty')
    for name in list(export.get('columns') or {}) + list(export.get('sort_by') or []):
        if name not in usable:
            errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: export column {name!r} is not in the dict '
                          f'(known: {", ".join(sorted(usable))})')
    if '{run_id}' not in str(export.get('file_name', '')):
        errors.append(f'CONFG_VALUE_INVALID: {where}: export.file_name must contain {{run_id}}')

    variant = spec.get('variant') or {}
    categories = read_yaml(Path(config_dir) / 'categories.yaml').get('categories') or {}
    fields = [str(f) for f in variant.get('fields') or []]
    if not fields:
        errors.append(f'CONFG_VALUE_INVALID: {where}: variant.fields is empty')
    for name in fields:
        if name not in categories:
            errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: variant field {name!r} is not a category in '
                          f'categories.yaml (known: {", ".join(categories)})')
    if len(set(fields)) != len(fields):
        errors.append(f'CONFG_DUPLICATE_ENTRY: {where}: variant.fields lists a field twice')
    if not str(variant.get('base_label') or '').strip():
        errors.append(f'CONFG_VALUE_INVALID: {where}: variant.base_label is empty')
    if variant.get('base_when', 'all_fields_empty') not in VARIANT_BASE_RULES:
        errors.append(f'CONFG_VALUE_INVALID: {where}: variant.base_when must be one of '
                      f'{", ".join(VARIANT_BASE_RULES)}, got {variant.get("base_when")!r}')

    _raise_if(errors, where)
    variant = {'fields': fields, 'separator': str(variant.get('separator', ' ')),
               'multi_value_separator': str(variant.get('multi_value_separator', ' ')),
               'base_label': str(variant.get('base_label', '')).strip(),
               'base_when': variant.get('base_when', 'all_fields_empty')}
    return {**spec, 'source': source, 'renames': renames, 'types': types,
            'sheet': spec.get('sheet', 0), 'keep_rows': spec.get('keep_rows') or {},
            'known_statuses': spec.get('known_statuses') or [], 'dq_rules': spec.get('dq_rules') or {},
            'fitment_hints': [str(h) for h in spec.get('fitment_hints') or []], 'export': export,
            'variant': variant, 'part_number': part_number}


def _part_number_spec(block, columns, renames, types, where, errors):
    """Check the part_number block (idea 008) and add check_column to the columns read, as make_model.
    Returns the normalized block, with source_column (the file column part_number comes from)."""
    if not block:
        errors.append(f'CONFG_VALUE_INVALID: {where}: part_number block is missing (idea 008)')
        return {}
    column, suffix = block.get('column'), block.get('suffix_column')
    check = str(block.get('check_column') or '')
    for name, value in (('column', column), ('suffix_column', suffix)):
        if value not in renames.values():
            errors.append(f'CONFG_UNKNOWN_REFERENCE: {where}: part_number.{name} {value!r} is not a pipeline '
                          f'column (known: {", ".join(sorted(renames.values()))})')
        elif types[value] != 'text':
            errors.append(f'CONFG_VALUE_INVALID: {where}: part_number.{name} {value!r} must be type text')
    if not check:
        errors.append(f'CONFG_VALUE_INVALID: {where}: part_number.check_column is empty')
    elif check in columns and renames[check] != CHECK_COLUMN_NAME:
        errors.append(f'CONFG_VALUE_INVALID: {where}: part_number.check_column {check!r} is already read as '
                      f'{renames[check]!r}; leave it out of columns:')
    elif CHECK_COLUMN_NAME in renames.values() and renames.get(check) != CHECK_COLUMN_NAME:
        errors.append(f'CONFG_DUPLICATE_ENTRY: {where}: another source column is renamed to {CHECK_COLUMN_NAME}')
    else:
        renames[check], types[CHECK_COLUMN_NAME] = CHECK_COLUMN_NAME, 'text'
    restore = block.get('restore', 'leading_zeros_only')
    if restore not in PART_NUMBER_RESTORE:
        errors.append(f'CONFG_VALUE_INVALID: {where}: part_number.restore must be one of '
                      f'{", ".join(PART_NUMBER_RESTORE)}, got {restore!r}')
    allowed = str(block.get('allowed_characters') or '')
    try:
        pattern = re.compile(f'[{allowed}]+') if allowed else None
    except re.error as error:
        pattern = None
        errors.append(f'CONFG_VALUE_INVALID: {where}: part_number.allowed_characters {allowed!r} is not a '
                      f'character class ({error})')
    if not allowed:
        errors.append(f'CONFG_VALUE_INVALID: {where}: part_number.allowed_characters is empty')
    share = block.get('max_unproven_share')
    if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 <= share <= 1:
        errors.append(f'CONFG_VALUE_INVALID: {where}: part_number.max_unproven_share must be a share from 0 '
                      f'to 1, got {share!r}')
    if not isinstance(block.get('export_as_text', True), bool):
        errors.append(f'CONFG_VALUE_INVALID: {where}: part_number.export_as_text must be true or false')
    source_column = next((src for src, name in renames.items() if name == column), '')
    return {'column': column, 'check_column': check, 'suffix_column': suffix, 'restore': restore,
            'allowed_characters': allowed, 'pattern': pattern, 'max_unproven_share': share,
            'export_as_text': block.get('export_as_text', True), 'source_column': source_column}


# ---------------------------------------------------------------- definitions export

def export_definitions(taxonomy, option_sets, out_dir):
    """Write the flattened, read-only definition tables to db/definitions/. Returns {name: rows}."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dim_category = pd.DataFrame([
        {'category': name, 'source': c.get('source'), 'multi_value': c.get('multi_value'),
         'use_for_matching': c.get('use_for_matching'), 'description': c.get('description', '')}
        for name, c in taxonomy['categories'].items()])

    dim_keyword = pd.DataFrame([
        {'category': kw['category'], 'kind': kw['kind'], 'match': kw['match'], 'value': kw['value'],
         'models': '|'.join(kw['models'])}
        for kw in taxonomy['keywords']]).sort_values(['category', 'kind', 'match'])

    model_rows = []
    for model, spec in sorted(taxonomy['models'].items()):
        model_rows.append({'make': taxonomy['make'], 'model': model, 'submodel': '', 'series': ''})
        for submodel, sub_spec in sorted(((spec or {}).get('submodels') or {}).items()):
            model_rows.append({'make': taxonomy['make'], 'model': model, 'submodel': submodel,
                               'series': (sub_spec or {}).get('series') or ''})
    dim_model = pd.DataFrame(model_rows)

    dim_option_set = pd.DataFrame([
        {'model': s['model'], 'submodel': s['submodel'] or '', 'year_start': s['start'], 'year_end': s['end'],
         'category': cat, 'allowed_values': '|'.join(sorted(vals)), 'file': s['file'], 'status': s['status']}
        for s in option_sets for cat, vals in sorted(s['options'].items())])

    dim_resolution = pd.DataFrame([
        {'match': r['match'], 'from_category': r['from_category'], 'from_value': r['from_value'],
         'to_category': r['to_category'], 'to_value': r['to_value'], 'when': r['when']}
        for r in taxonomy['resolutions']],
        columns=['match', 'from_category', 'from_value', 'to_category', 'to_value', 'when'])

    tables = {'dim_category': dim_category, 'dim_keyword': dim_keyword, 'dim_model': dim_model,
              'dim_option_set': dim_option_set, 'dim_resolution': dim_resolution}
    for name, df in tables.items():
        df.to_csv(out_dir / f'{name}.csv', index=False)
    return {name: len(df) for name, df in tables.items()}


def _raise_if(errors, where):
    """Raise one ConfigError listing every problem, each starting with its CONFG_ code."""
    if errors:
        lines = '\n  - '.join(errors)
        raise ConfigError(f'{where}: {len(errors)} problem(s)\n  - {lines}', [_split_code(e) for e in errors])
