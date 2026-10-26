"""Rebuild the VW vehicle database from the VW model export.

    python run_ingest.py                 # from source_code/VW
    python run_ingest.py --source other.csv

Steps (every one logged through run_step):
    config -> ingest -> staging -> year_window -> clean -> parse -> resolve -> validate -> write

Exit code: 0 = ok or ok with warnings, 1 = errors flagged or the run failed, 2 = pipeline.yaml unreadable.
"""

import argparse
import sys
from pathlib import Path

VW_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(VW_DIR))

from pipeline import config_helpers as cfg                                    # noqa: E402
from pipeline import storage_helpers as store                                 # noqa: E402
from pipeline.clean_helpers import clean_descriptions                         # noqa: E402
from pipeline.ingest_helpers import (KEY, filter_by_year_window, read_source,  # noqa: E402
                                     to_staging, validate_staging)
from pipeline.logging_helpers import (end_run, log_change, log_info, run_status,  # noqa: E402
                                      run_step, start_run)
from pipeline.parse_helpers import build_vehicles, vehicle_columns            # noqa: E402
from pipeline.resolve_helpers import apply_resolutions                        # noqa: E402
from pipeline.validate_helpers import (build_review_queue, check_model_number_consistency,  # noqa: E402
                                       check_option_sets, check_required)

DATASET = 'vw_models'


def run(config_dir=VW_DIR / 'config', db_dir=VW_DIR / 'db', source=None, run_id=None):
    """Run the whole pipeline. Returns (status, ctx summary dict)."""
    config_dir, db_dir = Path(config_dir), Path(db_dir)
    settings = cfg.load_settings(config_dir)
    source = Path(source) if source else VW_DIR / settings['sources'][DATASET]
    ctx = start_run(settings, _display(source), db_dir, run_id=run_id)
    state = {}

    try:
        # 1. config: vocabulary + availability, validated, definitions exported
        def load_config(_):
            taxonomy = cfg.validate_taxonomy(cfg.load_taxonomy(config_dir))
            option_sets = cfg.load_option_sets(config_dir, taxonomy)
            counts = cfg.export_definitions(taxonomy, option_sets, db_dir / 'definitions')
            log_info(ctx, 'config', 'LOADED', categories=len(taxonomy['categories']),
                     models=len(taxonomy['models']), keywords=len(taxonomy['keywords']),
                     aliases=len(taxonomy['aliases']), option_sets=len(option_sets),
                     taxonomy_version=taxonomy['version'])
            log_info(ctx, 'config', 'DEFINITIONS WRITTEN',
                     **{name: f'{rows} rows' for name, rows in counts.items()})
            compare = (((settings.get('validation') or {}).get('model_number_consistency') or {})
                       .get('compare', ['model', 'submodel']))
            unknown = [c for c in compare if c not in taxonomy['categories']]
            if unknown:
                raise cfg.ConfigError(f'pipeline.yaml: validation.model_number_consistency.compare names '
                                      f'unknown categor{"ies" if len(unknown) > 1 else "y"}: {", ".join(unknown)}')
            state.update(taxonomy=taxonomy, option_sets=option_sets, compare_categories=list(compare))

        run_step(ctx, 'config', load_config, conditions={
            'config_dir': _display(config_dir),
            'files': 'pipeline, categories, models, keywords + vehicles/*.yaml'})
        taxonomy, option_sets = state['taxonomy'], state['option_sets']

        # 2. ingest: read the source as text, drop all-empty columns
        raw = run_step(ctx, 'ingest', lambda _: read_source(source, ctx),
                       conditions={'file': _display(source)})

        # 3. staging: snake_case + lineage, key checks, written untouched
        def stage(df):
            staged = validate_staging(to_staging(df, _display(source), ctx), taxonomy['make'], ctx)
            path = store.write_table(staged, db_dir, 'staging', 'stg_vw_models', sort_by=['model_year', 'model_number'])
            log_info(ctx, 'staging', 'WRITTEN', table=_display(path), rows=len(staged))
            return staged

        staged = run_step(ctx, 'staging', stage, raw, conditions={'key': '(model_number, model_year)'})

        # 4. year window
        window = f"{settings['min_model_year']}..{settings.get('max_model_year') or '(no max)'}"
        kept = run_step(ctx, 'year_window', lambda df: filter_by_year_window(df, settings, DATASET, ctx), staged,
                        conditions={'rule': settings['datasets'][DATASET]['year_rule'],
                                    'column': settings['datasets'][DATASET]['year_column'], 'window': window})

        # 5. clean descriptions (aliases, spaces, repeated words)
        cleaned = run_step(ctx, 'clean', lambda df: clean_descriptions(df, taxonomy['aliases'], ctx), kept,
                           conditions={'aliases': len(taxonomy['aliases']),
                                       'rules': 'alias, trim_spaces, remove_repeated_words'},
                           key_cols=KEY, watch_cols=['description'])   # safety net: raw description must not change

        # 6. parse into taxonomy columns
        vehicles = run_step(ctx, 'parse', lambda df: build_vehicles(df, taxonomy, ctx), cleaned,
                            conditions={'keywords': len(taxonomy['keywords']),
                                        'unique_descriptions': cleaned['description_clean'].nunique(),
                                        'taxonomy_version': taxonomy['version']})

        # 7. resolve: re-read parsed values per the resolutions in keywords.yaml (e.g. a lone "Black" -> Black Edition)
        vehicles = run_step(ctx, 'resolve', lambda df: apply_resolutions(df, taxonomy, option_sets, ctx), vehicles,
                            conditions={'resolutions': len(taxonomy['resolutions']),
                                        'rules': ', '.join(f'{r["match"]}: {r["from_value"]} -> {r["to_value"]} '
                                                           f'({r["when"]})' for r in taxonomy['resolutions'])})

        # 8. validate against required fields, option sets, and model number history
        option_categories = [c for c, spec in taxonomy['categories'].items()
                             if spec['source'] == 'keywords' and c != 'inventory_status']
        compare_categories = state['compare_categories']
        note_categories = [c for c in ['model', 'submodel'] + option_categories if c not in compare_categories]

        def validate(df):
            counts = {'missing_required': check_required(df, ctx),
                      'option_set_flags': check_option_sets(df, option_sets, option_categories, ctx),
                      'inconsistent_model_number': check_model_number_consistency(
                          df, compare_categories, ctx, note_categories=note_categories)}
            log_info(ctx, 'validate', 'CHECKS RUN', **counts)
            return df

        vehicles = run_step(ctx, 'validate', validate, vehicles,
                            conditions={'option_sets': len(option_sets), 'strict': True,
                                        'categories_checked': len(option_categories),
                                        'model_number_compare': ', '.join(compare_categories)})

        # 9. write: compare with the previous vehicles.csv, then write final + review queue
        def write(df):
            columns = vehicle_columns(taxonomy)
            compare_db_changes(ctx, store.read_table(db_dir, 'final', 'vehicles'), df, columns)
            path = store.write_table(df, db_dir, 'final', 'vehicles',
                                     sort_by=['model', 'submodel', 'model_year', 'model_number'], columns=columns)
            queue = build_review_queue(ctx['flags'], df)
            queue_path = store.write_table(queue, db_dir, 'review', 'review_queue')
            log_info(ctx, 'write', 'WRITTEN', vehicles=_display(path), rows=len(df),
                     review_queue=_display(queue_path), review_rows=len(queue))
            return df

        vehicles = run_step(ctx, 'write', write, vehicles, conditions={'compare_with': 'previous final/vehicles.csv'})

        summary = run_summary(ctx, staged, kept, vehicles)
        store.append_row({'run_id': ctx['run_id'], 'started_at': ctx['started_at'],
                          'source_file': _display(source), 'min_model_year': settings['min_model_year'],
                          'max_model_year': settings.get('max_model_year') or '',
                          'taxonomy_version': taxonomy['version'], 'status': run_status(ctx), **summary},
                         db_dir, 'dq', 'ingest_runs')
        status = end_run(ctx, summary=summary)
        return status, summary

    except Exception:
        end_run(ctx, status='failed')
        raise


def compare_db_changes(ctx, previous, current, columns):
    """Log rows added / removed / changed in vehicles.csv since the previous run."""
    if previous is None:
        log_info(ctx, 'write', 'DB COMPARE', previous='none (first run)', added=len(current))
        for _, row in current.iterrows():
            log_change(ctx, 'write', row, '(row)', '', 'added', 'db_added', 'first run')
        return
    lineage = {'source_file', 'taxonomy_version'}
    prev = previous.set_index('vehicle_id')
    curr = current.astype(str).set_index('vehicle_id')
    added = curr.index.difference(prev.index)
    removed = prev.index.difference(curr.index)
    changed_cells = 0
    for vid in added:
        log_change(ctx, 'write', curr.loc[vid].to_dict() | {'vehicle_id': vid}, '(row)', '', 'added',
                   'db_added', curr.loc[vid, 'description_clean'])
    for vid in removed:
        log_change(ctx, 'write', prev.loc[vid].to_dict() | {'vehicle_id': vid}, '(row)', 'present', 'removed',
                   'db_removed', prev.loc[vid, 'description_clean'])
    for vid in curr.index.intersection(prev.index):
        for col in columns:
            if col == 'vehicle_id' or col in lineage or col not in prev.columns:
                continue
            before, after = prev.at[vid, col], curr.at[vid, col]
            if before != after:
                log_change(ctx, 'write', curr.loc[vid].to_dict() | {'vehicle_id': vid}, col, before, after,
                           'db_changed', 'differs from previous vehicles.csv')
                changed_cells += 1
    log_info(ctx, 'write', 'DB COMPARE', previous_rows=len(prev), added=len(added), removed=len(removed),
             changed_values=changed_cells)


def run_summary(ctx, staged, kept, vehicles):
    complete = (vehicles['parse_status'] == 'complete').sum()
    return {'rows_staged': len(staged), 'rows_excluded_by_year': len(staged) - len(kept),
            'rows_final': len(vehicles),
            'parsed_complete_pct': round(100 * complete / len(vehicles), 1) if len(vehicles) else 0.0,
            'flags_warning': sum(f['severity'] == 'warning' for f in ctx['flags']),
            'flags_error': sum(f['severity'] == 'error' for f in ctx['flags'])}


def _display(path):
    try:
        return Path(path).resolve().relative_to(VW_DIR).as_posix()
    except ValueError:
        return str(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Rebuild the VW vehicle database from the VW model export.')
    parser.add_argument('--source', help='source CSV (default: sources.vw_models in config/pipeline.yaml)')
    parser.add_argument('--config-dir', default=str(VW_DIR / 'config'))
    parser.add_argument('--db-dir', default=str(VW_DIR / 'db'))
    args = parser.parse_args(argv)
    try:
        status, _ = run(args.config_dir, args.db_dir, args.source)
    except cfg.ConfigError as error:
        print(f'CONFIG ERROR: {error}', file=sys.stderr)
        return 2 if 'pipeline.yaml' in str(error) else 1
    except Exception as error:   # already logged as FATAL in the run log
        print(f'RUN FAILED: {type(error).__name__}: {error}', file=sys.stderr)
        return 1
    return 1 if status in ('failed', 'ok_with_errors') else 0


if __name__ == '__main__':
    sys.exit(main())
