from typing import Any, Dict

import pandas as pd


def prepare_frames(
    transformed: Dict[str, pd.DataFrame],
    meta_data: Dict[str, Any],
    config: dict,
) -> Dict[str, pd.DataFrame]:
    """
    Prepare output frames: rename columns, enrich with metadata, filter.
    Preserves model_number and Year columns.
    Each language gets its own sheet: <year>_<model_name>_EN, <year>_<model_name>_FR.
    Returns dict without writing to disk.
    """
    model_name = meta_data.get("model_name", "unknown")
    vehicle_year = meta_data.get("vehicle_year", "unknown")
    col_mapping = config.get("rate_import_column_mapping", {})
    required_cols = config.get("rate_import_required_columns", [])

    frames: Dict[str, pd.DataFrame] = {}
    for lang, df in transformed.items():
        df = _enrich_with_metadata(df, meta_data)
        df = _apply_rate_import_mapping(df, col_mapping)
        df = _filter_to_required_columns(df, required_cols)
        sheet_key = f"{vehicle_year}_{model_name}_{lang}"[:31]
        frames[sheet_key] = df

    return frames


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _enrich_with_metadata(df: pd.DataFrame, meta_data: Dict[str, Any]) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "Year", meta_data.get("vehicle_year", "unknown"))
    df.insert(1, "model_name", meta_data.get("model_name", "unknown"))
    df.insert(2, "group_key", meta_data.get("group_key", "unknown"))
    return df


def _apply_rate_import_mapping(df: pd.DataFrame, col_mapping: dict) -> pd.DataFrame:
    rename = {k: v for k, v in col_mapping.items() if k in df.columns}
    return df.rename(columns=rename)


def _filter_to_required_columns(df: pd.DataFrame, required_cols: list) -> pd.DataFrame:
    if not required_cols:
        return df
    existing = [col for col in required_cols if col in df.columns]
    # Always include model_number and Year if they exist (but NOT model_number_status)
    always_include = ["model_number", "Year"]
    cols_to_return = []
    for col in existing:
        if col not in cols_to_return:
            cols_to_return.append(col)
    for col in always_include:
        if col in df.columns and col not in cols_to_return:
            cols_to_return.append(col)
    return df[cols_to_return]
