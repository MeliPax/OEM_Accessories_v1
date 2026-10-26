"""Apply the resolutions in keywords.yaml: re-read a parsed value as something else for specific vehicles.

Runs after parse and before validate. Example (the only rule today):
    a lone "Black" (appearance_package = Black) on a vehicle whose option set offers
    special_edition = Black Edition becomes special_edition = Black Edition.

    when: option_set_offers
        offered by the vehicle's option set      -> value moved, logged as rule "resolution"
        not offered, but the same model number
        has the "to" value in another year       -> not changed, flagged resolution_suggested
        the "to" category already holds a
        different single value                   -> not changed, flagged resolution_conflict

description_clean is never changed, so the original wording stays as evidence.
"""

from pipeline.config_helpers import find_option_set
from pipeline.logging_helpers import log_change, log_flag
from pipeline.parse_helpers import split_multi_value, to_cell


def apply_resolutions(vehicles, taxonomy, option_sets, ctx=None, step='resolve'):
    """Return a copy of vehicles with every resolution applied (each change logged with the reason)."""
    vehicles = vehicles.copy()
    multi = {n for n, c in taxonomy['categories'].items() if c.get('multi_value')}

    for rule in taxonomy['resolutions']:
        from_cat, from_val = rule['from_category'], rule['from_value']
        to_cat, to_val = rule['to_category'], rule['to_value']
        # evidence from the parse, before any rule changed it: model number -> years that have the "to" value
        evidence = {}
        for _, row in vehicles[vehicles[to_cat].map(lambda c: to_val in split_multi_value(c))].iterrows():
            evidence.setdefault(row['model_number'], []).append(row['model_year'])

        for idx, row in vehicles.iterrows():
            from_values = split_multi_value(row[from_cat])
            if from_val not in from_values:
                continue
            found = find_option_set(option_sets, row['model'], row['submodel'] or None, int(row['model_year']))
            offered = found is not None and to_val in found['options'].get(to_cat, set())
            other_years = sorted(y for y in evidence.get(row['model_number'], []) if y != row['model_year'])
            seen = (f'; model number {row["model_number"]} is {to_val} in {", ".join(other_years)}'
                    if other_years else '')

            if not offered:
                if other_years:
                    where = (f'vehicles/{found["file"]} {found["start"]}-{found["end"]}' if found
                             else 'no option set')
                    log_flag(ctx, step, row, 'resolution_suggested', 'warning', to_cat, to_val,
                             f'"{rule["match"]}" could be {to_val}{seen}, but {where} does not offer it; '
                             f'add {to_cat}: [{to_val}] to the option set if it is')
                continue

            to_values = split_multi_value(row[to_cat])
            if to_cat not in multi and to_values and to_val not in to_values:
                log_flag(ctx, step, row, 'resolution_conflict', 'warning', to_cat, row[to_cat],
                         f'"{rule["match"]}" would become {to_cat} = {to_val}, '
                         f'but it already has {row[to_cat]}; not changed')
                continue

            reason = (f'"{rule["match"]}" -> {to_val}: vehicles/{found["file"]} '
                      f'{found["start"]}-{found["end"]} offers {to_cat} {to_val}{seen}')
            new_from = to_cell(set(from_values) - {from_val})
            new_to = to_cell(set(to_values) | {to_val}) if to_cat in multi else to_val
            log_change(ctx, step, row, from_cat, row[from_cat], new_from, 'resolution', reason)
            log_change(ctx, step, row, to_cat, row[to_cat], new_to, 'resolution', reason)
            vehicles.at[idx, from_cat] = new_from
            vehicles.at[idx, to_cat] = new_to
    return vehicles
