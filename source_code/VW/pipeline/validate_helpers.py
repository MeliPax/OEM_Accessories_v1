"""Checks on the built vehicles table. Every problem is a flag; none of these stop the run (D17)."""

import pandas as pd

from pipeline.config_helpers import find_option_set
from pipeline.logging_helpers import log_flag, log_info
from pipeline.parse_helpers import split_multi_value

REQUIRED = ['make', 'model', 'model_year', 'model_number']


def check_required(vehicles, ctx=None, step='validate'):
    """make, model, model_year and model_number must be filled."""
    count = 0
    for _, row in vehicles.iterrows():
        for col in REQUIRED:
            if str(row[col]).strip() == '':
                log_flag(ctx, step, row, 'missing_required', 'error', col, '', f'{col} is empty')
                count += 1
    return count


def check_option_sets(vehicles, option_sets, option_categories, ctx=None, step='validate'):
    """Every vehicle must be covered by an option set, and every value must be offered by it.
    Strict (D16): a category not listed in the option set means "not offered"."""
    count = 0
    for _, row in vehicles.iterrows():
        if not row['model']:
            continue
        submodel = row['submodel'] or None
        year = int(row['model_year'])
        found = find_option_set(option_sets, row['model'], submodel, year)
        label = f'{row["model"]}{" " + submodel if submodel else ""} {year}'
        if found is None:
            log_flag(ctx, step, row, 'no_option_set', 'warning', '', '',
                     f'no option set covers {label}; add one to config/vehicles/')
            count += 1
            continue
        for category in option_categories:
            allowed = found['options'].get(category, set())
            for value in split_multi_value(row[category]):
                if value not in allowed:
                    offered = ', '.join(sorted(allowed)) if allowed else 'nothing (category not listed)'
                    log_flag(ctx, step, row, 'not_offered', 'warning', category, value,
                             f'{label} offers {category}: {offered} '
                             f'(vehicles/{found["file"]}, years {found["start"]}-{found["end"]})')
                    count += 1
    return count


def model_number_changes(vehicles, categories):
    """Model numbers used in several years whose values differ in any of these categories.
    Only categories filled in both years are compared, so a shorter description in a later year
    (fewer details) doesn't count. Returns {model_number: (rows, 'trim: Comfortline (2020); Highline (2021)')}."""
    changes = {}
    for model_number, group in vehicles.groupby('model_number'):
        if group['model_year'].nunique() < 2:
            continue
        differing = []
        for category in categories:
            filled = group[group[category] != '']
            if filled[category].nunique() > 1:
                by_value = filled.groupby(category)['model_year'].apply(lambda s: ', '.join(sorted(s)))
                differing.append(f'{category}: ' + '; '.join(f'{v} ({y})' for v, y in by_value.items()))
        if differing:
            changes[model_number] = (group.sort_values('model_year'), ' / '.join(differing))
    return changes


def check_model_number_consistency(vehicles, compare_categories, ctx=None, step='validate', note_categories=()):
    """Flag a model number whose compare_categories differ across years (e.g. it moved to another model).
    Differences in note_categories (trim, packages, ...) are allowed: logged at INFO, not flagged."""
    count = 0
    for model_number, (group, detail) in model_number_changes(vehicles, compare_categories).items():
        for _, row in group.iterrows():
            log_flag(ctx, step, row, 'inconsistent_model_number', 'warning', '', model_number, detail)
            count += 1

    allowed = {m: d for m, (_, d) in model_number_changes(vehicles, note_categories).items()}
    if allowed:
        log_info(ctx, step, 'MODEL NUMBER REUSED WITH CHANGES (allowed)', count=len(allowed),
                 examples=' ; '.join(f'{m} {d}' for m, d in list(allowed.items())[:5]))
    return count


REVIEW_COLUMNS = ['vehicle_id', 'model_number', 'model_year', 'description_clean', 'rule', 'severity',
                  'category', 'value', 'detail']


def build_review_queue(flags, vehicles):
    """Flags that need a person's eye, one row per vehicle and issue, with the description alongside."""
    queue = pd.DataFrame([{c: f.get(c, '') for c in REVIEW_COLUMNS if c != 'description_clean'} for f in flags])
    if queue.empty:
        return pd.DataFrame(columns=REVIEW_COLUMNS)
    descriptions = vehicles[['vehicle_id', 'description_clean']] if vehicles is not None else None
    if descriptions is not None:
        queue = queue.merge(descriptions, on='vehicle_id', how='left')
    return queue.reindex(columns=REVIEW_COLUMNS).fillna('').sort_values(['rule', 'vehicle_id'], kind='stable')
