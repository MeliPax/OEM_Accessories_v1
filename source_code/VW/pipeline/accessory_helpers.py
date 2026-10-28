"""Accessory ingest + model number matching (plan 003).

    from pipeline.accessory_helpers import build_accessory_model_dict
    model_year_dict = build_accessory_model_dict()        # from the notebook
    model_year_dict["GTI"]                                # one row per part, applicable year and vehicle

Steps (every one logged through run_step):
    config -> ingest -> part_numbers -> staging -> year_window -> clean_text -> dedupe -> part_number_review
    -> clean -> resolve_names -> lookup -> build_dict -> coverage -> validate -> export

Nothing merged is written to the DB. Written: the run logs, db/dq/part_number_check.csv (one row per
stockCode / make&model / model, idea 008), db/dq/accessory_lookup.csv (one row per key),
db/review/accessory_review.csv (unmatched part-years, unproven part numbers, suspect values and links,
vehicles with no parts),
db/dq/accessory_runs.csv, and the Excel export output/<run_id>.xlsx (one sheet per accessory model name,
matched rows only).
"""

import hashlib
import numbers
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline import config_helpers as cfg
from pipeline import storage_helpers as store
from pipeline.clean_helpers import clean_value
from pipeline.ingest_helpers import clip_years, filter_by_year_window
from pipeline.logging_helpers import (end_run, fatal, log_change, log_detail, log_excluded, log_flag, log_info,
                                      run_status, run_step, start_run)
from pipeline.lookup_helpers import coverage, fetch, load_vehicle_index, lookup_report
from pipeline.message_helpers import join_causes, join_fix, load_messages, message_for
from pipeline.parse_helpers import build_matchers, match_model, tokenize
from pipeline.text_helpers import clean_text, link_host
from pipeline.verify_helpers import accessory_contradictions, drop_verified, verified_report, verify_flags

VW_DIR = Path(__file__).resolve().parents[1]
PIPELINE = 'vw_accessories'
DATASET = 'accessories'
YEAR_RANGE = re.compile(r'^\s*(\d{4})\s*(?:-\s*(\d{4}))?\s*$')
SHEET_FORBIDDEN = re.compile(r'[\[\]:*?/\\]')
DICT_COLUMNS = ['part_number', 'part_number_source', 'part_number_check', 'model_name', 'model_name_clean', 'model', 'submodel', 'product_description',
                'comments', 'msrp', 'cost', 'labor_time', 'applicable_year', 'match_key', 'model_number',
                'vehicle_id', 'variant', 'match_status', 'source_row']
REVIEW_COLUMNS = ['type', 'record', 'part_number', 'model_name', 'model', 'submodel', 'year', 'match_key',
                  'model_number', 'code', 'severity', 'message', 'checked', 'found', 'causes', 'fix']
# idea 008: how stockCode was proven by make&model. Only these two results count as proven.
PROVEN = ('same', 'restored')
SPLIT_REASONS = {'no_check_value': 'make&model is empty',
                 'no_suffix': 'the model name is empty',
                 'suffix_not_at_end': 'make&model does not end with the model name',
                 'no_part_left': 'nothing is left after removing the model name',
                 'no_stock_code': 'stockCode is empty'}
# lineage columns say how a value arrived, not what it is; ignored when comparing copies
# (also every <column>_source column: the value as read, before units or text cleaning)
LINEAGE_COLUMNS = ['part_number_source', 'part_number_stored_as', 'part_number_check']
PART_NUMBER_REPORT = ['part_number_source', 'stored_as', 'make_model', 'model_name', 'make_model_part_number',
                      'make_model_model_name', 'part_number_check', 'part_number', 'reason', 'rows', 'source_rows']


# ---------------------------------------------------------------- ingest + staging

def read_accessories(path, spec, ctx=None, step='ingest'):
    """Read the sheet, take the column names from header_row, keep the configured columns as text.
    Adds source_row (the row number in the spreadsheet) and part_number_stored_as (number | text | empty:
    how Excel stored the part number cell; a number has lost any leading zeros, idea 008)."""
    path = Path(path)
    shown = path.as_posix()
    if not path.exists():
        raise fatal(ctx, 'ACCESS_SRC_FILE_NOT_FOUND', checked=f'file {shown}', found='file does not exist',
                    path=shown)
    try:
        raw = pd.read_excel(path, sheet_name=spec['sheet'], header=None, dtype=object)   # cell types kept
    except (ValueError, IndexError):
        sheets = pd.ExcelFile(path).sheet_names
        raise fatal(ctx, 'ACCESS_SRC_SHEET_NOT_FOUND', checked=f'sheet {spec["sheet"]!r} in {path.name}',
                    found=f'sheets: {", ".join(sheets)}', sheet=repr(spec['sheet']), sheets=sheets)

    header_row = spec['header_row']
    header = [str(v).strip() if pd.notna(v) else '' for v in raw.iloc[header_row - 1]] if len(raw) >= header_row else []
    wanted = list(spec['renames'])
    present = [c for c in wanted if c in header]
    if not present:
        raise fatal(ctx, 'ACCESS_SRC_HEADER_NOT_FOUND', checked=f'row {header_row} holds {", ".join(wanted)}',
                    found=f'row {header_row} holds: {", ".join(h for h in header if h) or "(empty)"}',
                    row=header_row)
    missing = [c for c in wanted if c not in header]
    if missing:
        raise fatal(ctx, 'ACCESS_SRC_COLUMN_MISSING', checked=f'row {header_row} holds {", ".join(wanted)}',
                    found=f'missing: {", ".join(missing)}', columns=missing)

    data = raw.iloc[header_row:].copy()
    data.columns = header
    stored_as = data[spec['part_number']['source_column']].map(_stored_as)
    data = data[wanted].fillna('').map(lambda v: str(v).strip())
    data.insert(0, 'source_row', data.index + 1)                   # spreadsheet row number
    data['part_number_stored_as'] = stored_as
    data = data[(data[wanted] != '').any(axis=1)]
    if data.empty:
        raise fatal(ctx, 'ACCESS_SRC_EMPTY', checked=f'rows below header row {header_row}', found='0 data rows',
                    path=shown)
    data = data.rename(columns=spec['renames']).reset_index(drop=True)
    log_info(ctx, step, 'SOURCE', file=path.name, size_kb=round(path.stat().st_size / 1024, 1),
             modified=datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
             sheet=spec['sheet'], header_row=header_row, rows=len(data), columns=len(wanted),
             part_numbers_stored_as_number=int((data['part_number_stored_as'] == 'number').sum()))
    return data


def _stored_as(value):
    if pd.isna(value) or str(value).strip() == '':
        return 'empty'
    return 'number' if isinstance(value, numbers.Number) and not isinstance(value, bool) else 'text'


# ---------------------------------------------------------------- part numbers (idea 008)

def split_check_value(value, suffix):
    """(part number, model name) from make&model: the row's own model name removed from the end.
    ('', '') unless value ends with exactly suffix and something is left. Never padded or guessed."""
    if value and suffix and value.endswith(suffix) and len(value) > len(suffix):
        return value[:-len(suffix)], suffix
    return '', ''


def prove_part_number(stock, check_value, suffix, pn):
    """(result, part number to use, split part, split model). result is same | restored (proven), or
    mismatch | unexpected_characters | one of SPLIT_REASONS (not proven: stockCode is kept)."""
    part, model = split_check_value(check_value, suffix)
    if not stock:
        return 'no_stock_code', stock, part, model
    if not part:
        reason = ('no_check_value' if not check_value else 'no_suffix' if not suffix
                  else 'no_part_left' if check_value == suffix else 'suffix_not_at_end')
        return reason, stock, part, model
    if not pn['pattern'].fullmatch(part):
        return 'unexpected_characters', stock, part, model
    if part == stock:
        return 'same', stock, part, model
    lost = part[:len(part) - len(stock)]
    if pn['restore'] == 'leading_zeros_only' and part.endswith(stock) and lost and set(lost) == {'0'}:
        return 'restored', part, part, model
    return 'mismatch', stock, part, model


def suffix_hint(check_value, suffix, known_suffixes):
    """Why make&model doesn't end with the model name, from looser checks. Only explains; never used to
    restore a part number."""
    if check_value.lower().endswith(suffix.lower()):
        return f'it ends with "{check_value[-len(suffix):]}", not "{suffix}" (case differs)'
    if check_value.replace(' ', '').endswith(suffix.replace(' ', '')):
        return f'it ends with "{suffix}" only when spaces are ignored'
    other = next((k for k in known_suffixes if k != suffix and check_value.endswith(k)), None)
    return f'it ends with another model name, "{other}"' if other else 'no known model name ends it'


def check_part_numbers(df, spec, ctx=None, step='part_numbers'):
    """Prove every part number with make&model (idea 008), once per distinct (stockCode, how it was
    stored, make&model, model name). Adds make_model_part_number / make_model_model_name (the split),
    part_number_check (the result) and part_number_source (stockCode as read); part_number changes only
    when restored. Returns (df, report): the report has one row per distinct combination."""
    pn = spec['part_number']
    column, suffix_col = pn['column'], pn['suffix_column']
    keys = [column, 'part_number_stored_as', cfg.CHECK_COLUMN_NAME, suffix_col]
    known = sorted(set(df[suffix_col]) - {''}, key=len, reverse=True)
    rows = []
    for (stock, stored_as, check_value, suffix), group in df.groupby(keys, sort=True):
        result, part_number, part, model = prove_part_number(stock, check_value, suffix, pn)
        reason = SPLIT_REASONS.get(result, '')
        if result == 'suffix_not_at_end':
            reason += f'; {suffix_hint(check_value, suffix, known)}'
        elif result == 'unexpected_characters':
            reason = f'"{part}" uses characters outside {pn["allowed_characters"]}'
        elif result == 'mismatch':
            reason = f'make&model holds "{part}", stockCode holds "{stock}"'
        elif result == 'restored':
            reason = f'make&model holds the {len(part) - len(stock)} leading zeros stockCode lost'
            log_change(ctx, step, {'record': f'part_number "{stock}" - {suffix}'}, column, stock, part_number,
                       'restore_leading_zeros', f'from make&model "{check_value}" (stockCode stored as '
                       f'{stored_as}); {len(group)} rows')
        source_rows = group['source_row'].tolist()
        rows.append({'part_number_source': stock, 'stored_as': stored_as, 'make_model': check_value,
                     'model_name': suffix, 'make_model_part_number': part, 'make_model_model_name': model,
                     'part_number_check': result, 'part_number': part_number, 'reason': reason,
                     'rows': len(group),
                     'source_rows': ', '.join(map(str, source_rows[:20])) + (' ...' if len(source_rows) > 20 else '')})
    report = pd.DataFrame(rows, columns=PART_NUMBER_REPORT)

    found = report.set_index(['part_number_source', 'stored_as', 'make_model', 'model_name'])
    at = pd.MultiIndex.from_frame(df[keys].set_axis(found.index.names, axis=1))
    out = df.copy()
    out['part_number_source'] = out[column]
    for col in ('make_model_part_number', 'make_model_model_name', 'part_number_check'):
        out[col] = found.loc[at, col].to_numpy()
    out[column] = found.loc[at, 'part_number'].to_numpy()
    counts = report.groupby('part_number_check')['rows'].sum()
    log_info(ctx, step, 'PART NUMBERS', rows=len(out), **{r: int(counts.get(r, 0)) for r in PROVEN},
             **{r: int(n) for r, n in counts.items() if r not in PROVEN})
    return out, report


def _rows(n):
    return f'{int(n)} row' + ('' if n == 1 else 's')


def check_unproven_share(report, spec, ctx=None):
    """Stop the run when more rows than max_unproven_share have a part number make&model can't prove
    (usually a changed file layout). Called after the check report is written, so it can be read."""
    limit = spec['part_number']['max_unproven_share']
    total = int(report['rows'].sum())
    unproven = report[~report['part_number_check'].isin(PROVEN)]
    count = int(unproven['rows'].sum())
    share = count / total if total else 0
    if share > limit:
        by_result = unproven.groupby('part_number_check')['rows'].sum()
        raise fatal(ctx, 'ACCESS_STGNG_PART_NUMBER_SPLIT_RATE',
                    checked=f'rows whose part number make&model proves (same or restored); at most '
                            f'{limit:.0%} not proven',
                    found=f'{count} of {total} not proven: ' + ', '.join(f'{r} {n}' for r, n in by_result.items()),
                    unproven=count, rows=total, share=f'{share:.1%}', limit=f'{limit:.0%}')
    return share


def flag_part_numbers(scope, report, ctx=None, step='part_number_review'):
    """Flag every part number whose result isn't 'same', for the rows still in scope (after the status
    filter, year window and duplicate removal): one flag per part number and result (idea 008, P13).
    Part numbers only in rows left out earlier are counted in the log. Returns the review rows."""
    review = []

    def flag(first, code, group, **facts):
        count = _rows(len(group))
        f = log_flag(ctx, step, first, code, 'part_number', first['part_number_source'],
                     subject=f'{first["part_number_source"]} - {count}', rows=count, **facts)
        if f:
            review.append({'type': 'part_number', 'record': f['record'], 'part_number': first['part_number'],
                           'model_name': ', '.join(sorted(set(group['model_name']))), 'model': '',
                           'submodel': '', 'year': '', 'match_key': '', 'model_number': '',
                           **{k: f[k] for k in ('code', 'severity', 'message', 'checked', 'found', 'causes',
                                                'fix')}})

    reasons = report.drop_duplicates(['part_number_source', 'part_number_check'])                     .set_index(['part_number_source', 'part_number_check'])['reason']
    flagged = scope[scope['part_number_check'] != 'same']
    for (stock, result), group in flagged.groupby(['part_number_source', 'part_number_check'], sort=True):
        first = group.iloc[0]
        reason = reasons.get((stock, result), '')
        checked = (f'stockCode "{stock}" (stored as {first["part_number_stored_as"]}) against make&model '
                   f'without the model name')
        if result == 'restored':
            flag(first, 'ACCESS_STGNG_PART_NUMBER_RESTORED', group, checked=checked,
                 found=f'{stock} -> {first["part_number"]}: {reason}', part_number=first['part_number'],
                 stock_code=stock)
        elif result in ('mismatch', 'unexpected_characters'):
            flag(first, 'ACCESS_STGNG_PART_NUMBER_MISMATCH', group, checked=checked, found=reason,
                 stock_code=stock, make_model_part=first['make_model_part_number'] or '(none)')
        else:
            code = ('ACCESS_STGNG_PART_NUMBER_UNVERIFIED_NUMBER' if first['part_number_stored_as'] == 'number'
                    else 'ACCESS_STGNG_PART_NUMBER_UNVERIFIED')
            flag(first, code, group, checked=checked, found=reason, stock_code=stock, reason=reason)

    for part, group in scope.groupby('part_number', sort=True):
        spellings = sorted(set(group['part_number_source']))
        if len(spellings) > 1:
            flag(group.iloc[0], 'ACCESS_STGNG_PART_NUMBER_INCONSISTENT', group,
                 checked=f'one stockCode spelling per proven part number {part}',
                 found=', '.join(f'"{s}" ({_rows((group["part_number_source"] == s).sum())})' for s in spellings),
                 part_number=part, count=len(spellings), spellings=', '.join(spellings))

    in_scope = set(zip(scope['part_number_source'], scope['part_number_check']))
    pairs = pd.Series(list(zip(report['part_number_source'], report['part_number_check'])), index=report.index)
    outside = report[(report['part_number_check'] != 'same') & ~pairs.isin(in_scope)]
    if len(outside):
        counts = outside.groupby('part_number_check').agg(parts=('part_number_source', 'nunique'),
                                                         rows=('rows', 'sum'))
        log_info(ctx, step, 'NOT IN SCOPE', note='rows left out earlier (status, year window); not flagged',
                 **{r: f'{c.parts} parts / {c.rows} rows' for r, c in counts.iterrows()})
    return review


def stage_accessories(df, spec, make, ctx=None, step='staging'):
    """Keep the rows the pipeline can use: part number and model name filled, the make from models.yaml,
    a kept status, and a readable year range (split into min_year / max_year). Every row left out is
    logged with its reason; problem rows are flagged."""
    df = df.copy()
    drop = pd.Series(False, index=df.index)
    reasons = {}

    def leave_out(mask, reason):
        nonlocal drop
        new = mask & ~drop
        for idx in df.index[new]:
            reasons[idx] = reason(df.loc[idx]) if callable(reason) else reason
        drop |= new

    for idx, row in df[df['part_number'] == ''].iterrows():
        held = row.get('make_model_part_number', '')
        found = f'empty; make&model holds "{held}", not filled in (nothing to compare it with)' if held else 'empty'
        log_flag(ctx, step, row, 'ACCESS_STGNG_MISSING_PART_NUMBER', 'part_number', '',
                 checked='part_number is filled', found=found, subject=f'source row {row["source_row"]}',
                 source_row=row['source_row'])
    leave_out(df['part_number'] == '', 'part_number is empty')
    for idx, row in df[(df['model_name'] == '') & ~drop].iterrows():
        log_flag(ctx, step, row, 'ACCESS_STGNG_MISSING_MODEL_NAME', 'model_name', '',
                 checked='model_name is filled', found='empty', source_row=row['source_row'],
                 part_number=row['part_number'])
    leave_out(df['model_name'] == '', 'model_name is empty')

    wrong_make = df['make'].str.lower() != str(make).lower()
    for _, row in df[wrong_make & ~drop].iterrows():
        log_flag(ctx, step, row, 'ACCESS_STGNG_MAKE_MISMATCH', 'make', row['make'],
                 checked=f'make = {make} (models.yaml)', found=f'"{row["make"]}"', source_row=row['source_row'],
                 value=row['make'], make=make)
    leave_out(wrong_make, lambda r: f'make {r["make"]!r} is not {make}')

    known = set(spec['known_statuses']) | {v for vals in spec['keep_rows'].values() for v in vals}
    if 'status' in df.columns and known:
        unexpected = ~df['status'].isin(known)
        for _, row in df[unexpected & ~drop].iterrows():
            log_flag(ctx, step, row, 'ACCESS_STGNG_STATUS_UNEXPECTED', 'status', row['status'],
                     checked=f'status is one of {", ".join(sorted(known))}', found=f'"{row["status"]}"',
                     source_row=row['source_row'], value=row['status'])
        leave_out(unexpected, lambda r: f'status {r["status"]!r} is not a known status')
    for col, values in spec['keep_rows'].items():
        leave_out(~df[col].isin(values), lambda r, c=col, v=values: f'{c} {r[c]!r} (keep_rows.{c}: {", ".join(v)})')

    parsed = df['year_range'].str.extract(YEAR_RANGE)
    df['min_year'] = pd.to_numeric(parsed[0], errors='coerce').astype('Int64')
    df['max_year'] = pd.to_numeric(parsed[1].fillna(parsed[0]), errors='coerce').astype('Int64')
    invalid = df['min_year'].isna()
    for _, row in df[invalid & ~drop].iterrows():
        log_flag(ctx, step, row, 'ACCESS_YEAR_RANGE_INVALID', 'year_range', row['year_range'],
                 checked='year_range reads as YYYY-YYYY or YYYY', found=f'"{row["year_range"]}"',
                 source_row=row['source_row'], value=row['year_range'])
    leave_out(invalid, lambda r: f'year range {r["year_range"]!r} cannot be read')
    reversed_range = ~invalid & (df['max_year'] < df['min_year'])
    for _, row in df[reversed_range.fillna(False) & ~drop].iterrows():
        log_flag(ctx, step, row, 'ACCESS_YEAR_RANGE_REVERSED', 'year_range', row['year_range'],
                 checked='end year >= start year', found=f'"{row["year_range"]}"', source_row=row['source_row'],
                 value=row['year_range'])
    leave_out(reversed_range.fillna(False), lambda r: f'year range {r["year_range"]!r} ends before it starts')

    excluded = df[drop]
    log_excluded(ctx, step, excluded, lambda r: reasons[r.name])
    if len(excluded):
        counts = pd.Series(list(reasons.values())).str.replace(r"'[^']*'", '...', regex=True).value_counts()
        log_info(ctx, step, 'LEFT OUT', count=len(excluded),
                 reasons=' ; '.join(f'{r}: {n}' for r, n in counts.items()))
    kept = df[~drop].copy()
    kept['min_year'] = kept['min_year'].astype(int)
    kept['max_year'] = kept['max_year'].astype(int)
    return kept


def note_clipped(df, settings, ctx=None, step='year_window'):
    """One info flag: rows whose range starts before min_model_year (their earlier years are dropped, D15)."""
    min_year = settings['min_model_year']
    clipped = int((df['min_year'] < min_year).sum())
    if max_year := settings.get('max_model_year'):
        clipped += int((df['max_year'] > max_year).sum())
    if clipped:
        log_flag(ctx, step, {}, 'ACCESS_YEAR_CLIPPED', subject=f'{clipped} accessory rows',
                 checked=f'year ranges against min_model_year {min_year}',
                 found=f'{clipped} ranges start earlier', count=clipped, min_year=min_year)
    return df


def _is_lineage(column):
    return column in LINEAGE_COLUMNS or column.endswith('_source')


def remove_duplicates(df, ctx=None, step='dedupe'):
    """Drop rows identical on every column but source_row and the lineage columns (the file repeats many
    rows), logging each one with the row it copies. Pairs (part_number, model_name) whose copies differ are flagged and all kept."""
    columns = [c for c in df.columns if c != 'source_row' and not _is_lineage(c)]
    first_row = df.groupby(columns, dropna=False, sort=False)['source_row'].transform('first')
    duplicated = df.duplicated(columns, keep='first')
    log_excluded(ctx, step, df[duplicated], lambda r: f'exact copy of source row {first_row[r.name]}')
    kept = df[~duplicated].reset_index(drop=True)

    for (part, model_name), group in kept.groupby(['part_number', 'model_name'], sort=True):
        if len(group) < 2:
            continue
        differing = [c for c in columns if c not in ('part_number', 'model_name') and group[c].nunique() > 1]
        log_flag(ctx, step, group.iloc[0], 'ACCESS_STGNG_DUPLICATE_CONFLICT', subject=f'{part} - {model_name}',
                 checked=f'one row per (part_number, model_name) after removing exact copies',
                 found='; '.join(f'source row {r.source_row}: ' + ', '.join(f'{c}={getattr(r, c)}' for c in differing)
                                 for r in group.itertuples()),
                 part_number=part, model_name=model_name, columns=differing)
    log_info(ctx, step, 'DUPLICATES REMOVED', rows_in=len(df), removed=int(duplicated.sum()), rows_out=len(kept))
    return kept


# ---------------------------------------------------------------- comment cleaning (idea 007) + units (idea 006)

def _value_review(flag, group):
    """A review row for a flagged value (a suspect unit, an unreviewed link)."""
    first = group.iloc[0]
    return {'type': 'value', 'record': flag['record'], 'part_number': first['part_number'],
            'model_name': ', '.join(sorted(set(group['model_name']))), 'model': '', 'submodel': '', 'year': '',
            'match_key': '', 'model_number': '',
            **{k: flag[k] for k in ('code', 'severity', 'message', 'checked', 'found', 'causes', 'fix')}}


def clean_text_columns(df, spec, ctx=None, step='clean_text'):
    """Clean the text_cleaning columns once per distinct text (idea 007): separators -> sentences, tags
    removed, link rules, spaces. Keeps <column>_source (the raw text). Each changed text is logged with
    the rules that fired; links no rule or allowed host covers are flagged. Returns (df, review rows)."""
    rules = spec['text_cleaning']
    df = df.copy()
    review = []
    for col in rules['columns']:
        df[f'{col}_source'] = df[col]
        cleaned, unknown_tags = {}, {}
        counts = {'texts': 0, 'changed': 0, 'rows_changed': 0, 'links_replaced': 0, 'links_allowed': 0,
                  'links_unreviewed': 0}
        for text, group in df[df[col] != ''].groupby(col, sort=True):
            result = clean_text(text, rules)
            cleaned[text] = result['text']
            counts['texts'] += 1
            first = group.iloc[0]
            if result['text'] != text:
                counts['changed'] += 1
                counts['rows_changed'] += len(group)
                log_change(ctx, step, {'record': f'{col} of {first["part_number"]} (+{len(group) - 1} rows)'},
                           col, text, result['text'], '; '.join(result['rules']), f'{_rows(len(group))}')
            for url, action, detail in result['links']:
                counts[f'links_{action}'] += 1
                if action == 'unreviewed':
                    flag = log_flag(ctx, step, first, 'ACCESS_CLEAN_UNREVIEWED_LINK', col, url,
                                    subject=f'{url} - {_rows(len(group))}',
                                    checked=f'link rules ({len(rules["link_rules"])}) and allowed hosts '
                                            f'({", ".join(rules["allowed_link_hosts"]) or "none"})',
                                    found=f'host {link_host(url)} is not covered', url=url, column=col,
                                    rows=_rows(len(group)))
                    if flag:
                        review.append(_value_review(flag, group))
            for name in result['unknown_tags']:
                unknown_tags.setdefault(name, []).append(len(group))
        for name, sizes in sorted(unknown_tags.items()):
            log_flag(ctx, step, {}, 'ACCESS_CLEAN_UNKNOWN_TAG', col, f'<{name}>', subject=f'<{name}> in {col}',
                     checked=f'tags in separators.tags ({", ".join(rules["separator_tags"])}) and remove_tags '
                             f'({", ".join(rules["remove_tags"])})',
                     found=f'<{name}> in {len(sizes)} texts, {sum(sizes)} rows', tag=name, column=col,
                     texts=len(sizes))
        df[col] = df[col].map(lambda v: cleaned.get(v, v))
        log_info(ctx, step, 'TEXT CLEANED', column=col, **counts)
    return df, review


def convert_units(df, spec, ctx=None, step='clean'):
    """Convert the units columns (idea 006): value x definitions[target] / definitions[source], rounded.
    Keeps <column>_source (the value as read). One change per distinct value; values that look like the
    wrong unit are flagged ACCESS_CLEAN_UNIT_SUSPECT and still converted. Returns (df, review rows)."""
    df = df.copy()
    review = []
    for col, rule in spec['units']['columns'].items():
        source = df[col]
        df[f'{col}_source'] = source
        df[col] = (source * rule['factor']).round(rule['decimals'])
        log_info(ctx, step, 'UNITS', column=col, rule=f'{rule["source_unit"]} -> {rule["target_unit"]} '
                 f'x {rule["factor"]:.6g}, {rule["decimals"]} decimals')
        for value, rows in source.dropna().value_counts().sort_index().items():
            converted = round(value * rule['factor'], rule['decimals'])
            if converted == value:                                      # 0 minutes = 0 hours
                continue
            log_change(ctx, step, {'record': f'{col} {_number_text(value)}'}, col, _number_text(value),
                       _number_text(converted), 'unit_convert',
                       f'{rule["source_unit"]} -> {rule["target_unit"]} x {rule["factor"]:.6g}, '
                       f'{rule["decimals"]} decimals; {_rows(rows)}')
        suspect = pd.Series('', index=df.index)
        if rule['not_whole']:
            suspect[source.notna() & (source % 1 != 0)] = f'not a whole number of {rule["source_unit"]}'
        if rule['above'] is not None:
            suspect[source.notna() & (source > rule['above'])] = f'above {_number_text(rule["above"])} ' \
                                                                  f'{rule["source_unit"]}'
        flagged = df[suspect != ''].assign(reason=suspect[suspect != ''])
        for (part, value), group in flagged.groupby(['part_number', f'{col}_source'], sort=True):
            first = group.iloc[0]
            flag = log_flag(ctx, step, first, 'ACCESS_CLEAN_UNIT_SUSPECT', col, value,
                            subject=f'{part} {col}={_number_text(value)} - {_rows(len(group))}',
                            checked=f'{col} in {rule["source_unit"]}: suspect if not whole / above '
                                    f'{_number_text(rule["above"])}',
                            found=first['reason'], column=col, value=_number_text(value),
                            source_unit=rule['source_unit'], target_unit=rule['target_unit'],
                            converted=_number_text(first[col]), reason=first['reason'], part_number=part,
                            rows=_rows(len(group)))
            if flag:
                review.append(_value_review(flag, group))
    return df, review


def _number_text(value):
    return '' if value is None or pd.isna(value) else (str(int(value)) if float(value).is_integer() else str(value))


# ---------------------------------------------------------------- clean + resolve names

def clean_accessories(df, spec, aliases, ctx=None, step='clean'):
    """Type the number columns (a value that isn't a number is flagged and left empty), count encoding
    replacement characters, and clean model_name with the shared aliases (model_name_clean)."""
    df = df.copy()
    for col, kind in spec['types'].items():
        if col not in df.columns:
            continue
        if kind == 'number':
            text = df[col].astype(str).str.strip()
            numbers = pd.to_numeric(text, errors='coerce')
            for _, row in df[(text != '') & numbers.isna()].iterrows():
                log_flag(ctx, step, row, 'ACCESS_CLEAN_NOT_NUMERIC', col, row[col],
                         checked=f'{col} reads as a number', found=f'"{row[col]}"', source_row=row['source_row'],
                         column=col, value=row[col])
            df[col] = numbers
        else:
            bad = int(df[col].astype(str).str.contains(chr(0xFFFD)).sum())   # U+FFFD replacement character
            if bad:
                log_flag(ctx, step, {}, 'ACCESS_CLEAN_BAD_CHARACTERS', subject=col,
                         checked=f'{col} for the replacement character U+FFFD', found=f'{bad} values',
                         count=bad, column=col)

    cleaned = {}
    for name, rows in df['model_name'].value_counts(sort=False).items():
        value, steps = clean_value(name, aliases)
        cleaned[name] = value
        for rule, before, after, detail in steps:
            log_change(ctx, step, {'record': f'model_name "{name}"'}, 'model_name_clean', before, after, rule,
                       f'{detail}; {rows} rows' if detail else f'{rows} rows')
    df['model_name_clean'] = df['model_name'].map(cleaned)
    return df


def resolve_names(df, taxonomy, ctx=None, step='resolve_names'):
    """Match each unique model_name_clean once to a model / submodel in models.yaml (C1). The whole name
    must match; anything else is flagged ACCESS_LOOKUP_UNKNOWN_MODEL_NAME, never guessed."""
    matchers = build_matchers(taxonomy)
    resolved = {}
    for name, group in df.groupby('model_name_clean', sort=True):
        phrase, rest = match_model(tokenize(name), matchers)
        parts = group['part_number'].nunique()
        if phrase and not rest:
            resolved[name] = (phrase['model'], phrase['submodel'] or '')
            log_detail(ctx, step, 'RESOLVED', name=name, model=phrase['model'],
                       submodel=phrase['submodel'] or '(base)', parts=parts)
        else:
            resolved[name] = ('', '')
            found = (f'"{phrase["match"]}" matches, then "{" ".join(rest)}" is left over' if phrase
                     else 'no model or submodel matches')
            log_flag(ctx, step, {}, 'ACCESS_LOOKUP_UNKNOWN_MODEL_NAME', subject=f'"{name}" - {parts} parts',
                     checked=f'"{name}" is a whole model / submodel name in models.yaml (after aliases)',
                     found=found, name=name)
    df = df.copy()
    df['model'] = df['model_name_clean'].map(lambda n: resolved[n][0])
    df['submodel'] = df['model_name_clean'].map(lambda n: resolved[n][1])
    log_info(ctx, step, 'NAMES RESOLVED', names=len(resolved), resolved=sum(1 for m, _ in resolved.values() if m),
             unknown=sum(1 for m, _ in resolved.values() if not m))
    return df


def unique_keys(df, settings):
    """{(model, submodel or None, year): parts} for every applicable year (clipped to the window, D15)."""
    known = df[df['model'] != '']
    years = [clip_years(lo, hi, settings) for lo, hi in zip(known['min_year'], known['max_year'])]
    exploded = known.assign(year=years).explode('year')
    counts = exploded.groupby(['model', 'submodel', 'year'])['part_number'].nunique()
    return {(m, s or None, int(y)): int(n) for (m, s, y), n in counts.items()}


# ---------------------------------------------------------------- build the dict

def build_model_year_dict(df, results, settings, catalogue):
    """One DataFrame per accessory model name: each row is a part, an applicable year and a vehicle.
    Model numbers (with vehicle_id and variant) are attached by a lookup on (model, submodel, year); unmatched part-years keep
    model_number empty and match_status = their ACCESS_LOOKUP_ code. Returns (dict, review rows)."""
    years = [clip_years(lo, hi, settings) for lo, hi in zip(df['min_year'], df['max_year'])]
    rows = df.assign(applicable_year=years).explode('applicable_year')
    rows = rows[rows['applicable_year'].notna()].copy()
    rows['applicable_year'] = rows['applicable_year'].astype(int)
    rows = rows.drop(columns=['year_range', 'min_year', 'max_year'])          # A11: only applicable_year is kept

    keys = [(m, s or None, y) for m, s, y in zip(rows['model'], rows['submodel'], rows['applicable_year'])]
    found = [results.get(k) if m else None for k, m in zip(keys, rows['model'])]
    rows['match_key'] = [r['match_key'] if r else '' for r in found]
    rows['match_status'] = [r['match_status'] if r else 'ACCESS_LOOKUP_UNKNOWN_MODEL_NAME' for r in found]
    rows['vehicles'] = [r['vehicles'] if r and r['vehicles'] else [{}] for r in found]
    rows = rows.explode('vehicles').reset_index(drop=True)
    for field in ('model_number', 'vehicle_id', 'variant'):
        rows[field] = rows['vehicles'].map(lambda v, f=field: (v or {}).get(f, ''))
    rows = rows.drop(columns=['vehicles'])

    review = _part_review_rows(rows[rows['model_number'] == ''], results, catalogue)
    rows = rows.reindex(columns=DICT_COLUMNS + [c for c in rows.columns
                                                if c.endswith('_source') and c not in DICT_COLUMNS])
    model_dict = {name: group.sort_values(['part_number', 'applicable_year', 'model_number'])
                             .reset_index(drop=True)
                  for name, group in rows.groupby('model_name', sort=True)}
    return model_dict, review


def _part_review_rows(unmatched, results, catalogue):
    out = []
    for row in unmatched.itertuples(index=False):
        key = (row.model, row.submodel or None, row.applicable_year)
        result = results.get(key) if row.model else None
        if result and result['issue']:
            issue = result['issue']
        else:                                                  # unknown model name
            m = message_for(catalogue, 'ACCESS_LOOKUP_UNKNOWN_MODEL_NAME', name=row.model_name_clean)
            issue = {'code': m['code'], 'severity': m['severity'], 'message': m['message'],
                     'checked': f'"{row.model_name_clean}" is a model / submodel name in models.yaml',
                     'found': 'no model or submodel matches', 'causes': join_causes(m['causes']),
                     'fix': join_fix(m['fix'])}
        out.append({'type': 'part', 'record': f'ACC-{row.source_row}-{row.part_number}',
                    'part_number': row.part_number, 'model_name': row.model_name, 'model': row.model,
                    'submodel': row.submodel, 'year': row.applicable_year, 'match_key': row.match_key,
                    'model_number': '', **{k: issue[k] for k in ('code', 'severity', 'message', 'checked',
                                                                  'found', 'causes', 'fix')}})
    return out


# ---------------------------------------------------------------- data quality

def check_quality(df, spec, ctx=None, step='validate'):
    """The DQ rules from accessories.yaml, one warning per row and rule (never stops the run), plus
    ACCESS_DQ_FITMENT_HINT notes at info. Runs on the deduplicated rows (one per part and model)."""
    rules = spec['dq_rules']
    counts = {}

    def flag(row, code, field, field_value, /, checked, found, **facts):
        log_flag(ctx, step, row, code, field, field_value, checked=checked, found=found,
                 subject=f'{row["part_number"]} - {row["model_name"]} (row {row["source_row"]})', **facts)
        counts[code] = counts.get(code, 0) + 1

    for _, row in df.iterrows():
        for left, right in rules.get('greater_than', []):
            a, b = row[left], row[right]
            if pd.notna(a) and pd.notna(b) and not a > b:
                flag(row, 'ACCESS_DQ_VALUE_NOT_ABOVE', left, a, checked=f'{left} > {right}',
                     found=f'{left}={a}, {right}={b}', left=left, left_value=a, right=right, right_value=b)
        for col in rules.get('not_null', []):
            if pd.isna(row[col]) or str(row[col]).strip() == '':
                flag(row, 'ACCESS_DQ_VALUE_MISSING', col, '', checked=f'{col} is filled', found='empty', column=col)
        for col in rules.get('numeric_non_zero', []):
            if pd.notna(row[col]) and row[col] == 0:
                flag(row, 'ACCESS_DQ_VALUE_ZERO', col, row[col], checked=f'{col} != 0', found='0', column=col)
        for col in rules.get('numeric_non_negative', []):
            if pd.notna(row[col]) and row[col] < 0:
                flag(row, 'ACCESS_DQ_VALUE_NEGATIVE', col, row[col], checked=f'{col} >= 0', found=str(row[col]),
                     column=col, value=row[col])

    hints = spec['fitment_hints']
    if hints:
        pattern = re.compile(r'\b(' + '|'.join(re.escape(h) for h in hints) + r')\b', re.IGNORECASE)
        for description, group in df.groupby('product_description', sort=True):
            match = pattern.search(str(description))
            if match:
                first = group.iloc[0]
                log_flag(ctx, step, first, 'ACCESS_DQ_FITMENT_HINT', 'product_description', description,
                         subject=f'{first["part_number"]} - {len(group)} rows',
                         checked=f'description for: {", ".join(hints)}', found=f'"{match.group(0)}"',
                         description=description, hint=match.group(0))
                counts['ACCESS_DQ_FITMENT_HINT'] = counts.get('ACCESS_DQ_FITMENT_HINT', 0) + 1
    log_info(ctx, step, 'CHECKS RUN', rows=len(df), **(counts or {'issues': 0}))
    return df


# ---------------------------------------------------------------- export

def sheet_name(name, used):
    """A valid, unique Excel sheet name: no / \\ ? * [ ] :, at most 31 characters."""
    base = SHEET_FORBIDDEN.sub(' ', str(name)).strip()[:31] or 'Sheet'
    candidate, n = base, 1
    while candidate.lower() in used:
        n += 1
        candidate = f'{base[:31 - len(str(n)) - 1]}~{n}'
    used.add(candidate.lower())
    return candidate


def export_accessories(model_dict, spec, run_id, output_dir, ctx=None, step='export'):
    """Write one sheet per accessory model name with the configured columns and headers (matched rows only,
    unless export.include_unmatched). Returns (path, {sheet: rows})."""
    export = spec['export']
    columns = export['columns']
    path = Path(output_dir) / str(export['file_name']).format(run_id=run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    used, written = set(), {}
    part_column = spec['part_number']['column']
    text_column = (list(columns).index(part_column) + 1
                   if spec['part_number']['export_as_text'] and part_column in columns else 0)
    try:
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            for name, df in model_dict.items():
                rows = df if export.get('include_unmatched') else df[df['model_number'] != '']
                rows = rows.sort_values(export.get('sort_by') or list(columns)[:1], kind='stable')
                sheet = sheet_name(name, used)
                if sheet != name:
                    log_flag(ctx, step, {}, 'ACCESS_EXPORT_SHEET_RENAMED', subject=name,
                             checked='Excel sheet name rules', found=f'written as "{sheet}"', name=name, sheet=sheet)
                if rows.empty:
                    log_flag(ctx, step, {}, 'ACCESS_EXPORT_SHEET_EMPTY', subject=name,
                             checked=f'matched rows for {name}', found=f'0 of {len(df)} rows have a model number',
                             name=name)
                rows[list(columns)].rename(columns=columns).to_excel(writer, sheet_name=sheet, index=False)
                if text_column:
                    for (cell,) in writer.sheets[sheet].iter_rows(min_row=2, min_col=text_column,
                                                                  max_col=text_column):
                        cell.number_format = '@'                         # text: Excel keeps leading zeros
                written[sheet] = len(rows)
    except PermissionError:
        raise fatal(ctx, 'ACCESS_EXPORT_FILE_LOCKED', checked=f'write {path.as_posix()}', found='permission denied',
                    path=path.as_posix())
    log_info(ctx, step, 'EXPORTED', file=path.as_posix(), sheets=len(written), rows=sum(written.values()),
             columns=', '.join(columns.values()))
    return path, written


# ---------------------------------------------------------------- the whole run

def run_pipeline(config_dir=VW_DIR / 'config', db_dir=VW_DIR / 'db', source=None, run_id=None, export=True,
                 output_dir=None):
    """Run every step. Returns (status, summary, model_dict)."""
    config_dir, db_dir = Path(config_dir), Path(db_dir)
    settings = cfg.load_settings(config_dir)
    messages = load_messages(config_dir / 'messages.yaml')
    spec = cfg.load_accessory_config(config_dir, settings)
    source = Path(source) if source else VW_DIR / spec['source']
    ctx = start_run(settings, _display(source), db_dir, run_id=run_id, pipeline=PIPELINE, messages=messages)
    state = {}
    try:
        def load_config(_):
            taxonomy = cfg.validate_taxonomy(cfg.load_taxonomy(config_dir))
            option_sets = cfg.load_option_sets(config_dir, taxonomy)
            declared = cfg.vehicle_years(option_sets)
            verified = cfg.load_verified(config_dir, taxonomy, option_sets)
            version = config_version(config_dir)
            log_info(ctx, 'config', 'LOADED', columns=len(spec['renames']), dq_rules=len(spec['dq_rules']),
                     export_columns=len(spec['export']['columns']), aliases=len(taxonomy['aliases']),
                     option_sets=len(option_sets), verified_facts=len(verified), taxonomy_version=taxonomy['version'],
                     accessory_config=version)
            state.update(taxonomy=taxonomy, declared=declared, verified=verified, accessory_config=version)

        run_step(ctx, 'config', load_config, conditions={'config_dir': _display(config_dir),
                                                         'files': 'pipeline, accessories, models, messages + vehicles/*.yaml'})
        taxonomy = state['taxonomy']

        raw = run_step(ctx, 'ingest', lambda _: read_accessories(source, spec, ctx),
                       conditions={'file': _display(source), 'sheet': spec['sheet'], 'header_row': spec['header_row']})
        def part_numbers(df):
            checked, report = check_part_numbers(df, spec, ctx)
            path = store.write_table(report, db_dir, 'dq', 'part_number_check')
            log_info(ctx, 'part_numbers', 'WRITTEN', check_report=_display(path), combinations=len(report))
            check_unproven_share(report, spec, ctx)
            state['part_number_report'] = report
            return checked

        pn = spec['part_number']
        proven = run_step(ctx, 'part_numbers', part_numbers, raw,
                          conditions={'check_column': pn['check_column'], 'suffix': pn['suffix_column'],
                                      'restore': pn['restore'], 'allowed': pn['allowed_characters'],
                                      'max_unproven_share': pn['max_unproven_share']})
        staged = run_step(ctx, 'staging', lambda df: stage_accessories(df, spec, taxonomy['make'], ctx), proven,
                          conditions={'keep_rows': spec['keep_rows'], 'make': taxonomy['make']})
        window = f"{settings['min_model_year']}..{settings.get('max_model_year') or '(no max)'}"
        kept = run_step(ctx, 'year_window', lambda df: note_clipped(
                            filter_by_year_window(df, settings, DATASET, ctx), settings, ctx), staged,
                        conditions={'rule': settings['datasets'][DATASET]['year_rule'], 'window': window})
        tc = spec['text_cleaning']
        cleaned_text = run_step(ctx, 'clean_text', lambda df: _keep_review(
                                    state, 'text_review', clean_text_columns(df, spec, ctx)), kept,
                                conditions={'columns': ', '.join(tc['columns']), 'link_rules': len(tc['link_rules']),
                                            'allowed_hosts': ', '.join(tc['allowed_link_hosts'])})
        unique = run_step(ctx, 'dedupe', lambda df: remove_duplicates(df, ctx), cleaned_text,
                          conditions={'compare': 'every column but source_row and lineage'})
        run_step(ctx, 'part_number_review', lambda df: state.update(
                     part_number_review=flag_part_numbers(df, state['part_number_report'], ctx)) or df, unique,
                 conditions={'flagged': 'every result but same, rows in scope only'})
        cleaned = run_step(ctx, 'clean', lambda df: _keep_review(state, 'unit_review', convert_units(
                               clean_accessories(df, spec, taxonomy['aliases'], ctx), spec, ctx)), unique,
                           conditions={'aliases': len(taxonomy['aliases']),
                                       'numbers': ', '.join(c for c, t in spec['types'].items() if t == 'number')})
        named = run_step(ctx, 'resolve_names', lambda df: resolve_names(df, taxonomy, ctx), cleaned,
                         conditions={'names': cleaned['model_name_clean'].nunique()})

        def lookup(df):
            index = load_vehicle_index(db_dir, taxonomy['version'], spec['variant'], ctx)
            keys = unique_keys(df, settings)
            results = fetch(keys, index, state['declared'], taxonomy, ctx)
            path = store.write_table(lookup_report(results), db_dir, 'dq', 'accessory_lookup')
            log_info(ctx, 'lookup', 'WRITTEN', lookup_report=_display(path), keys=len(results))
            state.update(index=index, keys=keys, results=results)
            return df

        run_step(ctx, 'lookup', lookup, named, conditions={'vehicle_db': 'db/final/vehicles.csv',
                                                           'key': '(make, model, submodel, year)'})

        def build(df):
            model_dict, review = build_model_year_dict(df, state['results'], settings, ctx['messages'])
            rows = sum(len(d) for d in model_dict.values())
            matched = sum(int((d['model_number'] != '').sum()) for d in model_dict.values())
            for name, d in model_dict.items():
                log_detail(ctx, 'build_dict', 'MODEL', name=name, rows=len(d),
                           matched=int((d['model_number'] != '').sum()), parts=d['part_number'].nunique())
            log_info(ctx, 'build_dict', 'DICT BUILT', models=len(model_dict), rows=rows, matched_rows=matched,
                     unmatched_part_years=len(review))
            state.update(model_dict=model_dict, part_review=review)
            return df

        run_step(ctx, 'build_dict', build, named, conditions={'one_row_per': 'part, applicable year, vehicle'})

        def cover(df):
            state['vehicle_review'] = coverage(state['index'], state['keys'], taxonomy, ctx)
            return df

        run_step(ctx, 'coverage', cover, named, conditions={'direction': 'vehicle DB -> accessories'})
        run_step(ctx, 'validate', lambda df: check_quality(df, spec, ctx), named,
                 conditions={'rules': ', '.join(spec['dq_rules']), 'fitment_hints': len(spec['fitment_hints'])})

        # the final check: flags a verified fact explains drop to info; contradictions become errors (idea 009)
        def verify(df):
            rows, verified = verify_flags(ctx, state['verified'])
            contradicted = accessory_contradictions(ctx, state['verified'], state['index'], taxonomy['make'])
            for d in state['model_dict'].values():
                hit = [(c, k) in verified for c, k in zip(d['match_status'], d['match_key'])]
                d.loc[hit, 'match_status'] = 'never_offered'
            review_rows = drop_verified(state['part_review'] + state['part_number_review'] + state['text_review']
                                        + state['unit_review'] + state['vehicle_review'], verified)
            review = pd.DataFrame(review_rows, columns=REVIEW_COLUMNS)
            path = store.write_table(review, db_dir, 'review', 'accessory_review')
            report = store.write_table(verified_report(rows), db_dir, 'dq', 'verified_flags')
            log_info(ctx, 'verify', 'WRITTEN', review=_display(path), review_rows=len(review),
                     verified_flags=_display(report), flags_verified=len(rows), contradicted=contradicted,
                     part_rows=sum(r['type'] == 'part' for r in review_rows),
                     vehicle_rows=sum(r['type'] == 'vehicle' for r in review_rows))
            state.update(review_rows=len(review), flags_verified=len(rows), verified_contradicted=contradicted)
            return df

        run_step(ctx, 'verify', verify, named, conditions={'facts': len(state['verified']),
                                                           'match': 'exact (model, submodel, year)'})

        state['export'] = ('', {})
        if export:
            out = Path(output_dir) if output_dir else VW_DIR / spec['export']['output_dir']
            run_step(ctx, 'export', lambda df: state.update(
                         export=export_accessories(state['model_dict'], spec, ctx['run_id'], out, ctx)) or df, named,
                     conditions={'output_dir': _display(out), 'include_unmatched': spec['export'].get('include_unmatched')})

        summary = run_summary(ctx, raw, staged, kept, unique, named, state)
        store.append_row({'run_id': ctx['run_id'], 'started_at': ctx['started_at'], 'source_file': _display(source),
                          'min_model_year': settings['min_model_year'],
                          'max_model_year': settings.get('max_model_year') or '',
                          'taxonomy_version': taxonomy['version'], 'accessory_config': state['accessory_config'],
                          'status': run_status(ctx), **summary}, db_dir, 'dq', 'accessory_runs')
        status = end_run(ctx, summary=summary)
        return status, summary, state['model_dict']
    except Exception:
        end_run(ctx, status='failed')
        raise


def _keep_review(state, name, result):
    """Store a step's review rows in state and pass its DataFrame on."""
    df, state[name] = result
    return df


def build_accessory_model_dict(config_dir=VW_DIR / 'config', db_dir=VW_DIR / 'db', source=None, export=True,
                               output_dir=None):
    """The per-model dict of accessory DataFrames with model numbers attached (the notebook entry point)."""
    return run_pipeline(config_dir, db_dir, source, export=export, output_dir=output_dir)[2]


def run_summary(ctx, raw, staged, kept, unique, named, state):
    results = state['results']
    model_dict = state['model_dict']
    path, sheets = state['export']
    checks = state['part_number_report'].groupby('part_number_check')['rows'].sum()
    return {'rows_read': len(raw),
            'part_numbers_restored': int(checks.get('restored', 0)),
            'part_numbers_unproven': int(checks[~checks.index.isin(PROVEN)].sum()),
            'texts_cleaned': sum(1 for c in ctx['changes'] if c['step'] == 'clean_text'),
            'links_flagged': len(state['text_review']), 'unit_suspects': len(state['unit_review']), 'rows_staged': len(staged), 'rows_in_window': len(kept),
            'rows_unique': len(unique), 'model_names': named['model_name'].nunique(),
            'unknown_model_names': named.loc[named['model'] == '', 'model_name'].nunique(),
            'keys': len(results), 'keys_found': sum(1 for r in results.values() if r['vehicles']),
            'keys_missed': sum(1 for r in results.values() if not r['vehicles']),
            'dict_rows': sum(len(d) for d in model_dict.values()),
            'matched_rows': sum(int((d['model_number'] != '').sum()) for d in model_dict.values()),
            'unmatched_part_years': len(state['part_review']),
            'vehicles_without_parts': len(state['vehicle_review']),
            'export_file': _display(path) if path else '', 'export_sheets': len(sheets),
            'review_rows': state['review_rows'], 'flags_verified': state['flags_verified'],
            'verified_contradicted': state['verified_contradicted'],
            'flags_warning': sum(f['severity'] == 'warning' for f in ctx['flags']),
            'flags_error': sum(f['severity'] in ('error', 'fatal') for f in ctx['flags'])}


def config_version(config_dir):
    """Short hash of the files that shape the accessory output (accessories, models, messages)."""
    digest = hashlib.sha1()
    for name in ('accessories.yaml', 'models.yaml', 'messages.yaml'):
        path = Path(config_dir) / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()[:10]


def _display(path):
    try:
        return Path(path).resolve().relative_to(VW_DIR).as_posix()
    except ValueError:
        return Path(path).as_posix()
