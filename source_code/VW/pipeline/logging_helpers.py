"""Logging for every pipeline step: run log, step log, change log (before -> after) and flag log.

A run is described by a plain dict (the "ctx") that is passed from step to step:

    ctx = start_run(settings, source_file, db_dir, pipeline='vw_ingest')
    df = run_step(ctx, "clean", clean_func, df, conditions={...}, key_cols=KEY, watch_cols=["description"])
    end_run(ctx)

Every helper accepts ctx=None, in which case it does nothing (so the helpers can be used from the
notebook without creating log files).

The run id is the pipeline name followed by the run's date and time: vw_ingest_20261027_143005.

Flags carry a code from config/messages.yaml (idea 004); the code passes only the facts, and the
flag gets its severity, message, causes and fix from the catalogue, plus what was checked and found.

Outputs (under <db_dir>/logs):
    runs/<run_id>.log       readable story of the run
    steps.csv               one row per step, appended every run
    changes/<run_id>.csv    one row per value changed: before, after, rule, detail
    flags/<run_id>.csv      one row per flag: code, severity, subject, message, checked, found, causes, fix
"""

import logging
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.message_helpers import default_messages, join_causes, join_fix, message_for

# record = the row a change or flag is about: the vehicle_id for vehicles, ACC-<source row>-<part> for accessories
CHANGE_COLUMNS = ['run_id', 'step', 'record', 'vehicle_id', 'model_number', 'model_year',
                  'field', 'before', 'after', 'rule', 'detail']
FLAG_COLUMNS = ['run_id', 'step', 'code', 'severity', 'subject', 'record', 'vehicle_id', 'model_number', 'model_year',
                'model', 'submodel', 'category', 'value', 'message', 'checked', 'found', 'causes', 'fix',
                'original_severity', 'verified_entry']
KEY_FIELDS = ('record', 'vehicle_id', 'model_number', 'model_year', 'model', 'submodel')
REVIEW_SEVERITIES = ('fatal', 'error', 'warning')       # info flags stay in the log
STEP_COLUMNS = ['run_id', 'step_order', 'step', 'started_at', 'duration_s', 'rows_in', 'rows_out',
                'rows_changed', 'rows_excluded', 'flags', 'conditions', 'status', 'message']

LOG_FORMAT = '[%(asctime)s] [%(levelname)-7s] %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

DEFAULT_LOGGING = {'console_level': 'INFO', 'file_level': 'DEBUG', 'examples_per_rule': 3, 'keep_runs': 30}


class PipelineFatal(Exception):
    """Raised when a problem must stop the run (broken config, duplicate key). .code holds its code."""

    def __init__(self, text, code=''):
        super().__init__(text)
        self.code = code


# ---------------------------------------------------------------- run

def start_run(settings, source_file, db_dir, run_id=None, pipeline='vw_ingest', messages=None):
    """Create the run id, log folders and logger; log RUN START with the settings. Returns ctx.

    messages: the flag catalogue (message_helpers.load_messages); defaults to config/messages.yaml.
    """
    log_settings = {**DEFAULT_LOGGING, **(settings.get('logging') or {})}
    log_dir = Path(db_dir) / 'logs'
    for sub in ('runs', 'changes', 'flags'):
        (log_dir / sub).mkdir(parents=True, exist_ok=True)
    if run_id is None:
        base = run_id = f"{pipeline}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        n = 1
        while (log_dir / 'runs' / f'{run_id}.log').exists():   # two runs in the same second
            n += 1
            run_id = f'{base}_{n}'

    logger = logging.getLogger(f'vw_pipeline.{run_id}')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    file_handler = logging.FileHandler(log_dir / 'runs' / f'{run_id}.log', encoding='utf-8')
    file_handler.setLevel(log_settings['file_level'])
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_settings['console_level'])
    console_handler.setFormatter(formatter)
    # per-row lines (flags) go to the file only; the console gets a summary per rule
    console_handler.addFilter(lambda record: getattr(record, 'console', True))
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    ctx = {
        'run_id': run_id,
        'pipeline': pipeline,
        'messages': messages if messages is not None else default_messages(),
        'source_file': str(source_file),
        'settings': settings,
        'log_settings': log_settings,
        'log_dir': log_dir,
        'logger': logger,
        'started': time.perf_counter(),
        'started_at': datetime.now().strftime(DATE_FORMAT),
        'step_order': 0,
        'current_step': None,
        'changes': [],
        'flags': [],
        'excluded': [],
        'steps': [],
        'explicit': set(),     # (step, key, field) already logged with a reason, skipped by the diff
    }
    _log(ctx, 'run', 'RUN START', run_id=run_id, pipeline=pipeline, source=source_file,
         min_model_year=settings.get('min_model_year'), max_model_year=settings.get('max_model_year'))
    return ctx


def end_run(ctx, status=None, summary=None):
    """Write the change and flag logs, log RUN END with totals, prune old runs. Returns the final status."""
    if ctx is None:
        return status
    if status is None:
        status = run_status(ctx)
    changes_path = ctx['log_dir'] / 'changes' / f"{ctx['run_id']}.csv"
    flags_path = ctx['log_dir'] / 'flags' / f"{ctx['run_id']}.csv"
    pd.DataFrame(ctx['changes'], columns=CHANGE_COLUMNS).to_csv(changes_path, index=False)
    pd.DataFrame(ctx['flags'], columns=FLAG_COLUMNS).to_csv(flags_path, index=False)

    counts = flag_counts(ctx)
    totals = {'status': status, 'steps': len(ctx['steps']), 'changes': len(ctx['changes']),
              'flags_info': counts.get('info', 0), 'flags_warning': counts.get('warning', 0),
              'flags_error': counts.get('error', 0) + counts.get('fatal', 0)}
    totals.update(summary or {})
    _log(ctx, 'run', 'RUN END', **totals, duration=f"{time.perf_counter() - ctx['started']:.2f}s")
    _log(ctx, 'run', 'LOG FILES', run_log=_rel(ctx['log_dir'] / 'runs' / f"{ctx['run_id']}.log"),
         changes=_rel(changes_path), flags=_rel(flags_path))
    prune_runs(ctx['log_dir'], ctx['log_settings']['keep_runs'])

    for handler in ctx['logger'].handlers[:]:
        ctx['logger'].removeHandler(handler)
        handler.close()
    return status


def run_status(ctx):
    """ok / ok_with_warnings / ok_with_errors / failed, from the steps and flags so far."""
    if any(s['status'] == 'failed' for s in ctx['steps']):
        return 'failed'
    counts = flag_counts(ctx)
    if counts.get('fatal'):
        return 'failed'
    if counts.get('error'):
        return 'ok_with_errors'
    if counts.get('warning'):
        return 'ok_with_warnings'
    return 'ok'


def flag_counts(ctx):
    counts = {}
    for flag in ctx['flags']:
        counts[flag['severity']] = counts.get(flag['severity'], 0) + 1
    return counts


# ---------------------------------------------------------------- steps

def run_step(ctx, step, func, df=None, conditions=None, key_cols=None, watch_cols=None):
    """Run one pipeline step with full logging.

    Logs STEP START with the conditions, runs func(df), records every changed value in watch_cols
    (before -> after, matched on key_cols), logs examples and STEP END with counts, and appends a
    row to steps.csv. If func raises, logs FATAL, records the step as failed and re-raises.
    """
    if ctx is None:
        return func(df)

    ctx['step_order'] += 1
    ctx['current_step'] = step
    marks = (len(ctx['changes']), len(ctx['flags']), len(ctx['excluded']))
    rows_in = len(df) if isinstance(df, pd.DataFrame) else 0
    started_at = datetime.now().strftime(DATE_FORMAT)
    started = time.perf_counter()
    _log(ctx, step, 'STEP START', rows_in=rows_in, **(conditions or {}))

    try:
        result = func(df)
    except Exception as error:
        duration = time.perf_counter() - started
        for code, text in getattr(error, 'problems', []):     # ConfigError: one fatal flag per problem
            log_flag(ctx, step, {}, code, subject=text.split(':')[0], checked=text, found='problem found')
        _log(ctx, step, 'FATAL', level=logging.ERROR, reason=str(error), error_type=type(error).__name__,
             code=getattr(error, 'code', ''))
        _record_step(ctx, step, started_at, duration, rows_in, rows_out=0, rows_changed=0, rows_excluded=0,
                     conditions=conditions, status='failed', message=str(error))
        ctx['current_step'] = None
        raise

    result_df = result if isinstance(result, pd.DataFrame) else None
    if watch_cols and key_cols and isinstance(df, pd.DataFrame) and result_df is not None:
        for change in diff_frames(df, result_df, key_cols, watch_cols):
            row_key = _row_key(change)
            if (step, row_key['record'], change['field']) not in ctx['explicit']:
                _add_change(ctx, step, row_key, change['field'],
                            change['before'], change['after'], 'diff', '')

    new_changes = ctx['changes'][marks[0]:]
    new_flags = ctx['flags'][marks[1]:]
    rows_excluded = sum(ctx['excluded'][marks[2]:])
    rows_changed = len({c['record'] for c in new_changes if c['rule'] != 'excluded'})
    rows_out = len(result_df) if result_df is not None else 0
    duration = time.perf_counter() - started

    _log_examples(ctx, step, new_changes)
    _log_flag_summary(ctx, step, new_flags)
    status = 'ok_with_warnings' if any(f['severity'] != 'info' for f in new_flags) else 'ok'
    _log(ctx, step, 'STEP END', status=status, rows_in=rows_in, rows_out=rows_out,
         rows_changed=rows_changed, rows_excluded=rows_excluded, flags=len(new_flags),
         duration=f'{duration:.2f}s')
    _record_step(ctx, step, started_at, duration, rows_in, rows_out, rows_changed, rows_excluded,
                 conditions, status, '', flags=len(new_flags))
    ctx['current_step'] = None
    return result


def _record_step(ctx, step, started_at, duration, rows_in, rows_out, rows_changed, rows_excluded,
                 conditions, status, message, flags=0):
    row = {
        'run_id': ctx['run_id'], 'step_order': ctx['step_order'], 'step': step,
        'started_at': started_at, 'duration_s': round(duration, 3),
        'rows_in': rows_in, 'rows_out': rows_out, 'rows_changed': rows_changed,
        'rows_excluded': rows_excluded, 'flags': flags,
        'conditions': '; '.join(f'{k}={v}' for k, v in (conditions or {}).items()),
        'status': status, 'message': message,
    }
    ctx['steps'].append(row)
    steps_path = ctx['log_dir'] / 'steps.csv'
    pd.DataFrame([row], columns=STEP_COLUMNS).to_csv(
        steps_path, mode='a', header=not steps_path.exists(), index=False)


# ---------------------------------------------------------------- changes, exclusions, flags

def log_change(ctx, step, row_key, field, before, after, rule, detail=''):
    """Record one value change with the reason (which rule / keyword caused it)."""
    if ctx is None:
        return
    row_key = _row_key(row_key)
    ctx['explicit'].add((step, row_key['record'], field))
    _add_change(ctx, step, row_key, field, before, after, rule, detail)


def log_excluded(ctx, step, df_excluded, reason_func):
    """Record rows a step dropped. reason_func(row) -> text explaining why that row was excluded."""
    if ctx is None or df_excluded is None or len(df_excluded) == 0:
        return
    for _, row in df_excluded.iterrows():
        _add_change(ctx, step, _row_key(row), '(row)', 'kept', 'excluded', 'excluded', reason_func(row))
        ctx['logger'].debug(f"[{step:<11}] EXCLUDED | record={_row_key(row)['record']} | reason={reason_func(row)}")
    ctx['excluded'].append(len(df_excluded))


def log_flag(ctx, step, row_key, code, category='', value='', /, checked='', found='', subject='', **facts):
    """Record a flag. Severity, message, causes and fix come from messages.yaml for this code, filled
    from facts; checked / found say what was looked at and what came back. The run log gets a block:

        [step       ] FLAG VEH_PARSE_UNKNOWN_WORD | VW-2024-ABC123
            what:    Word "Rline" in "Tiguan Rline" matches no keyword
            checked: config/keywords.yaml, every category
            ...
    """
    if ctx is None:
        return
    m = message_for(ctx['messages'], code, **facts)
    key = _key_fields(_row_key(row_key))
    flag = {'run_id': ctx['run_id'], 'step': step, 'code': code, 'severity': m['severity'],
            'subject': subject or key['record'], **key, 'category': category, 'value': _text(value),
            'message': m['message'], 'checked': _text(checked), 'found': _text(found),
            'causes': join_causes(m['causes']), 'fix': join_fix(m['fix'])}
    ctx['flags'].append(flag)
    level = {'fatal': logging.CRITICAL, 'error': logging.ERROR, 'warning': logging.WARNING}.get(
        m['severity'], logging.INFO)
    lines = [f'[{step:<11}] FLAG {code} | {flag["subject"]}', f'    what:    {flag["message"]}']
    lines += [f'    {name + ":":<9}{flag[name]}' for name in ('checked', 'found', 'causes', 'fix') if flag[name]]
    ctx['logger'].log(level, '\n'.join(lines), extra={'console': False})
    return flag


def fatal(ctx, code, checked='', found='', subject='', **facts):
    """Record a fatal flag and return the PipelineFatal to raise:  raise fatal(ctx, 'VEH_...', path=...)."""
    catalogue = ctx['messages'] if ctx else default_messages()
    m = message_for(catalogue, code, **facts)
    if ctx is not None:
        log_flag(ctx, ctx.get('current_step') or 'run', {}, code, checked=checked, found=found,
                 subject=subject or code, **facts)
    text = f'{code}: {m["message"]}' + (f' | found: {found}' if found else '') + f' | fix: {join_fix(m["fix"])}'
    return PipelineFatal(text, code=code)


def log_info(ctx, step, event, **fields):
    """Log an extra INFO line for a step (e.g. counts that aren't rows)."""
    if ctx is None:
        return
    _log(ctx, step, event, **fields)


def log_detail(ctx, step, event, **fields):
    """Log an INFO line to the run log file only (one line per key or item; the console gets a summary)."""
    if ctx is None:
        return
    _log(ctx, step, event, console=False, **fields)


def diff_frames(before, after, key_cols, watch_cols):
    """Changed cells between two frames, matched on key_cols. Rows only in one frame are ignored
    (exclusions are logged separately). Returns a list of dicts: key columns + field, before, after."""
    cols = [c for c in watch_cols if c in before.columns or c in after.columns]
    left = before.reindex(columns=list(key_cols) + cols).copy()
    right = after.reindex(columns=list(key_cols) + cols).copy()
    merged = left.merge(right, on=list(key_cols), how='inner', suffixes=('__before', '__after'))
    changes = []
    for col in cols:
        b = merged[f'{col}__before'].map(_text)
        a = merged[f'{col}__after'].map(_text)
        for idx in merged.index[b != a]:
            change = {k: merged.at[idx, k] for k in key_cols}
            change.update(field=col, before=b[idx], after=a[idx])
            changes.append(change)
    return changes


# ---------------------------------------------------------------- retention

def prune_runs(log_dir, keep_runs):
    """Keep the newest keep_runs files per pipeline in runs/, changes/ and flags/; steps.csv is never
    pruned. The pipeline is the run id before its date-time (ids without one form their own group)."""
    for sub in ('runs', 'changes', 'flags'):
        groups = {}
        for path in (Path(log_dir) / sub).glob('*.*'):
            groups.setdefault(_pipeline_of(path.stem), []).append(path)
        for files in groups.values():
            for old in sorted(files)[:-keep_runs] if keep_runs else []:
                old.unlink()


def _pipeline_of(run_id):
    match = re.match(r'^(.*?)_?\d{8}_\d{6}', run_id)
    return match.group(1) if match else ''


# ---------------------------------------------------------------- internals

def _add_change(ctx, step, row_key, field, before, after, rule, detail):
    change = {'run_id': ctx['run_id'], 'step': step, **_key_fields(row_key), 'field': field,
              'before': _text(before), 'after': _text(after), 'rule': rule, 'detail': detail}
    ctx['changes'].append(change)
    if rule != 'excluded':
        ctx['logger'].debug(f"[{step:<11}] CHANGE | record={change['record']} | field={field} | "
                            f"\"{change['before']}\" -> \"{change['after']}\" | rule={rule}"
                            + (f' | {detail}' if detail else ''))


def _key_fields(row_key):
    get = row_key.get if hasattr(row_key, 'get') else (lambda k, d='': d)
    return {k: _text(get(k, '')) for k in KEY_FIELDS}


def _row_key(row):
    """record / vehicle_id / model_number / model_year from a row, dict or Series. A vehicle row gets its
    vehicle_id (built if missing); an accessory row (part_number + source_row) gets ACC-<source row>-<part>."""
    get = row.get if hasattr(row, 'get') else (lambda k, d='': d)
    key = {k: _text(get(k, '')) for k in KEY_FIELDS}
    if not key['vehicle_id'] and key['model_number'] and key['model_year']:
        key['vehicle_id'] = vehicle_id(key['model_year'], key['model_number'])
    if not key['record']:
        part, source_row = _text(get('part_number', '')), _text(get('source_row', ''))
        key['record'] = key['vehicle_id'] or (accessory_id(source_row, part) if part or source_row else '')
    return key


def accessory_id(source_row, part_number):
    """Accessory row key for logs: ACC-<row in the accessory file>-<part number>."""
    return f'ACC-{source_row}-{part_number}'


def vehicle_id(model_year, model_number):
    """Deterministic vehicle key: VW-{model_year}-{model_number}."""
    return f'VW-{model_year}-{model_number}'


def _log_examples(ctx, step, changes):
    """INFO: count + a few before -> after examples per rule, so the run log reads as a story."""
    per_rule = {}
    for change in changes:
        per_rule.setdefault(change['rule'], []).append(change)
    limit = ctx['log_settings']['examples_per_rule']
    for rule, rows in per_rule.items():
        examples = [f"{r['record']} {r['field']}: \"{r['before']}\" -> \"{r['after']}\""
                    + (f" ({r['detail']})" if r['detail'] else '') for r in rows[:limit]]
        _log(ctx, step, 'CHANGED', rule=rule, count=len(rows), examples=' ; '.join(examples))


def _log_flag_summary(ctx, step, flags):
    """Console + log: one line per code with a count and a few examples (the per-flag blocks are file only)."""
    per_code = {}
    for flag in flags:
        per_code.setdefault((flag['code'], flag['severity']), []).append(flag)
    limit = ctx['log_settings']['examples_per_rule']
    for (code, severity), rows in per_code.items():
        examples = [f"{r['subject']} {r['category']}={r['value']}" if r['category'] else r['subject']
                    for r in rows[:limit]]
        level = {'fatal': logging.CRITICAL, 'error': logging.ERROR, 'warning': logging.WARNING}.get(
            severity, logging.INFO)
        _log(ctx, step, 'FLAGGED', level=level, code=code, severity=severity, count=len(rows),
             examples=' ; '.join(examples), message=rows[0]['message'] if len(rows) == 1 else '')


def _log(ctx, step, event, level=logging.INFO, console=True, **fields):
    parts = [f'[{step:<11}] {event}'] + [f'{k}={v}' for k, v in fields.items() if v not in (None, '')]
    ctx['logger'].log(level, ' | '.join(parts), extra={'console': console})


def _text(value):
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except (TypeError, ValueError):
        pass
    if isinstance(value, (set, frozenset, list, tuple)):
        return '|'.join(sorted(str(v) for v in value))
    return str(value)


def _rel(path):
    try:
        return str(Path(path).relative_to(Path.cwd()))
    except ValueError:
        return str(path)
