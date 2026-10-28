"""Attach VW model numbers to the accessory file and export one sheet per accessory model name.

    python run_accessories.py                 # from source_code/VW (run run_ingest.py first)
    python run_accessories.py --source other.xlsx --no-export

Steps (every one logged through run_step):
    config -> ingest -> staging -> year_window -> dedupe -> clean -> resolve_names -> lookup
    -> build_dict -> coverage -> validate -> export

Exit code: 0 = ok or ok with warnings, 1 = errors flagged or the run failed, 2 = pipeline.yaml unreadable.
"""

import argparse
import sys
from pathlib import Path

VW_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(VW_DIR))

from pipeline import config_helpers as cfg                         # noqa: E402
from pipeline.accessory_helpers import run_pipeline                # noqa: E402
from pipeline.message_helpers import MessageError                  # noqa: E402
from run_ingest import print_config_fixes                          # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description='Attach VW model numbers to the accessory file.')
    parser.add_argument('--source', help='accessory file (default: sources.accessories in config/pipeline.yaml)')
    parser.add_argument('--config-dir', default=str(VW_DIR / 'config'))
    parser.add_argument('--db-dir', default=str(VW_DIR / 'db'))
    parser.add_argument('--output-dir', help='export folder (default: export.output_dir in accessories.yaml)')
    parser.add_argument('--no-export', action='store_true', help='build the dict and reports, skip the Excel file')
    args = parser.parse_args(argv)
    try:
        status, summary, model_dict = run_pipeline(args.config_dir, args.db_dir, args.source,
                                                   export=not args.no_export, output_dir=args.output_dir)
    except cfg.ConfigError as error:
        print(f'CONFIG ERROR: {error}', file=sys.stderr)
        print_config_fixes(error, Path(args.config_dir))
        return 2 if 'pipeline.yaml' in str(error) else 1
    except MessageError as error:
        print(f'CONFIG ERROR: {error}', file=sys.stderr)
        return 1
    except Exception as error:   # already logged as FATAL in the run log
        print(f'RUN FAILED: {type(error).__name__}: {error}', file=sys.stderr)
        return 1

    print(f'\n{"Model":<20}{"rows":>8}{"matched":>9}')
    for name, df in model_dict.items():
        print(f'{name:<20}{len(df):>8}{int((df["model_number"] != "").sum()):>9}')
    print(f'\nstatus: {status} | keys found {summary["keys_found"]} of {summary["keys"]} | '
          f'unmatched part-years {summary["unmatched_part_years"]} | '
          f'vehicles without parts {summary["vehicles_without_parts"]} | '
          f'verified {summary["flags_verified"]} | review rows {summary["review_rows"]}')
    if summary['export_file']:
        print(f'export: {summary["export_file"]}')
    print('review: db/review/accessory_review.csv | lookup: db/dq/accessory_lookup.csv | '
          'verified: db/dq/verified_flags.csv')
    return 1 if status in ('failed', 'ok_with_errors') else 0


if __name__ == '__main__':
    sys.exit(main())
