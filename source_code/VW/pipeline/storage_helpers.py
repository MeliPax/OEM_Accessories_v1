"""The only module that knows the db/ layout. Writes are sorted and use a fixed column order,
so diffs between runs are meaningful.

db/
  definitions/   generated from config/ (read-only)
  staging/       source rows as ingested
  final/         vehicles.csv
  review/        review_queue.csv
  dq/            ingest_runs.csv
  logs/          run logs (see logging_helpers)
"""

from pathlib import Path

import pandas as pd

LAYERS = ('definitions', 'staging', 'final', 'review', 'dq')


def table_path(db_dir, layer, name):
    if layer not in LAYERS:
        raise ValueError(f'unknown db layer {layer!r}; expected one of {LAYERS}')
    return Path(db_dir) / layer / f'{name}.csv'


def write_table(df, db_dir, layer, name, sort_by=None, columns=None):
    """Write a table as CSV (sorted by sort_by, columns in the given order). Returns the path."""
    path = table_path(db_dir, layer, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        df = df.reindex(columns=columns)
    if sort_by:
        df = df.sort_values(sort_by, kind='stable')
    df.to_csv(path, index=False)
    return path


def read_table(db_dir, layer, name):
    """Read a table with every value as text (empty cells as ''), or None if it doesn't exist yet."""
    path = table_path(db_dir, layer, name)
    if not path.exists():
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
