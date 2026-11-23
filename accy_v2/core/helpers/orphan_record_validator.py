"""Orphaned record validator: last check at the output step for rows with no model number."""

from typing import Optional

import pandas as pd

from core.helpers.dq_logger import DQLogger

RULE = "orphaned_record_rule"
GROUP_COLUMNS = ["Year", "ModelName", "Trim"]
SAMPLE_SIZE = 5


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in ("", "nan")
    return bool(pd.isna(value))


def _native(value):
    """numpy/pandas scalar -> plain Python value (keeps the DQ JSON export serialisable)."""
    if _is_blank(value):
        return None
    return value.item() if hasattr(value, "item") else value


def flag_orphaned_records(
    df: pd.DataFrame,
    dq_logger: Optional[DQLogger],
    sheet_name: str,
    model_number_column: str = "Model",
) -> pd.DataFrame:
    """Log one DQ warning per (Year, ModelName, Trim) group whose rows have no model number.

    Runs after the output column mapping, so it catches rows any earlier step missed.
    One warning per group, not per row, so a missing trim doesn't add hundreds of lines
    to the DQ report. Returns df unchanged.
    """
    if dq_logger is None or df.empty:
        return df

    if model_number_column not in df.columns:
        dq_logger.log_warning(
            sheet_name=sheet_name,
            model_name=None,
            record_index=-1,
            record_snapshot={"columns": list(df.columns)},
            rule_violated=RULE,
            issue_description=f"Output has no '{model_number_column}' column, so model numbers could not be checked",
        )
        return df

    orphans = df[df[model_number_column].map(_is_blank)]
    if orphans.empty:
        return df

    keys = [c for c in GROUP_COLUMNS if c in orphans.columns]
    groups = orphans.groupby(keys, dropna=False, sort=False) if keys else [((), orphans)]

    for key, rows in groups:
        key = key if isinstance(key, tuple) else (key,)
        snapshot = {k: _native(v) for k, v in zip(keys, key)}
        snapshot["rows"] = len(rows)
        snapshot["sample_parts"] = [_native(v) for v in rows["Part"].head(SAMPLE_SIZE)] if "Part" in rows.columns else []
        dq_logger.log_warning(
            sheet_name=sheet_name,
            model_name=snapshot.get("ModelName"),
            record_index=int(rows.index[0]) if pd.api.types.is_integer(rows.index[0]) else -1,
            record_snapshot=snapshot,
            rule_violated=RULE,
            issue_description=(
                f"{len(rows)} row(s) reached the output with no {model_number_column}"
                f" ({', '.join(f'{k}={snapshot[k]}' for k in keys)})"
            ),
        )

    return df
