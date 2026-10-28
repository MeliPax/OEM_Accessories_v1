"""Human-verified vehicle facts (idea 009): the final check on whether a flag is still valid.

A person records in config/vehicles/<model>.yaml what they confirmed (config_helpers.load_verified):

    verified:
      - submodel: R
        never_offered: {years: [2020, 2021]}
        reason: ...    verified_by: P.M    verified_on: 2026-10-28

The verify step runs last in both pipelines:
  - a flag a fact covers exactly (code marked verifiable, same model, submodel and year) drops to info. It
    keeps its original severity and the entry in the flag log, and leaves the review files and run status;
  - data that contradicts a fact (the vehicle exists, or has the option) is a new error;
  - a fact that matched nothing is reported (info); a no_parts_expected fact past its until date brings
    its coverage flags back (warning).
Nothing is deleted: every verified flag is listed in db/dq/verified_flags.csv.
"""

from datetime import date

import pandas as pd

from pipeline.ingest_helpers import in_window
from pipeline.logging_helpers import log_flag, log_info
from pipeline.lookup_helpers import match_key, year_span
from pipeline.message_helpers import verifiable_codes

EXPLAINS = {'never_offered': 'LOOKUP', 'no_parts_expected': 'COVER'}   # fact kind -> the code stage it explains
VERIFIED_COLUMNS = ['run_id', 'code', 'original_severity', 'record', 'model', 'submodel', 'model_year', 'subject',
                    'entry', 'kind', 'reason', 'verified_by', 'verified_on', 'until', 'message']


def _year(value):
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def _explains(fact):
    """Facts that can explain a flag: year facts and no_parts_expected (an option fact only guards data)."""
    return fact['kind'] in EXPLAINS and not fact['category']


def _covers(fact, flag):
    """Exact match on model, submodel and year, and the fact kind explains the code's stage."""
    return (_explains(fact) and flag['code'].split('_')[1] == EXPLAINS[fact['kind']]
            and flag.get('model', '') == fact['model'] and flag.get('submodel', '') == (fact['submodel'] or '')
            and _year(flag.get('model_year', '')) in fact['years'])


def _expired(fact, today):
    return fact['kind'] == 'no_parts_expected' and today.isoformat() > fact['until']


def match_flag(flag, facts, codes, today=None):
    """The fact that covers this flag, or None. Expired facts and codes that aren't verifiable never match."""
    today = today or date.today()
    if flag['code'] not in codes or flag['severity'] == 'fatal':
        return None
    return next((f for f in facts if _covers(f, flag) and not _expired(f, today)), None)


def verify_flags(ctx, facts, step='verify', today=None):
    """Downgrade the flags a fact covers; report expired and unused facts. Returns (verified rows for
    verified_flags.csv, {(code, record)} of the verified flags)."""
    today = today or date.today()
    codes = verifiable_codes(ctx['messages'])
    flags = [f for f in ctx['flags'] if f['code'] in codes]
    rows, verified, used = [], set(), {}
    for flag in flags:
        fact = match_flag(flag, facts, codes, today)
        if fact is None:
            continue
        flag['original_severity'], flag['severity'], flag['verified_entry'] = flag['severity'], 'info', fact['label']
        verified.add((flag['code'], flag['record']))
        used.setdefault(fact['label'], []).append(flag['code'])
        rows.append({'run_id': ctx['run_id'], **{k: flag.get(k, '') for k in
                                                ('code', 'original_severity', 'record', 'model', 'submodel',
                                                 'model_year', 'subject', 'message')},
                     'entry': fact['label'], 'kind': fact['kind'], 'reason': fact['reason'],
                     'verified_by': fact['verified_by'], 'verified_on': fact['verified_on'], 'until': fact['until']})

    for fact in (f for f in facts if _explains(f)):
        label = fact['label']
        if label in used:
            log_info(ctx, step, 'VERIFIED', entry=label, vehicle=fact['vehicle'], kind=fact['kind'],
                     years=year_span(fact['years']), flags=len(used[label]), codes=', '.join(sorted(set(used[label]))),
                     verified_by=fact['verified_by'], verified_on=fact['verified_on'])
        elif _expired(fact, today) and any(_covers(fact, f) for f in flags):
            log_flag(ctx, step, _key(fact), 'ACCESS_VERIFY_EXPIRED', subject=label,
                     checked=f'{label}: no_parts_expected until {fact["until"]}; today {today.isoformat()}',
                     found=f'{sum(_covers(fact, f) for f in flags)} coverage flags are back',
                     entry=label, vehicle=fact['vehicle'], years=year_span(fact['years']), until=fact['until'])
        else:
            log_flag(ctx, step, _key(fact), 'ACCESS_VERIFY_ENTRY_UNUSED', subject=label,
                     checked=f'every verifiable flag of this run against {label}',
                     found='no flag with the same model, submodel and year',
                     entry=label, vehicle=fact['vehicle'], kind=fact['kind'], years=year_span(fact['years']))
    return rows, verified


def accessory_contradictions(ctx, facts, vehicle_index, make, step='verify'):
    """A never-offered year that the vehicle DB has vehicles for. Returns the number of flags raised."""
    count = 0
    for fact in (f for f in facts if f['kind'] == 'never_offered' and not f['category']):
        for year in sorted(fact['years']):
            vehicles = vehicle_index['index'].get((fact['model'], fact['submodel'], year), [])
            if not vehicles:
                continue
            key = match_key(make, fact['model'], fact['submodel'], year)
            log_flag(ctx, step, {**_key(fact), 'record': key, 'model_year': year}, 'ACCESS_VERIFY_CONTRADICTED',
                     subject=f'{key} - {fact["label"]}',
                     checked=f'{fact["label"]} (never offered {year}) against the vehicle DB',
                     found=f'{len(vehicles)} vehicles: ' + ', '.join(v['model_number'] for v in vehicles),
                     entry=fact['label'], vehicle=fact['vehicle'], year=year, count=len(vehicles))
            count += 1
    return count


def vehicle_contradictions(ctx, facts, vehicles, step='verify'):
    """Vehicles in the export that a fact says were never offered: in that year, or with that option.
    Returns the number of flags raised (one per vehicle and fact)."""
    count = 0
    if vehicles.empty:
        return count
    model = vehicles['model'].fillna('').astype(str)
    submodel = vehicles['submodel'].fillna('').astype(str)
    year = pd.to_numeric(vehicles['model_year'], errors='coerce')
    for fact in facts:
        if fact['kind'] != 'never_offered':
            continue
        hit = (model == fact['model']) & (submodel == (fact['submodel'] or '')) & year.isin(fact['years'])
        what = fact['vehicle']
        if fact['category']:
            has = vehicles[fact['category']].fillna('').astype(str).map(
                lambda cell: bool(set(cell.split('|')) & fact['values']))
            hit &= has
            what = f'{fact["vehicle"]} with {fact["category"]} {"/".join(sorted(fact["values"]))}'
        for _, row in vehicles[hit].iterrows():
            log_flag(ctx, step, row, 'VEH_VERIFY_CONTRADICTED', fact['category'],
                     row[fact['category']] if fact['category'] else '',
                     checked=f'{fact["label"]} against every vehicle in this export',
                     found=f'{row["vehicle_id"]}: {row.get("description_clean", "")}',
                     entry=fact['label'], what=what, year=int(row['model_year']), vehicle_id=row['vehicle_id'])
            count += 1
    return count


def facts_in_window(facts, settings):
    """(facts with a year inside the window, facts entirely outside it). Facts outside are still true but
    can't match this run's flags, so they aren't reported unused; contradiction checks still use every fact."""
    inside = [f for f in facts if any(in_window(y, settings) for y in f['years'])]
    return inside, [f for f in facts if f not in inside]


def drop_verified(rows, verified):
    """Review rows whose flag was verified are left out of the review file."""
    return [r for r in rows if (r.get('code'), r.get('match_key')) not in verified]


def verified_report(rows):
    return pd.DataFrame(rows, columns=VERIFIED_COLUMNS)


def _key(fact):
    return {'record': fact['label'], 'model': fact['model'], 'submodel': fact['submodel'] or ''}
