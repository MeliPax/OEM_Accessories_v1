"""The only module that knows the db/ layout. Writes are sorted and use a fixed column order,
so diffs between runs are meaningful.

Every file a run writes carries its run id (<pipeline>_<YYYYMMDD_HHMMSS>), so nothing is overwritten and
each file traces to its run: db/final/vehicles_vw_ingest_20261028_150102.csv. A reader takes the newest
(latest_path). The run registers (dq/ingest_runs.csv, dq/accessory_runs.csv) and logs/steps.csv are one file
each, appended once per run.

db/
  definitions/   generated from config/ (read-only)    dim_<name>_<run_id>.csv
  staging/       source rows as ingested                stg_vw_models_<run_id>.csv
  final/         vehicles                               vehicles_<run_id>.csv
  review/        review queues                          review_queue_<run_id>.csv, accessory_review_<run_id>.csv
  dq/            reports and the run registers          accessory_lookup_<run_id>.csv, ingest_runs.csv, ...
  logs/          run logs (see logging_helpers)
"""

from pathlib import Path

import pandas as pd

LAYERS = ('definitions', 'staging', 'final', 'review', 'dq')


def table_path(db_dir, layer, name, run_id=None):
    """db/<layer>/<name>_<run_id>.csv, or db/<layer>/<name>.csv for a run register (no run id)."""
    if layer not in LAYERS:
        raise ValueError(f'unknown db layer {layer!r}; expected one of {LAYERS}')
    return Path(db_dir) / layer / (f'{name}_{run_id}.csv' if run_id else f'{name}.csv')


def latest_path(db_dir, layer, name):
    """The newest run's <name>_<run_id>.csv (by write time, then name), or None if no run wrote one."""
    if layer not in LAYERS:
        raise ValueError(f'unknown db layer {layer!r}; expected one of {LAYERS}')
    paths = list((Path(db_dir) / layer).glob(f'{name}_*.csv'))
    return max(paths, key=lambda p: (p.stat().st_mtime_ns, p.name)) if paths else None


def write_table(df, db_dir, layer, name, sort_by=None, columns=None, run_id=None):
    """Write a table as CSV (sorted by sort_by, columns in the given order), named with the run id.
    Returns the path."""
    path = table_path(db_dir, layer, name, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        df = df.reindex(columns=columns)
    if sort_by:
        df = df.sort_values(sort_by, kind='stable')
    df.to_csv(path, index=False)
    return path


def read_table(db_dir, layer, name, latest=False):
    """Read a table with every value as text (empty cells as ''), or None if it doesn't exist yet.
    latest: the newest run's file (latest_path) instead of a run register."""
    path = latest_path(db_dir, layer, name) if latest else table_path(db_dir, layer, name)
    if path is None or not path.exists():
        return None
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def append_row(row, db_dir, layer, name):
    """Append one row to a table (header written the first time). When the row brings new columns, the
    table is rewritten with them (older rows get them empty), so columns never shift."""
    path = table_path(db_dir, layer, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame([row])
    if path.exists():
        header = list(pd.read_csv(path, nrows=0).columns)
        if header != list(new.columns):
            old = pd.read_csv(path, dtype=str, keep_default_na=False)
            columns = header + [c for c in new.columns if c not in header]
            pd.concat([old, new.astype(str)], ignore_index=True).reindex(columns=columns) \
              .to_csv(path, index=False)
            return path
    new.to_csv(path, mode='a', header=not path.exists(), index=False)
    return path
