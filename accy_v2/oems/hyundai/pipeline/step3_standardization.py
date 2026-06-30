from typing import Any, Dict, List

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.pipeline_logger import PipelineLogger


def run(
    working_df: pd.DataFrame,
    step2_result: Dict[str, Any],
    config: dict,
    meta_data: Dict[str, Any],
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Apply column mapping, enforce data types, light trim normalization,
    and drop configured unwanted columns.
    Returns standardized_df with standard column names.

    Hyundai differs from Mitsubishi: trim values hold actual strings (e.g., "Preferred", "3.5T Sport")
    not just "X" sentinels, so only strip/normalize, don't force-uppercase.
    """
    col_mapping = step2_result["col_mapping"]
    valid_trim_cols = step2_result["valid_trim_cols"]
    group_key = meta_data.get("group_key", "unknown")

    df = _apply_col_mapping(working_df, col_mapping, valid_trim_cols)
    df = _enforce_data_types(df, config["col_data_type_dict"], group_key)
    df = _normalize_trim_values(df, valid_trim_cols)
    df = _drop_unwanted_columns(df, config, valid_trim_cols)

    return df


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _apply_col_mapping(
    df: pd.DataFrame,
    col_mapping: Dict[str, Any],
    valid_trim_cols: List[str],
) -> pd.DataFrame:
    rename_map = {orig: mapped for orig, mapped in col_mapping.items() if mapped is not None}
    drop_cols = [
        orig for orig, mapped in col_mapping.items()
        if mapped is None and orig not in valid_trim_cols
    ]
    df = df.drop(columns=drop_cols, errors="ignore")
    return df.rename(columns=rename_map)


def _enforce_data_types(
    df: pd.DataFrame, col_data_type_dict: dict, group_key: str
) -> pd.DataFrame:
    df = df.copy()

    for col in col_data_type_dict.get("to_string", []):
        if col in df.columns:
            df[col] = df[col].where(df[col].isna(), df[col].astype(str))

    for col in col_data_type_dict.get("to_float", []):
        if col in df.columns:
            converted = pd.to_numeric(df[col], errors="coerce")
            bad = df[col][converted.isna() & df[col].notna()]
            if not bad.empty:
                raise PipelineFatalError(
                    f"Group '{group_key}': cannot convert '{col}' to float. "
                    f"Sample bad values: {bad.head(3).tolist()}"
                )
            df[col] = converted

    return df


def _normalize_trim_values(df: pd.DataFrame, trim_cols: List[str]) -> pd.DataFrame:
    """Light normalize: strip whitespace, preserve original case (don't force uppercase)."""
    df = df.copy()
    for col in trim_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: str(v).strip() if isinstance(v, str) else v
            )
    return df


def _drop_unwanted_columns(
    df: pd.DataFrame, config: dict, valid_trim_cols: List[str]
) -> pd.DataFrame:
    drop_keywords = [k.lower() for k in config.get("drop_columns", [])]
    if not drop_keywords:
        return df
    cols_to_drop = [
        col for col in df.columns
        if col not in valid_trim_cols
        and any(kw in col.lower() for kw in drop_keywords)
    ]
    return df.drop(columns=cols_to_drop, errors="ignore")
