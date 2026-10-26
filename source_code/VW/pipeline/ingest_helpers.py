"""Read the source file, stage it untouched, and apply the model year window."""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.logging_helpers import PipelineFatal, log_excluded, log_flag, log_info

REQUIRED_COLUMNS = ['description', 'manufacturer', 'model_number', 'model_year']
KEY = ['model_number', 'model_year']


def read_source(path, ctx=None, step='ingest'):
    """Read the CSV with every value as text (codes keep leading zeros) and drop all-empty columns."""
    path = Path(path)
    if not path.exists():
        raise PipelineFatal(f'source file not found: {path}')
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    empty = [c for c in df.columns if (df[c].str.strip() == '').all()]
    log_info(ctx, step, 'SOURCE', file=path.name, size_kb=round(path.stat().st_size / 1024, 1),
             modified=datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
             rows=len(df), columns=len(df.columns))
    if empty:
        log_info(ctx, step, 'DROPPED EMPTY COLUMNS', count=len(empty), columns=', '.join(empty))
    return df.drop(columns=empty)


def snake_case(name):
    """ModelNumber -> model_number, Style_ID -> style_id, engine_type -> engine_type."""
    name = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', str(name).strip())
    return re.sub(r'[^0-9a-zA-Z]+', '_', name).strip('_').lower()


def to_staging(df, source_file, ctx=None, step='staging'):
    """Rename columns to snake_case and add lineage; values stay exactly as read."""
    renames = {c: snake_case(c) for c in df.columns}
    changed = {a: b for a, b in renames.items() if a != b}
    if changed:
        log_info(ctx, step, 'RENAMED COLUMNS', columns=', '.join(f'{a}->{b}' for a, b in changed.items()))
    staged = df.rename(columns=renames)
    staged.insert(0, 'source_row', range(2, len(staged) + 2))     # row number in the file (header = 1)
    staged['source_file'] = Path(source_file).as_posix()
    staged['ingested_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return staged


def validate_staging(df, make, ctx=None, step='staging'):
    """Required columns, numeric model_year and a unique (model_number, model_year) key.
    Missing columns or duplicate keys stop the run; other problems are flagged."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise PipelineFatal(f'source is missing required column(s): {", ".join(missing)}')

    for _, row in df[~df['model_year'].str.fullmatch(r'\d{4}')].iterrows():
        log_flag(ctx, step, row, 'invalid_model_year', 'error', 'model_year', row['model_year'],
                 f'source row {row["source_row"]}: model_year is not a 4-digit year')
    for _, row in df[df['model_number'].str.strip() == ''].iterrows():
        log_flag(ctx, step, row, 'missing_model_number', 'error', 'model_number', '',
                 f'source row {row["source_row"]}: model_number is empty')
    for _, row in df[df['manufacturer'].str.strip().str.lower() != str(make).lower()].iterrows():
        log_flag(ctx, step, row, 'unexpected_manufacturer', 'warning', 'make', row['manufacturer'],
                 f'source row {row["source_row"]}: expected {make}')

    duplicated = df[df.duplicated(KEY, keep=False)]
    if len(duplicated):
        keys = sorted({f'{r.model_number}/{r.model_year}' for r in duplicated.itertuples()})
        raise PipelineFatal(f'duplicate (model_number, model_year) key in {len(duplicated)} rows: '
                            f'{", ".join(keys[:10])}{" ..." if len(keys) > 10 else ""}')
    log_info(ctx, step, 'KEY CHECK', key='(model_number, model_year)', unique_keys=len(df), duplicates=0)
    return df


def filter_by_year_window(df, settings, dataset, ctx=None, step='year_window'):
    """Keep rows inside the model year window; log every excluded row with the reason.

    single_year:   min <= year <= max
    range_overlap: end >= min and start <= max   (an accessory for 2018-2022 fits a 2020+ window)
    The max checks are skipped when max_model_year is empty.
    """
    rule_cfg = settings['datasets'][dataset]
    min_year, max_year = settings['min_model_year'], settings.get('max_model_year')
    rule = rule_cfg['year_rule']

    if rule == 'single_year':
        year = pd.to_numeric(df[rule_cfg['year_column']], errors='coerce')
        keep = year >= min_year
        if max_year is not None:
            keep &= year <= max_year

        def reason(row):
            y = row[rule_cfg['year_column']]
            if not str(y).isdigit():
                return f'model year {y!r} is not a number'
            if int(y) < min_year:
                return f'{y} < min_model_year {min_year}'
            return f'{y} > max_model_year {max_year}'
    else:
        start = pd.to_numeric(df[rule_cfg['start_column']], errors='coerce')
        end = pd.to_numeric(df[rule_cfg['end_column']], errors='coerce')
        keep = end >= min_year
        if max_year is not None:
            keep &= start <= max_year

        def reason(row):
            s, e = row[rule_cfg['start_column']], row[rule_cfg['end_column']]
            if pd.isna(pd.to_numeric(e, errors='coerce')):
                return f'year range {s}-{e} is not numeric'
            if float(e) < min_year:
                return f'range {s}-{e} ends before min_model_year {min_year}'
            return f'range {s}-{e} starts after max_model_year {max_year}'

    keep = keep.fillna(False).astype(bool)
    excluded = df[~keep]
    log_excluded(ctx, step, excluded, reason)
    if len(excluded):
        years = sorted({str(r) for r in excluded[rule_cfg.get('year_column', rule_cfg.get('start_column'))]})
        log_info(ctx, step, 'EXCLUDED', count=len(excluded), years=', '.join(years))
    kept = df[keep]
    if len(df) and not len(kept):
        log_flag(ctx, step, {}, 'empty_year_window', 'warning', '', '',
                 f'window {min_year}..{max_year or "(no max)"} removed every {dataset} row')
    return kept


def clip_years(min_year_value, max_year_value, settings):
    """Applicable years for a range, clipped to the window (D15): 2018-2022 at min 2020 -> [2020, 2021, 2022]."""
    lo = max(int(min_year_value), settings['min_model_year'])
    hi = int(max_year_value)
    if settings.get('max_model_year') is not None:
        hi = min(hi, settings['max_model_year'])
    return list(range(lo, hi + 1))
