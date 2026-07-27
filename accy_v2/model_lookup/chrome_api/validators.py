"""
Validation utilities for ADS data quality checks.

Detects duplicates within a batch before saving to database.
"""

import pandas as pd
from typing import List, Tuple


def validate_unique_keys(
    df: pd.DataFrame,
    key_columns: List[str],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Identify and remove duplicates within a DataFrame based on key columns.

    Keeps the first occurrence of each unique key combination, returns both the
    cleaned DataFrame and the dropped duplicates (for logging).

    Args:
        df: DataFrame to check
        key_columns: Columns that define uniqueness (e.g., ["Manufacturer", "ModelYear", "ModelNumber", "StyleID"])

    Returns:
        (deduped_df, duplicate_rows_df) — cleaned data and what was dropped
    """
    if df.empty or not key_columns:
        return df, pd.DataFrame()

    # Verify all key columns exist
    missing_cols = [col for col in key_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Key columns not in DataFrame: {missing_cols}")

    # Mark duplicates: keep='first' means first occurrence is NOT marked
    duplicates_mask = df.duplicated(subset=key_columns, keep="first")

    deduped_df = df[~duplicates_mask].copy()
    duplicate_rows_df = df[duplicates_mask].copy()

    return deduped_df, duplicate_rows_df
