from typing import Any, Dict

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.dq_logger import DQLogger
from core.helpers.header_helpers import clean_column_name, strip_df_string_values
from core.helpers.pipeline_logger import PipelineLogger


def run(
    df_raw: pd.DataFrame,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Validate the raw Mazda CSV and return a cleaned, column-normalized working_df.
    Mazda CSV already has headers in row 0 (no promotion needed).
    Populates meta_data in-place with model_name.
    Raises PipelineFatalError for structural issues (FATAL).
    Logs DQ_WARNINGs for data-level issues (nulls).
    """
    sheet_name = meta_data["sheet_name"]
    _extract_meta_data(df_raw, meta_data)

    working_df = _build_working_df(df_raw)
    working_df = _validate_non_null_columns(working_df, sheet_name, meta_data, config, dq_logger)
    _validate_data_types(working_df, sheet_name, config)

    return working_df


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_meta_data(df_raw: pd.DataFrame, meta_data: Dict[str, Any]) -> None:
    if df_raw.shape[0] == 0:
        raise PipelineFatalError("CSV is empty")
    meta_data["model_name"] = meta_data["sheet_name"]


def _build_working_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    working_df = df_raw.copy()
    working_df.columns = [clean_column_name(str(c)).lower() for c in working_df.columns]
    working_df = strip_df_string_values(working_df)
    working_df = working_df.dropna(axis=1, how="all")
    return working_df


def _validate_non_null_columns(
    working_df: pd.DataFrame,
    sheet_name: str,
    meta_data: Dict[str, Any],
    config: dict,
    dq_logger: DQLogger,
) -> pd.DataFrame:
    df = working_df.copy()
    col_lower = {c.lower(): c for c in df.columns}
    threshold = config.get("non_null_threshold", 0.5)
    exclude_mask = pd.Series(False, index=df.index)

    for std_col in config["non_null_columns"]:
        # Try to find the actual column using substring matching (same pattern as column_mapper)
        actual_col = next((orig for lower, orig in col_lower.items() if std_col in lower), None)
        if actual_col is None:
            # If not found, skip this column (will be caught in step2)
            continue
        null_mask = df[actual_col].isna() | (df[actual_col].astype(str).str.strip() == "")
        null_rate = null_mask.sum() / max(len(df), 1)
        if null_rate >= threshold:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': column '{actual_col}' has {null_mask.sum()} null/empty values "
                f"({null_rate:.0%}) — exceeds threshold of {threshold:.0%}, sheet skipped"
            )
        for idx, row in df[null_mask].iterrows():
            dq_logger.log_warning(
                sheet_name=sheet_name,
                model_name=meta_data.get("model_name", "unknown"),
                record_index=int(idx),
                record_snapshot=row.to_dict(),
                rule_violated="non_null_column_rule",
                issue_description=f"Column '{actual_col}' is null/empty — record excluded from output",
            )
        exclude_mask |= null_mask

    return df[~exclude_mask].reset_index(drop=True)


def _validate_data_types(working_df: pd.DataFrame, sheet_name: str, config: dict) -> None:
    col_lower = {c.lower(): c for c in working_df.columns}

    for std_col in config["col_data_type_dict"].get("to_float", []):
        actual_col = next((orig for lower, orig in col_lower.items() if std_col in lower), None)
        if actual_col is None:
            continue
        non_null = working_df[actual_col].dropna()
        bad = non_null[pd.to_numeric(non_null, errors="coerce").isna()]
        if not bad.empty:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': column '{actual_col}' contains non-numeric values: "
                f"{bad.head(3).tolist()}"
            )
