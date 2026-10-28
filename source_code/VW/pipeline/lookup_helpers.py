"""Fetch model numbers for accessories from the vehicle DB, once per unique (model, submodel, year) key.

The match is a lookup, not a merge (idea 003 A1): the vehicle DB is grouped once into an index, each unique
accessory key is looked up once, and the answer is attached while the per-model dict is built.

Each key goes through the checks of idea 004:
    C1  the accessory model name is a model / submodel in models.yaml      (resolve_names, before this)
    C2  db/final/vehicles.csv has vehicles for this model, submodel, year
    C3  config/vehicles/<model>.yaml declares the year
    C4  otherwise: which years the DB and the config do know (after / before / gap)
    C5  whether that config file is drafted from data or reviewed by a person
"""

from pathlib import Path

import pandas as pd

from pipeline import storage_helpers as store
from pipeline.logging_helpers import fatal, log_detail, log_flag, log_info
from pipeline.message_helpers import default_messages, join_causes, join_fix, message_for
from pipeline.parse_helpers import split_multi_value

INDEX_COLUMNS = ['vehicle_id', 'model', 'submodel', 'model_year', 'model_number', 'taxonomy_version']
NOT_OK = ('failed', 'ok_with_errors')
REPORT_COLUMNS = ['match_key', 'model', 'submodel', 'year', 'parts', 'in_db', 'in_config', 'known_db_years',
                  'known_config_years', 'config_file', 'config_status', 'code', 'match_status', 'model_count',
                  'model_numbers', 'checked', 'found']


# ---------------------------------------------------------------- the vehicle index (built once)

def load_vehicle_index(db_dir, config_version, variant, ctx=None, step='lookup'):
    """Read only the columns the lookup needs from vehicles.csv and group them once:
    {'index': {(model, submodel, year): [vehicle dicts]}, 'known_years': {(model, submodel): [years]}, ...}.
    submodel None = the base model. Each vehicle gets its variant label (variant_label, accessories.yaml)."""
    path = store.table_path(db_dir, 'final', 'vehicles')
    shown = _display(path, db_dir)
    if not path.exists():
        raise fatal(ctx, 'ACCESS_DB_NOT_FOUND', checked=f'file {shown}', found='file does not exist', path=shown)
    needed = INDEX_COLUMNS + [f for f in variant['fields'] if f not in INDEX_COLUMNS]
    header = pd.read_csv(path, nrows=0).columns
    missing = [c for c in needed if c not in header]
    if missing:
        raise fatal(ctx, 'ACCESS_DB_COLUMN_MISSING', checked=f'{shown} columns {", ".join(needed)}',
                    found=f'missing: {", ".join(missing)}', columns=missing)
    vehicles = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=needed)
    vehicles['variant'] = [variant_label(row, variant) for row in vehicles.to_dict('records')]

    versions = sorted(set(vehicles['taxonomy_version']) - {''})
    if versions != [config_version]:
        log_flag(ctx, step, {}, 'ACCESS_DB_STALE', subject=shown,
                 checked=f'taxonomy_version in {shown} = current config version {config_version}',
                 found=f'vehicles.csv has {", ".join(versions) or "none"}',
                 db_version=', '.join(versions) or 'none', config_version=config_version)
    _check_last_ingest(db_dir, ctx, step)

    index, known = {}, {}
    for row in vehicles.sort_values(['model', 'submodel', 'model_year', 'model_number']).itertuples(index=False):
        submodel = row.submodel or None
        year = int(row.model_year)
        index.setdefault((row.model, submodel, year), []).append(
            {'model_number': row.model_number, 'vehicle_id': row.vehicle_id, 'variant': row.variant})
        known.setdefault((row.model, submodel), set()).add(year)
    base = vehicles[vehicles['variant'] == variant['base_label']]
    log_info(ctx, step, 'VEHICLE INDEX', file=shown, vehicles=len(vehicles), keys=len(index),
             models=len(known), taxonomy_version=', '.join(versions))
    log_info(ctx, step, 'VARIANTS', fields=' > '.join(variant['fields']), distinct=vehicles['variant'].nunique(),
             base=f'{len(base)} vehicles labelled "{variant["base_label"]}" ({variant["base_when"]})',
             examples=' ; '.join(f'{r.vehicle_id}' for r in base.head(3).itertuples()))
    return {'index': index, 'known_years': {k: sorted(v) for k, v in known.items()}, 'vehicles': vehicles,
            'path': shown}


def _check_last_ingest(db_dir, ctx, step):
    runs = store.read_table(db_dir, 'dq', 'ingest_runs')
    if runs is None or runs.empty or 'status' not in runs.columns:
        return
    last = runs.iloc[-1]
    if last['status'] in NOT_OK:
        log_flag(ctx, step, {}, 'ACCESS_DB_LAST_INGEST_NOT_OK', subject=last.get('run_id', ''),
                 checked='status of the last run in db/dq/ingest_runs.csv', found=last['status'],
                 run_id=last.get('run_id', ''), status=last['status'])


def variant_label(vehicle, variant):
    """The vehicle's standardized fields in config order, empty ones skipped; multi-value cells are split
    and re-joined. base_label when the base rule applies (all_fields_empty: none of the fields has a value).
    {'trim': '', 'performance_package': 'Performance', 'transmission': 'Manual'} -> 'Performance Manual'."""
    parts = []
    for field in variant['fields']:
        values = split_multi_value(vehicle.get(field, ''))
        if values:
            parts.append(variant['multi_value_separator'].join(values))
    if not parts and variant['base_when'] == 'all_fields_empty':
        return variant['base_label']
    return variant['separator'].join(parts)


# ---------------------------------------------------------------- keys

def match_key(make, model, submodel, year):
    """volkswagen|golf|gti|2023; the base model is (base)."""
    return '|'.join([str(make), str(model), str(submodel) if submodel else '(base)', str(year)]).lower()


def vehicle_label(model, submodel, has_submodels):
    """'Golf GTI', 'Atlas (base)' when the model has submodels, otherwise just 'Arteon'."""
    if submodel:
        return f'{model} {submodel}'
    return f'{model} (base)' if has_submodels else model


def year_span(years):
    """[2020, 2021, 2023] -> '2020-2021, 2023'; [] -> 'none'."""
    years = sorted(set(int(y) for y in years))
    if not years:
        return 'none'
    runs, start, prev = [], years[0], years[0]
    for y in years[1:] + [None]:
        if y is not None and y == prev + 1:
            prev = y
            continue
        runs.append(f'{start}-{prev}' if prev != start else f'{start}')
        if y is not None:
            start = prev = y
    return ', '.join(runs)


# ---------------------------------------------------------------- the fetch

def fetch(keys, vehicle_index, declared, taxonomy, ctx=None, step='lookup'):
    """Look up each (model, submodel, year) key once. keys: {key: number of parts}.
    declared: config_helpers.vehicle_years(option_sets). Returns {key: result dict} where result has the
    vehicles found (attached when the DB has them) and, for a problem, the issue (code + message fields)."""
    index, known = vehicle_index['index'], vehicle_index['known_years']
    catalogue = ctx['messages'] if ctx else default_messages()
    make = taxonomy['make']
    results = {}
    for (model, submodel, year), parts in sorted(keys.items(), key=lambda kv: (kv[0][0], kv[0][1] or '', kv[0][2])):
        has_submodels = bool((taxonomy['models'].get(model) or {}).get('submodels'))
        label = vehicle_label(model, submodel, has_submodels)
        key_text = match_key(make, model, submodel, year)
        vehicles = index.get((model, submodel, year), [])
        db_years = known.get((model, submodel), [])
        config = declared.get((model, submodel))
        config_years = sorted(config['years']) if config else []
        in_config = bool(config) and year in config['years']
        status_text = ('reviewed' if config and config['status'] == 'reviewed'
                       else 'drafted from data, not reviewed')

        check_1 = (f'1) {vehicle_index["path"]} model={model} submodel={submodel or "(base)"} year={year} '
                   f'-> {len(vehicles)} rows (known years {year_span(db_years)})')
        check_2 = (f'2) config/vehicles/{config["files"]} {label} declared {year_span(config_years)} -> '
                   f'{year} {"declared" if in_config else "not declared"} ({status_text})' if config
                   else f'2) config/vehicles/: no option set for {label}')
        code, facts = '', {'vehicle': label, 'year': year}

        if vehicles:
            if config is None:
                code, facts = 'ACCESS_LOOKUP_NO_CONFIG_FOR_MODEL', {'vehicle': label}
            elif not in_config:
                code = 'ACCESS_LOOKUP_IN_DB_NOT_IN_CONFIG'
        elif config is None:
            code, facts = 'ACCESS_LOOKUP_NO_CONFIG_FOR_MODEL', {'vehicle': label}
        elif in_config:
            code = 'ACCESS_LOOKUP_IN_CONFIG_NOT_IN_DB'
        elif not db_years:
            code, facts = 'ACCESS_LOOKUP_MODEL_NOT_IN_DB', {'vehicle': label}
        else:
            all_years = sorted(set(db_years) | set(config_years))
            if year > all_years[-1]:
                code, facts = 'ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN', {**facts, 'last': all_years[-1]}
            elif year < all_years[0]:
                code, facts = 'ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN', {**facts, 'first': all_years[0]}
            else:
                code = 'ACCESS_LOOKUP_YEAR_IN_GAP'

        checked = f'{check_1}  {check_2}'
        found = (f'{len(vehicles)} vehicles in the DB; {year} {"declared" if in_config else "not declared"} '
                 f'in config; known years DB {year_span(db_years)} / config {year_span(config_years)}')
        issue = None
        if code:
            m = message_for(catalogue, code, **facts)
            issue = {'code': code, 'severity': m['severity'], 'message': m['message'], 'checked': checked,
                     'found': found, 'causes': join_causes(m['causes']), 'fix': join_fix(m['fix'])}
            log_flag(ctx, step, {'record': key_text, 'model': model, 'submodel': submodel or '', 'model_year': year},
                     code, subject=f'{key_text} - {parts} parts', checked=checked, found=found, **facts)
        if vehicles:
            log_detail(ctx, step, 'LOOKUP OK', match_key=key_text, parts=parts, found=len(vehicles),
                       model_numbers=', '.join(v['model_number'] for v in vehicles))

        results[(model, submodel, year)] = {
            'match_key': key_text, 'model': model, 'submodel': submodel or '', 'year': year, 'parts': parts,
            'vehicles': vehicles, 'match_status': 'matched' if vehicles else code, 'issue': issue,
            'in_config': in_config, 'known_db_years': year_span(db_years),
            'known_config_years': year_span(config_years), 'config_file': config['files'] if config else '',
            'config_status': config['status'] if config else '', 'checked': checked, 'found': found}

    found_keys = sum(1 for r in results.values() if r['vehicles'])
    log_info(ctx, step, 'FETCHED', keys=len(results), found=found_keys, missed=len(results) - found_keys,
             vehicles_attached=sum(len(r['vehicles']) for r in results.values()))
    return results


def lookup_report(results):
    """One row per key: what was checked, what was found, the model numbers (db/dq/accessory_lookup.csv)."""
    rows = [{**{k: r[k] for k in REPORT_COLUMNS if k in r},
             'in_db': len(r['vehicles']), 'in_config': 'yes' if r['in_config'] else 'no',
             'code': r['issue']['code'] if r['issue'] else '', 'model_count': len(r['vehicles']),
             'model_numbers': '|'.join(v['model_number'] for v in r['vehicles'])}
            for r in results.values()]
    return pd.DataFrame(rows, columns=REPORT_COLUMNS)


# ---------------------------------------------------------------- coverage: vehicles that get no parts

def coverage(vehicle_index, keys, taxonomy, ctx=None, step='coverage', min_year=None, max_year=None):
    """DB vehicles whose (model, submodel, year) no accessory covers. One flag per key (with the vehicle
    count and the years that model's accessories do cover); a model with no parts at all gets one flag.
    Only vehicle years inside the accessory window (min_year..max_year) are checked.
    Returns review rows (one per vehicle)."""
    catalogue = ctx['messages'] if ctx else default_messages()
    make = taxonomy['make']
    covered = {(m, s) for m, s, _ in keys}
    accessory_years = {}
    for m, s, y in keys:
        accessory_years.setdefault((m, s), set()).add(y)
    rows, flagged_models = [], set()
    in_window = {k: v for k, v in vehicle_index['index'].items()
                 if (min_year is None or k[2] >= min_year) and (max_year is None or k[2] <= max_year)}

    for (model, submodel, year), vehicles in sorted(in_window.items(),
                                                     key=lambda kv: (kv[0][0], kv[0][1] or '', kv[0][2])):
        if (model, submodel, year) in keys:
            continue
        has_submodels = bool((taxonomy['models'].get(model) or {}).get('submodels'))
        label = vehicle_label(model, submodel, has_submodels)
        key_text = match_key(make, model, submodel, year)
        acc_years = year_span(accessory_years.get((model, submodel), []))
        checked = f'accessory parts for model={model} submodel={submodel or "(base)"} year={year}'
        if (model, submodel) in covered:
            code, facts = 'ACCESS_COVER_VEHICLE_NO_PARTS', {'count': len(vehicles), 'vehicle': label, 'year': year}
            found = f'0 parts; {label} accessories cover {acc_years}'
            subject = f'{key_text} - {len(vehicles)} vehicles'
        else:
            code, facts = 'ACCESS_COVER_MODEL_NO_PARTS', {'vehicle': label}
            found = f'0 parts for {label} in any year'
            subject = f'{match_key(make, model, submodel, "*")}'
        m = message_for(catalogue, code, **facts)
        if code == 'ACCESS_COVER_VEHICLE_NO_PARTS' or (model, submodel) not in flagged_models:
            key = {'record': key_text if code == 'ACCESS_COVER_VEHICLE_NO_PARTS' else subject, 'model': model,
                   'submodel': submodel or '', 'model_year': year if code == 'ACCESS_COVER_VEHICLE_NO_PARTS' else ''}
            log_flag(ctx, step, key, code, subject=subject, checked=checked, found=found, **facts)
            flagged_models.add((model, submodel))
        for v in vehicles:
            rows.append({'type': 'vehicle', 'record': v['vehicle_id'], 'part_number': '', 'model_name': label,
                         'model': model, 'submodel': submodel or '', 'year': year, 'match_key': key_text,
                         'model_number': v['model_number'], 'code': code, 'severity': m['severity'],
                         'message': m['message'], 'checked': checked, 'found': found,
                         'causes': join_causes(m['causes']), 'fix': join_fix(m['fix'])})
    log_info(ctx, step, 'COVERAGE', vehicle_keys=len(in_window),
             outside_window=len(vehicle_index['index']) - len(in_window),
             keys_without_parts=len({r['match_key'] for r in rows}), vehicles_without_parts=len(rows))
    return rows


def _display(path, db_dir):
    try:
        return Path(path).resolve().relative_to(Path(db_dir).resolve().parent).as_posix()
    except ValueError:
        return Path(path).as_posix()
